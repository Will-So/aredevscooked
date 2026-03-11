"""FRED API collector for economic time series data."""

import os
from datetime import date, timedelta
from typing import Any

import requests

from aredevscooked.config import FRED_CONFIG


class FredCollector:
    """Collect economic data from the FRED (Federal Reserve Economic Data) API."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("FRED_API_KEY")
        if not self.api_key:
            raise ValueError(
                "FRED_API_KEY not found. Set it in .env or pass it directly."
            )
        self.base_url = FRED_CONFIG["base_url"]

    def fetch_latest_observation(self, series_id: str) -> dict[str, Any]:
        """Fetch the most recent observation for a FRED series.

        Args:
            series_id: FRED series identifier (e.g., "IHLIDXUSTPSOFTDEVE")

        Returns:
            Dict with "date" (str) and "value" (float)

        Raises:
            ValueError: If no valid observation is found
            requests.HTTPError: If the API request fails
        """
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 1,
        }

        response = requests.get(self.base_url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        observations = data.get("observations", [])

        if not observations:
            raise ValueError(f"No observations found for series {series_id}")

        obs = observations[0]
        value_str = obs.get("value", ".")

        if value_str == ".":
            raise ValueError(
                f"Missing value for series {series_id} on {obs.get('date')}"
            )

        return {
            "date": obs["date"],
            "value": float(value_str),
        }

    def fetch_observation_near_date(
        self, series_id: str, target_date: date
    ) -> dict[str, Any]:
        """Fetch the observation closest to (and not after) a target date.

        Args:
            series_id: FRED series identifier
            target_date: Date to find observation nearest to

        Returns:
            Dict with "date" (str) and "value" (float)

        Raises:
            ValueError: If no valid observation is found in range
            requests.HTTPError: If the API request fails
        """
        window_start = target_date - timedelta(days=30)

        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "observation_start": window_start.isoformat(),
            "observation_end": target_date.isoformat(),
            "sort_order": "desc",
            "limit": 1,
        }

        response = requests.get(self.base_url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        observations = data.get("observations", [])

        if not observations:
            raise ValueError(
                f"No observations found for {series_id} near {target_date}"
            )

        obs = observations[0]
        value_str = obs.get("value", ".")

        if value_str == ".":
            raise ValueError(f"Missing value for {series_id} on {obs.get('date')}")

        return {
            "date": obs["date"],
            "value": float(value_str),
        }

    def collect_indeed_index(self) -> dict[str, Any]:
        """Collect the latest Indeed Job Postings index for software development.

        Returns:
            Dict with current_value, date, series_id, and baselines for 30-day
            and 1-year comparisons fetched directly from the FRED API.
        """
        series_id = FRED_CONFIG["series_id"]
        obs = self.fetch_latest_observation(series_id)
        today = date.today()

        baselines = {}
        for period, days in [("30_day", 30), ("1_year", 365)]:
            try:
                baseline = self.fetch_observation_near_date(
                    series_id, today - timedelta(days=days)
                )
                baselines[period] = baseline
            except (ValueError, requests.RequestException):
                baselines[period] = None

        return {
            "current_value": obs["value"],
            "date": obs["date"],
            "series_id": series_id,
            "baselines": baselines,
        }

    def close(self):
        """Close any open resources (API compatibility with other collectors)."""
        pass
