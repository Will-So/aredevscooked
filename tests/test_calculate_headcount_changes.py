import pytest

from scripts.run_collection import calculate_headcount_changes
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
