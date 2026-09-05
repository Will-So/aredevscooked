"""Tests for orchestration script."""

import json
import pytest
from datetime import date, timedelta
from unittest.mock import Mock, patch
from scripts.run_collection import (
    HISTORY_30_DAY_TOLERANCE_DAYS,
    deepmind_long_term_change,
    collect_all_stock_data,
    collect_all_headcount_data,
    collect_all_job_posting_data,
    build_metrics_structure,
    find_recent_headcount_data,
    load_history_snapshot,
    load_same_day_headcount_data,
    load_same_day_job_posting_data,
    load_same_day_summary,
)


# Stock Data Collection Tests


@pytest.mark.parametrize("today,expected,label", [
    (date(2026, 9, 5), -66, True),
    (date(2027, 1, 6), -66, False),
    (date(2027, 2, 6), -14, False),
])
def test_deepmind_baseline_switches_to_rolling_year(mocker, today, expected, label):
    mocked_date = mocker.patch("scripts.run_collection.date", wraps=date)
    mocked_date.today.return_value = today
    snapshots = {
        "2026-01-06": {"job_postings": {"DeepMind": {"total_technical_jobs": 72}}},
        "2026-02-06": {"job_postings": {"DeepMind": {"total_technical_jobs": 20}}},
    }
    change = deepmind_long_term_change(6, snapshots)
    assert change["value"] == expected
    assert ("tooltip" in change) == label
    assert ("label" in change) == label


def test_deepmind_missing_baseline_does_not_invent_value():
    assert deepmind_long_term_change(6, {})["value"] is None


@pytest.mark.asyncio
async def test_collect_all_stock_data_returns_dict(mocker):
    """Should collect stock data for all IT consultancies."""
    mock_collector = mocker.Mock()
    mock_collector.collect_stock_data.return_value = {
        "company": "HCLTech",
        "ticker": "HCL.NS",
        "current_price": 1450.50,
        "price_1_year_ago": 1320.00,
    }

    result = await collect_all_stock_data(mock_collector, date(2024, 12, 26))

    assert isinstance(result, dict)
    assert len(result) == 7  # 7 IT consultancies
    assert "HCLTech" in result
    assert mock_collector.collect_stock_data.call_count == 7


@pytest.mark.asyncio
async def test_collect_all_stock_data_calls_collector_for_each_company(mocker):
    """Should call collector for each IT consultancy."""
    mock_collector = mocker.Mock()
    mock_collector.collect_stock_data.return_value = {
        "company": "HCLTech",
        "ticker": "HCLTECH.NS",
        "current_price": 1450.50,
        "price_1_year_ago": 1320.00,
    }

    one_year_ago = date(2024, 12, 26)
    await collect_all_stock_data(mock_collector, one_year_ago)

    # Verify called with correct company and ticker
    calls = mock_collector.collect_stock_data.call_args_list
    assert len(calls) == 7
    # Check first call
    assert calls[0][0][0] == "HCLTech"  # company_name
    assert calls[0][0][1] == "HCLTECH.NS"  # ticker
    assert calls[0][0][2] == one_year_ago  # date


@pytest.mark.asyncio
async def test_collect_all_stock_data_handles_errors(mocker, caplog):
    """Should handle errors gracefully and continue collecting."""
    mock_collector = mocker.Mock()
    # First call fails, rest succeed
    mock_collector.collect_stock_data.side_effect = [
        ValueError("API error"),
        {"company": "LTIMindtree", "current_price": 5600.0, "price_1_year_ago": 5200.0},
        {"company": "Cognizant", "current_price": 78.0, "price_1_year_ago": 75.0},
        {"company": "Infosys", "current_price": 1500.0, "price_1_year_ago": 1450.0},
        {"company": "TCS", "current_price": 3700.0, "price_1_year_ago": 3600.0},
        {
            "company": "Tech Mahindra",
            "current_price": 1150.0,
            "price_1_year_ago": 1200.0,
        },
        {"company": "Wipro", "current_price": 400.0, "price_1_year_ago": 420.0},
    ]

    result = await collect_all_stock_data(mock_collector, date(2024, 12, 26))

    # Should have 6 successful results (1 failed)
    assert len(result) == 6
    assert "HCLTech" not in result
    assert "LTIMindtree" in result


