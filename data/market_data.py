"""In-memory market-data source.

A small, deterministic price repository so agents can be built and tested with
zero network access. The `MarketDataProvider` protocol is the seam a real
data feed will implement later; `InMemoryMarketDataProvider` is the offline
implementation used for now.

Point-in-time discipline: `get_price_series` accepts an `as_of` and returns
only bars at or before that moment, so agents can never see the future.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from core.errors import DataError


class PriceBar(BaseModel):
    """One dated close price."""

    model_config = ConfigDict(extra="forbid")

    ts: datetime = Field(..., description="Bar timestamp (UTC).")
    close: float = Field(..., gt=0, description="Closing price.")


class PriceSeries(BaseModel):
    """An ordered series of price bars for a single ticker."""

    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(..., min_length=1)
    bars: list[PriceBar] = Field(default_factory=list)

    @property
    def closes(self) -> list[float]:
        """Close prices in chronological order."""
        return [bar.close for bar in self.bars]

    def __len__(self) -> int:
        return len(self.bars)


@runtime_checkable
class MarketDataProvider(Protocol):
    """The contract any price source must satisfy."""

    def get_price_series(
        self, ticker: str, as_of: datetime | None = None
    ) -> PriceSeries: ...


class InMemoryMarketDataProvider:
    """Serves price series from an in-memory dict. No network, fully deterministic."""

    def __init__(self, data: dict[str, list[PriceBar]] | None = None) -> None:
        # Store bars sorted chronologically per ticker.
        self._data: dict[str, list[PriceBar]] = {
            ticker: sorted(bars, key=lambda b: b.ts)
            for ticker, bars in (data or {}).items()
        }

    @property
    def tickers(self) -> list[str]:
        return sorted(self._data)

    def get_price_series(
        self, ticker: str, as_of: datetime | None = None
    ) -> PriceSeries:
        """Return the series for `ticker`, truncated to bars at/before `as_of`.

        Raises `DataError` if the ticker is unknown. A known ticker with no bars
        on or before `as_of` yields an empty series (the agent decides how to
        treat thin history) rather than an error.
        """
        key = ticker.upper()
        if key not in self._data:
            raise DataError(f"unknown ticker: {ticker!r}")

        bars = self._data[key]
        if as_of is not None:
            bars = [b for b in bars if b.ts <= as_of]
        return PriceSeries(ticker=key, bars=list(bars))


# --------------------------------------------------------------------------- #
# Deterministic sample data (used by the CLI and as a convenience in tests)
# --------------------------------------------------------------------------- #
_SAMPLE_START = datetime(2025, 12, 1, tzinfo=timezone.utc)


def _series(first: float, daily_factor: float, n: int = 30) -> list[PriceBar]:
    """Generate `n` daily bars starting at `first`, compounding by `daily_factor`."""
    bars: list[PriceBar] = []
    price = first
    for i in range(n):
        bars.append(PriceBar(ts=_SAMPLE_START + timedelta(days=i), close=round(price, 4)))
        price *= daily_factor
    return bars


def _sideways(base: float, n: int = 30) -> list[PriceBar]:
    """Flat series with a tiny deterministic oscillation (near-zero momentum)."""
    bars: list[PriceBar] = []
    for i in range(n):
        close = base + (0.2 if i % 2 == 0 else -0.2)
        bars.append(PriceBar(ts=_SAMPLE_START + timedelta(days=i), close=round(close, 4)))
    return bars


def build_sample_provider() -> InMemoryMarketDataProvider:
    """A provider seeded with a few clearly-shaped tickers for demos and tests."""
    return InMemoryMarketDataProvider(
        {
            "UPTREND": _series(100.0, 1.012),
            "DOWNTREND": _series(200.0, 0.988),
            "SIDEWAYS": _sideways(150.0),
            "AAPL": _series(180.0, 1.006),
        }
    )
