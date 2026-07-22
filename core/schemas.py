"""Standardized input/output contracts.

Every agent and every coordinator speaks these two shapes: `AgentInput` in,
`AgentOutput` out. Because a coordinator emits the same `AgentOutput` as an
individual agent, higher layers (the manager, the dashboard) only ever need
to understand one output schema.

These models validate at the boundary: malformed data fails loudly here
rather than silently flowing downstream into a money decision.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Horizon(str, Enum):
    """Which analytical lens a request is being run under."""

    SHORT_TERM = "SHORT_TERM"
    LONG_TERM = "LONG_TERM"
    RESEARCH = "RESEARCH"


class Signal(str, Enum):
    """The directional call an agent or coordinator emits.

    Ordered from most bearish to most bullish. NEUTRAL is distinct from HOLD:
    HOLD is an active "stay put" call, NEUTRAL means "no directional opinion"
    (e.g. a pure research/context agent).
    """

    STRONG_SELL = "STRONG_SELL"
    SELL = "SELL"
    HOLD = "HOLD"
    BUY = "BUY"
    STRONG_BUY = "STRONG_BUY"
    NEUTRAL = "NEUTRAL"


class Evidence(BaseModel):
    """A single structured fact a signal rests on.

    Free-form enough to hold any agent's supporting point, but structured
    enough that the QA agent and dashboard can iterate over it.
    """

    model_config = ConfigDict(extra="forbid")

    claim: str = Field(..., description="Human-readable supporting statement.")
    source: str | None = Field(
        default=None, description="Where the fact came from (feed, filing, indicator)."
    )
    value: float | str | None = Field(
        default=None, description="Optional numeric or textual value for the claim."
    )


class AgentInput(BaseModel):
    """The standardized input every agent and coordinator receives."""

    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(..., min_length=1, description="Symbol under analysis, e.g. 'AAPL'.")
    as_of: datetime = Field(
        ...,
        description="Point-in-time for the analysis. Enforces no look-ahead: "
        "agents must only use data available at or before this moment.",
    )
    horizon: Horizon = Field(..., description="Analytical lens for this request.")
    context: dict = Field(
        default_factory=dict,
        description="Shared upstream data and research signals for the agent to use.",
    )
    request_id: str = Field(
        ..., min_length=1, description="Trace id tying this request across agents/logs."
    )


class AgentOutput(BaseModel):
    """The standardized 'signal envelope' every agent and coordinator emits.

    `signal` + `confidence` are the machine-combinable fields a coordinator or
    the manager aggregates. `rationale` + `evidence` keep the call explainable.
    `metrics` is a free-form bag for agent-specific numbers. `warnings` makes
    data-quality problems first-class. `meta` carries trace/latency info.
    """

    model_config = ConfigDict(extra="forbid")

    agent_name: str = Field(..., min_length=1, description="Producer of this output.")
    ticker: str = Field(..., min_length=1)
    as_of: datetime = Field(..., description="Point-in-time this output corresponds to.")

    signal: Signal
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Strength of conviction, 0.0–1.0."
    )
    rationale: str = Field(..., min_length=1, description="Short 'why' for the signal.")

    evidence: list[Evidence] = Field(default_factory=list)
    metrics: dict = Field(
        default_factory=dict, description="Agent-specific numbers (RSI, payout ratio, ...)."
    )
    warnings: list[str] = Field(
        default_factory=list, description="Data gaps, stale inputs, low sample size."
    )
    meta: dict = Field(
        default_factory=dict, description="Latency, model used, tokens, request_id."
    )