# Headcount Data Collection Tests


@pytest.mark.asyncio
async def test_collect_all_headcount_data_returns_dict(mocker):
    """Should collect headcount for all companies (IT + Big Tech)."""
    mock_collector = mocker.Mock()
    mock_collector.collect_headcount.return_value = {
        "company": "HCLTech",
        "current_headcount": 226640,
        "data_date": "2025-09-30",
    }
    mocker.patch("scripts.run_collection.load_same_day_headcount_data", return_value={})

    result = await collect_all_headcount_data(mock_collector)

    assert isinstance(result, dict)
    assert len(result) == 12  # 7 IT consultancies + 5 big tech
    assert "HCLTech" in result
    assert "Microsoft" in result
    assert mock_collector.collect_headcount.call_count == 12


@pytest.mark.asyncio
async def test_collect_all_headcount_data_calls_collector_for_each_company(mocker):
    """Should call collector for each company."""
    mock_collector = mocker.Mock()
    mock_collector.collect_headcount.return_value = {
        "company": "Microsoft",
        "current_headcount": 228000,
    }
    mocker.patch("scripts.run_collection.load_same_day_headcount_data", return_value={})

    await collect_all_headcount_data(mock_collector)

    # Verify called with correct companies
    calls = mock_collector.collect_headcount.call_args_list
    assert len(calls) == 12
    company_names = [call[0][0] for call in calls]
    assert "HCLTech" in company_names
    assert "Microsoft" in company_names


@pytest.mark.asyncio
async def test_collect_all_headcount_data_reuses_same_day_values(mocker):
    """Should skip Gemini calls when today's headcount data already exists."""
    mock_collector = mocker.Mock()
    same_day_data = {
        "HCLTech": {"current_headcount": 226640},
        "Microsoft": {"current_headcount": 228000},
    }

    mocker.patch(
        "scripts.run_collection.load_same_day_headcount_data",
        return_value=same_day_data,
    )

    result = await collect_all_headcount_data(mock_collector)

    assert result["HCLTech"]["current_headcount"] == 226640
    assert result["Microsoft"]["current_headcount"] == 228000
    assert mock_collector.collect_headcount.call_count == 10
    called_companies = [
        call[0][0] for call in mock_collector.collect_headcount.call_args_list
    ]
    assert "HCLTech" not in called_companies
    assert "Microsoft" not in called_companies


@pytest.mark.asyncio
async def test_collect_all_headcount_data_force_company_bypasses_cache(mocker):
    """force_companies should re-collect even when same-day data exists."""
    mock_collector = mocker.Mock()
    mock_collector.collect_headcount.return_value = {
        "current_headcount": 999,
        "data_date": "2026-05-20",
    }
    same_day_data = {
        "Meta": {"current_headcount": 69986},
        "Microsoft": {"current_headcount": 228000},
    }

    mocker.patch(
        "scripts.run_collection.load_same_day_headcount_data",
        return_value=same_day_data,
    )

    result = await collect_all_headcount_data(mock_collector, force_companies={"Meta"})

    called_companies = [
        call[0][0] for call in mock_collector.collect_headcount.call_args_list
    ]
    assert "Meta" in called_companies
    assert "Microsoft" not in called_companies
    assert result["Meta"]["current_headcount"] == 999


@pytest.mark.asyncio
async def test_collect_all_headcount_data_refresh_recollects_all(mocker):
    """refresh=True should ignore same-day cache and re-collect every company."""
    mock_collector = mocker.Mock()
    mock_collector.collect_headcount.return_value = {
        "current_headcount": 999,
        "data_date": "2026-05-20",
    }
    same_day_data = {
        "HCLTech": {"current_headcount": 226640},
        "Microsoft": {"current_headcount": 228000},
    }

    mock_loader = mocker.patch(
        "scripts.run_collection.load_same_day_headcount_data",
        return_value=same_day_data,
    )

    result = await collect_all_headcount_data(mock_collector, refresh=True)

    assert mock_collector.collect_headcount.call_count == 12
    mock_loader.assert_not_called()
    assert len(result) == 12


