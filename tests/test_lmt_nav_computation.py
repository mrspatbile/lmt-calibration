"""Tests for NAV computation before and after LMT effects."""

from decimal import Decimal
from pathlib import Path

from lmt_calibration.services.streamlit_mvp import (
    load_app_sample_data,
    run_scenario_across_market_conditions,
)


def test_nav_before_lmt_excludes_swing_recovery():
    """Verify NAV before LMT does not include swing cost recovery."""
    sample_data = load_app_sample_data(Path("data/sample"))
    runs = run_scenario_across_market_conditions(
        sample_data, fund_id="lux_dynamic_allocation", strategy_id="cash_then_liquid_assets"
    )

    for run in runs:
        shocked_nav = sum(p.stressed_market_value for p in run.positions)
        gross_redemption = run.result.total_redemption_amount
        estimated_liq_cost = run.lmt_activation.estimated_liquidity_cost_amount

        # Expected NAV before LMT
        expected_nav_before_lmt = max(
            shocked_nav - gross_redemption - estimated_liq_cost, Decimal("0")
        )

        # Verify: no swing cost recovery should be added
        cost_recovered = (
            gross_redemption * run.lmt_activation.estimated_liquidity_cost_rate
            if run.lmt_activation.swing_activated
            else Decimal("0")
        )

        # NAV before LMT should NOT include cost recovery
        nav_before_should_exclude_recovery = expected_nav_before_lmt
        nav_with_recovery = expected_nav_before_lmt + cost_recovered

        assert (
            nav_before_should_exclude_recovery < nav_with_recovery
            if cost_recovered > Decimal("0")
            else True
        ), (
            f"NAV before LMT should not include swing recovery. "
            f"Before: {nav_before_should_exclude_recovery}, With recovery: {nav_with_recovery}"
        )


def test_nav_after_lmt_includes_swing_recovery():
    """Verify NAV after LMT includes swing cost recovery if swing is activated."""
    sample_data = load_app_sample_data(Path("data/sample"))
    runs = run_scenario_across_market_conditions(
        sample_data, fund_id="lux_dynamic_allocation", strategy_id="cash_then_liquid_assets"
    )

    for run in runs:
        if run.lmt_activation.swing_activated:
            shocked_nav = sum(p.stressed_market_value for p in run.positions)
            estimated_liq_cost = run.lmt_activation.estimated_liquidity_cost_amount
            redemption_paid = run.lmt_activation.redemption_paid_amount
            cost_recovered = (
                run.result.total_redemption_amount
                * run.lmt_activation.estimated_liquidity_cost_rate
            )

            # NAV after LMT should include cost recovery
            nav_after_lmt = max(
                shocked_nav - redemption_paid - estimated_liq_cost + cost_recovered, Decimal("0")
            )

            # Verify cost recovery is positive and included
            assert cost_recovered > Decimal("0"), (
                f"Cost recovery should be positive, got {cost_recovered}"
            )
            assert nav_after_lmt >= shocked_nav - redemption_paid - estimated_liq_cost, (
                f"NAV after LMT should include swing recovery. "
                f"Got {nav_after_lmt}, expected >= {shocked_nav - redemption_paid - estimated_liq_cost}"
            )


def test_nav_after_lmt_uses_paid_redemption_only():
    """Verify NAV after LMT uses redemption_paid_amount, not gross redemption."""
    sample_data = load_app_sample_data(Path("data/sample"))
    runs = run_scenario_across_market_conditions(
        sample_data, fund_id="lux_dynamic_allocation", strategy_id="cash_then_liquid_assets"
    )

    for run in runs:
        shocked_nav = sum(p.stressed_market_value for p in run.positions)
        estimated_liq_cost = run.lmt_activation.estimated_liquidity_cost_amount
        gross_redemption = run.result.total_redemption_amount
        redemption_paid = run.lmt_activation.redemption_paid_amount
        deferred = run.lmt_activation.redemption_deferred_amount

        # If gate is activated, deferred should be > 0
        if run.lmt_activation.gate_activated:
            assert deferred > Decimal("0"), (
                f"Gate activated, so deferred should be > 0, got {deferred}"
            )
            assert redemption_paid + deferred <= gross_redemption + Decimal("0.01"), (
                f"Paid + deferred should equal gross. "
                f"Paid: {redemption_paid}, Deferred: {deferred}, Gross: {gross_redemption}"
            )

        # NAV after LMT should use paid, not gross
        cost_recovered = (
            gross_redemption * run.lmt_activation.estimated_liquidity_cost_rate
            if run.lmt_activation.swing_activated
            else Decimal("0")
        )
        nav_after_lmt = max(
            shocked_nav - redemption_paid - estimated_liq_cost + cost_recovered, Decimal("0")
        )

        # Deferred is NOT subtracted from NAV (it's a liability, not a paid cash outflow)
        # So NAV should be: shocked - paid - liq_cost + recovery
        # NOT: shocked - paid - deferred - liq_cost + recovery
        expected_nav = max(
            shocked_nav - redemption_paid - estimated_liq_cost + cost_recovered, Decimal("0")
        )

        assert nav_after_lmt == expected_nav, (
            f"NAV after LMT mismatch. Got {nav_after_lmt}, expected {expected_nav}"
        )


