"""Tests for simulated LMT activation assessment and investor impact."""

from decimal import Decimal
from pathlib import Path

import pytest

from lmt_calibration.engines.lmt_activation import (
    CalibrationAdequacy,
    assess_lmt_impact,
    classify_calibration_adequacy,
    get_calibration_message,
)
from lmt_calibration.loaders import (
    load_lmt_parameters_csv,
    load_market_stresses_csv,
)


@pytest.fixture
def market_stresses():
    """Load market stresses for testing."""
    return load_market_stresses_csv(Path("data/sample/market_stresses.csv"))


@pytest.fixture
def lmt_params():
    """Load LMT parameters for testing."""
    return load_lmt_parameters_csv(Path("data/sample/lmt_parameters.csv"))


def test_swing_not_activated_below_threshold(market_stresses, lmt_params):
    """Test swing pricing does not activate below threshold."""
    normal = market_stresses[0]
    base_params = lmt_params[0]
    nav = Decimal("100000000")
    redemption_rate = Decimal("0.01")  # 1%, below 1.5% threshold

    result = assess_lmt_impact(
        nav=nav,
        redemption_rate=redemption_rate,
        market_stress=normal,
        lmt_parameters=base_params,
    )

    assert result.swing_activated is False
    assert result.recovered_cost_amount == Decimal("0")


def test_swing_activated_above_threshold(market_stresses, lmt_params):
    """Test swing pricing activates above threshold."""
    normal = market_stresses[0]
    base_params = lmt_params[0]
    nav = Decimal("100000000")
    redemption_rate = Decimal("0.06")  # 6%, above 1.5% threshold

    result = assess_lmt_impact(
        nav=nav,
        redemption_rate=redemption_rate,
        market_stress=normal,
        lmt_parameters=base_params,
    )

    assert result.swing_activated is True
    # Recovered = 100M * 0.06 * 0.03 = 180,000
    assert result.recovered_cost_amount == Decimal("180000")


def test_gate_not_activated_below_threshold(market_stresses, lmt_params):
    """Test gate does not activate below threshold."""
    normal = market_stresses[0]
    base_params = lmt_params[0]  # gate threshold 10%
    nav = Decimal("100000000")
    redemption_rate = Decimal("0.06")  # 6%, below 10% gate threshold

    result = assess_lmt_impact(
        nav=nav,
        redemption_rate=redemption_rate,
        market_stress=normal,
        lmt_parameters=base_params,
    )

    assert result.gate_activated is False
    assert result.redemption_paid_amount == Decimal("6000000")  # Full amount paid
    assert result.redemption_deferred_amount == Decimal("0")


def test_gate_activated_above_threshold(market_stresses, lmt_params):
    """Test gate activates above threshold."""
    normal = market_stresses[0]
    base_params = lmt_params[0]  # gate threshold 10%
    nav = Decimal("100000000")
    redemption_rate = Decimal("0.15")  # 15%, above 10% threshold

    result = assess_lmt_impact(
        nav=nav,
        redemption_rate=redemption_rate,
        market_stress=normal,
        lmt_parameters=base_params,
    )

    assert result.gate_activated is True
    # Paid = 100M * 0.10 = 10M
    assert result.redemption_paid_amount == Decimal("10000000")
    # Deferred = 15M - 10M = 5M
    assert result.redemption_deferred_amount == Decimal("5000000")


def test_coverage_ratio_normal_market(market_stresses, lmt_params):
    """Test coverage ratio for normal market."""
    normal = market_stresses[0]  # cost rate = 0.2%
    base_params = lmt_params[0]  # swing factor = 3%
    nav = Decimal("100000000")
    redemption_rate = Decimal("0.06")  # 6%

    result = assess_lmt_impact(
        nav=nav,
        redemption_rate=redemption_rate,
        market_stress=normal,
        lmt_parameters=base_params,
    )

    # Est cost = 6M * 0.002 = 12,000
    # Recovered = 6M * 0.03 = 180,000
    # Coverage = 180K / 12K = 15x (1500%)
    assert result.estimated_liquidity_cost_amount == Decimal("12000")
    assert result.recovered_cost_amount == Decimal("180000")
    assert result.coverage_ratio == Decimal("15")


def test_residual_dilution_normal_market(market_stresses, lmt_params):
    """Test residual dilution for normal market (swing pricing overprotects)."""
    normal = market_stresses[0]
    base_params = lmt_params[0]
    nav = Decimal("100000000")
    redemption_rate = Decimal("0.06")

    result = assess_lmt_impact(
        nav=nav,
        redemption_rate=redemption_rate,
        market_stress=normal,
        lmt_parameters=base_params,
    )

    # Residual = max(12K - 180K, 0) = 0
    assert result.residual_dilution_amount == Decimal("0")
    assert result.residual_dilution_rate == Decimal("0")


def test_residual_dilution_crisis_market(market_stresses, lmt_params):
    """Test residual dilution for crisis market (swing pricing underprotects)."""
    crisis = market_stresses[3]  # cost rate = 2.25%
    base_params = lmt_params[0]  # swing factor = 3%
    nav = Decimal("100000000")
    redemption_rate = Decimal("0.06")

    result = assess_lmt_impact(
        nav=nav,
        redemption_rate=redemption_rate,
        market_stress=crisis,
        lmt_parameters=base_params,
    )

    # Est cost = 6M * 0.0225 = 135,000
    # Recovered = 6M * 0.03 = 180,000
    # Residual = max(135K - 180K, 0) = 0 (still overprotected)
    assert result.estimated_liquidity_cost_amount == Decimal("135000")
    assert result.recovered_cost_amount == Decimal("180000")
    assert result.residual_dilution_amount == Decimal("0")


