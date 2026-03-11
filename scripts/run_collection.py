#!/usr/bin/env python3
"""Main orchestration script for data collection and processing."""

import asyncio
import json
import logging
import sys
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Coroutine
from pathlib import Path
from dotenv import load_dotenv


def setup_logging() -> logging.Logger:
    """Setup logging to both console and file.

    Returns:
        Configured logger instance
    """
    log_dir = Path("logs/collection")
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"collection_{timestamp}.log"

    logger = logging.getLogger("collection")
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console_handler)

    logger.info(f"Logging to: {log_file}")
    return logger


logger: logging.Logger | None = None


def log(message: str) -> None:
    """Log a message to both console and file."""
    if logger:
        logger.info(message)
    else:
        print(message)


from aredevscooked.collectors.gemini_collector import GeminiCollector
from aredevscooked.collectors.stock_collector import StockCollector
from aredevscooked.collectors.fred_collector import FredCollector
from aredevscooked.gemini_prompts import (
    create_headcount_prompt,
    create_job_postings_prompt,
)
from aredevscooked.processors.stock_processor import StockProcessor
from aredevscooked.processors.headcount_processor import HeadcountProcessor
from aredevscooked.processors.jobs_processor import JobsProcessor
from aredevscooked.processors.fred_processor import FredProcessor
from aredevscooked.generators.badge_generator import BadgeGenerator
from aredevscooked.config import IT_CONSULTANCIES, BIG_TECH_COMPANIES, AI_LABS

LOG_TIMEOUT_SECONDS = 60
STAGGER_SECONDS = 5
MAX_TIMEOUT_SECONDS = 600


async def with_timeout_logging(
    coro: Coroutine,
    task_name: str,
    position: int,
    prompt: str | None = None,
) -> Any:
    """Wrap a coroutine with timeout logging and hard timeout.

    Logs a warning if the task takes longer than LOG_TIMEOUT + (position * STAGGER_SECONDS).
    Raises TimeoutError if the task exceeds MAX_TIMEOUT_SECONDS.

    Args:
        coro: The coroutine to run
        task_name: Name of the task for logging
        position: Position in the batch (0-indexed), used to stagger log messages
        prompt: Optional prompt string to log when timeout threshold is hit

    Returns:
        The result of the coroutine

    Raises:
        TimeoutError: If task exceeds MAX_TIMEOUT_SECONDS
    """
    log_threshold = LOG_TIMEOUT_SECONDS + (position * STAGGER_SECONDS)
    start_time = time.time()
    last_log_time = 0.0

    task = asyncio.create_task(coro)

    try:
        while not task.done():
            elapsed = time.time() - start_time

            if elapsed > MAX_TIMEOUT_SECONDS:
                task.cancel()
                raise TimeoutError(
                    f"{task_name} timed out after {MAX_TIMEOUT_SECONDS}s"
                )

            # Log on first threshold, then every 60s after
            should_log = elapsed > log_threshold and (
                last_log_time == 0.0 or elapsed - last_log_time >= 60.0
            )
            if should_log:
                log(f"    ⏳ {task_name} still running after {elapsed:.0f}s...")
                if prompt:
                    # Show first 2 lines of prompt (the actual request, not the JSON template)
                    first_lines = "\n".join(prompt.split("\n")[:2])
                    log(f"       Request: {first_lines}")
                last_log_time = elapsed

            try:
                return await asyncio.wait_for(asyncio.shield(task), timeout=5.0)
            except asyncio.TimeoutError:
                continue

        return await task
    except asyncio.CancelledError:
        task.cancel()
        raise


async def collect_single_stock_data(
    collector: StockCollector,
    company_name: str,
    ticker: str,
    one_year_ago: date,
) -> tuple[str, dict[str, Any] | None]:
    """Collect stock data for a single company using yfinance.

    Args:
        collector: StockCollector instance
        company_name: Company name
        ticker: Stock ticker symbol
        one_year_ago: Date from exactly 1 year ago

    Returns:
        Tuple of (company_name, data) or (company_name, None) on error
    """
    try:
        log(f"  Collecting stock data for {company_name} ({ticker})...")

        # Run yfinance call in thread pool to avoid blocking
        data = await asyncio.to_thread(
            collector.collect_stock_data, company_name, ticker, one_year_ago
        )

        # Format currency based on ticker (INR for .NS, USD for others)
        currency = "₹" if ".NS" in ticker else "$"
        log(f"    ✓ Current: {currency}{data['current_price']:.2f}")
        return company_name, data
    except Exception as e:
        log(f"    ✗ Error collecting {company_name}: {e}")
        return company_name, None


