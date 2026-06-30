from decimal import Decimal
from pathlib import Path

import pytest

from lmt_calibration.services import (
    build_historical_result_rows,
    build_t0_liquidity_profile_rows,
    load_app_sample_data,
    run_sample_redemption_path,
    run_selected_sample_scenario,
)

SAMPLE_DATA_DIR = Path("data/sample")


def test_streamlit_mvp_service_loads_sample_data_and_runs_engine() -> None:
    inputs = load_app_sample_data(SAMPLE_DATA_DIR)
    fund = inputs.funds[0]
    strategy = inputs.liquidation_strategies[0]

    run = run_selected_sample_scenario(
        inputs,
        fund_id=fund.fund_id,
        strategy_id=strategy.liquidation_strategy_id,
    )

    assert run.fund == fund
    assert run.strategy == strategy
    assert run.redemption_amount > Decimal("0")
    assert run.result.liquidation_strategy_id == strategy.liquidation_strategy_id


def test_streamlit_mvp_service_returns_historical_context_rows() -> None:
    inputs = load_app_sample_data(SAMPLE_DATA_DIR)
    fund = inputs.funds[0]
    strategy = inputs.liquidation_strategies[0]
    run = run_selected_sample_scenario(
        inputs,
        fund_id=fund.fund_id,
        strategy_id=strategy.liquidation_strategy_id,
    )

    rows = build_historical_result_rows(inputs, run)

    assert {row["scenario_id"] for row in rows} == {
        "historical_2008_financial_crisis",
        "historical_2020_covid",
        "historical_2022_rate_inflation",
    }
    assert {row["status"] for row in rows} == {"Context only"}


def test_streamlit_mvp_service_runs_redemption_path_without_market_stress() -> None:
    inputs = load_app_sample_data(SAMPLE_DATA_DIR)
    fund = inputs.funds[0]
    strategy = inputs.liquidation_strategies[0]
    redemption = inputs.redemption_scenarios[0]

    run = run_sample_redemption_path(
        inputs,
        fund_id=fund.fund_id,
        strategy_id=strategy.liquidation_strategy_id,
        redemption_scenario_id=redemption.redemption_scenario_id,
        lmt_parameters_override=None,
        stress_months=(1, 2),
        random_seed=42,
        market_stress_id=None,
        market_stress_month=None,
        behavioural_feedback_enabled=False,
        behavioural_feedback_multiplier=Decimal("1"),
    )

    assert len(run.result.monthly_results) == 12
    assert len(run.monthly_rows) == 12
    assert len(run.lmt_timeline_rows) == 12
    assert run.market_stress is None
    assert {row["market_stress_applied"] for row in run.monthly_rows} == {False}
    assert run.liquidity_profile_rows
    assert {row["setting"] for row in run.configuration_rows} >= {
        "Market stress scenario",
        "Redemption-stress months",
        "Behavioural feedback",
        "Market contagion",
    }


def test_sample_normal_redemption_path_uses_stable_beta_draws() -> None:
    inputs = load_app_sample_data(SAMPLE_DATA_DIR)
    fund = inputs.funds[0]
    strategy = inputs.liquidation_strategies[0]
    redemption = inputs.redemption_scenarios[0]

    run = run_sample_redemption_path(
        inputs,
        fund_id=fund.fund_id,
        strategy_id=strategy.liquidation_strategy_id,
        redemption_scenario_id=redemption.redemption_scenario_id,
        lmt_parameters_override=None,
        stress_months=(),
        random_seed=42,
        market_stress_id=None,
        market_stress_month=None,
        behavioural_feedback_enabled=False,
        behavioural_feedback_multiplier=Decimal("1"),
    )

    first_four_month_rates = [
        row["new_redemption_demand"] / row["opening_nav"] for row in run.monthly_rows[:4]
    ]

    assert first_four_month_rates == [
        Decimal("0.02279958238952855675"),
        Decimal("0.03300293112535390314085616671"),
        Decimal("0.02271074983020271296240057116"),
        Decimal("0.02870684566739427417724533616"),
    ]
    assert max(first_four_month_rates) < Decimal("0.05")


