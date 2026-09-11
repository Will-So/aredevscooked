"""Tests for the Anthropic archived-board baseline backfill."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from backfill_anthropic_job_baseline import build_baseline, upsert_record  # noqa: E402


@pytest.fixture
def baselines():
    return {
        "researched_on": "2026-09-07",
        "records": [
            {"company": "OpenAI", "date": "2025-09-06", "total_technical_jobs": 198},
            {
                "company": "Anthropic",
                "date": "2025-09-06",
                "total_technical_jobs": None,
                "notes": "partial archive",
            },
        ],
    }


def test_upsert_record_replaces_a_partial_record_for_the_same_date(baselines):
    upsert_record(
        baselines,
        {"company": "Anthropic", "date": "2025-09-06", "total_technical_jobs": 120},
    )

    anthropic = [r for r in baselines["records"] if r["company"] == "Anthropic"]
    assert len(anthropic) == 1
    assert anthropic[0]["total_technical_jobs"] == 120
    assert len(baselines["records"]) == 2


def test_upsert_record_keeps_other_companies_and_dates(baselines):
    upsert_record(
        baselines,
        {"company": "Anthropic", "date": "2025-09-17", "total_technical_jobs": 130},
    )

    assert len(baselines["records"]) == 3
    assert baselines["researched_on"] != "2026-09-07"


def test_build_baseline_classifies_the_archived_board(monkeypatch):
    payload = {
        "departments": [
            {
                "id": 1,
                "name": "AI Research & Engineering",
                "jobs": [
                    {"id": 11, "title": "Research Engineer", "absolute_url": "u11"}
                ],
            },
            {
                "id": 2,
                "name": "Sales",
                "jobs": [
                    {"id": 21, "title": "Account Executive", "absolute_url": "u21"}
                ],
            },
        ]
    }
    monkeypatch.setattr(
        "backfill_anthropic_job_baseline.find_capture",
        lambda url, target, window_days=7: {
            "timestamp": "20250906013525",
            "date": "2025-09-06",
            "url": "https://replay",
        },
    )
    monkeypatch.setattr(
        "backfill_anthropic_job_baseline.fetch_archived_json", lambda url: payload
    )
    collector = _collector_classifying_ids({11})

    result = build_baseline(collector, None)

    assert result["record"]["total_technical_jobs"] == 1
    assert result["record"]["is_estimate"] is True
    assert result["record"]["date"] == "2025-09-06"
    assert result["evidence"]["total_roles"] == 2
    assert result["evidence"]["jobs"][0] == {
        "id": "21",
        "title": "Account Executive",
        "department": "Sales",
        "url": "u21",
        "technical": False,
    }
    assert (
        result["evidence_file"]
        == "website/evidence/job-postings/anthropic-2025-09-06.json"
    )


def _collector_classifying_ids(technical_ids):
    def classify(jobs, url):
        return [
            {"id": job["id"], "technical": job["id"] in technical_ids} for job in jobs
        ]

    return SimpleNamespace(classify_anthropic_jobs=classify)
