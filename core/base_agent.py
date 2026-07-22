"""Abstract base class every agent inherits.

`BaseAgent` owns the shared plumbing — input validation, timing, and turning
an unexpected exception into a well-typed `AgentError` — so that concrete
agents only implement their one analytical method, `analyze`.

There is deliberately no trading logic here. `analyze` is abstract; this file
defines the interface and the guarantees around it, nothing more.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod

from core.errors import AgentError
from core.schemas import AgentInput, AgentOutput


class BaseAgent(ABC):
    """Common contract for all agents and coordinators.

    Subclasses set a `name` and implement `analyze(input) -> AgentOutput`.
    Callers use `run(input)`, which validates, times, and error-wraps the call.
    """

    #: Human-readable identifier, stamped onto outputs and errors.
    name: str = "base_agent"

    def run(self, agent_input: AgentInput) -> AgentOutput:
        """Validate input, invoke `analyze`, and guarantee a typed result.

        Any exception raised inside `analyze` is re-raised as `AgentError` so
        that coordinators can catch a single, predictable type. Latency is
        recorded into the output's `meta` bag.
        """
        if not isinstance(agent_input, AgentInput):
            raise AgentError(self.name, "run() requires an AgentInput instance")

        start = time.perf_counter()
        try:
            output = self.analyze(agent_input)
        except AgentError:
            raise
        except Exception as exc:  # noqa: BLE001 - intentionally broad at the boundary
            raise AgentError(self.name, f"analyze() failed: {exc}") from exc

        if not isinstance(output, AgentOutput):
            raise AgentError(self.name, "analyze() must return an AgentOutput")

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        output.meta.setdefault("agent_name", self.name)
        output.meta.setdefault("request_id", agent_input.request_id)
        output.meta["latency_ms"] = round(elapsed_ms, 3)
        return output

    @abstractmethod
    def analyze(self, agent_input: AgentInput) -> AgentOutput:
        """Produce the agent's signal envelope for the given input.

        Concrete agents implement their analysis here. Must return an
        `AgentOutput`; raising is allowed and will be wrapped by `run`.
        """
        raise NotImplementedError
