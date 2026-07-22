"""Shared enumerations.

All typed vocabularies live here so every model, agent, and coordinator draws
from one source of truth instead of redefining string constants. No logic —
just the controlled sets of values the system is allowed to use.
"""

from __future__ import annotations

from enum import Enum


class AgentGroup(str, Enum):
    """Which team an agent belongs to / which team a coordinator represents."""

    SHORT_TERM = "SHORT_TERM"
    LONG_TERM = "LONG_TERM"
    RESEARCH = "RESEARCH"


class AgentName(str, Enum):
    """Canonical registry of every leaf agent in the system.

    Values are the snake_case identifiers used in code, logs, and outputs.
    """

    # short-term group
    CHART_SCAN_AGENT = "chart_scan_agent"
    MOMENTUM_AGENT = "momentum_agent"
    RISK_AGENT = "risk_agent"
    CATALYST_SENTIMENT_AGENT = "catalyst_sentiment_agent"

    # long-term group
    FINANCIAL_STATEMENT_AGENT = "financial_statement_agent"
    DIVIDEND_AGENT = "dividend_agent"
    INDUSTRY_GROWTH_AGENT = "industry_growth_agent"
    LONG_TERM_THESIS_AGENT = "long_term_thesis_agent"

    # research group
    NEWS_MONITOR_AGENT = "news_monitor_agent"
    FINANCIAL_REPORT_READER_AGENT = "financial_report_reader_agent"
    INDUSTRY_RESEARCH_AGENT = "industry_research_agent"
    MARKET_REGIME_NEWS_AGENT = "market_regime_news_agent"


class Status(str, Enum):
    """Outcome of an agent or coordinator run."""

    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"  # produced a result but with gaps/warnings
    SKIPPED = "SKIPPED"  # intentionally not run
    FAILED = "FAILED"  # errored, no usable result


class TimeHorizon(str, Enum):
    """Investment time horizon for a request or result."""

    SHORT_TERM = "SHORT_TERM"
    LONG_TERM = "LONG_TERM"
    RESEARCH = "RESEARCH"


class Signal(str, Enum):
    """Directional call, ordered most-bearish to most-bullish.

    NEUTRAL is distinct from HOLD: HOLD is an active "stay put" call, NEUTRAL
    means "no directional opinion" (e.g. a pure research/context agent).
    """

    STRONG_SELL = "STRONG_SELL"
    SELL = "SELL"
    HOLD = "HOLD"
    BUY = "BUY"
    STRONG_BUY = "STRONG_BUY"
    NEUTRAL = "NEUTRAL"


class ConfidenceLevel(str, Enum):
    """Categorical bucket for a 0.0–1.0 confidence score.

    The numeric score stays the machine-combinable field; this bucket is the
    human-readable companion used in summaries and the (later) dashboard.
    """

    VERY_LOW = "VERY_LOW"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"

    @classmethod
    def from_score(cls, score: float) -> "ConfidenceLevel":
        """Map a 0.0–1.0 score onto a bucket. Pure classification, no strategy."""
        if not 0.0 <= score <= 1.0:
            raise ValueError(f"confidence score must be in [0, 1], got {score}")
        if score < 0.2:
            return cls.VERY_LOW
        if score < 0.4:
            return cls.LOW
        if score < 0.6:
            return cls.MEDIUM
        if score < 0.8:
            return cls.HIGH
        return cls.VERY_HIGH


class MarketRegime(str, Enum):
    """Macro backdrop the market is currently in."""

    RISK_ON = "RISK_ON"
    RISK_OFF = "RISK_OFF"
    NEUTRAL = "NEUTRAL"
    TRANSITION = "TRANSITION"


class Direction(str, Enum):
    """Intended side of a candidate trade."""

    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"
