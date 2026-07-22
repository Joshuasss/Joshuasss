"""Standardized data contracts for the trading research system.

Every agent and coordinator speaks these shapes. The design rule: prefer one
shared, reusable contract over duplicated per-agent models. The base result
(`AgentOutput`) is the "signal envelope"; specialized results extend it rather
than restate it, so higher layers only ever learn one core schema.

All models validate at the boundary (`extra="forbid"`, bounded confidence,
non-empty required strings) so malformed data fails loudly here instead of
flowing silently downstream. Pydantic v2 gives JSON in/out for free via
`model_dump_json()` / `model_validate_json()`.

There is no trading logic in this module — only types, validation, and one
score→bucket classification helper.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class _Base(BaseModel):
    """Shared base config: reject unknown fields, validate on assignment."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


# --------------------------------------------------------------------------- #
# Error model
# --------------------------------------------------------------------------- #
class ErrorInfo(_Base):
    """A serializable error record.

    Distinct from the exceptions in `core.errors`: exceptions are raised and
    caught in code; `ErrorInfo` is a *data* record that travels inside results
    (e.g. a coordinator listing which member agents failed) and serializes to
    JSON for logs and the dashboard.
    """

    code: str = Field(..., min_length=1, description="Stable machine-readable error code.")
    message: str = Field(..., min_length=1, description="Human-readable description.")
    agent_name: AgentName | None = Field(default=None)
    group: AgentGroup | None = Field(default=None)
    details: dict = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# --------------------------------------------------------------------------- #
# Evidence & research artifacts
# --------------------------------------------------------------------------- #
class Evidence(_Base):
    """An atomic supporting fact carried inline inside a result's `evidence`."""

    claim: str = Field(..., min_length=1, description="Supporting statement.")
    source: str | None = Field(default=None, description="Feed, filing, or indicator.")
    value: float | str | None = Field(default=None, description="Optional value for the claim.")


class ResearchNote(_Base):
    """A standalone research artifact produced by the research group.

    Richer than `Evidence`: a note is a first-class item that can be stored,
    listed, and later fed as context into short-/long-term agents.
    """

    note_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    source: str | None = Field(default=None)
    url: str | None = Field(default=None)
    published_at: datetime | None = Field(default=None)
    tickers: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Requests
# --------------------------------------------------------------------------- #
class AgentInput(_Base):
    """The standardized input a single agent receives from its coordinator."""

    ticker: str = Field(..., min_length=1, description="Symbol under analysis, e.g. 'AAPL'.")
    as_of: datetime = Field(
        ...,
        description="Point-in-time for the analysis. Enforces no look-ahead: agents "
        "must only use data available at or before this moment.",
    )
    horizon: TimeHorizon = Field(..., description="Analytical lens for this request.")
    context: dict = Field(
        default_factory=dict,
        description="Shared upstream data and research signals for the agent to use.",
    )
    request_id: str = Field(..., min_length=1, description="Trace id across agents/logs.")


class ResearchRequest(_Base):
    """Top-level user request for a ticker/company.

    The entry point a coordinator fans out into per-agent `AgentInput`s. Kept
    separate from `AgentInput` because it targets *groups*, not one agent.
    """

    ticker: str = Field(..., min_length=1)
    company_name: str | None = Field(default=None)
    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    horizon: TimeHorizon | None = Field(default=None)
    groups: list[AgentGroup] = Field(
        default_factory=lambda: list(AgentGroup),
        description="Which groups to run. Defaults to all.",
    )
    questions: list[str] = Field(
        default_factory=list, description="Optional specific questions to steer research."
    )
    context: dict = Field(default_factory=dict)
    request_id: str = Field(..., min_length=1)


# --------------------------------------------------------------------------- #
# Base result (the signal envelope)
# --------------------------------------------------------------------------- #
class AgentOutput(_Base):
    """The standardized 'signal envelope' every agent emits.

    `signal` + `confidence` are the machine-combinable fields a coordinator or
    manager aggregates. `confidence_level` is auto-derived from `confidence`
    when omitted. `rationale` + `evidence` keep the call explainable. `metrics`
    is a free-form bag for agent-specific numbers; `warnings`/`error` surface
    data-quality and failure information; `meta` carries trace/latency info.
    """

    agent_name: AgentName
    group: AgentGroup
    ticker: str = Field(..., min_length=1)
    as_of: datetime = Field(..., description="Point-in-time this output corresponds to.")

    status: Status = Field(default=Status.SUCCESS)
    signal: Signal
    confidence: float = Field(..., ge=0.0, le=1.0, description="Conviction, 0.0–1.0.")
    confidence_level: ConfidenceLevel | None = Field(
        default=None, description="Auto-derived from `confidence` if not supplied."
    )
    rationale: str = Field(..., min_length=1, description="Short 'why' for the signal.")

    evidence: list[Evidence] = Field(default_factory=list)
    metrics: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    error: ErrorInfo | None = Field(default=None)
    meta: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _fill_confidence_level(self) -> "AgentOutput":
        if self.confidence_level is None:
            # assign via __dict__ to avoid re-triggering validate_assignment
            object.__setattr__(
                self, "confidence_level", ConfidenceLevel.from_score(self.confidence)
            )
        return self


# --------------------------------------------------------------------------- #
# Specialized results (extend, don't duplicate)
# --------------------------------------------------------------------------- #
class ShortTermResult(AgentOutput):
    """Short-term group result: adds price-action context."""

    key_levels: dict = Field(
        default_factory=dict, description="e.g. {'support': 180.0, 'resistance': 195.0}."
    )
    catalysts: list[str] = Field(default_factory=list)
    trade_candidate: "TradeCandidate | None" = Field(default=None)


class LongTermResult(AgentOutput):
    """Long-term group result: adds thesis/fundamentals context."""

    thesis: str | None = Field(default=None)
    fundamental_metrics: dict = Field(default_factory=dict)
    risks: list[str] = Field(default_factory=list)


class MarketRegimeResult(AgentOutput):
    """Research group result describing the macro regime."""

    regime: MarketRegime
    drivers: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Trade candidate / watchlist item
# --------------------------------------------------------------------------- #
class TradeCandidate(_Base):
    """A surfaced idea for the watchlist. Pure data — not an order."""

    ticker: str = Field(..., min_length=1)
    direction: Direction
    group: AgentGroup
    time_horizon: TimeHorizon
    conviction: ConfidenceLevel
    rationale: str = Field(..., min_length=1)
    source_agent: AgentName | None = Field(default=None)
    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tags: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Coordinator result (group-level envelope)
# --------------------------------------------------------------------------- #
class CoordinatorResult(_Base):
    """A group lead's aggregated result over its member agents.

    Carries the raw `member_outputs` plus the coordinator's aggregate call, so
    the (later) manager and dashboard can see both the summary and the parts.
    """

    group: AgentGroup
    ticker: str = Field(..., min_length=1)
    as_of: datetime
    status: Status = Field(default=Status.SUCCESS)

    signal: Signal
    confidence: float = Field(..., ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel | None = Field(default=None)
    summary: str = Field(..., min_length=1)

    member_outputs: list[AgentOutput] = Field(default_factory=list)
    candidates: list[TradeCandidate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[ErrorInfo] = Field(default_factory=list)
    meta: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _fill_confidence_level(self) -> "CoordinatorResult":
        if self.confidence_level is None:
            object.__setattr__(
                self, "confidence_level", ConfidenceLevel.from_score(self.confidence)
            )
        return self


# Resolve the forward reference in ShortTermResult.trade_candidate.
ShortTermResult.model_rebuild()
