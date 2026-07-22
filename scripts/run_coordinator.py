"""Run a group coordinator end-to-end from the command line.

Mirrors scripts/run_agent.py but at the group level: builds the shared
`ResearchRequest`, runs the named coordinator, and prints the
`CoordinatorResult` as JSON. Only `short_term` is registered so far.

Examples:
    python -m scripts.run_coordinator --group short_term --ticker UPTREND
    python -m scripts.run_coordinator --group short_term --ticker AAPL --as-of 2026-01-15
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone

from coordinators.short_term_coordinator import build_short_term_coordinator
from core.errors import TradingResearchError
from core.schemas import CoordinatorResult, ResearchRequest
from data.market_data import MarketDataProvider

# Registry of runnable coordinators: name -> factory(provider) -> coordinator.
COORDINATOR_FACTORIES = {
    "short_term": build_short_term_coordinator,
}


def run_coordinator(
    group_key: str,
    ticker: str,
    *,
    as_of: datetime | None = None,
    provider: MarketDataProvider | None = None,
) -> CoordinatorResult:
    """Build the request, run the named coordinator, and return its result."""
    if group_key not in COORDINATOR_FACTORIES:
        raise ValueError(
            f"unknown coordinator {group_key!r}; available: {sorted(COORDINATOR_FACTORIES)}"
        )

    coordinator = COORDINATOR_FACTORIES[group_key](provider)
    request = ResearchRequest(
        ticker=ticker,
        as_of=as_of or datetime.now(timezone.utc),
        request_id=f"cli-{uuid.uuid4().hex[:8]}",
    )
    return coordinator.run(request)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a trading-research group coordinator.")
    parser.add_argument("--group", default="short_term", choices=sorted(COORDINATOR_FACTORIES))
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
        result = run_coordinator(args.group, args.ticker, as_of=as_of)
    except TradingResearchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
