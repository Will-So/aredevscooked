#!/usr/bin/env python3
"""Recompute the AI-lab job postings section from already-collected counts.

Run after backfilling job-posting baselines so the published metrics pick up a
newly available comparison without re-running collection (which would spend a
full round of Gemini and market-data calls).

    uv run python scripts/refresh_job_postings_metrics.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_collection import build_job_postings_section  # noqa: E402

METRICS_FILES = [
    ROOT / "data/processed/metrics_latest.json",
    ROOT / "website/metrics_latest.json",
]
HISTORY_FILE = ROOT / "data/processed/metrics_history.json"


def main() -> None:
    metrics = json.loads(METRICS_FILES[0].read_text())
    companies = metrics["high_end"]["job_postings"]["companies"]
    job_data = {
        name: {**data, "total_technical_jobs": data["current"]}
        for name, data in companies.items()
    }
    # run_collection resolves history relative to the working directory; load it
    # here so this script produces the same result from any directory.
    snapshots = json.loads(HISTORY_FILE.read_text()).get("snapshots", {})
    section = build_job_postings_section(job_data, snapshots)
    metrics["high_end"]["job_postings"] = section
    for path in METRICS_FILES:
        path.write_text(json.dumps(metrics, indent=2))
        print(f"Updated {path}")
    for name, data in section["companies"].items():
        change = data["changes"]["1_year_ago"]
        print(
            f"  {name}: current={data['current']} 1y={change['value']} ({change['badge']})"
        )
    print(f"  net YoY: {section['net_change_pct_yoy']}")


if __name__ == "__main__":
    main()
