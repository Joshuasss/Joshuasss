"""Core shared contracts for the trading research system.

This package defines the types and interfaces every agent and coordinator
depends on. It contains no trading logic and no model calls — only the
standardized enums, input/output schemas, error types, and the abstract
base agent.
"""

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
from core.errors import AgentError, ContractError, DataError, TradingResearchError
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

__all__ = [
    # enums
    "AgentGroup",
    "AgentName",
    "ConfidenceLevel",
    "Direction",
    "MarketRegime",
    "Signal",
    "Status",
    "TimeHorizon",
    # errors
    "AgentError",
    "ContractError",
    "DataError",
    "TradingResearchError",
    # schemas
    "AgentInput",
    "AgentOutput",
    "CoordinatorResult",
    "ErrorInfo",
    "Evidence",
    "LongTermResult",
    "MarketRegimeResult",
    "ResearchNote",
    "ResearchRequest",
    "ShortTermResult",
    "TradeCandidate",
]
