"""Shared exception types.

Kept in one place so agents, coordinators, and the manager can catch a
common hierarchy instead of provider- or agent-specific errors.
"""


class TradingResearchError(Exception):
    """Base class for all errors raised by this system."""


class AgentError(TradingResearchError):
    """An agent failed while producing its output.

    Coordinators catch this so that one failing agent does not sink an
    entire group; the failure is recorded rather than propagated blindly.
    """

    def __init__(self, agent_name: str, message: str) -> None:
        self.agent_name = agent_name
        super().__init__(f"[{agent_name}] {message}")


class DataError(TradingResearchError):
    """A data-access layer failed to fetch or normalize required data."""


class ContractError(TradingResearchError):
    """An input or output violated the standardized schema contract."""
