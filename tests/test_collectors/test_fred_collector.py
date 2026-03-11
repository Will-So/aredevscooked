"""Tests for FredCollector."""

from datetime import date
from unittest.mock import patch, MagicMock

import pytest

from aredevscooked.collectors.fred_collector import FredCollector


@pytest.fixture
def collector():
    with patch.dict("os.environ", {"FRED_API_KEY": "test-key"}):
        return FredCollector()


@pytest.fixture
def mock_fred_response():
    def _make(observations):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"observations": observations}
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    return _make


def test_init_reads_api_key_from_env():
    with patch.dict("os.environ", {"FRED_API_KEY": "my-key"}):
        collector = FredCollector()
        assert collector.api_key == "my-key"


def test_init_accepts_explicit_api_key():
    collector = FredCollector(api_key="explicit-key")
    assert collector.api_key == "explicit-key"


def test_init_raises_without_api_key():
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="FRED_API_KEY not found"):
            FredCollector()


@patch("aredevscooked.collectors.fred_collector.requests.get")
def test_fetch_latest_observation_success(mock_get, collector, mock_fred_response):
    mock_get.return_value = mock_fred_response(
        [{"date": "2026-03-01", "value": "85.23"}]
    )

    result = collector.fetch_latest_observation("IHLIDXUSTPSOFTDEVE")

    assert result == {"date": "2026-03-01", "value": 85.23}
    mock_get.assert_called_once()
    call_kwargs = mock_get.call_args
    assert call_kwargs.kwargs["params"]["series_id"] == "IHLIDXUSTPSOFTDEVE"
    assert call_kwargs.kwargs["params"]["sort_order"] == "desc"
    assert call_kwargs.kwargs["params"]["limit"] == 1


@patch("aredevscooked.collectors.fred_collector.requests.get")
def test_fetch_latest_observation_missing_value(
    mock_get, collector, mock_fred_response
):
    mock_get.return_value = mock_fred_response([{"date": "2026-03-01", "value": "."}])

    with pytest.raises(ValueError, match="Missing value"):
        collector.fetch_latest_observation("IHLIDXUSTPSOFTDEVE")


@patch("aredevscooked.collectors.fred_collector.requests.get")
def test_fetch_latest_observation_empty_observations(
    mock_get, collector, mock_fred_response
):
    mock_get.return_value = mock_fred_response([])

    with pytest.raises(ValueError, match="No observations found"):
        collector.fetch_latest_observation("IHLIDXUSTPSOFTDEVE")


@patch("aredevscooked.collectors.fred_collector.requests.get")
def test_fetch_latest_observation_http_error(mock_get, collector):
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("403 Forbidden")
    mock_get.return_value = mock_resp

    with pytest.raises(Exception, match="403 Forbidden"):
        collector.fetch_latest_observation("IHLIDXUSTPSOFTDEVE")


@patch("aredevscooked.collectors.fred_collector.requests.get")
def test_fetch_observation_near_date(mock_get, collector, mock_fred_response):
    mock_get.return_value = mock_fred_response(
        [{"date": "2025-03-07", "value": "92.10"}]
    )

    result = collector.fetch_observation_near_date(
        "IHLIDXUSTPSOFTDEVE", date(2025, 3, 10)
    )

    assert result == {"date": "2025-03-07", "value": 92.10}
    call_kwargs = mock_get.call_args
    assert call_kwargs.kwargs["params"]["observation_end"] == "2025-03-10"


@patch("aredevscooked.collectors.fred_collector.requests.get")
def test_collect_indeed_index(mock_get, collector, mock_fred_response):
    mock_get.return_value = mock_fred_response(
        [{"date": "2026-03-01", "value": "85.23"}]
    )

    result = collector.collect_indeed_index()

    assert result["current_value"] == 85.23
    assert result["date"] == "2026-03-01"
    assert result["series_id"] == "IHLIDXUSTPSOFTDEVE"
    assert "baselines" in result
    assert "30_day" in result["baselines"]
    assert "1_year" in result["baselines"]
    # All 3 calls: latest + 30-day baseline + 1-year baseline
    assert mock_get.call_count == 3


@patch("aredevscooked.collectors.fred_collector.requests.get")
def test_collect_indeed_index_baselines_graceful_on_failure(
    mock_get, collector, mock_fred_response
):
    latest_resp = mock_fred_response([{"date": "2026-03-01", "value": "85.23"}])
    empty_resp = mock_fred_response([])
    mock_get.side_effect = [latest_resp, empty_resp, empty_resp]

    result = collector.collect_indeed_index()

    assert result["current_value"] == 85.23
    assert result["baselines"]["30_day"] is None
    assert result["baselines"]["1_year"] is None