def test_find_recent_headcount_data_returns_most_recent(tmp_path, mocker):
    """Should return most recent headcount data from history."""
    history_file = tmp_path / "data" / "processed" / "metrics_history.json"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    today = date.today()
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)

    history_data = {
        "metadata": {"description": "Test history"},
        "snapshots": {
            two_days_ago.isoformat(): {
                "headcounts": {"Meta": {"headcount": 70000, "data_date": "2024-06-30"}}
            },
            yesterday.isoformat(): {
                "headcounts": {"Meta": {"headcount": 70799, "data_date": "2024-06-30"}}
            },
        },
    }

    import json

    with open(history_file, "w") as f:
        json.dump(history_data, f)

    mocker.patch("scripts.run_collection.Path", return_value=history_file)

    result = find_recent_headcount_data("Meta", max_days_old=7)

    assert result is not None
    assert result["current_headcount"] == 70799


def test_find_recent_headcount_data_returns_none_if_not_found(tmp_path, mocker):
    """Should return None if company not found in recent history."""
    history_file = tmp_path / "data" / "processed" / "metrics_history.json"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    today = date.today()
    yesterday = today - timedelta(days=1)

    history_data = {
        "metadata": {"description": "Test history"},
        "snapshots": {
            yesterday.isoformat(): {
                "headcounts": {
                    "HCLTech": {"headcount": 218621, "data_date": "2024-09-30"}
                }
            },
        },
    }

    import json

    with open(history_file, "w") as f:
        json.dump(history_data, f)

    mocker.patch("scripts.run_collection.Path", return_value=history_file)

    result = find_recent_headcount_data("Meta", max_days_old=7)

    assert result is None


def test_find_recent_headcount_data_returns_none_if_file_missing(tmp_path, mocker):
    """Should return None if history file doesn't exist."""
    history_file = tmp_path / "data" / "processed" / "metrics_history.json"

    mocker.patch("scripts.run_collection.Path", return_value=history_file)

    result = find_recent_headcount_data("Meta", max_days_old=7)

    assert result is None


def test_find_recent_headcount_data_respects_max_days_old(tmp_path, mocker):
    """Should not return data older than max_days_old."""
    history_file = tmp_path / "data" / "processed" / "metrics_history.json"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    today = date.today()
    eight_days_ago = today - timedelta(days=8)

    history_data = {
        "metadata": {"description": "Test history"},
        "snapshots": {
            eight_days_ago.isoformat(): {
                "headcounts": {"Meta": {"headcount": 70799, "data_date": "2024-06-30"}}
            },
        },
    }

    import json

    with open(history_file, "w") as f:
        json.dump(history_data, f)

    mocker.patch("scripts.run_collection.Path", return_value=history_file)

    result = find_recent_headcount_data("Meta", max_days_old=7)

    assert result is None


def test_load_same_day_headcount_data_reconstructs_payload(tmp_path, mocker):
    """Should rebuild Gemini-compatible headcount payloads from today's metrics file."""
    metrics_file = tmp_path / "data" / "processed" / "metrics_latest.json"
    metrics_file.parent.mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()
    metrics_data = {
        "metadata": {"last_updated": f"{today}T12:00:00+00:00"},
        "low_end": {
            "headcount": {
                "companies": {
                    "HCLTech": {
                        "current": 226640,
                        "data_date": "2026-03-01",
                        "source_url": "https://example.com/current",
                        "notes": "Current note",
                        "source_urls": ["https://example.com/current"],
                        "changes": {
                            "1_year_ago": {
                                "baseline_headcount": 220000,
                                "baseline_date": "2025-03-01",
                                "source_url": "https://example.com/1y",
                            },
                            "q1_2023": {
                                "baseline_headcount": 200000,
                                "baseline_date": "2023-03-31",
                                "source_url": "https://example.com/q1-2023",
                            },
                        },
                    }
                }
            }
        },
        "medium_end": {"headcount": {"companies": {}}},
    }

    with open(metrics_file, "w") as f:
        json.dump(metrics_data, f)

    mocker.patch("scripts.run_collection.Path", return_value=metrics_file)

    result = load_same_day_headcount_data()

    assert result["HCLTech"]["current_headcount"] == 226640
    assert result["HCLTech"]["current"]["notes"] == "Current note"
    assert result["HCLTech"]["one_year_ago"]["headcount"] == 220000
    assert result["HCLTech"]["q1_2023"]["headcount"] == 200000


