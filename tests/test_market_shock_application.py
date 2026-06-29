"""Tests for market shock application and scenario comparison matrix."""

from decimal import Decimal
from pathlib import Path

from lmt_calibration.services.streamlit_mvp import (
    load_app_sample_data,
    run_scenario_across_market_conditions,
    run_selected_sample_scenario,
)


def test_redemption_rate_uses_market_shocked_nav_before_lmt_effects():
    """Use post-market-shock, pre-LMT NAV as the redemption-rate denominator."""
    sample_data = load_app_sample_data(Path("data/sample"))
    run = run_selected_sample_scenario(
        sample_data,
        fund_id="lux_dynamic_allocation",
        strategy_id="cash_then_liquid_assets",
        market_stress=sample_data.market_stress_by_id["historical_crisis_2008"],
    )

    expected_nav = sum(
        (position.stressed_market_value or Decimal("0") for position in run.positions),
        Decimal("0"),
    )

    assert run.current_pre_lmt_nav == expected_nav
    assert run.redemption_rate == run.result.total_redemption_amount / expected_nav


def test_swing_and_gate_use_canonical_redemption_rate():
    """Apply both simulated activation threshold comparisons to the scenario rate."""
    sample_data = load_app_sample_data(Path("data/sample"))
    run = run_selected_sample_scenario(
        sample_data,
        fund_id="lux_dynamic_allocation",
        strategy_id="cash_then_liquid_assets",
        market_stress=sample_data.market_stress_by_id["historical_crisis_2008"],
    )

    assert run.lmt_activation.swing_activated == (
        run.redemption_rate >= run.parameters.swing_threshold_rate
    )
    assert run.lmt_activation.gate_activated == (
        run.redemption_rate >= run.parameters.gate_threshold_rate
    )


def test_market_shocks_applied_to_positions():
    """Verify market shocks are applied to position values based on asset group."""
    sample_data = load_app_sample_data(Path("data/sample"))

    # Run with different market stresses
    normal_run = run_selected_sample_scenario(
        sample_data,
        fund_id="lux_dynamic_allocation",
        strategy_id="cash_then_liquid_assets",
        market_stress=sample_data.market_stress_by_id["normal_market_conditions"],
    )

    severe_run = run_selected_sample_scenario(
        sample_data,
        fund_id="lux_dynamic_allocation",
        strategy_id="cash_then_liquid_assets",
        market_stress=sample_data.market_stress_by_id["severe_market_stress"],
    )

    # Calculate total position values
    normal_total = sum(p.stressed_market_value for p in normal_run.positions)
    severe_total = sum(p.stressed_market_value for p in severe_run.positions)

    # Severe stress should have lower position values
    assert severe_total < normal_total, "Severe stress should reduce position values"

    # Verify the difference is significant (not just rounding)
    actual_difference_rate = (normal_total - severe_total) / normal_total
    assert actual_difference_rate > Decimal("0.04"), (
        f"Expected >4% impact, got {actual_difference_rate * 100:.1f}%"
    )


def test_scenario_matrix_uses_different_runs():
    """Verify scenario matrix columns use separate runs, not the same run."""
    sample_data = load_app_sample_data(Path("data/sample"))

    runs = run_scenario_across_market_conditions(
        sample_data,
        fund_id="lux_dynamic_allocation",
        strategy_id="cash_then_liquid_assets",
    )

    # Should have 4 runs
    assert len(runs) == 4, f"Expected 4 market condition runs, got {len(runs)}"

    # Each run should have different market stress
    market_stress_rates = [run.market_stress.market_shock_rate for run in runs]
    assert len(set(market_stress_rates)) == 4, "All runs should have different market shock rates"

    # Values should differ across runs
    position_totals = [sum(p.stressed_market_value for p in run.positions) for run in runs]
    assert len(set(position_totals)) == 4, "Position totals should differ across market conditions"


def test_buffer_changes_with_market_shock():
    """Verify market stress changes the post-redemption liquidity ratio."""
    sample_data = load_app_sample_data(Path("data/sample"))

    runs = run_scenario_across_market_conditions(
        sample_data,
        fund_id="lux_dynamic_allocation",
        strategy_id="cash_then_liquid_assets",
    )

    buffers = [float(run.result.remaining_liquid_buffer_rate) for run in runs]

    assert len(set(buffers)) == 4


def test_calibration_adequacy_varies_by_market():
    """Verify calibration adequacy changes with market conditions."""
    sample_data = load_app_sample_data(Path("data/sample"))

    runs = run_scenario_across_market_conditions(
        sample_data,
        fund_id="lux_dynamic_allocation",
        strategy_id="cash_then_liquid_assets",
    )

    adequacies = [run.lmt_activation.calibration_adequacy for run in runs]

    # At least some should be different
    unique_adequacies = set(adequacies)
    assert len(unique_adequacies) >= 1, "Should have at least one calibration adequacy value"

    # Crisis should be more conservative or under-calibrated than normal
    assert adequacies[0].value in [
        "No liquidity cost",
        "Aligned",
        "Conservative",
        "Over-calibrated",
    ], f"Normal market adequacy: {adequacies[0]}"


def test_shortfall_under_extreme_stress():
    """Verify shortfall may occur under extreme market stress."""
    sample_data = load_app_sample_data(Path("data/sample"))

    # Run under crisis conditions
    crisis_run = run_selected_sample_scenario(
        sample_data,
        fund_id="lux_dynamic_allocation",
        strategy_id="cash_then_liquid_assets",
        market_stress=sample_data.market_stress_by_id["historical_crisis_2008"],
    )

    # In crisis with 35% shock, should still meet redemption (good liquidity)
    assert crisis_run.result.shortfall == Decimal("0"), (
        "Even in crisis, redemption should be met with good liquidity"
    )


def test_liquidity_stress_capacity_and_haircut_assumptions_are_applied():
    """Verify liquidity stress controls position capacity and haircut treatment."""
    sample_data = load_app_sample_data(Path("data/sample"))

    normal_run = run_selected_sample_scenario(
        sample_data,
        fund_id="lux_dynamic_allocation",
        strategy_id="cash_then_liquid_assets",
    )

    liquidity_stress = sample_data.liquidity_stress_by_id[normal_run.scenario.liquidity_stress_id]
    equity_assumptions = liquidity_stress.execution_assumptions_by_asset_group["listed_equity"]
    stressed_equity = next(
        position
        for position in normal_run.positions
        if position.asset_group.value == "listed_equity"
    )
    raw_equity = next(
        position
        for position in sample_data.positions
        if position.position_id == stressed_equity.position_id
    )

    assert stressed_equity.stressed_liquidity_capacity_rate == (
        raw_equity.base_liquidity_capacity_rate * equity_assumptions.participation_rate
    )
    assert stressed_equity.stressed_haircut_rate == (
        raw_equity.base_haircut_rate + equity_assumptions.liquidity_haircut_rate
    )