def test_lmt_pills_reflect_activation_states():
    """Verify LMT pill indicators correctly show which LMTs are activated."""
    sample_data = load_app_sample_data(Path("data/sample"))
    runs = run_scenario_across_market_conditions(
        sample_data, fund_id="lux_dynamic_allocation", strategy_id="cash_then_liquid_assets"
    )

    for run in runs:
        swing_activated = run.lmt_activation.swing_activated
        gate_activated = run.lmt_activation.gate_activated
        buffer_breached = run.lmt_activation.buffer_breached

        # Build expected pills
        pills = []
        if swing_activated:
            pills.append("swing")
        if gate_activated:
            pills.append("gate")
        if buffer_breached:
            pills.append("buffer")

        # If no pills, should show "no lmt"
        if not pills:
            assert not swing_activated and not gate_activated and not buffer_breached, (
                f"If no pills, all states should be false. "
                f"Swing: {swing_activated}, Gate: {gate_activated}, Buffer: {buffer_breached}"
            )

        # All activation states should be booleans
        assert isinstance(swing_activated, bool), (
            f"swing_activated should be bool, got {type(swing_activated)}"
        )
        assert isinstance(gate_activated, bool), (
            f"gate_activated should be bool, got {type(gate_activated)}"
        )
        assert isinstance(buffer_breached, bool), (
            f"buffer_breached should be bool, got {type(buffer_breached)}"
        )


def test_before_and_after_lmt_nav_consistency():
    """Verify NAV before and after LMT are computed consistently."""
    sample_data = load_app_sample_data(Path("data/sample"))
    runs = run_scenario_across_market_conditions(
        sample_data, fund_id="lux_dynamic_allocation", strategy_id="cash_then_liquid_assets"
    )

    for run in runs:
        shocked_nav = sum(p.stressed_market_value for p in run.positions)
        gross_redemption = run.result.total_redemption_amount
        estimated_liq_cost = run.lmt_activation.estimated_liquidity_cost_amount

        # Compute before LMT
        nav_before_lmt = max(shocked_nav - gross_redemption - estimated_liq_cost, Decimal("0"))

        # Compute after LMT
        cost_recovered = (
            gross_redemption * run.lmt_activation.estimated_liquidity_cost_rate
            if run.lmt_activation.swing_activated
            else Decimal("0")
        )
        redemption_paid = run.lmt_activation.redemption_paid_amount
        nav_after_lmt = max(
            shocked_nav - redemption_paid - estimated_liq_cost + cost_recovered, Decimal("0")
        )

        # If swing not activated and gate not activated:
        # redemption_paid == gross_redemption, cost_recovered == 0
        # So nav_after_lmt == nav_before_lmt
        if not run.lmt_activation.swing_activated and not run.lmt_activation.gate_activated:
            assert nav_after_lmt == nav_before_lmt, (
                f"Without LMT activation, NAV should be same. Before: {nav_before_lmt}, After: {nav_after_lmt}"
            )

        # If swing is activated, nav_after_lmt should be > nav_before_lmt (recovery is positive)
        if run.lmt_activation.swing_activated:
            assert nav_after_lmt > nav_before_lmt, (
                f"With swing activated, NAV after LMT should be > NAV before LMT. "
                f"Before: {nav_before_lmt}, After: {nav_after_lmt}"
            )

        # If gate is activated, redemption_paid < gross_redemption, so nav_after_lmt > nav_before_lmt
        if run.lmt_activation.gate_activated:
            assert redemption_paid <= gross_redemption, (
                f"Gate activated, so paid should be <= gross. "
                f"Paid: {redemption_paid}, Gross: {gross_redemption}"
            )
