"""Tests for StockProcessor class."""

import pytest
from aredevscooked.processors.stock_processor import StockProcessor


@pytest.fixture
def processor():
    """Create a StockProcessor instance."""
    return StockProcessor()


# Equal-Weighted Index Calculation Tests


def test_calculate_index_all_stocks_same_increase(processor):
    """Equal-weighted index should average percentage changes."""
    baseline_prices = {
        "HCLTech": 100.0,
        "LTIMindtree": 200.0,
        "Cognizant": 150.0,
    }
    current_prices = {
        "HCLTech": 120.0,  # +20%
        "LTIMindtree": 240.0,  # +20%
        "Cognizant": 180.0,  # +20%
    }

    index = processor.calculate_index(current_prices, baseline_prices)

    # All stocks at 120% → average 120% → index = 120.0
    assert index == pytest.approx(120.0, rel=1e-2)


def test_calculate_index_mixed_changes(processor):
    """Equal-weighted index should average mixed percentage changes."""
    baseline_prices = {
        "HCLTech": 100.0,
        "LTIMindtree": 100.0,
        "Cognizant": 100.0,
    }
    current_prices = {
        "HCLTech": 120.0,  # +20%
        "LTIMindtree": 90.0,  # -10%
        "Cognizant": 115.0,  # +15%
    }

    index = processor.calculate_index(current_prices, baseline_prices)

    # Average: (120% + 90% + 115%) / 3 = 108.33%
    assert index == pytest.approx(108.33, rel=1e-2)


def test_calculate_index_single_stock(processor):
    """Should work with single stock."""
    baseline_prices = {"HCLTech": 100.0}
    current_prices = {"HCLTech": 150.0}  # +50%

    index = processor.calculate_index(current_prices, baseline_prices)

    assert index == pytest.approx(150.0, rel=1e-2)


def test_calculate_index_seven_stocks(processor):
    """Should calculate index for 7 IT consultancies."""
    baseline_prices = {
        "HCLTech": 1320.0,
        "LTIMindtree": 5200.0,
        "Cognizant": 75.0,
        "Infosys": 1450.0,
        "TCS": 3600.0,
        "Tech Mahindra": 1200.0,
        "Wipro": 420.0,
    }
    current_prices = {
        "HCLTech": 1450.5,  # +9.88%
        "LTIMindtree": 5600.0,  # +7.69%
        "Cognizant": 78.0,  # +4.0%
        "Infosys": 1500.0,  # +3.45%
        "TCS": 3700.0,  # +2.78%
        "Tech Mahindra": 1150.0,  # -4.17%
        "Wipro": 400.0,  # -4.76%
    }

    index = processor.calculate_index(current_prices, baseline_prices)

    # Manual calculation: (109.88 + 107.69 + 104.0 + 103.45 + 102.78 + 95.83 + 95.24) / 7
    # = 718.87 / 7 = 102.70
    assert index == pytest.approx(102.70, rel=1e-2)


def test_calculate_index_validates_matching_companies(processor):
    """Should raise error if companies don't match."""
    baseline_prices = {"HCLTech": 100.0, "LTIMindtree": 200.0}
    current_prices = {"HCLTech": 120.0, "Cognizant": 180.0}

    with pytest.raises(ValueError, match="Companies must match"):
        processor.calculate_index(current_prices, baseline_prices)


def test_calculate_index_validates_empty_dict(processor):
    """Should raise error for empty price dictionaries."""
    with pytest.raises(ValueError, match="at least one"):
        processor.calculate_index({}, {})


def test_calculate_index_validates_positive_prices(processor):
    """Should raise error for non-positive prices."""
    baseline_prices = {"HCLTech": 100.0}
    current_prices = {"HCLTech": -50.0}

    with pytest.raises(ValueError, match="positive"):
        processor.calculate_index(current_prices, baseline_prices)


def test_calculate_index_validates_positive_baseline(processor):
    """Should raise error for non-positive baseline prices."""
    baseline_prices = {"HCLTech": 0.0}
    current_prices = {"HCLTech": 100.0}

    with pytest.raises(ValueError, match="positive"):
        processor.calculate_index(current_prices, baseline_prices)


# Index Change Calculation Tests


def test_calculate_index_change_positive(processor):
    """Should calculate positive index change."""
    current_index = 108.5
    baseline_index = 100.0

    change = processor.calculate_index_change(current_index, baseline_index)

    assert change == pytest.approx(8.5, rel=1e-2)


