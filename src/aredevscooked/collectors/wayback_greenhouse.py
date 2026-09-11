"""Read complete historical Greenhouse boards out of the Wayback Machine.

The live Greenhouse jobs API is only archived sporadically, but the
``/departments`` endpoint of the same board is captured roughly weekly and
carries the full role list (every department with its jobs), so it is the
reliable source for a historical, complete technical-job count. The paginated
HTML board (``job-boards.greenhouse.io/<board>``) is not usable for this: a
capture only contains the first 50 listings.
"""

import json
from datetime import date, datetime
from typing import Any

import requests

CDX_URL = "http://web.archive.org/cdx/search/cdx"
DEPARTMENTS_URL = "https://boards-api.greenhouse.io/v1/boards/{board}/departments"


def find_capture(url: str, target: date, window_days: int = 7) -> dict[str, str]:
    """Find the archived capture of a URL closest to a target date.

    Args:
        url: Original (unarchived) URL
        target: Date the baseline should represent
        window_days: Maximum distance in days a capture may be from the target

    Returns:
        Dict with the capture ``timestamp``, its ``date`` and the replay
        ``url`` that serves the original bytes (``id_`` modifier)

    Raises:
        LookupError: If no successful capture falls inside the window
    """
    response = requests.get(
        CDX_URL,
        params={
            "url": url,
            "output": "json",
            "filter": "statuscode:200",
            "from": _shift(target, -window_days),
            "to": _shift(target, window_days),
        },
        timeout=60,
    )
    response.raise_for_status()
    rows = response.json()
    captures = [row[1] for row in rows[1:]] if len(rows) > 1 else []
    if not captures:
        raise LookupError(
            f"No archived capture of {url} within {window_days} days of {target}"
        )
    best = min(captures, key=lambda ts: abs((_capture_date(ts) - target).days))
    return {
        "timestamp": best,
        "date": _capture_date(best).isoformat(),
        "url": f"https://web.archive.org/web/{best}id_/{url}",
    }


def _shift(target: date, days: int) -> str:
    return date.fromordinal(target.toordinal() + days).strftime("%Y%m%d")


def _capture_date(timestamp: str) -> date:
    return datetime.strptime(timestamp[:8], "%Y%m%d").date()


def fetch_archived_json(replay_url: str) -> Any:
    """Fetch an archived JSON payload, following the Wayback replay redirect."""
    response = requests.get(replay_url, timeout=60, headers={"Accept-Encoding": "gzip"})
    response.raise_for_status()
    return json.loads(response.text)


def flatten_departments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten a Greenhouse ``/departments`` payload into job records.

    Produces the same shape the live jobs feed yields, so the records can be
    handed straight to the classifier. Greenhouse nests child departments, and
    a job listed under both a parent and a child would otherwise be counted
    twice, so records are de-duplicated by ID.

    Args:
        payload: Parsed ``/departments`` response

    Returns:
        Job records with ``id``, ``title`` and ``departments``

    Raises:
        ValueError: If the payload carries no departments or no jobs
    """
    departments = payload.get("departments")
    if not isinstance(departments, list) or not departments:
        raise ValueError("Archived departments payload has no departments")
    jobs: dict[int, dict[str, Any]] = {}
    for department in departments:
        for job in department.get("jobs") or []:
            jobs[job["id"]] = {
                "id": job["id"],
                "title": job["title"],
                "departments": [{"name": department["name"].strip()}],
                "absolute_url": job.get("absolute_url", ""),
            }
    if not jobs:
        raise ValueError("Archived departments payload lists no jobs")
    return sorted(jobs.values(), key=lambda job: job["title"].lower())