async def collect_all_stock_data(
    collector: StockCollector, one_year_ago: date
) -> dict[str, dict[str, Any]]:
    """Collect stock price data for all IT consultancies using yfinance.

    Args:
        collector: StockCollector instance
        one_year_ago: Date from exactly 1 year ago

    Returns:
        Dictionary mapping company name to stock data
    """
    tasks = [
        collect_single_stock_data(
            collector,
            company_info["name"],
            company_info["ticker"],
            one_year_ago,
        )
        for i, company_info in enumerate(IT_CONSULTANCIES)
    ]

    results = await asyncio.gather(*tasks)

    # Filter out failed collections (None values)
    stock_data = {name: data for name, data in results if data is not None}
    return stock_data


async def collect_single_headcount_data(
    collector: GeminiCollector, company_name: str, position: int
) -> tuple[str, dict[str, Any] | None]:
    """Collect headcount data for a single company (async wrapper).

    Args:
        collector: GeminiCollector instance
        company_name: Company name
        position: Position in batch for staggered timeout logging

    Returns:
        Tuple of (company_name, data) or (company_name, None) on error
    """
    try:
        log(f"  Collecting headcount for {company_name}...")
        prompt = create_headcount_prompt(company_name)

        async def do_collect():
            return await asyncio.to_thread(collector.collect_headcount, company_name)

        data = await with_timeout_logging(
            do_collect(), f"{company_name} headcount", position, prompt
        )
        log(f"    ✓ {company_name} Headcount: {data['current_headcount']:,}")
        return company_name, data
    except Exception as e:
        log(f"    ✗ Error collecting {company_name}: {e}")
        return company_name, None


async def collect_all_headcount_data(
    collector: GeminiCollector,
) -> dict[str, dict[str, Any]]:
    """Collect headcount data for all companies (IT consultancies + Big Tech) concurrently.

    Args:
        collector: GeminiCollector instance

    Returns:
        Dictionary mapping company name to headcount data
    """
    # Combine IT consultancies and big tech
    all_companies = [c["name"] for c in IT_CONSULTANCIES] + [
        c["name"] for c in BIG_TECH_COMPANIES
    ]

    tasks = [
        collect_single_headcount_data(collector, company_name, position=i)
        for i, company_name in enumerate(all_companies)
    ]

    results = await asyncio.gather(*tasks)

    # Filter out failed collections (None values)
    headcount_data = {name: data for name, data in results if data is not None}
    return headcount_data


async def collect_single_job_posting_data(
    collector: GeminiCollector, company_name: str, jobs_url: str, position: int
) -> tuple[str, dict[str, Any] | None]:
    """Collect job posting data for a single company (async wrapper).

    Args:
        collector: GeminiCollector instance
        company_name: Company name
        jobs_url: URL to the company's job board
        position: Position in batch for staggered timeout logging

    Returns:
        Tuple of (company_name, data) or (company_name, None) on error
    """
    try:
        log(f"  Collecting job postings for {company_name}...")
        prompt = create_job_postings_prompt(company_name, jobs_url)

        async def do_collect():
            return await asyncio.to_thread(
                collector.collect_job_postings, company_name, jobs_url
            )

        data = await with_timeout_logging(
            do_collect(), f"{company_name} jobs", position, prompt
        )
        log(f"    ✓ Technical jobs: {data['total_technical_jobs']}")
        return company_name, data
    except Exception as e:
        log(f"    ✗ Error collecting {company_name}: {e}")
        return company_name, None


async def collect_all_job_posting_data(
    collector: GeminiCollector,
) -> dict[str, dict[str, Any]]:
    """Collect job posting data for all AI labs concurrently.

    Args:
        collector: GeminiCollector instance

    Returns:
        Dictionary mapping company name to job posting data
    """
    tasks = [
        collect_single_job_posting_data(
            collector, lab_info["name"], lab_info["jobs_url"], position=i
        )
        for i, lab_info in enumerate(AI_LABS)
    ]

    results = await asyncio.gather(*tasks)

    # Filter out failed collections (None values)
    job_posting_data = {name: data for name, data in results if data is not None}
    return job_posting_data


async def collect_indeed_data(collector: FredCollector) -> dict[str, Any] | None:
    """Collect Indeed Job Postings index from FRED API.

    Args:
        collector: FredCollector instance

    Returns:
        Indeed index data dict or None on error
    """
    try:
        log("  Collecting Indeed Job Postings index...")
        data = await asyncio.to_thread(collector.collect_indeed_index)
        log(f"    ✓ Current Indeed index: {data['current_value']}")
        return data
    except Exception as e:
        log(f"    ✗ Error collecting Indeed data: {e}")
        return None


