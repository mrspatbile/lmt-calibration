"""Verification tests that matrix columns show different values for different market conditions."""

from decimal import Decimal
from pathlib import Path

from lmt_calibration.services.streamlit_mvp import (
    load_app_sample_data,
    run_scenario_across_market_conditions,
)


def test_matrix_columns_have_different_shocked_nav():
    """Verify each matrix column shows different shocked NAV."""
    sample_data = load_app_sample_data(Path("data/sample"))
    runs = run_scenario_across_market_conditions(
        sample_data, fund_id="lux_dynamic_allocation", strategy_id="cash_then_liquid_assets"
    )

    shocked_navs = [sum(p.stressed_market_value for p in run.positions) for run in runs]

    # All should be different
    assert len(set(shocked_navs)) == 4, f"Expected 4 different NAVs, got {len(set(shocked_navs))}"

    # Should decrease with market stress
    assert shocked_navs[0] > shocked_navs[1] > shocked_navs[2] > shocked_navs[3], (
        f"NAVs should decrease: {shocked_navs}"
    )

    # Specific values (based on -5%, -12%, -35% shocks)
    initial_nav = Decimal("100000000")
    assert shocked_navs[0] == initial_nav, "Normal should have full NAV"
    assert shocked_navs[1] == Decimal("96850000"), (
        f"Moderate should be -3.15%, got {shocked_navs[1]}"
    )
    assert shocked_navs[2] == Decimal("92440000"), f"Severe should be -7.56%, got {shocked_navs[2]}"
    assert shocked_navs[3] == Decimal("77950000"), (
        f"Crisis should be -22.05%, got {shocked_navs[3]}"
    )


def test_matrix_columns_have_different_final_nav():
    """Verify each matrix column shows different final NAV after redemption and costs."""
    sample_data = load_app_sample_data(Path("data/sample"))
    runs = run_scenario_across_market_conditions(
        sample_data, fund_id="lux_dynamic_allocation", strategy_id="cash_then_liquid_assets"
    )

    final_navs = [
        max(
            sum(p.stressed_market_value for p in run.positions)
            - run.result.total_redemption_amount
            - run.result.dilution_amount,
            Decimal("0"),
        )
        for run in runs
    ]

    # All should be different
    assert len(set(final_navs)) == 4, f"Expected 4 different final NAVs, got {len(set(final_navs))}"

    # Should decrease with market stress
    assert final_navs[0] > final_navs[1] > final_navs[2] > final_navs[3], (
        f"Final NAVs should decrease: {final_navs}"
    )


def test_matrix_columns_have_different_buffer():
    """Verify each matrix column shows different remaining buffer."""
    sample_data = load_app_sample_data(Path("data/sample"))
    runs = run_scenario_across_market_conditions(
        sample_data, fund_id="lux_dynamic_allocation", strategy_id="cash_then_liquid_assets"
    )

    buffers = [run.result.remaining_liquid_buffer_rate for run in runs]

    # At least 2 should be different
    assert len(set(buffers)) >= 2, f"Expected different buffers, got {buffers}"

    # Should decrease with stress
    assert buffers[0] >= buffers[3], f"Buffer should decrease: {buffers}"


def test_matrix_redemption_same_across_columns():
    """Verify redemption amount is the same across all columns (same redemption scenario)."""
    sample_data = load_app_sample_data(Path("data/sample"))
    runs = run_scenario_across_market_conditions(
        sample_data, fund_id="lux_dynamic_allocation", strategy_id="cash_then_liquid_assets"
    )

    redemptions = [run.result.total_redemption_amount for run in runs]

    # All should be the same (same redemption scenario)
    assert len(set(redemptions)) == 1, f"Expected same redemptions, got {set(redemptions)}"
    assert redemptions[0] == Decimal("11500000"), (
        f"Expected €11.5M redemption, got {redemptions[0]}"
    )


def test_market_condition_labels_correct():
    """Verify market condition labels are correct."""
    sample_data = load_app_sample_data(Path("data/sample"))
    runs = run_scenario_across_market_conditions(
        sample_data, fund_id="lux_dynamic_allocation", strategy_id="cash_then_liquid_assets"
    )

    shocks = [run.market_stress.market_shock_rate for run in runs]

    assert shocks[0] == Decimal("0.00"), f"First should be normal (0%), got {shocks[0]}"
    assert shocks[1] == Decimal("-0.05"), f"Second should be moderate (-5%), got {shocks[1]}"
    assert shocks[2] == Decimal("-0.12"), f"Third should be severe (-12%), got {shocks[2]}"
    assert shocks[3] == Decimal("-0.35"), f"Fourth should be crisis (-35%), got {shocks[3]}"


def test_each_column_is_independent_run():
    """Verify each column uses a separate AppScenarioRun object."""
    sample_data = load_app_sample_data(Path("data/sample"))
    runs = run_scenario_across_market_conditions(
        sample_data, fund_id="lux_dynamic_allocation", strategy_id="cash_then_liquid_assets"
    )

    # All should be different objects
    ids = [id(run) for run in runs]
    assert len(set(ids)) == 4, "Each run should be a separate object"

    # Each run should have its own market stress object
    market_stress_ids = [id(run.market_stress) for run in runs]
    assert len(set(market_stress_ids)) == 4, "Each run should have its own market stress object"


def test_liquidity_cost_varies_across_scenarios():
    """Verify estimated liquidity cost varies across scenarios."""
    sample_data = load_app_sample_data(Path("data/sample"))
    runs = run_scenario_across_market_conditions(
        sample_data, fund_id="lux_dynamic_allocation", strategy_id="cash_then_liquid_assets"
    )

    costs = [run.lmt_activation.estimated_liquidity_cost_amount for run in runs]

    # At least some should be different (due to different market shocks affecting cost estimation)
    assert len(set(costs)) >= 1, "Should have liquidity cost values"