def test_load_same_day_headcount_data_ignores_stale_metrics(tmp_path, mocker):
    """Should not reuse metrics from an earlier day."""
    metrics_file = tmp_path / "data" / "processed" / "metrics_latest.json"
    metrics_file.parent.mkdir(parents=True, exist_ok=True)

    stale_day = (date.today() - timedelta(days=1)).isoformat()
    metrics_data = {
        "metadata": {"last_updated": f"{stale_day}T12:00:00+00:00"},
        "low_end": {"headcount": {"companies": {"HCLTech": {"current": 226640}}}},
        "medium_end": {"headcount": {"companies": {}}},
    }

    with open(metrics_file, "w") as f:
        json.dump(metrics_data, f)

    mocker.patch("scripts.run_collection.Path", return_value=metrics_file)

    result = load_same_day_headcount_data()

    assert result == {}


def test_load_same_day_headcount_data_accepts_same_local_day_from_utc_timestamp(
    tmp_path, mocker
):
    """Should reuse data when UTC date rolls over but local date is still the same day."""
    metrics_file = tmp_path / "data" / "processed" / "metrics_latest.json"
    metrics_file.parent.mkdir(parents=True, exist_ok=True)

    metrics_data = {
        "metadata": {"last_updated": "2026-03-13T04:25:52+00:00"},
        "low_end": {"headcount": {"companies": {"HCLTech": {"current": 226640}}}},
        "medium_end": {"headcount": {"companies": {}}},
    }

    with open(metrics_file, "w") as f:
        json.dump(metrics_data, f)

    class FakeDate:
        @classmethod
        def today(cls):
            return __import__("datetime").date(2026, 3, 12)

    mocker.patch("scripts.run_collection.Path", return_value=metrics_file)
    mocker.patch("scripts.run_collection.date", FakeDate)

    result = load_same_day_headcount_data()

    assert result["HCLTech"]["current_headcount"] == 226640


# Job Posting Data Collection Tests


@pytest.mark.asyncio
async def test_collect_all_job_posting_data_returns_dict(mocker):
    """Should collect job postings for all AI labs."""
    mock_collector = mocker.Mock()
    mock_collector.collect_job_postings.return_value = {
        "company": "DeepMind",
        "total_technical_jobs": 45,
    }
    mocker.patch(
        "scripts.run_collection.load_same_day_job_posting_data", return_value={}
    )

    result = await collect_all_job_posting_data(mock_collector)

    assert isinstance(result, dict)
    assert len(result) == 3  # 3 AI labs
    assert "DeepMind" in result
    assert mock_collector.collect_job_postings.call_count == 3


@pytest.mark.asyncio
async def test_collect_all_job_posting_data_calls_collector_for_each_lab(mocker):
    """Should call collector for each AI lab with jobs URL."""
    mock_collector = mocker.Mock()
    mock_collector.collect_job_postings.return_value = {
        "company": "Anthropic",
        "total_technical_jobs": 35,
    }
    mocker.patch(
        "scripts.run_collection.load_same_day_job_posting_data", return_value={}
    )

    await collect_all_job_posting_data(mock_collector)

    # Verify called with correct company and jobs URL
    calls = mock_collector.collect_job_postings.call_args_list
    assert len(calls) == 3
    # Check that jobs URLs are passed
    jobs_urls = [call[0][1] for call in calls]
    assert any("greenhouse.io/deepmind" in url for url in jobs_urls)
    assert any("anthropic.com/jobs" in url for url in jobs_urls)
    assert any("openai.com/careers" in url for url in jobs_urls)


