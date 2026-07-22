"""Run a single agent end-to-end from the command line.

The smallest clean wiring: a name->factory registry, a helper that builds the
shared `AgentInput`, runs the agent, and returns its `AgentOutput`, and a
`main()` that prints the result as JSON. Only `momentum` is registered so far.

Examples:
    python -m scripts.run_agent --agent momentum --ticker UPTREND
    python -m scripts.run_agent --agent momentum --ticker AAPL --as-of 2026-01-15
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone

from agents.short_term.momentum_agent import MomentumAgent
from core.enums import TimeHorizon
from core.errors import TradingResearchError
from core.schemas import AgentInput, AgentOutput
from data.market_data import MarketDataProvider, build_sample_provider

# Registry of runnable agents: name -> (factory, horizon).
AGENT_FACTORIES = {
    "momentum": (MomentumAgent, TimeHorizon.SHORT_TERM),
}


def run_agent(
    agent_key: str,
    ticker: str,
    *,
    as_of: datetime | None = None,
    provider: MarketDataProvider | None = None,
) -> AgentOutput:
    """Build the input, run the named agent, and return its output."""
    if agent_key not in AGENT_FACTORIES:
        raise ValueError(
            f"unknown agent {agent_key!r}; available: {sorted(AGENT_FACTORIES)}"
        )

    factory, horizon = AGENT_FACTORIES[agent_key]
    provider = provider or build_sample_provider()
    agent = factory(provider)

    agent_input = AgentInput(
        ticker=ticker,
        as_of=as_of or datetime.now(timezone.utc),
        horizon=horizon,
        request_id=f"cli-{uuid.uuid4().hex[:8]}",
    )
    return agent.run(agent_input)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a single trading-research agent.")
    parser.add_argument("--agent", default="momentum", choices=sorted(AGENT_FACTORIES))
    parser.add_argument("--ticker", required=True, help="Symbol, e.g. UPTREND or AAPL.")
    parser.add_argument(
        "--as-of",
        default=None,
        help="ISO datetime; only data at/before this is used. Defaults to now.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    as_of = datetime.fromisoformat(args.as_of) if args.as_of else None
    if as_of is not None and as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)

    try:
        output = run_agent(args.agent, args.ticker, as_of=as_of)
    except TradingResearchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(output.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
