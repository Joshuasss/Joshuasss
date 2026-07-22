"""Contract tests for the standardized schemas.

These assert the validation rules we rely on downstream — not any trading
behavior.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from core.schemas import AgentInput, AgentOutput, Evidence, Horizon, Signal


def _now() -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_agent_input_valid():
    inp = AgentInput(
        ticker="AAPL",
        as_of=_now(),
        horizon=Horizon.SHORT_TERM,
        request_id="req-1",
    )
    assert inp.ticker == "AAPL"
    assert inp.context == {}  # default factory, not shared mutable state


def test_agent_input_defaults_are_independent():
    a = AgentInput(ticker="A", as_of=_now(), horizon=Horizon.RESEARCH, request_id="r1")
    b = AgentInput(ticker="B", as_of=_now(), horizon=Horizon.RESEARCH, request_id="r2")
    a.context["x"] = 1
    assert b.context == {}  # each instance gets its own dict


def test_agent_input_rejects_empty_ticker():
    with pytest.raises(ValidationError):
        AgentInput(ticker="", as_of=_now(), horizon=Horizon.LONG_TERM, request_id="r")


def test_agent_input_rejects_unknown_field():
    with pytest.raises(ValidationError):
        AgentInput(
            ticker="AAPL",
            as_of=_now(),
            horizon=Horizon.SHORT_TERM,
            request_id="r",
            surprise="boom",  # extra="forbid"
        )


def test_agent_output_valid_minimal():
    out = AgentOutput(
        agent_name="stub",
        ticker="AAPL",
        as_of=_now(),
        signal=Signal.BUY,
        confidence=0.7,
        rationale="momentum positive",
    )
    assert out.evidence == []
    assert out.warnings == []
    assert out.metrics == {}


def test_agent_output_confidence_bounds():
    for bad in (-0.1, 1.1):
        with pytest.raises(ValidationError):
            AgentOutput(
                agent_name="stub",
                ticker="AAPL",
                as_of=_now(),
                signal=Signal.HOLD,
                confidence=bad,
                rationale="x",
            )


def test_agent_output_requires_rationale():
    with pytest.raises(ValidationError):
        AgentOutput(
            agent_name="stub",
            ticker="AAPL",
            as_of=_now(),
            signal=Signal.SELL,
            confidence=0.5,
            rationale="",
        )


def test_evidence_shape():
    ev = Evidence(claim="RSI oversold", source="momentum", value=28.4)
    out = AgentOutput(
        agent_name="stub",
        ticker="AAPL",
        as_of=_now(),
        signal=Signal.BUY,
        confidence=0.6,
        rationale="oversold bounce",
        evidence=[ev],
    )
    assert out.evidence[0].value == 28.4


def test_signal_enum_is_string_serializable():
    assert Signal.STRONG_BUY.value == "STRONG_BUY"
    assert Horizon.RESEARCH.value == "RESEARCH"
