"""Shared coordinator machinery.

A coordinator is a group lead: it fans a request out to its member agents,
collects each agent's `AgentOutput`, and folds them into a single
`CoordinatorResult` — which uses the same envelope vocabulary as an agent, so
the (later) manager sees one shape whether it looks at an agent or a group.

`BaseCoordinator` owns the reusable parts (fan-out, per-agent error capture,
a simple explicit confidence-weighted vote). Concrete coordinators only supply
their `group` and their list of agents. Adding a future short-term agent is a
one-line append to that list — no changes here.

Aggregation is deliberately simple and explicit (documented in `_aggregate`).
No network, no trade logic.
"""

from __future__ import annotations

from core.base_agent import BaseAgent
from core.enums import AgentGroup, AgentName, Signal, Status, TimeHorizon
from core.errors import AgentError, TradingResearchError
from core.schemas import (
    AgentInput,
    AgentOutput,
    CoordinatorResult,
    ErrorInfo,
    ResearchRequest,
)

# Signal -> numeric score, used for the confidence-weighted vote.
_SIGNAL_SCORE: dict[Signal, float] = {
    Signal.STRONG_SELL: -2.0,
    Signal.SELL: -1.0,
    Signal.HOLD: 0.0,
    Signal.NEUTRAL: 0.0,
    Signal.BUY: 1.0,
    Signal.STRONG_BUY: 2.0,
}

_GROUP_HORIZON: dict[AgentGroup, TimeHorizon] = {
    AgentGroup.SHORT_TERM: TimeHorizon.SHORT_TERM,
    AgentGroup.LONG_TERM: TimeHorizon.LONG_TERM,
    AgentGroup.RESEARCH: TimeHorizon.RESEARCH,
}


def _score_to_signal(score: float) -> Signal:
    """Map an aggregate score back onto a Signal bucket (inverse of _SIGNAL_SCORE)."""
    if score >= 1.5:
        return Signal.STRONG_BUY
    if score >= 0.5:
        return Signal.BUY
    if score <= -1.5:
        return Signal.STRONG_SELL
    if score <= -0.5:
        return Signal.SELL
    return Signal.HOLD


def _as_agent_name(raw: str | None) -> AgentName | None:
    try:
        return AgentName(raw) if raw is not None else None
    except ValueError:
        return None


class BaseCoordinator:
    """Runs a group of agents and aggregates their outputs.

    Subclasses set `group` and pass their agent list to `__init__`.
    """

    #: The group this coordinator represents. Subclasses must set this.
    group: AgentGroup

    def __init__(self, agents: list[BaseAgent]) -> None:
        if getattr(self, "group", None) is None:
            raise ValueError(f"{type(self).__name__} must set a `group`")
        if not agents:
            raise ValueError(f"{type(self).__name__} requires at least one agent")
        self.agents = agents

    # -- public API -------------------------------------------------------- #
    def run(self, request: ResearchRequest) -> CoordinatorResult:
        """Fan `request` out to every member agent and aggregate the results."""
        if not isinstance(request, ResearchRequest):
            raise ValueError("run() requires a ResearchRequest instance")

        as_of = request.as_of
        member_outputs: list[AgentOutput] = []
        errors: list[ErrorInfo] = []

        for agent in self.agents:
            agent_input = self._build_input(request)
            try:
                member_outputs.append(agent.run(agent_input))
            except (AgentError, TradingResearchError) as exc:
                errors.append(
                    ErrorInfo(
                        code="AGENT_FAILED",
                        message=str(exc),
                        agent_name=_as_agent_name(getattr(exc, "agent_name", None)),
                        group=self.group,
                    )
                )

        status, signal, confidence, summary, warnings = self._aggregate(
            member_outputs, errors
        )

        return CoordinatorResult(
            group=self.group,
            ticker=request.ticker.upper(),
            as_of=as_of,
            status=status,
            signal=signal,
            confidence=confidence,
            summary=summary,
            member_outputs=member_outputs,
            warnings=warnings,
            errors=errors,
            meta={
                "request_id": request.request_id,
                "agents_total": len(self.agents),
                "agents_reported": len(member_outputs),
                "agents_failed": len(errors),
            },
        )

    # -- extension points -------------------------------------------------- #
    def _build_input(self, request: ResearchRequest) -> AgentInput:
        """Translate the group request into a single agent's input."""
        horizon = request.horizon or _GROUP_HORIZON[self.group]
        return AgentInput(
            ticker=request.ticker,
            as_of=request.as_of,
            horizon=horizon,
            context=dict(request.context),
            request_id=request.request_id,
        )

    def _aggregate(
        self, outputs: list[AgentOutput], errors: list[ErrorInfo]
    ) -> tuple[Status, Signal, float, str, list[str]]:
        """Fold member outputs into (status, signal, confidence, summary, warnings).

        Approach (simple and explicit):
          * signal  — confidence-weighted vote: each agent's signal maps to a
            score in [-2, +2], weighted by its confidence; the mean maps back to
            a Signal bucket.
          * confidence — the mean of contributing agents' confidence (how sure
            the desk is on average).
          * status  — FAILED if nobody reported; PARTIAL if any agent failed or
            any output was itself PARTIAL; otherwise SUCCESS.
        """
        total = len(self.agents)

        if not outputs:
            summary = f"{self.group.value}: no agents reported ({len(errors)}/{total} failed)."
            return Status.FAILED, Signal.NEUTRAL, 0.0, summary, ["all member agents failed"]

        weight = sum(o.confidence for o in outputs)
        if weight > 0:
            score = sum(_SIGNAL_SCORE[o.signal] * o.confidence for o in outputs) / weight
        else:
            score = 0.0
        signal = _score_to_signal(score)
        confidence = round(sum(o.confidence for o in outputs) / len(outputs), 4)

        any_partial = any(o.status is Status.PARTIAL for o in outputs)
        status = Status.PARTIAL if (errors or any_partial) else Status.SUCCESS

        warnings: list[str] = []
        if errors:
            warnings.append(f"{len(errors)}/{total} agent(s) failed")
        if any_partial:
            warnings.append("one or more agents returned partial results")

        per_agent = "; ".join(
            f"{o.agent_name.value}: {o.signal.value} ({o.confidence:.2f})" for o in outputs
        )
        summary = (
            f"{self.group.value} aggregate {signal.value} "
            f"(confidence {confidence:.2f}) from {len(outputs)}/{total} agent(s). {per_agent}."
        )
        return status, signal, confidence, summary, warnings
