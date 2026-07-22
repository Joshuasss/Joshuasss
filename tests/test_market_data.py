"""Tests for the in-memory market-data source."""

from datetime import datetime, timedelta, timezone

import pytest

from core.errors import DataError
from data.market_data import (
    InMemoryMarketDataProvider,
    MarketDataProvider,
    PriceBar,
    build_sample_provider,
)


def _bars(n: int, start_price: float = 100.0):
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [PriceBar(ts=t0 + timedelta(days=i), close=start_price + i) for i in range(n)]


def test_provider_satisfies_protocol():
    assert isinstance(build_sample_provider(), MarketDataProvider)


def test_get_series_returns_all_bars_without_as_of():
    p = InMemoryMarketDataProvider({"ABC": _bars(5)})
    series = p.get_price_series("ABC")
    assert len(series) == 5
    assert series.closes == [100.0, 101.0, 102.0, 103.0, 104.0]


def test_as_of_truncates_to_point_in_time():
    p = InMemoryMarketDataProvider({"ABC": _bars(5)})
    cutoff = datetime(2026, 1, 3, tzinfo=timezone.utc)  # keeps bars for days 1-3
    series = p.get_price_series("ABC", as_of=cutoff)
    assert len(series) == 3


def test_as_of_before_history_yields_empty_series():
    p = InMemoryMarketDataProvider({"ABC": _bars(5)})
    series = p.get_price_series("ABC", as_of=datetime(2025, 1, 1, tzinfo=timezone.utc))
    assert len(series) == 0


def test_unknown_ticker_raises_data_error():
    p = InMemoryMarketDataProvider({"ABC": _bars(2)})
    with pytest.raises(DataError):
        p.get_price_series("ZZZ")


def test_ticker_lookup_is_case_insensitive():
    p = InMemoryMarketDataProvider({"ABC": _bars(2)})
    assert p.get_price_series("abc").ticker == "ABC"


def test_price_bar_rejects_nonpositive_close():
    with pytest.raises(ValueError):
        PriceBar(ts=datetime(2026, 1, 1, tzinfo=timezone.utc), close=0)


def test_sample_provider_has_expected_tickers():
    assert set(build_sample_provider().tickers) == {"AAPL", "DOWNTREND", "SIDEWAYS", "UPTREND"}
