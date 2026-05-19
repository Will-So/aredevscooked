from unittest.mock import patch
from datetime import date, timedelta

import pytest

from scripts.run_collection import (
    calculate_headcount_changes,
    load_history_snapshot,
    load_all_snapshots,
    save_daily_snapshot,
)
from aredevscooked.processors.headcount_processor import HeadcountProcessor


@pytest.fixture
def headcount_processor():
    return HeadcountProcessor()


@pytest.fixture
def baselines_data():
    return {
        "baselines": {
            "1_year_ago": {"headcounts": {}},
            "q1_2023": {"headcounts": {}},
        }
    }


@pytest.fixture
def gemini_data():
    return {
        "one_year_ago": {
            "headcount": 350000,
            "source_url": "https://example.com",
            "as_of_date": "2025-03-18",
        },
        "q1_2023": {
            "headcount": 340000,
            "source_url": "https://example.com/q1",
            "as_of_date": "2023-03-31",
        },
    }


def test_30d_with_history_snapshot(headcount_processor, baselines_data, gemini_data):
    snapshot = {
        "date": "2026-02-16",
        "headcounts": {
            "Amazon": {"headcount": 320000, "data_date": "2026-02-16"},
        },
    }

    changes = calculate_headcount_changes(
        current=319900,
        company_name="Amazon",
        baselines_data=baselines_data,
        headcount_processor=headcount_processor,
        gemini_data=gemini_data,
        history_snapshot_30d=snapshot,
    )

    assert changes["30_days_ago"]["value"] == 319900 - 320000
    assert changes["30_days_ago"]["pct"] == round((319900 - 320000) / 320000 * 100, 2)
    assert changes["30_days_ago"]["baseline_headcount"] == 320000
    assert changes["30_days_ago"]["baseline_date"] == "2026-02-16"
    assert changes["30_days_ago"]["badge"] == "neutral"


def test_30d_without_snapshot(headcount_processor, baselines_data, gemini_data):
    changes = calculate_headcount_changes(
        current=319900,
        company_name="Amazon",
        baselines_data=baselines_data,
        headcount_processor=headcount_processor,
        gemini_data=gemini_data,
        history_snapshot_30d=None,
    )

    assert changes["30_days_ago"]["value"] is None
    assert changes["30_days_ago"]["pct"] is None
    assert changes["30_days_ago"]["badge"] == "neutral"


def test_30d_company_missing_from_snapshot(
    headcount_processor, baselines_data, gemini_data
):
    snapshot = {
        "date": "2026-02-16",
        "headcounts": {
            "Google": {"headcount": 180000, "data_date": "2026-02-16"},
        },
    }

    changes = calculate_headcount_changes(
        current=319900,
        company_name="Amazon",
        baselines_data=baselines_data,
        headcount_processor=headcount_processor,
        gemini_data=gemini_data,
        history_snapshot_30d=snapshot,
    )

    assert changes["30_days_ago"]["value"] is None
    assert changes["30_days_ago"]["pct"] is None


def test_1yr_and_q1_still_use_gemini(headcount_processor, baselines_data, gemini_data):
    changes = calculate_headcount_changes(
        current=319900,
        company_name="Amazon",
        baselines_data=baselines_data,
        headcount_processor=headcount_processor,
        gemini_data=gemini_data,
    )

    assert changes["1_year_ago"]["baseline_headcount"] == 350000
    assert changes["1_year_ago"]["baseline_date"] == "2025-03-18"
    assert changes["q1_2023"]["baseline_headcount"] == 340000


def test_per_company_snapshot_finds_company_in_adjacent_date():
    """When the closest snapshot is missing a company, validate finds it in an adjacent one."""
    target = date.today() - timedelta(days=30)
    day_before = (target - timedelta(days=1)).isoformat()
    target_str = target.isoformat()

    preloaded = {
        target_str: {
            "date": target_str,
            "headcounts": {
                "Google": {"headcount": 180000},
            },
        },
        day_before: {
            "date": day_before,
            "headcounts": {
                "Google": {"headcount": 180000},
                "Amazon": {"headcount": 320000},
            },
        },
    }

    result = load_history_snapshot(
        30,
        tolerance_days=5,
        validate=lambda s, n="Amazon": n in s.get("headcounts", {}),
        preloaded_snapshots=preloaded,
    )

    assert result is not None
    assert "Amazon" in result["headcounts"]
    assert result["date"] == day_before