def test_streamlit_mvp_service_prepares_behavioural_feedback_rows() -> None:
    inputs = load_app_sample_data(SAMPLE_DATA_DIR)
    fund = inputs.funds[0]
    strategy = inputs.liquidation_strategies[0]
    redemption = inputs.redemption_scenarios[0]
    scenario = next(item for item in inputs.scenario_definitions if item.fund_id == fund.fund_id)
    parameters = inputs.parameters_by_key[
        (scenario.fund_id, scenario.as_of_date, scenario.lmt_parameter_set_id)
    ].model_copy(
        update={
            "swing_threshold_rate": Decimal("0"),
            "gate_threshold_rate": Decimal("1"),
            "minimum_buffer_rate": Decimal("0"),
        }
    )

    run = run_sample_redemption_path(
        inputs,
        fund_id=fund.fund_id,
        strategy_id=strategy.liquidation_strategy_id,
        redemption_scenario_id=redemption.redemption_scenario_id,
        lmt_parameters_override=parameters,
        stress_months=(1, 2),
        random_seed=42,
        market_stress_id=None,
        market_stress_month=None,
        behavioural_feedback_enabled=True,
        behavioural_feedback_multiplier=Decimal("1.50"),
    )

    second_month_rows = [row for row in run.investor_rows if row["month"] == 2]

    assert second_month_rows
    assert {row["behavioural_feedback_source_outcome"] for row in second_month_rows} == {
        "swing_pricing"
    }
    assert {row["behavioural_feedback_multiplier"] for row in second_month_rows} == {
        Decimal("1.50")
    }


def test_streamlit_mvp_service_disables_behavioural_feedback_explicitly() -> None:
    inputs = load_app_sample_data(SAMPLE_DATA_DIR)
    fund = inputs.funds[0]
    strategy = inputs.liquidation_strategies[0]
    redemption = inputs.redemption_scenarios[0]
    scenario = next(item for item in inputs.scenario_definitions if item.fund_id == fund.fund_id)
    parameters = inputs.parameters_by_key[
        (scenario.fund_id, scenario.as_of_date, scenario.lmt_parameter_set_id)
    ].model_copy(
        update={
            "swing_threshold_rate": Decimal("0"),
            "gate_threshold_rate": Decimal("1"),
            "minimum_buffer_rate": Decimal("0"),
        }
    )

    run = run_sample_redemption_path(
        inputs,
        fund_id=fund.fund_id,
        strategy_id=strategy.liquidation_strategy_id,
        redemption_scenario_id=redemption.redemption_scenario_id,
        lmt_parameters_override=parameters,
        stress_months=(1, 2),
        random_seed=42,
        market_stress_id=None,
        market_stress_month=None,
        behavioural_feedback_enabled=False,
        behavioural_feedback_multiplier=Decimal("2"),
    )

    second_month_rows = [row for row in run.investor_rows if row["month"] == 2]

    assert {row["behavioural_feedback_source_outcome"] for row in second_month_rows} == {
        "swing_pricing"
    }
    assert {row["behavioural_feedback_multiplier"] for row in second_month_rows} == {Decimal("1")}


def test_streamlit_mvp_service_rejects_enabled_behavioural_feedback_below_one() -> None:
    inputs = load_app_sample_data(SAMPLE_DATA_DIR)
    fund = inputs.funds[0]
    strategy = inputs.liquidation_strategies[0]
    redemption = inputs.redemption_scenarios[0]

    with pytest.raises(ValueError, match="at least 1"):
        run_sample_redemption_path(
            inputs,
            fund_id=fund.fund_id,
            strategy_id=strategy.liquidation_strategy_id,
            redemption_scenario_id=redemption.redemption_scenario_id,
            lmt_parameters_override=None,
            stress_months=(1,),
            random_seed=42,
            market_stress_id=None,
            market_stress_month=None,
            behavioural_feedback_enabled=True,
            behavioural_feedback_multiplier=Decimal("0.99"),
        )


def test_t0_liquidity_profile_rows_include_cash_and_liquid_resources() -> None:
    inputs = load_app_sample_data(SAMPLE_DATA_DIR)
    fund = inputs.funds[0]
    positions = [
        position
        for position in inputs.positions
        if position.fund_id == fund.fund_id and position.as_of_date == fund.as_of_date
    ]

    rows = build_t0_liquidity_profile_rows(positions)
    rows_by_bucket = {str(row["liquidity_bucket"]): row for row in rows}

    assert list(rows_by_bucket) == [
        "Cash",
        "0-7 days",
        "8-30 days",
        ">30 days / constrained",
    ]
    assert rows_by_bucket["Cash"]["liquid_resources"] == Decimal("12000000")
    assert rows_by_bucket["0-7 days"]["liquid_resources"] > Decimal("0")
    assert rows_by_bucket["8-30 days"]["nav_amount"] > Decimal("0")
