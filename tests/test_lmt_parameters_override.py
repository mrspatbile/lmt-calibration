"""Test that LMT parameter overrides affect scenario outputs."""

from decimal import Decimal
from pathlib import Path

from lmt_calibration.services.streamlit_mvp import (
    load_app_sample_data,
    run_scenario_across_market_conditions,
    run_selected_sample_scenario,
)


def test_swing_threshold_override_affects_activation():
    """Verify that overriding swing_threshold_rate changes activation status."""
    sample_data = load_app_sample_data(Path("data/sample"))

    # Run with default parameters
    run_default = run_selected_sample_scenario(
        sample_data,
        fund_id="lux_dynamic_allocation",
        strategy_id="cash_then_liquid_assets",
    )

    # Get default parameters and modify swing threshold to be much higher
    default_params = run_default.parameters
    high_swing_params = default_params.model_copy(
        update={
            "swing_threshold_rate": Decimal("0.50"),  # 50% swing threshold (very high)
        }
    )

    # Run with higher swing threshold
    run_high_threshold = run_selected_sample_scenario(
        sample_data,
        fund_id="lux_dynamic_allocation",
        strategy_id="cash_then_liquid_assets",
        lmt_parameters_override=high_swing_params,
    )

    # With high threshold, swing should NOT be activated
    assert not run_high_threshold.lmt_activation.swing_activated, (
        "High swing threshold should prevent activation"
    )
    assert run_default.lmt_activation.swing_activated, "Default threshold should allow activation"
    print("✓ Swing threshold override correctly affects activation")


def test_gate_threshold_override_affects_deferred():
    """Verify that overriding gate_threshold_rate changes deferred amounts."""
    sample_data = load_app_sample_data(Path("data/sample"))

    # Run with default parameters
    run_default = run_selected_sample_scenario(
        sample_data,
        fund_id="lux_dynamic_allocation",
        strategy_id="cash_then_liquid_assets",
    )

    # Get default parameters and modify gate threshold to be much higher
    default_params = run_default.parameters
    high_gate_params = default_params.model_copy(
        update={
            "gate_threshold_rate": Decimal("0.50"),  # 50% gate threshold (very high)
        }
    )

    # Run with higher gate threshold
    run_high_gate = run_selected_sample_scenario(
        sample_data,
        fund_id="lux_dynamic_allocation",
        strategy_id="cash_then_liquid_assets",
        lmt_parameters_override=high_gate_params,
    )

    # With high gate threshold, redemption should not be deferred
    assert (
        run_high_gate.lmt_activation.redemption_deferred_amount
        < run_default.lmt_activation.redemption_deferred_amount
    ), "Higher gate threshold should reduce deferred amount"
    print("✓ Gate threshold override correctly affects deferred amounts")


def test_buffer_target_override_affects_warning():
    """Verify that overriding minimum_buffer_rate changes buffer warning status."""
    sample_data = load_app_sample_data(Path("data/sample"))

    # Run with default parameters
    run_default = run_selected_sample_scenario(
        sample_data,
        fund_id="lux_dynamic_allocation",
        strategy_id="cash_then_liquid_assets",
    )

    # Get default parameters and modify buffer target to be very high
    default_params = run_default.parameters
    high_buffer_params = default_params.model_copy(
        update={
            "minimum_buffer_rate": Decimal("0.50"),  # 50% buffer target (very high)
        }
    )

    # Run with higher buffer target
    run_high_buffer = run_selected_sample_scenario(
        sample_data,
        fund_id="lux_dynamic_allocation",
        strategy_id="cash_then_liquid_assets",
        lmt_parameters_override=high_buffer_params,
    )

    # With high buffer target, buffer warning should be triggered
    assert run_high_buffer.lmt_activation.buffer_breached, (
        "High buffer target should trigger warning"
    )
    print("✓ Buffer target override correctly affects warning status")


def test_market_condition_runs_use_override():
    """Verify that run_scenario_across_market_conditions uses parameter override."""
    sample_data = load_app_sample_data(Path("data/sample"))

    # Get default parameters and modify swing threshold
    scenario_template = next(
        s for s in sample_data.scenario_definitions if s.fund_id == "lux_dynamic_allocation"
    )
    default_params = sample_data.parameters_by_key[
        (
            scenario_template.fund_id,
            scenario_template.as_of_date,
            scenario_template.lmt_parameter_set_id,
        )
    ]

    low_swing_params = default_params.model_copy(
        update={
            "swing_threshold_rate": Decimal("0.01"),  # Very low, 1%
        }
    )

    # Run across market conditions with override
    runs = run_scenario_across_market_conditions(
        sample_data,
        fund_id="lux_dynamic_allocation",
        strategy_id="cash_then_liquid_assets",
        lmt_parameters_override=low_swing_params,
    )

    # All runs should have low swing threshold and thus swing activated
    for run in runs:
        assert run.lmt_activation.swing_activated, (
            "All runs should use overridden low swing threshold"
        )
        assert run.parameters.swing_threshold_rate == Decimal("0.01"), (
            "All runs should have overridden parameters"
        )

    print("✓ Market condition runs correctly use parameter override")