def load_baselines() -> dict[str, Any] | None:
    """Load baseline data from baselines.json.

    Returns:
        Baseline data dict or None if file doesn't exist
    """
    baselines_file = Path("data/processed/baselines.json")
    if not baselines_file.exists():
        log("  ⚠️  No baselines.json found, skipping change calculations")
        return None

    with open(baselines_file, "r") as f:
        return json.load(f)


def calculate_headcount_changes(
    current: int,
    company_name: str,
    baselines_data: dict[str, Any],
    headcount_processor: HeadcountProcessor,
    gemini_data: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Calculate headcount changes against baselines and Gemini historical data.

    For 1_year_ago and q1_2023, uses Gemini's returned historical data with citations.
    For 30_days_ago, uses stored baselines.

    Args:
        current: Current headcount
        company_name: Company name
        baselines_data: Baseline data structure
        headcount_processor: HeadcountProcessor instance
        gemini_data: Optional Gemini response with one_year_ago and q1_2023 data

    Returns:
        Dictionary of changes for each baseline period with source_url citations
    """
    changes = {}

    # Map Gemini response keys to baseline names
    gemini_period_map = {
        "1_year_ago": "one_year_ago",
        "q1_2023": "q1_2023",
    }

    for baseline_name in ["30_days_ago", "1_year_ago", "q1_2023"]:
        # For 1_year_ago and q1_2023, prefer Gemini's historical data
        gemini_key = gemini_period_map.get(baseline_name)
        if gemini_key and gemini_data and gemini_key in gemini_data:
            period_data = gemini_data[gemini_key]
            if period_data and isinstance(period_data, dict):
                baseline_value = period_data.get("headcount")
                if baseline_value:
                    pct_change = headcount_processor.calculate_percentage_change(
                        current, baseline_value
                    )
                    abs_change = headcount_processor.calculate_absolute_change(
                        current, baseline_value
                    )
                    badge = headcount_processor.classify_change(pct_change)

                    changes[baseline_name] = {
                        "value": abs_change,
                        "pct": round(pct_change, 2),
                        "badge": badge,
                        "source_url": period_data.get("source_url", ""),
                        "baseline_headcount": baseline_value,
                        "baseline_date": period_data.get("as_of_date", ""),
                    }
                    continue

        # Fall back to stored baselines (always used for 30_days_ago)
        baseline = baselines_data["baselines"].get(baseline_name, {})
        headcounts = baseline.get("headcounts", {})

        if company_name in headcounts:
            baseline_value = headcounts[company_name]["headcount"]
            pct_change = headcount_processor.calculate_percentage_change(
                current, baseline_value
            )
            abs_change = headcount_processor.calculate_absolute_change(
                current, baseline_value
            )
            badge = headcount_processor.classify_change(pct_change)

            changes[baseline_name] = {
                "value": abs_change,
                "pct": round(pct_change, 2),
                "badge": badge,
                "source_url": headcounts[company_name].get("source_url", ""),
                "baseline_headcount": baseline_value,
                "baseline_date": headcounts[company_name].get("date", ""),
            }
        else:
            # No baseline data available
            changes[baseline_name] = {
                "value": None,
                "pct": None,
                "badge": "neutral",
                "source_url": "",
            }

    return changes


def load_history_snapshot(days_ago: int) -> dict[str, Any] | None:
    """Load a snapshot from metrics_history.json.

    Args:
        days_ago: Number of days ago (1, 30, etc.)

    Returns:
        Snapshot data or None if not found
    """
    history_file = Path("data/processed/metrics_history.json")
    if not history_file.exists():
        return None

    target_date = (date.today() - timedelta(days=days_ago)).isoformat()

    with open(history_file, "r") as f:
        history = json.load(f)

    return history.get("snapshots", {}).get(target_date)


def find_recent_job_posting_data(
    company_name: str, max_days_old: int = 7
) -> dict[str, Any] | None:
    """Find the most recent job posting data for a company from history.

    Searches backwards through daily snapshots up to max_days_old days.

    Args:
        company_name: Name of the company to search for
        max_days_old: Maximum age of data to accept (default: 7 days)

    Returns:
        Most recent job posting data or None if not found
    """
    history_file = Path("data/processed/metrics_history.json")
    if not history_file.exists():
        return None

    with open(history_file, "r") as f:
        history = json.load(f)

    snapshots = history.get("snapshots", {})

    # Search backwards from today up to max_days_old
    for days_back in range(max_days_old + 1):
        target_date = (date.today() - timedelta(days=days_back)).isoformat()
        snapshot = snapshots.get(target_date)

        if snapshot and company_name in snapshot.get("job_postings", {}):
            job_data = snapshot["job_postings"][company_name]
            log(
                f"  ⏪ Using {days_back}-day-old data for {company_name}: {job_data['total_technical_jobs']} jobs"
            )
            return job_data

    return None


def find_recent_headcount_data(
    company_name: str, max_days_old: int = 7
) -> dict[str, Any] | None:
    """Find the most recent headcount data for a company from history.

    Searches backwards through daily snapshots up to max_days_old days.

    Args:
        company_name: Name of the company to search for
        max_days_old: Maximum age of data to accept (default: 7 days)

    Returns:
        Most recent headcount data or None if not found
    """
    history_file = Path("data/processed/metrics_history.json")
    if not history_file.exists():
        return None

    with open(history_file, "r") as f:
        history = json.load(f)

    snapshots = history.get("snapshots", {})

    # Search backwards from today up to max_days_old
    for days_back in range(max_days_old + 1):
        target_date = (date.today() - timedelta(days=days_back)).isoformat()
        snapshot = snapshots.get(target_date)

        if snapshot and company_name in snapshot.get("headcounts", {}):
            headcount_data = snapshot["headcounts"][company_name]
            log(
                f"  ⏪ Using {days_back}-day-old headcount data for {company_name}: {headcount_data['headcount']:,}"
            )
            return {
                "current_headcount": headcount_data["headcount"],
                "data_date": headcount_data.get("data_date", ""),
                "source_urls": headcount_data.get("source_urls", []),
            }

    return None


def build_metrics_structure(
    stock_data: dict[str, dict[str, Any]],
    headcount_data: dict[str, dict[str, Any]],
    job_posting_data: dict[str, dict[str, Any]],
    ai_summary: str,
    indeed_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the complete metrics_latest.json structure.

    Args:
        stock_data: Stock price data for IT consultancies
        headcount_data: Headcount data for all companies
        job_posting_data: Job posting data for AI labs
        ai_summary: AI-generated market summary
        indeed_data: Indeed Job Postings index data from FRED

    Returns:
        Complete metrics structure ready for JSON serialization
    """
    # Initialize processors
    stock_processor = StockProcessor()
    headcount_processor = HeadcountProcessor()
    jobs_processor = JobsProcessor()
    badge_generator = BadgeGenerator()

    # Load baselines for change calculations
    baselines_data = load_baselines()
    has_baselines = baselines_data is not None

    # Build metadata
    metadata = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "collection_status": "success",
    }

    # Build low-end tier (IT consultancies)
    low_end_companies = [c["name"] for c in IT_CONSULTANCIES]

    # Populate headcount data for IT consultancies
    low_end_headcount_companies = {}

    for name in low_end_companies:
        # Try to get fresh data first, fallback to recent historical data (up to 7 days old)
        company_headcount_data = None
        if name in headcount_data:
            company_headcount_data = headcount_data[name]
        else:
            # Collection failed for this company, try to find recent data
            historical_headcount_data = find_recent_headcount_data(name, max_days_old=7)
            if historical_headcount_data:
                company_headcount_data = historical_headcount_data

        if company_headcount_data:
            current_headcount = company_headcount_data["current_headcount"]

            # Calculate changes if we have baselines
            if has_baselines:
                changes = calculate_headcount_changes(
                    current_headcount,
                    name,
                    baselines_data,
                    headcount_processor,
                    gemini_data=company_headcount_data,
                )
            else:
                changes = {}

            # Extract current period citation info
            current_source_url = ""
            current_notes = ""
            if "current" in company_headcount_data and isinstance(
                company_headcount_data["current"], dict
            ):
                current_source_url = company_headcount_data["current"].get(
                    "source_url", ""
                )
                current_notes = company_headcount_data["current"].get("notes", "")

            low_end_headcount_companies[name] = {
                "current": current_headcount,
                "data_date": company_headcount_data.get("data_date", ""),
                "source_url": current_source_url,
                "notes": current_notes,
                "source_urls": company_headcount_data.get("source_urls", []),
                "changes": changes,
            }

    # Calculate net headcount YoY percentage for low-end
    # Use baseline values from per-company changes for consistency with Gemini data
    total_current_headcount = sum(
        data["current"] for data in low_end_headcount_companies.values()
    )
    net_headcount_pct_yoy_low = None
    total_baseline_headcount = sum(
        data.get("changes", {}).get("1_year_ago", {}).get("baseline_headcount", 0) or 0
        for data in low_end_headcount_companies.values()
    )
    if total_baseline_headcount > 0:
        net_headcount_pct_yoy_low = (
            (total_current_headcount - total_baseline_headcount)
            / total_baseline_headcount
            * 100
        )

    # Calculate aggregate badge based on total average YoY percentage
    if net_headcount_pct_yoy_low is not None:
        low_end_aggregate_badge = badge_generator.get_headcount_badge(
            net_headcount_pct_yoy_low
        )
    else:
        low_end_aggregate_badge = "neutral"

    # Populate stock index data
    stock_index_companies = {}
    current_prices = {}
    for company_info in IT_CONSULTANCIES:
        name = company_info["name"]
        ticker = company_info["ticker"]
        if name in stock_data:
            current_price = stock_data[name]["current_price"]

            # Calculate per-stock changes
            change_30_day = None
            change_1_year = None

            if has_baselines:
                baseline_30d = baselines_data["baselines"].get("30_days_ago", {})
                baseline_30d_stocks = baseline_30d.get("stock_prices", {})
                if name in baseline_30d_stocks:
                    baseline_price_30d = baseline_30d_stocks[name]["price"]
                    change_30_day = round(
                        ((current_price - baseline_price_30d) / baseline_price_30d)
                        * 100,
                        2,
                    )

                baseline_1yr = baselines_data["baselines"].get("1_year_ago", {})
                baseline_1yr_stocks = baseline_1yr.get("stock_prices", {})
                if name in baseline_1yr_stocks:
                    baseline_price_1yr = baseline_1yr_stocks[name]["price"]
                    change_1_year = round(
                        ((current_price - baseline_price_1yr) / baseline_price_1yr)
                        * 100,
                        2,
                    )

            stock_index_companies[name] = {
                "ticker": ticker,
                "current_price": current_price,
                "weight": 1.0 / len(IT_CONSULTANCIES),  # Equal weights
                "change_30_day": change_30_day,
                "change_1_year": change_1_year,
            }
            current_prices[name] = current_price

    # Calculate stock index changes vs baselines
    stock_index_changes = {}
    stock_index_current_value = 100.0  # Default if calculation fails
    baseline_date_1yr = date.today() - timedelta(days=365)

    for baseline_name, days_ago in [("30_day", 30), ("1_year", 365)]:
        baseline_key = "30_days_ago" if baseline_name == "30_day" else "1_year_ago"
        baseline = baselines_data["baselines"].get(baseline_key, {})
        baseline_stocks = baseline.get("stock_prices", {})

        if baseline_stocks:
            # Extract baseline prices
            baseline_prices = {}
            for name in current_prices:
                if name in baseline_stocks:
                    baseline_prices[name] = baseline_stocks[name]["price"]

            # Calculate index if we have matching companies
            if len(baseline_prices) == len(current_prices):
                try:
                    current_index = stock_processor.calculate_index(
                        current_prices, baseline_prices
                    )
                    index_change = stock_processor.calculate_index_change(
                        current_index, 100.0
                    )
                    stock_index_changes[baseline_name] = round(index_change, 2)
                    # Store the actual current index value from 1-year calculation
                    if baseline_name == "1_year":
                        stock_index_current_value = round(current_index, 2)
                except ValueError:
                    stock_index_changes[baseline_name] = 0.0
            else:
                stock_index_changes[baseline_name] = 0.0
        else:
            stock_index_changes[baseline_name] = 0.0

    # Calculate aggregate badge for stock index based on 1-year performance
    stock_index_1yr_change = stock_index_changes.get("1_year", 0.0)
    stock_index_badge = headcount_processor.classify_change(stock_index_1yr_change)

    stock_index_structure = {
        "current_value": stock_index_current_value,
        "baseline_date": baseline_date_1yr.isoformat(),
        "changes": stock_index_changes,
        "companies": stock_index_companies,
        "aggregate_badge": stock_index_badge,
    }

    low_end = {
        "headcount": {
            "companies": low_end_headcount_companies,
            "aggregate_badge": low_end_aggregate_badge,
            "net_headcount_pct_yoy": net_headcount_pct_yoy_low,
        },
    }

    # Build medium-end tier (Big Tech)
    medium_end_companies = [c["name"] for c in BIG_TECH_COMPANIES]

    # Populate headcount data for Big Tech
    medium_end_headcount_companies = {}

    for name in medium_end_companies:
        # Try to get fresh data first, fallback to recent historical data (up to 7 days old)
        company_headcount_data = None
        if name in headcount_data:
            company_headcount_data = headcount_data[name]
        else:
            # Collection failed for this company, try to find recent data
            historical_headcount_data = find_recent_headcount_data(name, max_days_old=7)
            if historical_headcount_data:
                company_headcount_data = historical_headcount_data

        if company_headcount_data:
            current_headcount = company_headcount_data["current_headcount"]

            # Calculate changes if we have baselines
            if has_baselines:
                changes = calculate_headcount_changes(
                    current_headcount,
                    name,
                    baselines_data,
                    headcount_processor,
                    gemini_data=company_headcount_data,
                )
            else:
                changes = {}

            # Extract current period citation info
            current_source_url = ""
            current_notes = ""
            if "current" in company_headcount_data and isinstance(
                company_headcount_data["current"], dict
            ):
                current_source_url = company_headcount_data["current"].get(
                    "source_url", ""
                )
                current_notes = company_headcount_data["current"].get("notes", "")

            medium_end_headcount_companies[name] = {
                "current": current_headcount,
                "data_date": company_headcount_data.get("data_date", ""),
                "source_url": current_source_url,
                "notes": current_notes,
                "source_urls": company_headcount_data.get("source_urls", []),
                "changes": changes,
            }

    # Calculate net headcount YoY percentage for medium-end
    # Use baseline values from per-company changes for consistency with Gemini data
    total_current_headcount_med = sum(
        data["current"] for data in medium_end_headcount_companies.values()
    )
    net_headcount_pct_yoy_med = None
    total_baseline_headcount_med = sum(
        data.get("changes", {}).get("1_year_ago", {}).get("baseline_headcount", 0) or 0
        for data in medium_end_headcount_companies.values()
    )
    if total_baseline_headcount_med > 0:
        net_headcount_pct_yoy_med = (
            (total_current_headcount_med - total_baseline_headcount_med)
            / total_baseline_headcount_med
            * 100
        )

    # Calculate aggregate badge based on total average YoY percentage
    if net_headcount_pct_yoy_med is not None:
        medium_end_aggregate_badge = badge_generator.get_headcount_badge(
            net_headcount_pct_yoy_med
        )
    else:
        medium_end_aggregate_badge = "neutral"

    medium_end = {
        "headcount": {
            "companies": medium_end_headcount_companies,
            "aggregate_badge": medium_end_aggregate_badge,
            "net_headcount_pct_yoy": net_headcount_pct_yoy_med,
        }
    }

    # Build high-end tier (AI labs)
    high_end_companies = [c["name"] for c in AI_LABS]

    # Populate job posting data for AI labs
    # Note: We use history snapshots for job postings since Greenhouse doesn't provide historical data
    high_end_job_companies = {}

    for name in high_end_companies:
        # Try to get fresh data first, fallback to recent historical data (up to 7 days old)
        job_data = None
        if name in job_posting_data:
            job_data = job_posting_data[name]
        else:
            # Collection failed for this company, try to find recent data
            historical_job_data = find_recent_job_posting_data(name, max_days_old=7)
            if historical_job_data:
                job_data = historical_job_data

        if job_data:
            current_jobs = job_data["total_technical_jobs"]
            collection_date = job_data.get("collection_date", date.today().isoformat())
            changes = {}

            # Try to get historical data from baselines (1_year_ago = Dec 26, 2024)
            baseline_1yr = baselines_data["baselines"].get("1_year_ago", {})
            baseline_jobs = baseline_1yr.get("job_postings", {})

            if name in baseline_jobs:
                historical_jobs = baseline_jobs[name]["total_technical_jobs"]
                job_change = current_jobs - historical_jobs
                badge = jobs_processor.classify_change(job_change)
                changes["1_year_ago"] = {"value": job_change, "badge": badge}
            else:
                # No baseline data available for 1 year ago
                changes["1_year_ago"] = {"value": None, "badge": "neutral"}

            # Try to get historical snapshots from metrics_history.json for 30 days
            snapshot = load_history_snapshot(30)
            if snapshot and name in snapshot.get("job_postings", {}):
                historical_jobs = snapshot["job_postings"][name]["total_technical_jobs"]
                job_change = current_jobs - historical_jobs
                badge = jobs_processor.classify_change(job_change)
                changes["30_days_ago"] = {"value": job_change, "badge": badge}
            else:
                # No 30-day snapshot available
                changes["30_days_ago"] = {"value": None, "badge": "neutral"}

            high_end_job_companies[name] = {
                "current": current_jobs,
                "collection_date": collection_date,
                "source_url": job_data.get("source_url", ""),
                "changes": changes,
            }

    # Calculate net jobs YoY percentage and total change
    total_current_jobs = sum(
        data["current"] for data in high_end_job_companies.values()
    )

    net_change_pct_yoy = None
    total_job_change_yoy = 0
    if has_baselines:
        baseline_1yr = baselines_data["baselines"].get("1_year_ago", {})
        baseline_jobs = baseline_1yr.get("job_postings", {})

        if baseline_jobs:
            total_baseline_jobs = sum(
                baseline_jobs[name]["total_technical_jobs"]
                for name in baseline_jobs
                if name in high_end_job_companies
            )
            if total_baseline_jobs > 0:
                net_change_pct_yoy = (
                    (total_current_jobs - total_baseline_jobs)
                    / total_baseline_jobs
                    * 100
                )
                total_job_change_yoy = total_current_jobs - total_baseline_jobs

    # Calculate aggregate badge based on total YoY job change (absolute number)
    if total_job_change_yoy != 0:
        high_end_aggregate_badge = jobs_processor.classify_change(total_job_change_yoy)
    else:
        high_end_aggregate_badge = "neutral"

    high_end = {
        "job_postings": {
            "companies": high_end_job_companies,
            "aggregate_badge": high_end_aggregate_badge,
            "net_change_pct_yoy": net_change_pct_yoy,
        }
    }

    # Build Indeed Job Postings index
    fred_processor = FredProcessor()
    indeed_index_structure = None

    if indeed_data:
        indeed_current = indeed_data["current_value"]
        indeed_changes = {}

        for period_name in ["30_day", "1_year"]:
            baseline = indeed_data.get("baselines", {}).get(period_name)
            if baseline and baseline["value"] > 0:
                pct = fred_processor.calculate_percentage_change(
                    indeed_current, baseline["value"]
                )
                badge = fred_processor.classify_change(pct)
                indeed_changes[period_name] = {
                    "value": baseline["value"],
                    "pct": round(pct, 2),
                    "badge": badge,
                }
            else:
                indeed_changes[period_name] = {
                    "value": None,
                    "pct": None,
                    "badge": "neutral",
                }

        # Aggregate badge: use 1-year change if available, else neutral
        if indeed_changes.get("1_year", {}).get("pct") is not None:
            indeed_aggregate_badge = indeed_changes["1_year"]["badge"]
        else:
            indeed_aggregate_badge = "neutral"

        indeed_index_structure = {
            "current_value": indeed_current,
            "date": indeed_data["date"],
            "series_id": indeed_data["series_id"],
            "source_url": "https://fred.stlouisfed.org/series/IHLIDXUSTPSOFTDEVE",
            "changes": indeed_changes,
            "aggregate_badge": indeed_aggregate_badge,
        }

    result = {
        "metadata": metadata,
        "low_end": low_end,
        "medium_end": medium_end,
        "high_end": high_end,
        "stock_index": stock_index_structure,
        "ai_summary": ai_summary,
    }

    if indeed_index_structure:
        result["indeed_index"] = indeed_index_structure

    return result