@pytest.mark.asyncio
async def test_collect_all_job_posting_data_reuses_same_day_values(mocker):
    """Should skip Gemini calls when today's job posting data already exists."""
    mock_collector = mocker.Mock()
    same_day_data = {
        "DeepMind": {"total_technical_jobs": 45},
        "Anthropic": {"total_technical_jobs": 35},
    }

    mocker.patch(
        "scripts.run_collection.load_same_day_job_posting_data",
        return_value=same_day_data,
    )

    result = await collect_all_job_posting_data(mock_collector)

    assert result["DeepMind"]["total_technical_jobs"] == 45
    assert result["Anthropic"]["total_technical_jobs"] == 35
    assert mock_collector.collect_job_postings.call_count == 1
    called_companies = [
        call[0][0] for call in mock_collector.collect_job_postings.call_args_list
    ]
    assert "DeepMind" not in called_companies
    assert "Anthropic" not in called_companies


@pytest.mark.asyncio
async def test_collect_all_job_posting_data_refresh_recollects_all(mocker):
    """refresh=True should ignore same-day cache and re-collect every lab."""
    mock_collector = mocker.Mock()
    mock_collector.collect_job_postings.return_value = {
        "company": "DeepMind",
        "total_technical_jobs": 45,
    }
    same_day_data = {
        "DeepMind": {"total_technical_jobs": 45},
        "Anthropic": {"total_technical_jobs": 35},
    }

    mock_loader = mocker.patch(
        "scripts.run_collection.load_same_day_job_posting_data",
        return_value=same_day_data,
    )

    result = await collect_all_job_posting_data(mock_collector, refresh=True)

    assert mock_collector.collect_job_postings.call_count == 3
    mock_loader.assert_not_called()
    assert len(result) == 3


def test_load_same_day_job_posting_data_reconstructs_payload(tmp_path, mocker):
    """Should rebuild job posting payloads from today's metrics file."""
    metrics_file = tmp_path / "data" / "processed" / "metrics_latest.json"
    metrics_file.parent.mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()
    metrics_data = {
        "metadata": {"last_updated": f"{today}T12:00:00+00:00"},
        "high_end": {
            "job_postings": {
                "companies": {
                    "DeepMind": {
                        "current": 45,
                        "collection_date": "2026-03-12",
                        "source_url": "https://example.com/jobs",
                    }
                }
            }
        },
    }

    with open(metrics_file, "w") as f:
        json.dump(metrics_data, f)

    mocker.patch("scripts.run_collection.Path", return_value=metrics_file)

    result = load_same_day_job_posting_data()

    assert result["DeepMind"]["total_technical_jobs"] == 45
    assert result["DeepMind"]["collection_date"] == "2026-03-12"
    assert result["DeepMind"]["source_url"] == "https://example.com/jobs"


def test_load_same_day_job_posting_data_accepts_same_local_day_from_utc_timestamp(
    tmp_path, mocker
):
    """Should reuse job postings when UTC date rolls over but local date is still the same day."""
    metrics_file = tmp_path / "data" / "processed" / "metrics_latest.json"
    metrics_file.parent.mkdir(parents=True, exist_ok=True)

    metrics_data = {
        "metadata": {"last_updated": "2026-03-13T04:25:52+00:00"},
        "high_end": {"job_postings": {"companies": {"DeepMind": {"current": 45}}}},
    }

    with open(metrics_file, "w") as f:
        json.dump(metrics_data, f)

    class FakeDate:
        @classmethod
        def today(cls):
            return date(2026, 3, 12)

    mocker.patch("scripts.run_collection.Path", return_value=metrics_file)
    mocker.patch("scripts.run_collection.date", FakeDate)

    result = load_same_day_job_posting_data()

    assert result["DeepMind"]["total_technical_jobs"] == 45


