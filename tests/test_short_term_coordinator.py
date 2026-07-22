"""Tests for the short-term coordinator and its aggregation."""

from datetime import datetime, timezone

import pytest

from agents.short_term.momentum_agent import MomentumAgent
from coordinators.short_term_coordinator import (
    ShortTermCoordinator,
    build_short_term_coordinator,
)
from core.base_agent import BaseAgent
from core.enums import AgentGroup, AgentName, Signal, Status
from core.schemas import AgentInput, AgentOutput, CoordinatorResult, ResearchRequest
from data.market_data import build_sample_provider


def _request(ticker: str, as_of: datetime | None = None) -> ResearchRequest:
    return ResearchRequest(
        ticker=ticker,
        as_of=as_of or datetime(2026, 6, 1, tzinfo=timezone.utc),
        request_id="test-req",
    )


class _FixedAgent(BaseAgent):
    """Test stub that returns a fixed signal/confidence (not a real agent)."""

    def __init__(self, name: AgentName, signal: Signal, confidence: float) -> None:
        self.name = name.value
        self._name = name
        self._signal = signal
        self._confidence = confidence

    def analyze(self, agent_input: AgentInput) -> AgentOutput:
        return AgentOutput(
            agent_name=self._name,
            group=AgentGroup.SHORT_TERM,
            ticker=agent_input.ticker.upper(),
            as_of=agent_input.as_of,
            signal=self._signal,
            confidence=self._confidence,
            rationale="fixed stub",
        )


class _FailingAgent(BaseAgent):
    """Test stub that always errors."""

    name = AgentName.CHART_SCAN_AGENT.value

    def analyze(self, agent_input: AgentInput) -> AgentOutput:
        raise ValueError("boom")


# --------------------------------------------------------------------------- #
# Happy path / single child
# --------------------------------------------------------------------------- #
def test_happy_path_returns_coordinator_result():
    coord = build_short_term_coordinator()
    result = coord.run(_request("UPTREND"))
    assert isinstance(result, CoordinatorResult)
    assert result.group is AgentGroup.SHORT_TERM
    assert result.status is Status.SUCCESS
    assert result.signal in (Signal.BUY, Signal.STRONG_BUY)
    assert len(result.member_outputs) == 1
    assert result.errors == []
    assert result.confidence_level is not None  # auto-derived


def test_default_wiring_has_exactly_momentum():
    coord = build_short_term_coordinator()
    assert len(coord.agents) == 1
    assert isinstance(coord.agents[0], MomentumAgent)


def test_single_child_confidence_matches_that_agent():
    coord = build_short_term_coordinator()
    result = coord.run(_request("UPTREND"))
    assert result.confidence == result.member_outputs[0].confidence


# --------------------------------------------------------------------------- #
# Error / partial propagation
# --------------------------------------------------------------------------- #
def test_all_agents_failing_yields_failed_status():
    coord = build_short_term_coordinator()
    result = coord.run(_request("NOPE"))  # unknown ticker -> momentum errors
    assert result.status is Status.FAILED
    assert result.signal is Signal.NEUTRAL
    assert result.confidence == 0.0
    assert result.member_outputs == []
    assert len(result.errors) == 1
    assert result.errors[0].agent_name is AgentName.MOMENTUM_AGENT
    assert result.errors[0].code == "AGENT_FAILED"


def test_partial_when_one_of_several_fails():
    provider = build_sample_provider()
    coord = ShortTermCoordinator(
        provider, agents=[MomentumAgent(provider), _FailingAgent()]
    )
    result = coord.run(_request("UPTREND"))
    assert result.status is Status.PARTIAL
    assert len(result.member_outputs) == 1
    assert len(result.errors) == 1
    assert any("failed" in w for w in result.warnings)


# --------------------------------------------------------------------------- #
# Aggregation across multiple agents
# --------------------------------------------------------------------------- #
def test_opposing_equal_weight_signals_net_to_hold():
    provider = build_sample_provider()
    coord = ShortTermCoordinator(
        provider,
        agents=[
            _FixedAgent(AgentName.MOMENTUM_AGENT, Signal.STRONG_BUY, 0.8),
            _FixedAgent(AgentName.RISK_AGENT, Signal.STRONG_SELL, 0.8),
        ],
    )
    result = coord.run(_request("UPTREND"))
    assert result.signal is Signal.HOLD
    assert result.confidence == 0.8  # mean of the two
    assert len(result.member_outputs) == 2


def test_confidence_weighting_favors_the_surer_agent():
    provider = build_sample_provider()
    coord = ShortTermCoordinator(
        provider,
        agents=[
            _FixedAgent(AgentName.MOMENTUM_AGENT, Signal.STRONG_BUY, 0.9),
            _FixedAgent(AgentName.RISK_AGENT, Signal.SELL, 0.2),
        ],
    )
    result = coord.run(_request("UPTREND"))
    assert result.signal in (Signal.BUY, Signal.STRONG_BUY)


# --------------------------------------------------------------------------- #
# Contract / validation
# --------------------------------------------------------------------------- #
def test_result_round_trips_through_json():
    result = build_short_term_coordinator().run(_request("AAPL"))
    assert CoordinatorResult.model_validate_json(result.model_dump_json()) == result


def test_run_requires_research_request():
    with pytest.raises(ValueError):
        build_short_term_coordinator().run({"ticker": "AAPL"})  # type: ignore[arg-type]


def test_coordinator_requires_at_least_one_agent():
    with pytest.raises(ValueError):
        ShortTermCoordinator(build_sample_provider(), agents=[])