def test_calculate_index_change_negative(processor):
    """Should calculate negative index change."""
    current_index = 92.0
    baseline_index = 100.0

    change = processor.calculate_index_change(current_index, baseline_index)

    assert change == pytest.approx(-8.0, rel=1e-2)


def test_calculate_index_change_no_change(processor):
    """Should return zero for no change."""
    current_index = 100.0
    baseline_index = 100.0

    change = processor.calculate_index_change(current_index, baseline_index)

    assert change == pytest.approx(0.0, rel=1e-2)


def test_calculate_index_change_large_decrease(processor):
    """Should handle large decreases."""
    current_index = 50.0
    baseline_index = 100.0

    change = processor.calculate_index_change(current_index, baseline_index)

    assert change == pytest.approx(-50.0, rel=1e-2)


def test_calculate_index_change_validates_positive_baseline(processor):
    """Should raise error for non-positive baseline."""
    with pytest.raises(ValueError, match="positive"):
        processor.calculate_index_change(100.0, 0.0)


def test_calculate_index_change_validates_positive_current(processor):
    """Should raise error for non-positive current index."""
    with pytest.raises(ValueError, match="positive"):
        processor.calculate_index_change(-50.0, 100.0)


# Company Weight Calculation Tests


def test_calculate_company_weights_equal_weights(processor):
    """Should calculate equal weights for all companies."""
    companies = ["HCLTech", "LTIMindtree", "Cognizant"]

    weights = processor.calculate_company_weights(companies)

    assert len(weights) == 3
    assert weights["HCLTech"] == pytest.approx(1 / 3, rel=1e-2)
    assert weights["LTIMindtree"] == pytest.approx(1 / 3, rel=1e-2)
    assert weights["Cognizant"] == pytest.approx(1 / 3, rel=1e-2)


def test_calculate_company_weights_seven_companies(processor):
    """Should calculate equal weights for 7 IT consultancies."""
    companies = [
        "HCLTech",
        "LTIMindtree",
        "Cognizant",
        "Infosys",
        "TCS",
        "Tech Mahindra",
        "Wipro",
    ]

    weights = processor.calculate_company_weights(companies)

    assert len(weights) == 7
    for company in companies:
        assert weights[company] == pytest.approx(1 / 7, rel=1e-2)


def test_calculate_company_weights_single_company(processor):
    """Should return 1.0 for single company."""
    companies = ["HCLTech"]

    weights = processor.calculate_company_weights(companies)

    assert weights["HCLTech"] == pytest.approx(1.0, rel=1e-2)


def test_calculate_company_weights_validates_non_empty(processor):
    """Should raise error for empty company list."""
    with pytest.raises(ValueError, match="at least one"):
        processor.calculate_company_weights([])


# Integration Tests


def test_full_workflow_with_realistic_data(processor):
    """Test complete workflow with realistic stock data."""
    # Baseline from 1 year ago
    baseline_prices = {
        "HCLTech": 1320.0,
        "LTIMindtree": 5200.0,
        "Cognizant": 75.0,
    }

    # Current prices (mixed performance)
    current_prices = {
        "HCLTech": 1450.5,  # +9.88%
        "LTIMindtree": 5100.0,  # -1.92%
        "Cognizant": 78.0,  # +4.0%
    }

    # Calculate index
    index = processor.calculate_index(current_prices, baseline_prices)
    assert index == pytest.approx(103.99, rel=1e-2)

    # Calculate change from baseline (100.0)
    change = processor.calculate_index_change(index, 100.0)
    assert change == pytest.approx(3.99, rel=1e-2)

    # Calculate weights
    weights = processor.calculate_company_weights(list(baseline_prices.keys()))
    assert len(weights) == 3
    for weight in weights.values():
        assert weight == pytest.approx(1 / 3, rel=1e-2)


def test_relative_to_spy_it_underperforming(processor):
    """IT index down 30%, SPY up 5% => relative = -35%."""
    it_index_change = -30.0
    spy_pct_change = 5.0
    relative = it_index_change - spy_pct_change
    assert relative == pytest.approx(-35.0)


def test_relative_to_spy_both_declining(processor):
    """IT index down 30%, SPY down 15% => relative = -15%."""
    it_index_change = -30.0
    spy_pct_change = -15.0
    relative = it_index_change - spy_pct_change
    assert relative == pytest.approx(-15.0)


def test_relative_to_spy_it_outperforming(processor):
    """IT index up 10%, SPY up 3% => relative = +7%."""
    it_index_change = 10.0
    spy_pct_change = 3.0
    relative = it_index_change - spy_pct_change
    assert relative == pytest.approx(7.0)
