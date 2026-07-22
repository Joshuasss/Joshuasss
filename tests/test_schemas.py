"""Contract tests for the shared schemas.

Covers: valid construction, rejection of invalid input, required-field
enforcement, auto-derived confidence buckets, and JSON round-trips. No trading
behavior is exercised — these assert the contract only.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from core.enums import (
    AgentGroup,
    AgentName,
    ConfidenceLevel,
    Direction,
    MarketRegime,
    Signal,
    Status,
    TimeHorizon,
)
from core.schemas import (
    AgentInput,
    AgentOutput,
    CoordinatorResult,
    ErrorInfo,
    Evidence,
    LongTermResult,
    MarketRegimeResult,
    ResearchNote,
    ResearchRequest,
    ShortTermResult,
    TradeCandidate,
)


def _now() -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


def _output(**overrides) -> AgentOutput:
    base = dict(
        agent_name=AgentName.MOMENTUM_AGENT,
        group=AgentGroup.SHORT_TERM,
        ticker="AAPL",
        as_of=_now(),
        signal=Signal.BUY,
        confidence=0.7,
        rationale="momentum positive",
    )
    base.update(overrides)
    return AgentOutput(**base)


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
def test_confidence_level_from_score_buckets():
    assert ConfidenceLevel.from_score(0.0) is ConfidenceLevel.VERY_LOW
    assert ConfidenceLevel.from_score(0.3) is ConfidenceLevel.LOW
    assert ConfidenceLevel.from_score(0.5) is ConfidenceLevel.MEDIUM
    assert ConfidenceLevel.from_score(0.7) is ConfidenceLevel.HIGH
    assert ConfidenceLevel.from_score(1.0) is ConfidenceLevel.VERY_HIGH


def test_confidence_level_from_score_rejects_out_of_range():
    with pytest.raises(ValueError):
        ConfidenceLevel.from_score(1.5)


def test_enums_are_string_serializable():
    assert Signal.STRONG_BUY.value == "STRONG_BUY"
    assert AgentName.RISK_AGENT.value == "risk_agent"
    assert Status.PARTIAL.value == "PARTIAL"


# --------------------------------------------------------------------------- #
# AgentInput / ResearchRequest
# --------------------------------------------------------------------------- #
def test_agent_input_valid_and_defaults_independent():
    a = AgentInput(ticker="A", as_of=_now(), horizon=TimeHorizon.RESEARCH, request_id="r1")
    b = AgentInput(ticker="B", as_of=_now(), horizon=TimeHorizon.RESEARCH, request_id="r2")
    a.context["x"] = 1
    assert b.context == {}  # each instance gets its own dict


def test_agent_input_rejects_empty_ticker():
    with pytest.raises(ValidationError):
        AgentInput(ticker="", as_of=_now(), horizon=TimeHorizon.LONG_TERM, request_id="r")


def test_agent_input_rejects_unknown_field():
    with pytest.raises(ValidationError):
        AgentInput(
            ticker="AAPL",
            as_of=_now(),
            horizon=TimeHorizon.SHORT_TERM,
            request_id="r",
            surprise="boom",
        )


def test_research_request_defaults_to_all_groups():
    req = ResearchRequest(ticker="AAPL", request_id="r1")
    assert set(req.groups) == set(AgentGroup)


# --------------------------------------------------------------------------- #
# AgentOutput
# --------------------------------------------------------------------------- #
def test_agent_output_valid_minimal_and_autofills_level():
    out = _output()
    assert out.status is Status.SUCCESS
    assert out.confidence_level is ConfidenceLevel.HIGH  # derived from 0.7
    assert out.evidence == [] and out.warnings == [] and out.metrics == {}


def test_agent_output_keeps_explicit_confidence_level():
    out = _output(confidence=0.7, confidence_level=ConfidenceLevel.LOW)
    assert out.confidence_level is ConfidenceLevel.LOW  # not overwritten


def test_agent_output_confidence_bounds():
    for bad in (-0.1, 1.1):
        with pytest.raises(ValidationError):
            _output(confidence=bad)


def test_agent_output_requires_rationale():
    with pytest.raises(ValidationError):
        _output(rationale="")


def test_agent_output_requires_agent_name():
    with pytest.raises(ValidationError):
        AgentOutput(
            group=AgentGroup.SHORT_TERM,
            ticker="AAPL",
            as_of=_now(),
            signal=Signal.BUY,
            confidence=0.5,
            rationale="x",
        )


def test_agent_output_rejects_invalid_enum_value():
    with pytest.raises(ValidationError):
        _output(agent_name="not_a_real_agent")


# --------------------------------------------------------------------------- #
# Specialized results
# --------------------------------------------------------------------------- #
def test_short_term_result_carries_trade_candidate():
    cand = TradeCandidate(
        ticker="AAPL",
        direction=Direction.LONG,
        group=AgentGroup.SHORT_TERM,
        time_horizon=TimeHorizon.SHORT_TERM,
        conviction=ConfidenceLevel.HIGH,
        rationale="breakout",
    )
    res = ShortTermResult(
        agent_name=AgentName.CHART_SCAN_AGENT,
        group=AgentGroup.SHORT_TERM,
        ticker="AAPL",
        as_of=_now(),
        signal=Signal.BUY,
        confidence=0.8,
        rationale="breakout above resistance",
        key_levels={"support": 180.0, "resistance": 195.0},
        catalysts=["earnings"],
        trade_candidate=cand,
    )
    assert res.trade_candidate.direction is Direction.LONG
    assert res.key_levels["resistance"] == 195.0


def test_long_term_result_fields():
    res = LongTermResult(
        agent_name=AgentName.LONG_TERM_THESIS_AGENT,
        group=AgentGroup.LONG_TERM,
        ticker="AAPL",
        as_of=_now(),
        signal=Signal.BUY,
        confidence=0.6,
        rationale="durable moat",
        thesis="services flywheel",
        risks=["regulation"],
    )
    assert res.thesis == "services flywheel"


def test_market_regime_result_requires_regime():
    with pytest.raises(ValidationError):
        MarketRegimeResult(
            agent_name=AgentName.MARKET_REGIME_NEWS_AGENT,
            group=AgentGroup.RESEARCH,
            ticker="SPY",
            as_of=_now(),
            signal=Signal.NEUTRAL,
            confidence=0.5,
            rationale="mixed",
        )
    ok = MarketRegimeResult(
        agent_name=AgentName.MARKET_REGIME_NEWS_AGENT,
        group=AgentGroup.RESEARCH,
        ticker="SPY",
        as_of=_now(),
        signal=Signal.NEUTRAL,
        confidence=0.5,
        rationale="mixed",
        regime=MarketRegime.RISK_OFF,
    )
    assert ok.regime is MarketRegime.RISK_OFF


# --------------------------------------------------------------------------- #
# Research note / evidence / error
# --------------------------------------------------------------------------- #
def test_research_note_and_evidence():
    note = ResearchNote(note_id="n1", title="t", summary="s", tickers=["AAPL"])
    ev = Evidence(claim="RSI oversold", source="momentum", value=28.4)
    assert note.tickers == ["AAPL"]
    assert ev.value == 28.4


def test_error_info_is_serializable_record():
    err = ErrorInfo(code="DATA_MISSING", message="no prices", agent_name=AgentName.RISK_AGENT)
    assert err.agent_name is AgentName.RISK_AGENT
    assert err.occurred_at is not None


# --------------------------------------------------------------------------- #
# CoordinatorResult
# --------------------------------------------------------------------------- #
def test_coordinator_result_aggregates_members():
    res = CoordinatorResult(
        group=AgentGroup.SHORT_TERM,
        ticker="AAPL",
        as_of=_now(),
        signal=Signal.BUY,
        confidence=0.65,
        summary="net bullish",
        member_outputs=[_output(), _output(signal=Signal.HOLD, confidence=0.4)],
    )
    assert len(res.member_outputs) == 2
    assert res.confidence_level is ConfidenceLevel.HIGH


# --------------------------------------------------------------------------- #
# JSON serialization
# --------------------------------------------------------------------------- #
def test_agent_output_json_round_trip():
    out = _output(evidence=[Evidence(claim="c")], warnings=["stale"])
    raw = out.model_dump_json()
    assert isinstance(raw, str)
    restored = AgentOutput.model_validate_json(raw)
    assert restored == out


def test_coordinator_result_json_round_trip():
    res = CoordinatorResult(
        group=AgentGroup.LONG_TERM,
        ticker="AAPL",
        as_of=_now(),
        signal=Signal.HOLD,
        confidence=0.5,
        summary="balanced",
        member_outputs=[_output()],
        errors=[ErrorInfo(code="X", message="y")],
    )
    restored = CoordinatorResult.model_validate_json(res.model_dump_json())
    assert restored == res