def save_daily_snapshot(
    stock_data: dict[str, dict[str, Any]],
    headcount_data: dict[str, dict[str, Any]],
    job_posting_data: dict[str, dict[str, Any]],
    indeed_data: dict[str, Any] | None = None,
) -> None:
    """Save today's raw data as a snapshot in metrics_history.json.

    This creates a historical record for future change calculations.

    Args:
        stock_data: Stock price data for IT consultancies
        headcount_data: Headcount data for all companies
        job_posting_data: Job posting data for AI labs
        indeed_data: Indeed Job Postings index data from FRED
    """
    history_file = Path("data/processed/metrics_history.json")
    today = date.today().isoformat()

    # Load existing history or create new
    if history_file.exists():
        with open(history_file, "r") as f:
            history = json.load(f)
    else:
        history = {
            "metadata": {
                "description": "Daily snapshots of market data",
                "first_snapshot": today,
            },
            "snapshots": {},
        }

    # Create today's snapshot
    snapshot = {
        "date": today,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stock_prices": {},
        "headcounts": {},
        "job_postings": {},
    }

    # Save stock prices
    for company_name, data in stock_data.items():
        snapshot["stock_prices"][company_name] = {
            "price": data["current_price"],
            "ticker": data["ticker"],
        }

    # Save headcounts (including source_urls for 30-day citation tracking)
    for company_name, data in headcount_data.items():
        snapshot["headcounts"][company_name] = {
            "headcount": data["current_headcount"],
            "data_date": data.get("data_date", ""),
            "source_urls": data.get("source_urls", []),
        }

    # Save job postings
    for company_name, data in job_posting_data.items():
        snapshot["job_postings"][company_name] = {
            "total_technical_jobs": data["total_technical_jobs"],
            "collection_date": data.get("collection_date", ""),
        }

    # Save Indeed index
    if indeed_data:
        snapshot["indeed_index"] = {
            "value": indeed_data["current_value"],
            "date": indeed_data["date"],
        }

    # Add to history
    history["snapshots"][today] = snapshot
    history["metadata"]["last_updated"] = datetime.now(timezone.utc).isoformat()

    # Write back
    with open(history_file, "w") as f:
        json.dump(history, f, indent=2)

    log(f"  💾 Daily snapshot saved to {history_file}")


