#!/usr/bin/env python3
"""Backfill Anthropic technical-job baselines from archived Greenhouse boards.

The one-year job-posting comparison needs a dated, cited technical count near
today minus 365 days. Anthropic's jobs API was not archived in 2025, but the
board's ``/departments`` endpoint was captured roughly weekly and contains the
complete role list, so each capture can be replayed and classified with the
same Gemini rules used for the live count.

Usage:

    uv run python scripts/backfill_anthropic_job_baseline.py            # today - 365
    uv run python scripts/backfill_anthropic_job_baseline.py 2025-09-06 2025-09-17

``researched_job_change`` in run_collection.py only accepts a baseline within
seven days of the target, and that target moves forward daily, so backfilling
several dates keeps the comparison alive for weeks instead of two days.
"""

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from aredevscooked.collectors.gemini_collector import GeminiCollector
from aredevscooked.collectors.wayback_greenhouse import (
    DEPARTMENTS_URL,
    fetch_archived_json,
    find_capture,
    flatten_departments,
)

ROOT = Path(__file__).resolve().parents[1]
BASELINES_FILE = ROOT / "data/processed/job_posting_baselines.json"
EVIDENCE_DIR = ROOT / "website/evidence/job-postings"
BOARD_URL = DEPARTMENTS_URL.format(board="anthropic")
NOTES = (
    "Estimate from a complete archived board, classified by job title using the "
    "site’s technical-role categories. Ambiguous titles may affect the count; "
    "this is not an employer-reported technical total."
)


def build_baseline(
    collector: GeminiCollector, target: date, window_days: int = 7
) -> dict[str, Any]:
    """Classify the archived board nearest a target date into a baseline record.

    Args:
        collector: Gemini collector used for classification
        target: Date the baseline should represent
        window_days: How far from the target a capture may be

    Returns:
        Dict with the baseline ``record`` and the full ``evidence`` payload
    """
    capture = find_capture(BOARD_URL, target, window_days)
    jobs = flatten_departments(fetch_archived_json(capture["url"]))
    source_url = f"https://web.archive.org/web/{capture['timestamp']}/{BOARD_URL}"
    decisions = collector.classify_anthropic_jobs(jobs, source_url)
    technical = {row["id"] for row in decisions if row["technical"]}
    evidence = {
        "company": "Anthropic",
        "date": capture["date"],
        "source_url": source_url,
        "method": NOTES,
        "total_roles": len(jobs),
        "total_technical_jobs": len(technical),
        "jobs": [
            {
                "id": str(job["id"]),
                "title": job["title"],
                "department": job["departments"][0]["name"],
                "url": job["absolute_url"],
                "technical": job["id"] in technical,
            }
            for job in jobs
        ],
    }
    evidence_file = f"website/evidence/job-postings/anthropic-{capture['date']}.json"
    record = {
        "company": "Anthropic",
        "date": capture["date"],
        "source_url": source_url,
        "total_technical_jobs": len(technical),
        "is_estimate": True,
        "notes": NOTES,
        "evidence_file": evidence_file,
    }
    return {"record": record, "evidence": evidence, "evidence_file": evidence_file}


def upsert_record(baselines: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    """Replace any existing record for the same company and date, else append.

    A partial-archive record (``total_technical_jobs: null``) for the same
    company sitting closer to the target would otherwise keep winning the
    tie-break in ``researched_job_change``, so equal dates are overwritten.

    Args:
        baselines: Parsed job_posting_baselines.json contents
        record: Baseline record to store

    Returns:
        The updated baselines dict
    """
    records = [
        existing
        for existing in baselines.get("records", [])
        if not (
            existing.get("company") == record["company"]
            and existing.get("date") == record["date"]
        )
    ]
    records.append(record)
    baselines["records"] = records
    baselines["researched_on"] = datetime.now(timezone.utc).date().isoformat()
    return baselines


def main() -> None:
    load_dotenv()
    targets = [date.fromisoformat(arg) for arg in sys.argv[1:]] or [
        date.today() - timedelta(days=365)
    ]
    collector = GeminiCollector()
    baselines = json.loads(BASELINES_FILE.read_text())
    for target in targets:
        print(f"Backfilling Anthropic baseline near {target}...")
        result = build_baseline(collector, target)
        record = result["record"]
        (ROOT / result["evidence_file"]).write_text(
            json.dumps(result["evidence"], indent=2) + "\n"
        )
        upsert_record(baselines, record)
        print(
            f"  ✓ {record['date']}: {record['total_technical_jobs']} technical of "
            f"{result['evidence']['total_roles']} roles"
        )
    BASELINES_FILE.write_text(json.dumps(baselines, indent=2) + "\n")
    print(f"Wrote {BASELINES_FILE}")


if __name__ == "__main__":
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    main()
