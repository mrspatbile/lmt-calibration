"""Tests for strategy-dependent scenario matrix outcomes."""

from pathlib import Path

from lmt_calibration.services import (
    AppScenarioRun,
    build_scenario_matrix_outcome,
    load_app_sample_data,
    run_selected_sample_scenario,
)

SAMPLE_DATA_DIR = Path("data/sample")
FUND_ID = "lux_dynamic_allocation"
NORMAL_MARKET_ID = "normal_market_conditions"
CRISIS_MARKET_ID = "historical_crisis_2008"


def _run(strategy_id: str, market_stress_id: str = NORMAL_MARKET_ID) -> AppScenarioRun:
    inputs = load_app_sample_data(SAMPLE_DATA_DIR)
    return run_selected_sample_scenario(
        inputs,
        fund_id=FUND_ID,
        strategy_id=strategy_id,
        market_stress=inputs.market_stress_by_id[market_stress_id],
    )


def test_matrix_outcome_exposes_strategy_dependent_realised_liquidity_cost() -> None:
    cash_first = _run("cash_then_liquid_assets")
    pro_rata = _run("portfolio_profile_pro_rata")
    cash_outcome = build_scenario_matrix_outcome(cash_first)
    pro_rata_outcome = build_scenario_matrix_outcome(pro_rata)

    assert cash_first.result.total_haircut_cost != pro_rata.result.total_haircut_cost
    assert cash_outcome.realised_liquidity_cost == cash_first.result.total_haircut_cost
    assert pro_rata_outcome.realised_liquidity_cost == pro_rata.result.total_haircut_cost
    assert cash_outcome.realised_liquidity_cost != pro_rata_outcome.realised_liquidity_cost


def test_before_and_after_lmt_nav_follow_strategy_dependent_cost() -> None:
    cash_first = _run("cash_then_liquid_assets")
    pro_rata = _run("portfolio_profile_pro_rata")
    cash_outcome = build_scenario_matrix_outcome(cash_first)
    pro_rata_outcome = build_scenario_matrix_outcome(pro_rata)

    for run, outcome in ((cash_first, cash_outcome), (pro_rata, pro_rata_outcome)):
        expected_before = (
            run.current_nav_before_lmt_effects
            - run.result.total_redemption_amount
            - run.result.total_haircut_cost
        )
        expected_after = (
            expected_before + run.lmt_activation.redemption_deferred_amount + outcome.cost_recovered
        )

        assert outcome.nav_before_lmt == expected_before
        assert outcome.nav_after_lmt == expected_after

    assert cash_outcome.nav_before_lmt != pro_rata_outcome.nav_before_lmt
    assert cash_outcome.nav_after_lmt != pro_rata_outcome.nav_after_lmt


def test_swing_recovery_is_capped_at_realised_liquidation_cost() -> None:
    run = _run("cash_then_liquid_assets", CRISIS_MARKET_ID)
    outcome = build_scenario_matrix_outcome(run)

    assert run.lmt_activation.swing_activated
    assert outcome.estimated_swing_recovery > run.result.total_haircut_cost
    assert outcome.cost_recovered == run.result.total_haircut_cost
    assert outcome.cost_recovered <= run.result.total_haircut_cost