def test_load_same_day_summary_returns_summary(tmp_path, mocker):
    """Should return today's ai_summary from the metrics file."""
    metrics_file = tmp_path / "data" / "processed" / "metrics_latest.json"
    metrics_file.parent.mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()
    metrics_data = {
        "metadata": {"last_updated": f"{today}T12:00:00+00:00"},
        "ai_summary": "Devs are cooked. But at least the coffee is hot.",
    }

    with open(metrics_file, "w") as f:
        json.dump(metrics_data, f)

    mocker.patch("scripts.run_collection.Path", return_value=metrics_file)

    result = load_same_day_summary()

    assert result == "Devs are cooked. But at least the coffee is hot."


def test_load_same_day_summary_ignores_stale_metrics(tmp_path, mocker):
    """Should not reuse a summary from an earlier day."""
    metrics_file = tmp_path / "data" / "processed" / "metrics_latest.json"
    metrics_file.parent.mkdir(parents=True, exist_ok=True)

    stale_day = (date.today() - timedelta(days=1)).isoformat()
    metrics_data = {
        "metadata": {"last_updated": f"{stale_day}T12:00:00+00:00"},
        "ai_summary": "Yesterday's joke.",
    }

    with open(metrics_file, "w") as f:
        json.dump(metrics_data, f)

    mocker.patch("scripts.run_collection.Path", return_value=metrics_file)

    result = load_same_day_summary()

    assert result is None


def test_load_same_day_summary_returns_none_when_empty(tmp_path, mocker):
    """Should return None when today's metrics has no ai_summary."""
    metrics_file = tmp_path / "data" / "processed" / "metrics_latest.json"
    metrics_file.parent.mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()
    metrics_data = {
        "metadata": {"last_updated": f"{today}T12:00:00+00:00"},
        "ai_summary": "",
    }

    with open(metrics_file, "w") as f:
        json.dump(metrics_data, f)

    mocker.patch("scripts.run_collection.Path", return_value=metrics_file)

    result = load_same_day_summary()

    assert result is None


# Metrics Structure Building Tests


def test_build_metrics_structure_returns_complete_structure(mocker):
    """Should build complete metrics_latest.json structure."""
    mock_stock_data = {
        "HCLTech": {"current_price": 1450.50, "price_1_year_ago": 1320.00}
    }
    mock_headcount_data = {"HCLTech": {"current_headcount": 226640}}
    mock_job_data = {"DeepMind": {"total_technical_jobs": 45}}

    result = build_metrics_structure(
        stock_data=mock_stock_data,
        headcount_data=mock_headcount_data,
        job_posting_data=mock_job_data,
        ai_summary="Test summary",
    )

    assert isinstance(result, dict)
    assert "metadata" in result
    assert "low_end" in result
    assert "medium_end" in result
    assert "high_end" in result
    assert "ai_summary" in result


def test_build_metrics_structure_includes_metadata(mocker):
    """Should include metadata with timestamp."""
    result = build_metrics_structure(
        stock_data={}, headcount_data={}, job_posting_data={}, ai_summary=""
    )

    assert "last_updated" in result["metadata"]
    assert "collection_status" in result["metadata"]
    assert result["metadata"]["collection_status"] == "success"


def test_build_metrics_structure_low_end_tier(mocker):
    """Should build low-end tier with headcount."""
    mock_stock_data = {
        "HCLTech": {"current_price": 1450.50, "price_1_year_ago": 1320.00}
    }
    mock_headcount_data = {"HCLTech": {"current_headcount": 226640}}

    result = build_metrics_structure(
        stock_data=mock_stock_data,
        headcount_data=mock_headcount_data,
        job_posting_data={},
        ai_summary="",
    )

    assert "headcount" in result["low_end"]
    assert "stock_index" in result  # stock_index is at top level
    assert "companies" in result["low_end"]["headcount"]
    assert "aggregate_badge" in result["low_end"]["headcount"]


def test_build_metrics_structure_medium_end_tier(mocker):
    """Should build medium-end tier with headcount."""
    mock_headcount_data = {"Microsoft": {"current_headcount": 228000}}

    result = build_metrics_structure(
        stock_data={},
        headcount_data=mock_headcount_data,
        job_posting_data={},
        ai_summary="",
    )

    assert "headcount" in result["medium_end"]
    assert "companies" in result["medium_end"]["headcount"]
    assert "aggregate_badge" in result["medium_end"]["headcount"]


