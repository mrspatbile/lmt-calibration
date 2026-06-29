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
from lmt_calibration.loaders import load_lmt_parameters_csv

NORMAL_EXECUTION_COST_RATE = Decimal("0.0020")
CRISIS_EXECUTION_COST_RATE = Decimal("0.0225")
DEFAULT_REMAINING_LIQUID_RESOURCES = Decimal("10000000")


@pytest.fixture
def lmt_params():
    """Load LMT parameters for testing."""
    return load_lmt_parameters_csv(Path("data/sample/lmt_parameters.csv"))


def test_swing_not_activated_below_threshold(lmt_params):
    """Test swing pricing does not activate below threshold."""
    base_params = lmt_params[0]
    nav = Decimal("100000000")
    redemption_rate = Decimal("0.01")  # 1%, below 1.5% threshold

    result = assess_lmt_impact(
        nav=nav,
        redemption_rate=redemption_rate,
        estimated_execution_cost_rate=NORMAL_EXECUTION_COST_RATE,
        lmt_parameters=base_params,
        realised_liquidation_cost=Decimal("2000"),
        remaining_liquid_resources=DEFAULT_REMAINING_LIQUID_RESOURCES,
    )

    assert result.swing_activated is False
    assert result.recovered_cost_amount == Decimal("0")


def test_swing_activated_above_threshold(lmt_params):
    """Test swing pricing activates above threshold."""
    base_params = lmt_params[0]
    nav = Decimal("100000000")
    redemption_rate = Decimal("0.06")  # 6%, above 1.5% threshold

    result = assess_lmt_impact(
        nav=nav,
        redemption_rate=redemption_rate,
        estimated_execution_cost_rate=NORMAL_EXECUTION_COST_RATE,
        lmt_parameters=base_params,
        realised_liquidation_cost=Decimal("12000"),
        remaining_liquid_resources=DEFAULT_REMAINING_LIQUID_RESOURCES,
    )

    assert result.swing_activated is True
    assert result.applied_swing_factor_rate == Decimal("0.0020")
    assert result.theoretical_recovery_amount == Decimal("12000")
    assert result.applied_cost_recovery_amount == Decimal("12000")


def test_gate_not_activated_below_threshold(lmt_params):
    """Test gate does not activate below threshold."""
    base_params = lmt_params[0]  # gate threshold 10%
    nav = Decimal("100000000")
    redemption_rate = Decimal("0.06")  # 6%, below 10% gate threshold

    result = assess_lmt_impact(
        nav=nav,
        redemption_rate=redemption_rate,
        estimated_execution_cost_rate=NORMAL_EXECUTION_COST_RATE,
        lmt_parameters=base_params,
        realised_liquidation_cost=Decimal("12000"),
        remaining_liquid_resources=DEFAULT_REMAINING_LIQUID_RESOURCES,
    )

    assert result.gate_activated is False
    assert result.redemption_paid_amount == Decimal("6000000")  # Full amount paid
    assert result.redemption_deferred_amount == Decimal("0")


def test_gate_activated_above_threshold(lmt_params):
    """Test gate activates above threshold."""
    base_params = lmt_params[0]  # gate threshold 10%
    nav = Decimal("100000000")
    redemption_rate = Decimal("0.15")  # 15%, above 10% threshold

    result = assess_lmt_impact(
        nav=nav,
        redemption_rate=redemption_rate,
        estimated_execution_cost_rate=NORMAL_EXECUTION_COST_RATE,
        lmt_parameters=base_params,
        realised_liquidation_cost=Decimal("30000"),
        remaining_liquid_resources=DEFAULT_REMAINING_LIQUID_RESOURCES,
    )

    assert result.gate_activated is True
    # Paid = 100M * 0.10 = 10M
    assert result.redemption_paid_amount == Decimal("10000000")
    # Deferred = 15M - 10M = 5M
    assert result.redemption_deferred_amount == Decimal("5000000")


def test_coverage_ratio_normal_market(lmt_params):
    """Test coverage ratio for normal market."""
    base_params = lmt_params[0]  # swing factor = 3%
    nav = Decimal("100000000")
    redemption_rate = Decimal("0.06")  # 6%

    result = assess_lmt_impact(
        nav=nav,
        redemption_rate=redemption_rate,
        estimated_execution_cost_rate=NORMAL_EXECUTION_COST_RATE,
        lmt_parameters=base_params,
        realised_liquidation_cost=Decimal("12000"),
        remaining_liquid_resources=DEFAULT_REMAINING_LIQUID_RESOURCES,
    )

    # Est cost = 6M * 0.002 = 12,000
    # Applied factor = min(0.2%, 3%) and fully covers the estimate.
    assert result.estimated_liquidity_cost_amount == Decimal("12000")
    assert result.theoretical_recovery_amount == Decimal("12000")
    assert result.applied_cost_recovery_amount == Decimal("12000")
    assert result.coverage_ratio == Decimal("1")


