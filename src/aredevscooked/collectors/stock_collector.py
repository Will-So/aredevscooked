"""Stock price collector using yfinance and SQLite for accurate data."""

import math
import sqlite3
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import yfinance as yf


class StockCollector:
    """Collect stock price data using yfinance with SQLite caching."""

    def __init__(self, db_path: str | Path = "data/stocks.db"):
        """Initialize stock collector.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database with schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stock_prices (
                    id INTEGER PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    date TEXT NOT NULL,
                    close_price REAL NOT NULL,
                    collected_at TEXT NOT NULL,
                    UNIQUE(ticker, date)
                )
            """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ticker_date ON stock_prices(ticker, date)"
            )
            conn.commit()

    def _get_cached_price(self, ticker: str, target_date: date) -> float | None:
        """Get price from SQLite cache.

        Args:
            ticker: Stock ticker symbol
            target_date: Date to look up

        Returns:
            Cached price or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT close_price FROM stock_prices WHERE ticker = ? AND date = ?",
                (ticker, target_date.isoformat()),
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def _store_price(self, ticker: str, price_date: date, price: float):
        """Store price in SQLite cache.

        Args:
            ticker: Stock ticker symbol
            price_date: Date of the price
            price: Closing price
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO stock_prices (ticker, date, close_price, collected_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    ticker,
                    price_date.isoformat(),
                    price,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

    def fetch_current_price(self, ticker: str) -> tuple[float, date]:
        """Fetch current/latest stock price using yfinance.

        Args:
            ticker: Stock ticker symbol (e.g., "HCL.NS", "CTSH")

        Returns:
            Tuple of (price, date)

        Raises:
            ValueError: If price cannot be fetched
        """
        stock = yf.Ticker(ticker)

        # Get the most recent trading day's data
        hist = stock.history(period="5d")
        if hist.empty:
            raise ValueError(f"No price data available for {ticker}")

        # Drop NaN closes — yfinance includes the current calendar day for non-US
        # markets before data is reconciled, resulting in a NaN close for that row.
        valid = hist["Close"].dropna()
        if valid.empty:
            raise ValueError(f"No valid close price data for {ticker}")
        latest_price = float(valid.iloc[-1])
        latest_date = valid.index[-1].date()

        # Cache it
        self._store_price(ticker, latest_date, latest_price)

        return latest_price, latest_date

    def fetch_historical_price(self, ticker: str, target_date: date) -> float:
        """Fetch historical stock price for a specific date.

        Args:
            ticker: Stock ticker symbol
            target_date: Date to fetch price for

        Returns:
            Closing price for that date (or nearest trading day)

        Raises:
            ValueError: If price cannot be fetched
        """
        # Check cache first
        cached = self._get_cached_price(ticker, target_date)
        if cached is not None:
            return cached

        stock = yf.Ticker(ticker)

        # Fetch a range around the target date to handle weekends/holidays
        start = target_date - timedelta(days=7)
        end = target_date + timedelta(days=1)
        hist = stock.history(start=start.isoformat(), end=end.isoformat())

        if hist.empty:
            raise ValueError(f"No historical data for {ticker} around {target_date}")

        # Find the closest date <= target_date
        valid_dates = [d.date() for d in hist.index if d.date() <= target_date]
        if not valid_dates:
            # If no date before target, use the first available
            closest_date = hist.index[0].date()
        else:
            closest_date = max(valid_dates)

        # Get the price for that date
        for idx in hist.index:
            if idx.date() == closest_date:
                price = float(hist.loc[idx, "Close"])
                if math.isnan(price):
                    raise ValueError(f"Price data for {ticker} on {closest_date} is NaN (API returned incomplete data)")
                self._store_price(ticker, closest_date, price)
                return price

        raise ValueError(f"Could not find price for {ticker} on {target_date}")

    def collect_stock_data(
        self, company_name: str, ticker: str, one_year_ago: date | None = None
    ) -> dict[str, Any]:
        """Collect stock price data for a company.

        Returns data in the same format as GeminiCollector.collect_stock_data()
        for compatibility.

        Args:
            company_name: Full company name
            ticker: Stock ticker symbol
            one_year_ago: Date from exactly 1 year ago (optional)

        Returns:
            Dictionary with stock price data
        """
        if one_year_ago is None:
            one_year_ago = date.today() - timedelta(days=365)

        # Fetch current price
        current_price, current_date = self.fetch_current_price(ticker)

        # Fetch historical price
        price_1_year_ago = self.fetch_historical_price(ticker, one_year_ago)

        return {
            "company": company_name,
            "ticker": ticker,
            "current_price": round(current_price, 2),
            "current_date": current_date.isoformat(),
            "price_1_year_ago": round(price_1_year_ago, 2),
            "price_1_year_ago_date": one_year_ago.isoformat(),
            "source_urls": [f"https://finance.yahoo.com/quote/{ticker}"],
        }

    def close(self):
        """Close any open resources (for API compatibility)."""
        pass
