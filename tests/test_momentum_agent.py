"""Tests for momentum_agent (deterministic, offline)."""

from datetime import datetime, timedelta, timezone

import pytest

from agents.short_term.momentum_agent import MomentumAgent
from core.enums import AgentGroup, AgentName, Signal, Status, TimeHorizon
from core.errors import AgentError
from core.schemas import AgentInput, AgentOutput
from data.market_data import InMemoryMarketDataProvider, PriceBar, build_sample_provider

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _input(ticker: str, as_of: datetime | None = None) -> AgentInput:
    return AgentInput(
        ticker=ticker,
        as_of=as_of or datetime(2026, 6, 1, tzinfo=timezone.utc),
        horizon=TimeHorizon.SHORT_TERM,
        request_id="test-req",
    )


def _provider_from(closes: list[float]) -> InMemoryMarketDataProvider:
    bars = [PriceBar(ts=_T0 + timedelta(days=i), close=c) for i, c in enumerate(closes)]
    return InMemoryMarketDataProvider({"TEST": bars})


def test_rising_series_is_bullish():
    out = MomentumAgent(build_sample_provider()).run(_input("UPTREND"))
    assert out.signal in (Signal.BUY, Signal.STRONG_BUY)
    assert out.metrics["roc"] > 0


def test_falling_series_is_bearish():
    out = MomentumAgent(build_sample_provider()).run(_input("DOWNTREND"))
    assert out.signal in (Signal.SELL, Signal.STRONG_SELL)
    assert out.metrics["roc"] < 0


def test_flat_series_is_hold():
    out = MomentumAgent(build_sample_provider()).run(_input("SIDEWAYS"))
    assert out.signal is Signal.HOLD
    assert out.confidence < 0.4  # low conviction on a directionless tape


def test_output_conforms_to_shared_schema():
    out = MomentumAgent(build_sample_provider()).run(_input("AAPL"))
    assert isinstance(out, AgentOutput)
    assert out.agent_name is AgentName.MOMENTUM_AGENT
    assert out.group is AgentGroup.SHORT_TERM
    assert out.confidence_level is not None  # auto-derived by the schema
    assert len(out.evidence) == 3
    # round-trips through JSON like any shared result
    assert AgentOutput.model_validate_json(out.model_dump_json()) == out


def test_point_in_time_changes_the_read():
    # Early in the UPTREND we still have positive but shorter history.
    early = MomentumAgent(build_sample_provider()).run(
        _input("UPTREND", as_of=datetime(2025, 12, 4, tzinfo=timezone.utc))
    )
    assert early.status is Status.PARTIAL  # < long_window bars available
    assert any("limited price history" in w for w in early.warnings)


def test_insufficient_history_is_neutral_partial():
    out = MomentumAgent(_provider_from([100.0])).run(_input("TEST"))
    assert out.signal is Signal.NEUTRAL
    assert out.status is Status.PARTIAL
    assert out.confidence == 0.05
    assert out.warnings


def test_unknown_ticker_surfaces_as_agent_error():
    with pytest.raises(AgentError):
        MomentumAgent(build_sample_provider()).run(_input("NOPE"))


def test_run_requires_agent_input_type():
    with pytest.raises(AgentError):
        MomentumAgent(build_sample_provider()).run({"ticker": "AAPL"})  # type: ignore[arg-type]
