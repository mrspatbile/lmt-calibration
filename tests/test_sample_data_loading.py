"""Tests for sample data loading with new market stress fields."""

from pathlib import Path

from lmt_calibration.services.streamlit_mvp import (
    load_app_sample_data,
    run_selected_sample_scenario,
)


def test_load_all_sample_data():
    """Test loading all sample data files."""
    sample_data = load_app_sample_data(Path("data/sample"))

    assert len(sample_data.funds) > 0
    assert len(sample_data.positions) > 0
    assert len(sample_data.investor_classes) > 0
    assert len(sample_data.redemption_scenarios) > 0
    assert len(sample_data.market_stresses) == 4
    assert len(sample_data.liquidity_stresses) > 0
    assert len(sample_data.scenario_definitions) > 0
    assert len(sample_data.lmt_parameters) > 0
    assert len(sample_data.liquidation_strategies) > 0


def test_market_stress_ids_in_lookup():
    """Test that all market stress IDs are in lookup map."""
    sample_data = load_app_sample_data(Path("data/sample"))

    expected_ids = {
        "normal_market_conditions",
        "moderate_market_stress",
        "severe_market_stress",
        "historical_crisis_2008",
    }
    actual_ids = set(sample_data.market_stress_by_id.keys())

    assert actual_ids == expected_ids


def test_scenario_definitions_reference_valid_market_stresses():
    """Test that all scenario definitions reference valid market stresses."""
    sample_data = load_app_sample_data(Path("data/sample"))

    for scenario in sample_data.scenario_definitions:
        assert scenario.market_stress_id in sample_data.market_stress_by_id


def test_run_scenario_with_new_analysis():
    """Test running a scenario produces liquidity cost and LMT activation results."""
    sample_data = load_app_sample_data(Path("data/sample"))
    run = run_selected_sample_scenario(
        sample_data,
        fund_id="lux_dynamic_allocation",
        strategy_id="cash_then_liquid_assets",
    )

    # Check new fields exist
    assert hasattr(run, "redemption_rate")
    assert hasattr(run, "liquidity_cost_breakdown")
    assert hasattr(run, "lmt_activation")

    # Check liquidity cost breakdown
    assert "total_cost_amount" in run.liquidity_cost_breakdown
    assert "total_cost_rate" in run.liquidity_cost_breakdown
    assert "bid_ask_cost_amount" in run.liquidity_cost_breakdown

    # Check LMT activation result
    assert isinstance(run.lmt_activation.swing_activated, bool)
    assert isinstance(run.lmt_activation.gate_activated, bool)
    assert isinstance(run.lmt_activation.buffer_breached, bool)
    assert run.lmt_activation.coverage_ratio > 0


def test_run_scenario_cost_consistency():
    """Test that cost breakdown sums to total."""
    sample_data = load_app_sample_data(Path("data/sample"))
    run = run_selected_sample_scenario(
        sample_data,
        fund_id="lux_dynamic_allocation",
        strategy_id="cash_then_liquid_assets",
    )

    breakdown = run.liquidity_cost_breakdown
    component_sum = (
        breakdown["bid_ask_cost_amount"]
        + breakdown["transaction_cost_amount"]
        + breakdown["market_impact_cost_amount"]
    )

    assert component_sum == breakdown["total_cost_amount"]
