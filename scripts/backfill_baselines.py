#!/usr/bin/env python3
"""Backfill historical baseline data for change calculations.

This script collects historical data for specific baseline dates:
- Q1 2023 (2023-03-31): Long-term baseline
- 1 year ago: Annual comparison
- 30 days ago: Monthly trend
- 1 day ago: Daily change

The data is saved to data/processed/baselines.json
"""

import asyncio
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

from aredevscooked.collectors.gemini_collector import GeminiCollector
from aredevscooked.collectors.stock_collector import StockCollector
from aredevscooked.config import (
    IT_CONSULTANCIES,
    BIG_TECH_COMPANIES,
    AI_LABS,
    MARKET_BENCHMARK,
)


async def collect_historical_stock_data(
    collector: GeminiCollector, company_name: str, ticker: str, target_date: date
) -> dict[str, Any] | None:
    """Collect historical stock price for a specific date.

    Args:
        collector: GeminiCollector instance
        company_name: Company name
        ticker: Stock ticker
        target_date: Historical date to collect

    Returns:
        Stock data dict or None on error
    """
    try:
        print(f"  Collecting {company_name} stock price for {target_date}...")
        # We'll ask for the price on the target date
        data = await asyncio.to_thread(
            collector.collect_stock_data, company_name, ticker, target_date
        )
        # Extract just the historical price (price_1_year_ago field has our target)
        return {
            "company": company_name,
            "ticker": ticker,
            "price": data.get("price_1_year_ago", data.get("current_price")),
            "date": target_date.isoformat(),
        }
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return None


async def collect_historical_headcount(
    collector: GeminiCollector, company_name: str, target_date: date
) -> dict[str, Any] | None:
    """Collect historical headcount for a specific date.

    Args:
        collector: GeminiCollector instance
        company_name: Company name
        target_date: Historical date to collect

    Returns:
        Headcount data dict or None on error
    """
    try:
        print(f"  Collecting {company_name} headcount for {target_date}...")
        # Pass target_date to Gemini so it searches for historical data
        data = await asyncio.to_thread(
            collector.collect_headcount, company_name, target_date.isoformat()
        )
        return {
            "company": company_name,
            "headcount": data.get("current_headcount"),
            "date": data.get("data_date", target_date.isoformat()),
        }
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return None


async def collect_historical_jobs(
    collector: GeminiCollector, company_name: str, jobs_url: str
) -> dict[str, Any] | None:
    """Collect historical job posting count.

    Note: Historical job posting data is not available from job boards.
    We'll need to rely on daily snapshots going forward.

    Args:
        collector: GeminiCollector instance
        company_name: Company name
        jobs_url: URL to the company's job board

    Returns:
        Job posting data dict or None
    """
    # Job postings: Historical data not available from job boards
    # We'll need to rely on daily snapshots going forward
    return None