def test_build_metrics_structure_high_end_tier(mocker):
    """Should build high-end tier with job postings."""
    mock_job_data = {"DeepMind": {"total_technical_jobs": 45}}

    result = build_metrics_structure(
        stock_data={},
        headcount_data={},
        job_posting_data=mock_job_data,
        ai_summary="",
    )

    assert "job_postings" in result["high_end"]
    assert "companies" in result["high_end"]["job_postings"]
    assert "aggregate_badge" in result["high_end"]["job_postings"]


# Indeed Index Tests


def test_build_metrics_structure_includes_indeed_index(mocker):
    """Should include indeed_index when indeed_data is provided, normalized to 1yr ago = 100."""
    indeed_data = {
        "current_value": 85.23,
        "date": "2026-03-01",
        "series_id": "IHLIDXUSTPSOFTDEVE",
        "baselines": {
            "30_day": {"date": "2026-02-01", "value": 80.0},
            "1_year": {"date": "2025-03-05", "value": 90.0},
            "q1_2023": {"date": "2023-03-31", "value": 100.0},
        },
    }

    result = build_metrics_structure(
        stock_data={},
        headcount_data={},
        job_posting_data={},
        ai_summary="",
        indeed_data=indeed_data,
    )

    assert "indeed_index" in result
    # Normalized: (85.23 / 90.0) * 100 = 94.7
    assert result["indeed_index"]["current_value"] == round((85.23 / 90.0) * 100, 2)
    assert result["indeed_index"]["date"] == "2026-03-01"
    assert result["indeed_index"]["series_id"] == "IHLIDXUSTPSOFTDEVE"
    assert "aggregate_badge" in result["indeed_index"]
    assert "changes" in result["indeed_index"]
    assert "source_url" in result["indeed_index"]
    changes = result["indeed_index"]["changes"]
    assert changes["30_day"]["pct"] is not None
    assert changes["1_year"]["pct"] is not None
    assert changes["q1_2023"]["pct"] is not None


def test_build_metrics_structure_without_indeed_data(mocker):
    """Should not include indeed_index when indeed_data is None."""
    result = build_metrics_structure(
        stock_data={},
        headcount_data={},
        job_posting_data={},
        ai_summary="",
        indeed_data=None,
    )

    assert "indeed_index" not in result


def test_build_metrics_structure_indeed_changes_default_neutral(mocker):
    """Indeed changes should default to neutral when no baselines exist."""
    indeed_data = {
        "current_value": 85.23,
        "date": "2026-03-01",
        "series_id": "IHLIDXUSTPSOFTDEVE",
        "baselines": {"30_day": None, "1_year": None, "q1_2023": None},
    }

    result = build_metrics_structure(
        stock_data={},
        headcount_data={},
        job_posting_data={},
        ai_summary="",
        indeed_data=indeed_data,
    )

    changes = result["indeed_index"]["changes"]
    assert changes["30_day"]["badge"] == "neutral"
    assert changes["1_year"]["badge"] == "neutral"
    assert changes["q1_2023"]["badge"] == "neutral"
    assert result["indeed_index"]["aggregate_badge"] == "neutral"
    # When no 1yr baseline, current_value falls back to raw value
    assert result["indeed_index"]["current_value"] == 85.23


@pytest.fixture
def history_file(tmp_path, monkeypatch):
    """Create a temporary metrics_history.json with known snapshots."""

    today = date.today()
    snapshots = {}
    # Only put data at exactly 30 days ago - 2 days (i.e., 32 days ago)
    nearby_date = (today - timedelta(days=32)).isoformat()
    snapshots[nearby_date] = {"job_postings": {"OpenAI": {"total_technical_jobs": 100}}}
    # Also put data at exactly 30 days ago
    exact_date = (today - timedelta(days=30)).isoformat()
    snapshots[exact_date] = {"job_postings": {"OpenAI": {"total_technical_jobs": 120}}}

    history = {"snapshots": snapshots}
    history_path = tmp_path / "data" / "processed"
    history_path.mkdir(parents=True)
    with open(history_path / "metrics_history.json", "w") as f:
        json.dump(history, f)

    monkeypatch.chdir(tmp_path)
    return snapshots