async def main_async():
    """Main async entry point for data collection."""
    global logger
    logger = setup_logging()

    # Load environment variables
    load_dotenv()

    log("🚀 Starting aredevscooked data collection...")
    log("=" * 60)

    # Initialize collectors
    stock_collector = StockCollector()
    log("✓ StockCollector initialized (yfinance)")

    try:
        gemini_collector = GeminiCollector()
        log("✓ GeminiCollector initialized")
    except ValueError as e:
        log(f"❌ Error: {e}")
        log("Make sure GEMINI_API_KEY is set in .env file")
        return 1

    try:
        fred_collector = FredCollector()
        log("✓ FredCollector initialized (FRED API)\n")
    except ValueError as e:
        log(f"⚠️  FredCollector not initialized: {e}")
        fred_collector = None

    # Calculate dates
    one_year_ago = date.today() - timedelta(days=365)

    # Collect stock data and Indeed data in parallel
    log("\n📊 Collecting stock price data (via yfinance)...")
    stock_data = await collect_all_stock_data(stock_collector, one_year_ago)
    log(f"  Collected {len(stock_data)}/7 companies")

    log("\n📈 Collecting Indeed Job Postings index (via FRED)...")
    indeed_data = None
    if fred_collector:
        indeed_data = await collect_indeed_data(fred_collector)
    else:
        log("  ⚠️  Skipped (no FRED_API_KEY)")

    log("\n👥 Collecting headcount data...")
    headcount_data = await collect_all_headcount_data(gemini_collector)
    log(f"  Collected {len(headcount_data)}/12 companies")

    log("\n🎯 Collecting job posting data...")
    job_posting_data = await collect_all_job_posting_data(gemini_collector)
    log(f"  Collected {len(job_posting_data)}/3 companies")

    # Build metrics structure first (needed for summary generation)
    log("\n🏗️  Building metrics structure...")
    metrics_without_summary = build_metrics_structure(
        stock_data, headcount_data, job_posting_data, "", indeed_data=indeed_data
    )

    log("\n📝 Generating AI summary...")
    ai_summary = gemini_collector.generate_summary(metrics_without_summary)

    # Rebuild with actual summary
    metrics = build_metrics_structure(
        stock_data,
        headcount_data,
        job_posting_data,
        ai_summary,
        indeed_data=indeed_data,
    )

    # Save daily snapshot to history
    log("\n💾 Saving daily snapshot...")
    save_daily_snapshot(
        stock_data, headcount_data, job_posting_data, indeed_data=indeed_data
    )

    # Write to file
    output_dir = Path("data/processed")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "metrics_latest.json"

    with open(output_file, "w") as f:
        json.dump(metrics, f, indent=2)

    log(f"\n✅ Metrics written to {output_file}")

    # Also copy to website/ directory for GitHub Pages deployment
    website_dir = Path("website")
    website_metrics_file = website_dir / "metrics_latest.json"

    with open(website_metrics_file, "w") as f:
        json.dump(metrics, f, indent=2)

    log(f"✅ Metrics copied to {website_metrics_file} (for GitHub Pages)")
    log("=" * 60)

    # Clean up collectors to release resources
    stock_collector.close()
    gemini_collector.close()
    if fred_collector:
        fred_collector.close()

    return 0


def main():
    """Synchronous entry point that runs async main."""
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