def test_residual_dilution_normal_market(lmt_params):
    """Test residual dilution for normal market (swing pricing overprotects)."""
    base_params = lmt_params[0]
    nav = Decimal("100000000")
    redemption_rate = Decimal("0.06")

    result = assess_lmt_impact(
        nav=nav,
        redemption_rate=redemption_rate,
        estimated_execution_cost_rate=NORMAL_EXECUTION_COST_RATE,
        lmt_parameters=base_params,
        realised_liquidation_cost=Decimal("20000"),
        remaining_liquid_resources=DEFAULT_REMAINING_LIQUID_RESOURCES,
    )

    assert result.applied_cost_recovery_amount == Decimal("12000")
    assert result.residual_dilution_amount == Decimal("8000")
    assert result.residual_dilution_rate == Decimal("0.00008")


def test_residual_dilution_crisis_market(lmt_params):
    """Test residual dilution for crisis market (swing pricing underprotects)."""
    base_params = lmt_params[0]  # swing factor = 3%
    nav = Decimal("100000000")
    redemption_rate = Decimal("0.06")

    result = assess_lmt_impact(
        nav=nav,
        redemption_rate=redemption_rate,
        estimated_execution_cost_rate=CRISIS_EXECUTION_COST_RATE,
        lmt_parameters=base_params,
        realised_liquidation_cost=Decimal("150000"),
        remaining_liquid_resources=DEFAULT_REMAINING_LIQUID_RESOURCES,
    )

    # Est cost = 6M * 0.0225 = 135,000
    assert result.estimated_liquidity_cost_amount == Decimal("135000")
    assert result.theoretical_recovery_amount == Decimal("135000")
    assert result.applied_cost_recovery_amount == Decimal("135000")
    assert result.residual_dilution_amount == Decimal("15000")


def test_buffer_rate_uses_current_post_lmt_nav(lmt_params):
    """Test remaining liquid resources use current post-LMT NAV."""
    base_params = lmt_params[0]
    nav = Decimal("100000000")
    redemption_rate = Decimal("0.06")

    result = assess_lmt_impact(
        nav=nav,
        redemption_rate=redemption_rate,
        estimated_execution_cost_rate=NORMAL_EXECUTION_COST_RATE,
        lmt_parameters=base_params,
        realised_liquidation_cost=Decimal("12000"),
        remaining_liquid_resources=Decimal("7520000"),
    )

    assert result.current_post_lmt_nav == Decimal("94000000")
    assert result.remaining_liquid_buffer_rate == Decimal("0.08")
    assert result.buffer_breached is False


def test_buffer_not_breached_when_above_minimum(lmt_params):
    """Test that the liquidity buffer is not breached when above the minimum."""
    base_params = lmt_params[0]  # min buffer 5%
    nav = Decimal("100000000")
    redemption_rate = Decimal("0.06")

    result = assess_lmt_impact(
        nav=nav,
        redemption_rate=redemption_rate,
        estimated_execution_cost_rate=NORMAL_EXECUTION_COST_RATE,
        lmt_parameters=base_params,
        realised_liquidation_cost=Decimal("12000"),
        remaining_liquid_resources=Decimal("7520000"),
    )

    assert result.buffer_breached is False


def test_buffer_breached_when_below_minimum(lmt_params):
    """Test that the liquidity buffer is breached when below the minimum."""
    base_params = lmt_params[0]  # min buffer 5%
    nav = Decimal("100000000")
    redemption_rate = Decimal("0.06")

    result = assess_lmt_impact(
        nav=nav,
        redemption_rate=redemption_rate,
        estimated_execution_cost_rate=NORMAL_EXECUTION_COST_RATE,
        lmt_parameters=base_params,
        realised_liquidation_cost=Decimal("12000"),
        remaining_liquid_resources=Decimal("2820000"),
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


def test_lmt_impact_includes_calibration_adequacy(lmt_params):
    """Test that assess_lmt_impact returns calibration adequacy and message."""
    base_params = lmt_params[0]
    nav = Decimal("100000000")
    redemption_rate = Decimal("0.06")

    result = assess_lmt_impact(
        nav=nav,
        redemption_rate=redemption_rate,
        estimated_execution_cost_rate=NORMAL_EXECUTION_COST_RATE,
        lmt_parameters=base_params,
        realised_liquidation_cost=Decimal("12000"),
        remaining_liquid_resources=DEFAULT_REMAINING_LIQUID_RESOURCES,
    )

    assert result.calibration_adequacy is not None
    assert result.calibration_message != ""
    assert isinstance(result.calibration_adequacy, CalibrationAdequacy)
    assert isinstance(result.calibration_message, str)