def test_buffer_breach_not_checked_when_none(market_stresses, lmt_params):
    """Test buffer breach is false when not provided."""
    normal = market_stresses[0]
    base_params = lmt_params[0]
    nav = Decimal("100000000")
    redemption_rate = Decimal("0.06")

    result = assess_lmt_impact(
        nav=nav,
        redemption_rate=redemption_rate,
        market_stress=normal,
        lmt_parameters=base_params,
        remaining_liquid_buffer_rate=None,
    )

    assert result.buffer_breached is False


def test_buffer_not_breached_when_above_minimum(market_stresses, lmt_params):
    """Test that the liquidity buffer is not breached when above the minimum."""
    normal = market_stresses[0]
    base_params = lmt_params[0]  # min buffer 5%
    nav = Decimal("100000000")
    redemption_rate = Decimal("0.06")

    result = assess_lmt_impact(
        nav=nav,
        redemption_rate=redemption_rate,
        market_stress=normal,
        lmt_parameters=base_params,
        remaining_liquid_buffer_rate=Decimal("0.08"),  # 8%, above 5% minimum
    )

    assert result.buffer_breached is False


def test_buffer_breached_when_below_minimum(market_stresses, lmt_params):
    """Test that the liquidity buffer is breached when below the minimum."""
    normal = market_stresses[0]
    base_params = lmt_params[0]  # min buffer 5%
    nav = Decimal("100000000")
    redemption_rate = Decimal("0.06")

    result = assess_lmt_impact(
        nav=nav,
        redemption_rate=redemption_rate,
        market_stress=normal,
        lmt_parameters=base_params,
        remaining_liquid_buffer_rate=Decimal("0.03"),  # 3%, below 5% minimum
    )

    assert result.buffer_breached is True


def test_calibration_adequacy_no_cost():
    """Test calibration adequacy when both cost and recovery are zero."""
    adequacy = classify_calibration_adequacy(
        estimated_liquidity_cost_amount=Decimal("0"),
        recovered_cost_amount=Decimal("0"),
        coverage_ratio=Decimal("1"),
    )
    assert adequacy == CalibrationAdequacy.NO_LIQUIDITY_COST


def test_calibration_adequacy_under_calibrated():
    """Test calibration adequacy when coverage < 80%."""
    adequacy = classify_calibration_adequacy(
        estimated_liquidity_cost_amount=Decimal("10000"),
        recovered_cost_amount=Decimal("5000"),
        coverage_ratio=Decimal("0.50"),
    )
    assert adequacy == CalibrationAdequacy.UNDER_CALIBRATED


def test_calibration_adequacy_aligned():
    """Test calibration adequacy when 80% <= coverage <= 120%."""
    adequacy = classify_calibration_adequacy(
        estimated_liquidity_cost_amount=Decimal("10000"),
        recovered_cost_amount=Decimal("10000"),
        coverage_ratio=Decimal("1.00"),
    )
    assert adequacy == CalibrationAdequacy.ALIGNED

    adequacy = classify_calibration_adequacy(
        estimated_liquidity_cost_amount=Decimal("10000"),
        recovered_cost_amount=Decimal("9600"),
        coverage_ratio=Decimal("0.96"),
    )
    assert adequacy == CalibrationAdequacy.ALIGNED


def test_calibration_adequacy_conservative():
    """Test calibration adequacy when 120% < coverage <= 200%."""
    adequacy = classify_calibration_adequacy(
        estimated_liquidity_cost_amount=Decimal("10000"),
        recovered_cost_amount=Decimal("15000"),
        coverage_ratio=Decimal("1.50"),
    )
    assert adequacy == CalibrationAdequacy.CONSERVATIVE


def test_calibration_adequacy_over_calibrated():
    """Test calibration adequacy when coverage > 200%."""
    adequacy = classify_calibration_adequacy(
        estimated_liquidity_cost_amount=Decimal("10000"),
        recovered_cost_amount=Decimal("300000"),
        coverage_ratio=Decimal("30.0"),
    )
    assert adequacy == CalibrationAdequacy.OVER_CALIBRATED


def test_get_calibration_message_all_labels():
    """Test that all calibration adequacy labels have messages."""
    for adequacy in CalibrationAdequacy:
        message = get_calibration_message(adequacy)
        assert message != ""
        assert isinstance(message, str)


def test_calibration_message_under_calibrated():
    """Test message for under-calibrated calibration."""
    message = get_calibration_message(CalibrationAdequacy.UNDER_CALIBRATED)
    assert "does not fully cover" in message.lower()


def test_calibration_message_aligned():
    """Test message for aligned calibration."""
    message = get_calibration_message(CalibrationAdequacy.ALIGNED)
    assert "broadly matches" in message.lower()


def test_calibration_message_conservative():
    """Test message for conservative calibration."""
    message = get_calibration_message(CalibrationAdequacy.CONSERVATIVE)
    assert "above" in message.lower()


def test_calibration_message_over_calibrated():
    """Test message for over-calibrated calibration."""
    message = get_calibration_message(CalibrationAdequacy.OVER_CALIBRATED)
    assert "exceeds" in message.lower() or "materially" in message.lower()


def test_lmt_impact_includes_calibration_adequacy(market_stresses, lmt_params):
    """Test that assess_lmt_impact returns calibration adequacy and message."""
    normal = market_stresses[0]
    base_params = lmt_params[0]
    nav = Decimal("100000000")
    redemption_rate = Decimal("0.06")

    result = assess_lmt_impact(
        nav=nav,
        redemption_rate=redemption_rate,
        market_stress=normal,
        lmt_parameters=base_params,
    )

    assert result.calibration_adequacy is not None
    assert result.calibration_message != ""
    assert isinstance(result.calibration_adequacy, CalibrationAdequacy)
    assert isinstance(result.calibration_message, str)