def test_per_company_snapshot_returns_none_when_company_missing_everywhere():
    target = date.today() - timedelta(days=30)
    target_str = target.isoformat()

    preloaded = {
        target_str: {
            "date": target_str,
            "headcounts": {
                "Google": {"headcount": 180000},
            },
        },
    }

    result = load_history_snapshot(
        30,
        tolerance_days=5,
        validate=lambda s, n="Amazon": n in s.get("headcounts", {}),
        preloaded_snapshots=preloaded,
    )

    assert result is None


def test_preloaded_snapshots_skips_file_read():
    preloaded = {}

    result = load_history_snapshot(
        30,
        tolerance_days=0,
        preloaded_snapshots=preloaded,
    )

    assert result is None


def test_30d_gemini_takes_priority_over_history(headcount_processor, baselines_data):
    """Gemini's own 30_days_ago estimate should take priority over the history snapshot."""
    gemini_data_with_30d = {
        "one_year_ago": {
            "headcount": 350000,
            "source_url": "",
            "as_of_date": "2025-03-18",
        },
        "q1_2023": {"headcount": 340000, "source_url": "", "as_of_date": "2023-03-31"},
        "30_days_ago": {
            "headcount": 315000,
            "as_of_date": "2026-04-19",
            "source_url": "https://example.com/30d",
        },
    }
    history_snapshot = {
        "date": "2026-04-19",
        "headcounts": {
            "Amazon": {"headcount": 293000, "data_date": "2026-04-19"},
        },
    }

    changes = calculate_headcount_changes(
        current=319900,
        company_name="Amazon",
        baselines_data=baselines_data,
        headcount_processor=headcount_processor,
        gemini_data=gemini_data_with_30d,
        history_snapshot_30d=history_snapshot,
    )

    assert changes["30_days_ago"]["baseline_headcount"] == 315000
    assert changes["30_days_ago"]["source_url"] == "https://example.com/30d"
    assert changes["30_days_ago"]["baseline_date"] == "2026-04-19"


def test_30d_change_exceeding_threshold_returns_null(
    headcount_processor, baselines_data, gemini_data
):
    """A 30-day change exceeding max_30day_change_pct (10%) should be treated as unreliable."""
    snapshot = {
        "date": "2026-02-16",
        "headcounts": {
            "Amazon": {"headcount": 400000, "data_date": "2026-02-16"},
        },
    }

    changes = calculate_headcount_changes(
        current=319900,
        company_name="Amazon",
        baselines_data=baselines_data,
        headcount_processor=headcount_processor,
        gemini_data=gemini_data,
        history_snapshot_30d=snapshot,
    )

    assert changes["30_days_ago"]["value"] is None
    assert changes["30_days_ago"]["pct"] is None
    assert changes["30_days_ago"]["badge"] == "neutral"


def test_30d_change_within_threshold_is_kept(
    headcount_processor, baselines_data, gemini_data
):
    """A 30-day change within ±10% should be kept normally."""
    snapshot = {
        "date": "2026-02-16",
        "headcounts": {
            "Amazon": {"headcount": 310000, "data_date": "2026-02-16"},
        },
    }

    changes = calculate_headcount_changes(
        current=319900,
        company_name="Amazon",
        baselines_data=baselines_data,
        headcount_processor=headcount_processor,
        gemini_data=gemini_data,
        history_snapshot_30d=snapshot,
    )

    assert changes["30_days_ago"]["value"] is not None
    assert changes["30_days_ago"]["pct"] is not None


def test_save_daily_snapshot_stores_confidence(tmp_path, monkeypatch):
    """save_daily_snapshot should store the confidence field in headcount snapshots."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "processed").mkdir(parents=True)

    headcount_data = {
        "Meta": {
            "current_headcount": 78165,
            "data_date": "2026-03-25",
            "source_urls": ["https://example.com"],
            "confidence": "high",
        },
        "Amazon": {
            "current_headcount": 320000,
            "data_date": "2026-03-25",
            "source_urls": [],
        },
    }

    save_daily_snapshot(
        stock_data={},
        headcount_data=headcount_data,
        job_posting_data={},
    )

    import json

    with open(tmp_path / "data" / "processed" / "metrics_history.json") as f:
        history = json.load(f)

    today = date.today().isoformat()
    snapshot = history["snapshots"][today]
    assert snapshot["headcounts"]["Meta"]["confidence"] == "high"
    assert snapshot["headcounts"]["Amazon"]["confidence"] == "unknown"
