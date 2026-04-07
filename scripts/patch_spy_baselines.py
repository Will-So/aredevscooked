#!/usr/bin/env python3
"""One-time script to backfill SPY prices into existing baselines.json.

Loads data/processed/baselines.json, fetches SPY closing price for each
baseline's recorded date using yfinance, and adds an "S&P 500" entry to
each baseline's stock_prices dict.
"""

import json
from datetime import date
from pathlib import Path

from aredevscooked.collectors.stock_collector import StockCollector
from aredevscooked.config import MARKET_BENCHMARK


def main():
    baselines_file = Path("data/processed/baselines.json")
    with open(baselines_file) as f:
        data = json.load(f)

    collector = StockCollector()
    ticker = MARKET_BENCHMARK["ticker"]
    name = MARKET_BENCHMARK["name"]

    for baseline_name, baseline in data["baselines"].items():
        target_date = date.fromisoformat(baseline["date"])
        print(f"Fetching {ticker} price for {baseline_name} ({target_date})...")
        price = collector.fetch_historical_price(ticker, target_date)
        price = round(price, 2)
        print(f"  {ticker} on {target_date}: {price}")
        baseline["stock_prices"][name] = {
            "company": name,
            "ticker": ticker,
            "price": price,
            "date": target_date.isoformat(),
        }

    with open(baselines_file, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nPatched {len(data['baselines'])} baselines in {baselines_file}")


if __name__ == "__main__":
    main()