async def backfill_baseline(
    collector: GeminiCollector, baseline_name: str, target_date: date
) -> dict[str, Any]:
    """Collect all data for a specific baseline date.

    Args:
        collector: GeminiCollector instance
        baseline_name: Name for this baseline (e.g., "q1_2023", "1_year_ago")
        target_date: Date to collect data for

    Returns:
        Baseline data structure
    """
    print(f"\n📅 Collecting baseline: {baseline_name} ({target_date})")
    print("=" * 60)

    # Collect stock prices for IT consultancies
    print(f"\n📊 Stock prices as of {target_date}:")
    stock_tasks = [
        collect_historical_stock_data(
            collector, company_info["name"], company_info["ticker"], target_date
        )
        for company_info in IT_CONSULTANCIES
    ]
    stock_results = await asyncio.gather(*stock_tasks)
    stock_data = {r["company"]: r for r in stock_results if r is not None}
    print(f"  Collected {len(stock_data)}/7 companies")

    print(f"  Fetching {MARKET_BENCHMARK['ticker']} price for {target_date}...")
    try:
        spy_price = StockCollector().fetch_historical_price(
            MARKET_BENCHMARK["ticker"], target_date
        )
        stock_data[MARKET_BENCHMARK["name"]] = {
            "company": MARKET_BENCHMARK["name"],
            "ticker": MARKET_BENCHMARK["ticker"],
            "price": round(spy_price, 2),
            "date": target_date.isoformat(),
        }
        print(f"  ✓ {MARKET_BENCHMARK['ticker']}: {round(spy_price, 2)}")
    except Exception as e:
        print(f"  ✗ Could not fetch {MARKET_BENCHMARK['ticker']}: {e}")

    # Collect headcount for all companies
    print(f"\n👥 Headcount as of {target_date}:")
    all_companies = [c["name"] for c in IT_CONSULTANCIES] + [
        c["name"] for c in BIG_TECH_COMPANIES
    ]
    headcount_tasks = [
        collect_historical_headcount(collector, company_name, target_date)
        for company_name in all_companies
    ]
    headcount_results = await asyncio.gather(*headcount_tasks)
    headcount_data = {r["company"]: r for r in headcount_results if r is not None}
    print(f"  Collected {len(headcount_data)}/12 companies")

    # Job postings: Skip for historical (not available)
    print(f"\n🎯 Job postings: Skipping (historical data not available)")
    job_data = {}

    return {
        "baseline_name": baseline_name,
        "date": target_date.isoformat(),
        "stock_prices": stock_data,
        "headcounts": headcount_data,
        "job_postings": job_data,
    }


async def main_async():
    """Main entry point for baseline backfill."""
    load_dotenv()

    print("🚀 Starting baseline data backfill...")
    print("=" * 60)

    # Initialize collector
    try:
        collector = GeminiCollector()
        print("✓ GeminiCollector initialized")
    except ValueError as e:
        print(f"❌ Error: {e}")
        print("Make sure GEMINI_API_KEY is set in .env file")
        return 1

    # Load existing baselines to preserve static data (q1_2023)
    output_dir = Path("data/processed")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "baselines.json"

    existing_baselines = {}
    if output_file.exists():
        with open(output_file) as f:
            existing_data = json.load(f)
            existing_baselines = existing_data.get("baselines", {})

    # Define baseline dates
    today = date.today()
    baselines_to_collect = {
        "1_year_ago": today - timedelta(days=365),  # Annual comparison
        "30_days_ago": today - timedelta(days=30),  # Monthly trend
    }

    # Collect dynamic baselines only (q1_2023 is static and preserved from existing data)
    baselines = {}

    # Preserve q1_2023 - this is static historical data that should not be re-collected
    if "q1_2023" in existing_baselines:
        print("\n📅 Preserving static baseline: q1_2023 (2023-03-31)")
        baselines["q1_2023"] = existing_baselines["q1_2023"]
    else:
        # Only collect q1_2023 if it doesn't exist
        baseline_data = await backfill_baseline(collector, "q1_2023", date(2023, 3, 31))
        baselines["q1_2023"] = baseline_data

    for baseline_name, target_date in baselines_to_collect.items():
        baseline_data = await backfill_baseline(collector, baseline_name, target_date)
        baselines[baseline_name] = baseline_data

    baseline_output = {
        "metadata": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "description": "Historical baseline data for change calculations",
        },
        "baselines": baselines,
    }

    with open(output_file, "w") as f:
        json.dump(baseline_output, f, indent=2)

    print(f"\n✅ Baselines written to {output_file}")
    print("=" * 60)
    print("\nBaseline summary:")
    for name, data in baselines.items():
        print(
            f"  {name}: {data['date']} - "
            f"{len(data['stock_prices'])} stocks, {len(data['headcounts'])} headcounts"
        )

    return 0


def main():
    """Synchronous entry point."""
    return asyncio.run(main_async())


if __name__ == "__main__":
    exit(main())
