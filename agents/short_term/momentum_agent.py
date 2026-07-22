"""momentum_agent — first real agent (short-term group).

v1 is a deterministic, offline momentum reading of a price series:

  * short vs. long simple moving average (trend alignment)
  * rate-of-change over a lookback window (trend strength)

It maps those into the shared `Signal` + `confidence` envelope with explainable
`evidence`. It emits an analytical *signal*, not a trade — there is no order,
sizing, or portfolio logic here.
"""

from __future__ import annotations

from statistics import mean

from core.base_agent import BaseAgent
from core.enums import AgentGroup, AgentName, Signal, Status
from core.errors import DataError
from core.schemas import AgentInput, AgentOutput, Evidence
from data.market_data import MarketDataProvider

# Tunables (kept explicit and small so behavior is easy to reason about/test).
SHORT_WINDOW = 3
LONG_WINDOW = 10
ROC_LOOKBACK = 10
STRONG_ROC = 0.08  # |ROC| at/above this is a "strong" move
ENTRY_ROC = 0.015  # |ROC| below this is directionless (HOLD)


def _sign(x: float) -> int:
    return (x > 0) - (x < 0)


class MomentumAgent(BaseAgent):
    """Reads a price series and reports a momentum signal."""

    name = AgentName.MOMENTUM_AGENT.value
    group = AgentGroup.SHORT_TERM

    def __init__(
        self,
        provider: MarketDataProvider,
        *,
        short_window: int = SHORT_WINDOW,
        long_window: int = LONG_WINDOW,
        roc_lookback: int = ROC_LOOKBACK,
    ) -> None:
        self.provider = provider
        self.short_window = short_window
        self.long_window = long_window
        self.roc_lookback = roc_lookback

    def analyze(self, agent_input: AgentInput) -> AgentOutput:
        series = self.provider.get_price_series(agent_input.ticker, as_of=agent_input.as_of)
        closes = series.closes
        n = len(closes)

        # Not enough history to say anything directional.
        if n < 2:
            return self._insufficient(agent_input, n)

        warnings: list[str] = []
        status = Status.SUCCESS
        if n < self.long_window:
            warnings.append(
                f"limited price history (have {n} bars, prefer >= {self.long_window})"
            )
            status = Status.PARTIAL

        short_ma = mean(closes[-min(self.short_window, n):])
        long_ma = mean(closes[-min(self.long_window, n):])
        ma_gap = (short_ma - long_ma) / long_ma

        lookback = min(self.roc_lookback, n - 1)
        base_price = closes[-1 - lookback]
        roc = (closes[-1] - base_price) / base_price

        signal = self._classify(roc, ma_gap)
        confidence = self._confidence(roc, ma_gap, degraded=status is Status.PARTIAL)

        metrics = {
            "n_bars": n,
            "last_close": closes[-1],
            "short_window": self.short_window,
            "long_window": self.long_window,
            "short_ma": round(short_ma, 4),
            "long_ma": round(long_ma, 4),
            "ma_gap": round(ma_gap, 6),
            "roc_lookback": lookback,
            "roc": round(roc, 6),
        }
        evidence = [
            Evidence(claim=f"{lookback}-bar rate-of-change", source="price_series", value=round(roc, 6)),
            Evidence(claim="short vs long MA gap", source="price_series", value=round(ma_gap, 6)),
            Evidence(claim="last close", source="price_series", value=closes[-1]),
        ]
        rationale = (
            f"{lookback}-bar ROC is {roc:+.2%} with the {self.short_window}-bar MA "
            f"{'above' if ma_gap >= 0 else 'below'} the {self.long_window}-bar MA "
            f"({ma_gap:+.2%}); momentum reads {signal.value}."
        )

        return AgentOutput(
            agent_name=AgentName.MOMENTUM_AGENT,
            group=self.group,
            ticker=series.ticker,
            as_of=agent_input.as_of,
            status=status,
            signal=signal,
            confidence=confidence,
            rationale=rationale,
            evidence=evidence,
            metrics=metrics,
            warnings=warnings,
        )

    # -- helpers ----------------------------------------------------------- #
    def _classify(self, roc: float, ma_gap: float) -> Signal:
        if roc >= STRONG_ROC and ma_gap > 0:
            return Signal.STRONG_BUY
        if roc >= ENTRY_ROC:
            return Signal.BUY
        if roc <= -STRONG_ROC and ma_gap < 0:
            return Signal.STRONG_SELL
        if roc <= -ENTRY_ROC:
            return Signal.SELL
        return Signal.HOLD

    def _confidence(self, roc: float, ma_gap: float, *, degraded: bool) -> float:
        mag = min(abs(roc) / STRONG_ROC, 1.0)
        agree = _sign(roc) == _sign(ma_gap) and roc != 0.0
        raw = 0.2 + 0.6 * mag
        if not agree:
            raw *= 0.7
        if degraded:
            raw *= 0.6
        return round(min(0.95, max(0.05, raw)), 4)

    def _insufficient(self, agent_input: AgentInput, n: int) -> AgentOutput:
        return AgentOutput(
            agent_name=AgentName.MOMENTUM_AGENT,
            group=self.group,
            ticker=agent_input.ticker.upper(),
            as_of=agent_input.as_of,
            status=Status.PARTIAL,
            signal=Signal.NEUTRAL,
            confidence=0.05,
            rationale=f"insufficient price history to compute momentum (have {n} bars).",
            metrics={"n_bars": n},
            warnings=[f"insufficient price history (have {n} bars, need >= 2)"],
        )
