"""Contract tests for BaseAgent.

Uses throwaway stub agents to verify the base class's guarantees. These stubs
are test fixtures only — not real analytical agents, and carry no strategy.
"""

from datetime import datetime, timezone

import pytest

from core.base_agent import BaseAgent
from core.enums import AgentGroup, AgentName, Signal
from core.errors import AgentError
from core.schemas import AgentInput, AgentOutput, TimeHorizon


def _input() -> AgentInput:
    return AgentInput(
        ticker="AAPL",
        as_of=datetime(2026, 1, 1, tzinfo=timezone.utc),
        horizon=TimeHorizon.SHORT_TERM,
        request_id="req-42",
    )


class _EchoAgent(BaseAgent):
    """Returns a fixed valid output."""

    name = "echo_agent"

    def analyze(self, agent_input: AgentInput) -> AgentOutput:
        return AgentOutput(
            agent_name=AgentName.MOMENTUM_AGENT,
            group=AgentGroup.SHORT_TERM,
            ticker=agent_input.ticker,
            as_of=agent_input.as_of,
            signal=Signal.HOLD,
            confidence=0.5,
            rationale="stub",
        )


class _BoomAgent(BaseAgent):
    """Raises a plain exception to test error-wrapping."""

    name = "boom_agent"

    def analyze(self, agent_input: AgentInput) -> AgentOutput:
        raise ValueError("kaboom")


class _WrongTypeAgent(BaseAgent):
    """Returns the wrong type to test the output guard."""

    name = "wrong_type_agent"

    def analyze(self, agent_input: AgentInput) -> AgentOutput:
        return "not an output"  # type: ignore[return-value]


def test_run_returns_output_and_stamps_meta():
    out = _EchoAgent().run(_input())
    assert isinstance(out, AgentOutput)
    assert out.meta["agent_name"] == "echo_agent"
    assert out.meta["request_id"] == "req-42"
    assert "latency_ms" in out.meta


def test_run_rejects_non_agent_input():
    with pytest.raises(AgentError):
        _EchoAgent().run({"ticker": "AAPL"})  # type: ignore[arg-type]


def test_run_wraps_exceptions_as_agent_error():
    with pytest.raises(AgentError) as exc_info:
        _BoomAgent().run(_input())
    assert exc_info.value.agent_name == "boom_agent"
    assert "kaboom" in str(exc_info.value)


def test_run_rejects_wrong_return_type():
    with pytest.raises(AgentError):
        _WrongTypeAgent().run(_input())


def test_base_agent_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseAgent()  # abstract: analyze not implemented
