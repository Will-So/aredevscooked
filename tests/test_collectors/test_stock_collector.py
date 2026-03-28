"""Tests for StockCollector class."""

import sqlite3
import tempfile
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aredevscooked.collectors.stock_collector import StockCollector


@pytest.fixture
def temp_db():
    """Create a temporary database file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        yield f.name
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def collector(temp_db):
    """Create a StockCollector with temporary database."""
    return StockCollector(db_path=temp_db)


def test_init_creates_database(temp_db):
    """Should create database and table on initialization."""
    collector = StockCollector(db_path=temp_db)

    with sqlite3.connect(temp_db) as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='stock_prices'"
        )
        assert cursor.fetchone() is not None


def test_store_and_retrieve_price(collector, temp_db):
    """Should store and retrieve prices from cache."""
    test_date = date(2024, 1, 15)
    collector._store_price("TEST", test_date, 123.45)

    cached = collector._get_cached_price("TEST", test_date)

    assert cached == 123.45


def test_get_cached_price_returns_none_if_not_found(collector):
    """Should return None if price not in cache."""
    cached = collector._get_cached_price("NONEXISTENT", date.today())

    assert cached is None


def test_store_price_overwrites_existing(collector):
    """Should overwrite existing price for same ticker/date."""
    test_date = date(2024, 1, 15)
    collector._store_price("TEST", test_date, 100.0)
    collector._store_price("TEST", test_date, 200.0)

    cached = collector._get_cached_price("TEST", test_date)

    assert cached == 200.0


@patch("aredevscooked.collectors.stock_collector.yf")
def test_fetch_current_price_uses_yfinance(mock_yf, collector):
    """Should use yfinance to fetch current price."""
    mock_ticker = MagicMock()
    mock_yf.Ticker.return_value = mock_ticker

    # Create mock history DataFrame
    import pandas as pd

    mock_hist = pd.DataFrame(
        {"Close": [100.0, 101.0, 102.5]},
        index=pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"]),
    )
    mock_ticker.history.return_value = mock_hist

    price, price_date = collector.fetch_current_price("TEST")

    assert price == 102.5
    assert price_date == date(2025, 1, 3)
    mock_yf.Ticker.assert_called_once_with("TEST")


@patch("aredevscooked.collectors.stock_collector.yf")
def test_fetch_current_price_raises_if_no_data(mock_yf, collector):
    """Should raise ValueError if no price data available."""
    mock_ticker = MagicMock()
    mock_yf.Ticker.return_value = mock_ticker

    import pandas as pd

    mock_ticker.history.return_value = pd.DataFrame()

    with pytest.raises(ValueError, match="No price data available"):
        collector.fetch_current_price("INVALID")


@patch("aredevscooked.collectors.stock_collector.yf")
def test_fetch_historical_price_uses_cache_first(mock_yf, collector):
    """Should use cached price if available."""
    test_date = date(2024, 6, 15)
    collector._store_price("TEST", test_date, 150.0)

    price = collector.fetch_historical_price("TEST", test_date)

    assert price == 150.0
    mock_yf.Ticker.assert_not_called()


@patch("aredevscooked.collectors.stock_collector.yf")
def test_fetch_historical_price_falls_back_to_yfinance(mock_yf, collector):
    """Should fetch from yfinance if not in cache."""
    mock_ticker = MagicMock()
    mock_yf.Ticker.return_value = mock_ticker

    import pandas as pd

    target_date = date(2024, 6, 15)
    mock_hist = pd.DataFrame(
        {"Close": [145.0, 150.0, 155.0]},
        index=pd.to_datetime(["2024-06-13", "2024-06-14", "2024-06-15"]),
    )
    mock_ticker.history.return_value = mock_hist

    price = collector.fetch_historical_price("TEST", target_date)

    assert price == 155.0
    mock_yf.Ticker.assert_called_once_with("TEST")


@patch("aredevscooked.collectors.stock_collector.yf")
def test_collect_stock_data_returns_expected_format(mock_yf, collector):
    """Should return data in expected format."""
    mock_ticker = MagicMock()
    mock_yf.Ticker.return_value = mock_ticker

    import pandas as pd

    today = date.today()
    one_year_ago = today - timedelta(days=365)

    # Current prices
    mock_hist_current = pd.DataFrame(
        {"Close": [1630.80]}, index=pd.to_datetime([today.isoformat()])
    )

    # Historical prices
    mock_hist_historical = pd.DataFrame(
        {"Close": [1850.0]}, index=pd.to_datetime([one_year_ago.isoformat()])
    )

    mock_ticker.history.side_effect = [mock_hist_current, mock_hist_historical]

    data = collector.collect_stock_data("HCLTech", "HCLTECH.NS", one_year_ago)

    assert data["company"] == "HCLTech"
    assert data["ticker"] == "HCLTECH.NS"
    assert data["current_price"] == 1630.80
    assert data["price_1_year_ago"] == 1850.0
    assert "source_urls" in data
    assert "yahoo.com" in data["source_urls"][0]


@patch("aredevscooked.collectors.stock_collector.yf")
def test_collect_spy_data(mock_yf, collector):
    """Should collect SPY data using the same collect_stock_data method."""
    mock_ticker = MagicMock()
    mock_yf.Ticker.return_value = mock_ticker

    import pandas as pd

    today = date.today()
    one_year_ago = today - timedelta(days=365)

    mock_hist_current = pd.DataFrame(
        {"Close": [565.42]}, index=pd.to_datetime([today.isoformat()])
    )
    mock_hist_historical = pd.DataFrame(
        {"Close": [520.10]}, index=pd.to_datetime([one_year_ago.isoformat()])
    )
    mock_ticker.history.side_effect = [mock_hist_current, mock_hist_historical]

    data = collector.collect_stock_data("S&P 500", "SPY", one_year_ago)

    assert data["company"] == "S&P 500"
    assert data["ticker"] == "SPY"
    assert data["current_price"] == 565.42
    assert data["price_1_year_ago"] == 520.10


def test_close_does_not_raise(collector):
    """Close method should not raise errors."""
    collector.close()
