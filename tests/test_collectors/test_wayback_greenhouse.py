"""Tests for reading archived Greenhouse boards out of the Wayback Machine."""

from datetime import date
from types import SimpleNamespace

import pytest

from aredevscooked.collectors.wayback_greenhouse import (
    find_capture,
    flatten_departments,
)


@pytest.fixture
def departments_payload():
    return {
        "departments": [
            {
                "id": 1,
                "name": "AI Research & Engineering",
                "jobs": [
                    {"id": 11, "title": "Research Engineer", "absolute_url": "u11"},
                    {"id": 12, "title": "Software Engineer", "absolute_url": "u12"},
                ],
            },
            {
                "id": 2,
                "name": "Sales ",
                "jobs": [
                    {"id": 21, "title": "Account Executive", "absolute_url": "u21"}
                ],
            },
            {"id": 3, "name": "No Department", "jobs": []},
        ]
    }


def test_flatten_departments_returns_classifier_ready_records(departments_payload):
    jobs = flatten_departments(departments_payload)

    assert [job["id"] for job in jobs] == [21, 11, 12]
    assert jobs[0]["departments"] == [{"name": "Sales"}]
    assert jobs[1]["title"] == "Research Engineer"


def test_flatten_departments_deduplicates_jobs_in_nested_departments(
    departments_payload,
):
    departments_payload["departments"].append(
        {
            "id": 4,
            "name": "Research",
            "jobs": [{"id": 11, "title": "Research Engineer", "absolute_url": "u11"}],
        }
    )

    assert len(flatten_departments(departments_payload)) == 3


def test_flatten_departments_rejects_empty_board():
    with pytest.raises(ValueError, match="no jobs"):
        flatten_departments({"departments": [{"id": 1, "name": "Sales", "jobs": []}]})

    with pytest.raises(ValueError, match="no departments"):
        flatten_departments({"departments": []})


def test_find_capture_picks_the_closest_capture(monkeypatch):
    rows = [
        ["urlkey", "timestamp", "original", "mimetype", "statuscode", "digest", "len"],
        ["k", "20250903005349", "https://board", "application/json", "200", "d", "1"],
        ["k", "20250906013525", "https://board", "application/json", "200", "d", "1"],
        ["k", "20250917181657", "https://board", "application/json", "200", "d", "1"],
    ]
    monkeypatch.setattr(
        "aredevscooked.collectors.wayback_greenhouse.requests.get",
        lambda *args, **kwargs: _cdx_response(rows),
    )

    capture = find_capture("https://board", date(2025, 9, 7))

    assert capture["date"] == "2025-09-06"
    assert (
        capture["url"] == "https://web.archive.org/web/20250906013525id_/https://board"
    )


def test_find_capture_raises_when_the_window_is_empty(monkeypatch):
    monkeypatch.setattr(
        "aredevscooked.collectors.wayback_greenhouse.requests.get",
        lambda *args, **kwargs: _cdx_response([]),
    )

    with pytest.raises(LookupError, match="No archived capture"):
        find_capture("https://board", date(2025, 9, 7))


def _cdx_response(payload):
    return SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)