def test_load_history_snapshot_exact_match(history_file):
    snapshot = load_history_snapshot(30)
    assert snapshot is not None
    assert snapshot["job_postings"]["OpenAI"]["total_technical_jobs"] == 120


def test_load_history_snapshot_no_exact_match_without_tolerance(history_file):
    snapshot = load_history_snapshot(28)
    assert snapshot is None


def test_load_history_snapshot_tolerance_finds_nearby(history_file):
    # 28 days ago has no data, but 30 days ago does (offset=2), within tolerance=5
    snapshot = load_history_snapshot(28, tolerance_days=5)
    assert snapshot is not None
    assert snapshot["job_postings"]["OpenAI"]["total_technical_jobs"] == 120


def test_load_history_snapshot_tolerance_prefers_closest(history_file):
    # 31 days ago: nearest is 30 (offset=1) not 32 (offset=1 the other way)
    # Actually both are offset=1, but 30 is checked first (minus offset)
    # For 30 days ago exact, tolerance should still return exact
    snapshot = load_history_snapshot(30, tolerance_days=5)
    assert snapshot["job_postings"]["OpenAI"]["total_technical_jobs"] == 120


@pytest.mark.parametrize("age,accepted", [(46, True), (51, True), (52, False), (8, False)])
def test_30_day_history_outage_window(age, accepted):
    snapshot = {"job_postings": {"OpenAI": {"total_technical_jobs": 100}}}
    snapshots = {(date.today() - timedelta(days=age)).isoformat(): snapshot}
    result = load_history_snapshot(
        30,
        tolerance_days=HISTORY_30_DAY_TOLERANCE_DAYS,
        preloaded_snapshots=snapshots,
    )
    assert result == (snapshot if accepted else None)


def test_load_history_snapshot_tolerance_too_small(history_file):
    # 25 days ago, nearest data is 30 days ago (5 days away), tolerance=3 won't reach
    snapshot = load_history_snapshot(25, tolerance_days=3)
    assert snapshot is None


def test_load_history_snapshot_validate_skips_empty(tmp_path, monkeypatch):
    """Snapshot at exact date has empty job_postings; validate skips it and finds nearby."""
    today = date.today()
    exact_date = (today - timedelta(days=30)).isoformat()
    nearby_date = (today - timedelta(days=28)).isoformat()
    snapshots = {
        exact_date: {"job_postings": {}},
        nearby_date: {"job_postings": {"OpenAI": {"total_technical_jobs": 200}}},
    }
    history = {"snapshots": snapshots}
    history_path = tmp_path / "data" / "processed"
    history_path.mkdir(parents=True)
    with open(history_path / "metrics_history.json", "w") as f:
        json.dump(history, f)
    monkeypatch.chdir(tmp_path)

    snapshot = load_history_snapshot(
        30,
        tolerance_days=5,
        validate=lambda s: "OpenAI" in s.get("job_postings", {}),
    )
    assert snapshot is not None
    assert snapshot["job_postings"]["OpenAI"]["total_technical_jobs"] == 200


def test_load_history_snapshot_validate_without_tolerance(tmp_path, monkeypatch):
    """With tolerance_days=0, validate still rejects empty snapshots."""
    today = date.today()
    exact_date = (today - timedelta(days=30)).isoformat()
    snapshots = {exact_date: {"job_postings": {}}}
    history = {"snapshots": snapshots}
    history_path = tmp_path / "data" / "processed"
    history_path.mkdir(parents=True)
    with open(history_path / "metrics_history.json", "w") as f:
        json.dump(history, f)
    monkeypatch.chdir(tmp_path)

    snapshot = load_history_snapshot(
        30,
        validate=lambda s: "OpenAI" in s.get("job_postings", {}),
    )
    assert snapshot is None
