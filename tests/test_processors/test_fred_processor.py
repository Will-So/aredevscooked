"""Tests for FredProcessor."""

import pytest

from aredevscooked.processors.fred_processor import FredProcessor


@pytest.fixture
def processor():
    return FredProcessor()


def test_calculate_percentage_change_increase(processor):
    result = processor.calculate_percentage_change(110.0, 100.0)
    assert result == pytest.approx(10.0)


def test_calculate_percentage_change_decrease(processor):
    result = processor.calculate_percentage_change(85.0, 100.0)
    assert result == pytest.approx(-15.0)


def test_calculate_percentage_change_no_change(processor):
    result = processor.calculate_percentage_change(100.0, 100.0)
    assert result == pytest.approx(0.0)


def test_calculate_percentage_change_validates_baseline(processor):
    with pytest.raises(ValueError, match="Baseline must be positive"):
        processor.calculate_percentage_change(85.0, 0.0)

    with pytest.raises(ValueError, match="Baseline must be positive"):
        processor.calculate_percentage_change(85.0, -10.0)


def test_classify_change_strong(processor):
    assert processor.classify_change(10.0) == "strong"


def test_classify_change_neutral(processor):
    assert processor.classify_change(0.0) == "neutral"
    assert processor.classify_change(3.0) == "neutral"
    assert processor.classify_change(-3.0) == "neutral"


def test_classify_change_reasonably_weak(processor):
    assert processor.classify_change(-7.0) == "reasonably_weak"


def test_classify_change_weak(processor):
    assert processor.classify_change(-15.0) == "weak"


def test_classify_change_collapsing(processor):
    assert processor.classify_change(-25.0) == "collapsing"


def test_relative_to_market_calculation(processor):
    """SDE growth minus total market growth gives relative performance.

    Example: SDE +13%, total market -10% => relative = +23%.
    """
    sde_current, sde_baseline = 113.0, 100.0
    total_current, total_baseline = 90.0, 100.0

    sde_pct = processor.calculate_percentage_change(sde_current, sde_baseline)
    total_pct = processor.calculate_percentage_change(total_current, total_baseline)
    relative_pct = sde_pct - total_pct

    assert sde_pct == pytest.approx(13.0)
    assert total_pct == pytest.approx(-10.0)
    assert relative_pct == pytest.approx(23.0)
    assert processor.classify_change(relative_pct) == "strong"


def test_relative_to_market_both_declining(processor):
    """When both decline, relative shows how SDE fares vs market."""
    sde_pct = processor.calculate_percentage_change(85.0, 100.0)
    total_pct = processor.calculate_percentage_change(80.0, 100.0)
    relative_pct = sde_pct - total_pct

    assert relative_pct == pytest.approx(5.0)
    assert processor.classify_change(relative_pct) == "strong"
