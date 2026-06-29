"""Characterization tests for issue 27 methodology alignment."""

from decimal import Decimal
from pathlib import Path

from lmt_calibration.audit import JsonAuditWriter
from lmt_calibration.domain import AssetGroup
from lmt_calibration.engines.liquidity_cost import estimate_liquidity_cost_rate
from lmt_calibration.services import (
    build_scenario_matrix_outcome,
    load_app_sample_data,
    run_selected_sample_scenario,
)

SAMPLE_DATA_DIR = Path("data/sample")
FUND_ID = "lux_dynamic_allocation"
STRATEGY_ID = "cash_then_liquid_assets"


def _run(market_stress_id: str = "historical_crisis_2008"):
    inputs = load_app_sample_data(SAMPLE_DATA_DIR)
    return inputs, run_selected_sample_scenario(
        inputs,
        fund_id=FUND_ID,
        strategy_id=STRATEGY_ID,
        market_stress=inputs.market_stress_by_id[market_stress_id],
    )


def test_current_execution_cost_and_liquidation_inputs_have_separate_sources() -> None:
    inputs, run = _run()
    liquidity_stress = inputs.liquidity_stress_by_id[run.scenario.liquidity_stress_id]
    equity_assumptions = liquidity_stress.execution_assumptions_by_asset_group[
        AssetGroup.LISTED_EQUITY
    ]
    equity_position = next(
        position for position in run.positions if position.asset_group.value == "listed_equity"
    )
    raw_equity = next(
        position
        for position in inputs.positions
        if position.position_id == equity_position.position_id
    )

    market_values: dict[AssetGroup, Decimal] = {}
    for position in run.positions:
        market_values[position.asset_group] = market_values.get(
            position.asset_group, Decimal("0")
        ) + (position.stressed_market_value or Decimal("0"))
    assert (
        estimate_liquidity_cost_rate(liquidity_stress, market_values)
        == (run.liquidity_cost_breakdown["total_cost_rate"])
    )
    assert not hasattr(run.market_stress, "bid_ask_spread_rate")
    assert equity_position.stressed_liquidity_capacity_rate == (
        raw_equity.base_liquidity_capacity_rate * equity_assumptions.participation_rate
    )
    assert equity_position.stressed_haircut_rate == (
        raw_equity.base_haircut_rate + equity_assumptions.liquidity_haircut_rate
    )


def test_current_nav_bases_are_intentional_and_distinct() -> None:
    inputs, run = _run()
    redemption = inputs.redemption_by_id[run.scenario.redemption_scenario_id]
    investors = [
        investor
        for investor in inputs.investor_classes
        if investor.fund_id == run.fund.fund_id and investor.as_of_date == run.fund.as_of_date
    ]
    expected_redemption = sum(
        (
            run.fund.nav
            * investor.nav_share_rate
            * investor.stress_redemption_rate
            * redemption.redemption_multiplier
            for investor in investors
        ),
        Decimal("0"),
    )

    assert run.result.total_redemption_amount == expected_redemption
    assert run.initial_snapshot_nav == run.fund.nav
    assert run.redemption_rate == (run.result.total_redemption_amount / run.current_pre_lmt_nav)
    assert run.result.dilution_rate == run.result.dilution_amount / run.fund.nav
    assert run.result.remaining_liquid_buffer_rate == (
        run.result.remaining_liquid_resources / run.lmt_activation.nav_after_redemption_before_lmt
    )
    assert run.lmt_activation.remaining_liquid_buffer_rate == (
        run.result.remaining_liquid_resources / run.lmt_activation.current_post_lmt_nav
    )


def test_swing_recovery_is_centralized_in_activation_output() -> None:
    _, run = _run()
    outcome = build_scenario_matrix_outcome(run)

    assert run.lmt_activation.applied_swing_factor_rate == min(
        run.lmt_activation.estimated_liquidity_cost_rate,
        run.parameters.max_swing_factor_rate,
    )
    assert run.lmt_activation.theoretical_recovery_amount == (
        run.result.total_redemption_amount * run.lmt_activation.applied_swing_factor_rate
    )
    assert run.lmt_activation.applied_cost_recovery_amount == min(
        run.lmt_activation.theoretical_recovery_amount,
        run.result.total_haircut_cost,
    )
    assert outcome.estimated_swing_recovery == run.lmt_activation.theoretical_recovery_amount
    assert outcome.cost_recovered == run.lmt_activation.applied_cost_recovery_amount


def test_scenario_execution_does_not_write_audit_files(monkeypatch) -> None:
    write_calls = 0

    def record_write(*args: object, **kwargs: object) -> Path:
        nonlocal write_calls
        write_calls += 1
        raise AssertionError("scenario execution must not write audit files")

    monkeypatch.setattr(JsonAuditWriter, "write", record_write)
    _run("normal_market_conditions")

    assert write_calls == 0
