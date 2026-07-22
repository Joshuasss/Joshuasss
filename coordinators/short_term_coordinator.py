"""short_term_coordinator — group lead for the short-term desk.

For now it wires up exactly one real agent, `momentum_agent`. The others
(chart_scan, risk, catalyst_sentiment) are not implemented yet; when they are,
they slot into `_default_agents` and the aggregation in `BaseCoordinator`
handles them with no further change here.
"""

from __future__ import annotations

from agents.short_term.momentum_agent import MomentumAgent
from coordinators.base_coordinator import BaseCoordinator
from core.base_agent import BaseAgent
from core.enums import AgentGroup
from data.market_data import MarketDataProvider, build_sample_provider


class ShortTermCoordinator(BaseCoordinator):
    """Aggregates the short-term group's agents into one CoordinatorResult."""

    group = AgentGroup.SHORT_TERM

    def __init__(
        self,
        provider: MarketDataProvider,
        *,
        agents: list[BaseAgent] | None = None,
    ) -> None:
        # Extension point: future short-term agents are appended in _default_agents.
        # `None` means "use the defaults"; an explicit list (even empty) is honored.
        super().__init__(self._default_agents(provider) if agents is None else agents)

    @staticmethod
    def _default_agents(provider: MarketDataProvider) -> list[BaseAgent]:
        return [
            MomentumAgent(provider),
            # TODO(step-5+): ChartScanAgent(provider), RiskAgent(provider),
            #                CatalystSentimentAgent(provider)
        ]


def build_short_term_coordinator(
    provider: MarketDataProvider | None = None,
) -> ShortTermCoordinator:
    """Convenience factory using the in-memory sample provider by default."""
    return ShortTermCoordinator(provider or build_sample_provider())
