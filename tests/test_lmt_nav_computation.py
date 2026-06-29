"""Tests for explicit NAV bases before and after simulated LMT effects."""

from decimal import Decimal
from pathlib import Path

from lmt_calibration.services import (
    build_scenario_matrix_outcome,
    load_app_sample_data,
    run_scenario_across_market_conditions,
)


def _runs():
    sample_data = load_app_sample_data(Path("data/sample"))
    return run_scenario_across_market_conditions(
        sample_data,
        fund_id="lux_dynamic_allocation",
        strategy_id="cash_then_liquid_assets",
    )


def test_nav_after_redemption_before_lmt_excludes_recovery() -> None:
    for run in _runs():
        outcome = build_scenario_matrix_outcome(run)
        expected = max(
            run.current_pre_lmt_nav
            - run.result.total_redemption_amount
            - run.result.total_haircut_cost,
            Decimal("0"),
        )

        assert outcome.nav_after_redemption_before_lmt == expected


def test_current_post_lmt_nav_uses_returned_recovery_and_deferral() -> None:
    for run in _runs():
        outcome = build_scenario_matrix_outcome(run)
        expected = max(
            outcome.nav_after_redemption_before_lmt
            + run.lmt_activation.redemption_deferred_amount
            + run.lmt_activation.applied_cost_recovery_amount,
            Decimal("0"),
        )

        assert outcome.current_post_lmt_nav == expected


def test_gate_assessment_reconciles_paid_and_deferred_redemption() -> None:
    for run in _runs():
        paid = run.lmt_activation.redemption_paid_amount
        deferred = run.lmt_activation.redemption_deferred_amount

        assert paid + deferred == run.result.total_redemption_amount
        if run.lmt_activation.gate_activated:
            assert deferred > Decimal("0")


def test_swing_recovery_fields_are_zero_when_swing_is_not_activated() -> None:
    for run in _runs():
        if not run.lmt_activation.swing_activated:
            assert run.lmt_activation.theoretical_recovery_amount == Decimal("0")
            assert run.lmt_activation.applied_cost_recovery_amount == Decimal("0")


def test_activation_and_breach_states_are_boolean() -> None:
    for run in _runs():
        assert isinstance(run.lmt_activation.swing_activated, bool)
        assert isinstance(run.lmt_activation.gate_activated, bool)
        assert isinstance(run.lmt_activation.buffer_breached, bool)


def test_remaining_liquidity_rates_use_matching_post_redemption_nav() -> None:
    for run in _runs():
        outcome = build_scenario_matrix_outcome(run)

        assert outcome.remaining_liquid_buffer_rate_before_lmt == (
            run.result.remaining_liquid_resources / outcome.nav_after_redemption_before_lmt
        )
        assert outcome.remaining_liquid_buffer_rate_after_lmt == (
            run.result.remaining_liquid_resources / outcome.current_post_lmt_nav
        )
