from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest

from lmt_calibration.services import (
    build_historical_result_rows,
    build_t0_liquidity_profile_rows,
    load_app_sample_data,
    run_sample_redemption_path,
    run_selected_sample_scenario,
    streamlit_mvp,
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
        behavioural_feedback_multiplier=Decimal("1"),
        market_contagion_liquidity_cost_multiplier=Decimal("1"),
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
        "Liquidation days per month",
        "LMT application mode",
        "Applied swing pricing months",
        "Applied gate months",
        "Applied suspension months",
        "Behavioural feedback",
        "Market contagion",
    }
    assert (
        next(
            row["value"]
            for row in run.configuration_rows
            if row["setting"] == "Liquidation days per month"
        )
        == 20
    )


def test_streamlit_path_passes_empty_applied_months_when_no_lmt_is_selected() -> None:
    inputs = load_app_sample_data(SAMPLE_DATA_DIR)
    fund = inputs.funds[0]
    strategy = inputs.liquidation_strategies[0]
    redemption = inputs.redemption_scenarios[0]
    with patch.object(
        streamlit_mvp,
        "run_redemption_path",
        wraps=streamlit_mvp.run_redemption_path,
    ) as engine_mock:
        run = run_sample_redemption_path(
            inputs,
            fund_id=fund.fund_id,
            strategy_id=strategy.liquidation_strategy_id,
            redemption_scenario_id=redemption.redemption_scenario_id,
            lmt_parameters_override=None,
            stress_months=(1,),
            random_seed=42,
            market_stress_id=None,
            market_stress_month=None,
            behavioural_feedback_multiplier=Decimal("1"),
            market_contagion_liquidity_cost_multiplier=Decimal("1"),
        )

    assumptions = engine_mock.call_args.kwargs["assumptions"]
    assert assumptions.apply_lmts_in_all_signal_months is False
    assert assumptions.swing_pricing_months == ()
    assert assumptions.gate_months == ()
    assert assumptions.suspension_months == ()
    assert all(not row["gate_applied"] for row in run.lmt_timeline_rows)
    assert all(not row["suspension_applied"] for row in run.lmt_timeline_rows)
    assert all(
        row["cumulative_backlog"] == run.result.monthly_results[index].backlog_cash_value
        for index, row in enumerate(run.monthly_rows)
    )
    assert all(
        row["liquidity_shortfall"] == run.result.monthly_results[index].liquidation_result.shortfall
        for index, row in enumerate(run.monthly_rows)
    )


def test_page_one_threshold_assessment_remains_automatic() -> None:
    inputs = load_app_sample_data(SAMPLE_DATA_DIR)
    fund = inputs.funds[0]
    strategy = inputs.liquidation_strategies[0]
    scenario = next(item for item in inputs.scenario_definitions if item.fund_id == fund.fund_id)
    parameters = inputs.parameters_by_key[
        (scenario.fund_id, scenario.as_of_date, scenario.lmt_parameter_set_id)
    ].model_copy(
        update={
            "swing_threshold_rate": Decimal("0"),
            "gate_threshold_rate": Decimal("0"),
        }
    )

    run = run_selected_sample_scenario(
        inputs,
        fund_id=fund.fund_id,
        strategy_id=strategy.liquidation_strategy_id,
        lmt_parameters_override=parameters,
    )

    assert run.lmt_activation.swing_activated is True
    assert run.lmt_activation.gate_activated is True
    assert run.lmt_activation.redemption_deferred_amount > Decimal("0")


def test_page_one_does_not_apply_monthly_liquidation_capacity_scaling() -> None:
    inputs = load_app_sample_data(SAMPLE_DATA_DIR)
    fund = inputs.funds[0]
    strategy = next(
        item
        for item in inputs.liquidation_strategies
        if item.liquidation_strategy_id == "cash_then_liquid_assets"
    )

    run = run_selected_sample_scenario(
        inputs,
        fund_id=fund.fund_id,
        strategy_id=strategy.liquidation_strategy_id,
    )

    sap_position = next(
        position for position in run.positions if position.position_id == "sap_equity_position"
    )
    assert sap_position.stressed_liquidity_capacity_rate == Decimal("0.06000")


def test_streamlit_mvp_service_reports_user_selected_suspension() -> None:
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
        suspension_months=(2,),
        random_seed=42,
        market_stress_id=None,
        market_stress_month=None,
        behavioural_feedback_multiplier=Decimal("1"),
        market_contagion_liquidity_cost_multiplier=Decimal("1"),
    )

    assert [row["suspension_applied"] for row in run.lmt_timeline_rows[:3]] == [
        False,
        True,
        False,
    ]
    assert run.lmt_timeline_rows[1]["priority_outcome"] == "suspension"
    assert (
        next(
            row["value"]
            for row in run.configuration_rows
            if row["setting"] == "Applied suspension months"
        )
        == "2"
    )


def test_streamlit_mvp_signal_linked_mode_applies_swing_and_gate_without_suspension() -> None:
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
            "gate_threshold_rate": Decimal("0"),
        }
    )

    run = run_sample_redemption_path(
        inputs,
        fund_id=fund.fund_id,
        strategy_id=strategy.liquidation_strategy_id,
        redemption_scenario_id=redemption.redemption_scenario_id,
        lmt_parameters_override=parameters,
        stress_months=(1,),
        random_seed=42,
        market_stress_id=None,
        market_stress_month=None,
        behavioural_feedback_multiplier=Decimal("1"),
        market_contagion_liquidity_cost_multiplier=Decimal("1"),
        apply_lmts_in_all_signal_months=True,
    )

    assert all(row["swing_signal"] == row["swing_applied"] for row in run.lmt_timeline_rows)
    assert all(row["gate_signal"] == row["gate_applied"] for row in run.lmt_timeline_rows)
    assert all(not row["suspension_applied"] for row in run.lmt_timeline_rows)
    assert (
        next(
            row["value"]
            for row in run.configuration_rows
            if row["setting"] == "LMT application mode"
        )
        == "All signal months"
    )


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
        behavioural_feedback_multiplier=Decimal("1"),
        market_contagion_liquidity_cost_multiplier=Decimal("1"),
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
        swing_pricing_months=(1,),
        random_seed=42,
        market_stress_id=None,
        market_stress_month=None,
        behavioural_feedback_multiplier=Decimal("1.50"),
        market_contagion_liquidity_cost_multiplier=Decimal("1"),
    )

    second_month_rows = [row for row in run.investor_rows if row["month"] == 2]

    assert second_month_rows
    assert {row["behavioural_feedback_source_outcome"] for row in second_month_rows} == {
        "swing_pricing"
    }
    assert {row["behavioural_feedback_multiplier"] for row in second_month_rows} == {
        Decimal("1.50")
    }


def test_streamlit_mvp_service_uses_one_as_neutral_behavioural_feedback() -> None:
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
        swing_pricing_months=(1,),
        random_seed=42,
        market_stress_id=None,
        market_stress_month=None,
        behavioural_feedback_multiplier=Decimal("1"),
        market_contagion_liquidity_cost_multiplier=Decimal("1"),
    )

    second_month_rows = [row for row in run.investor_rows if row["month"] == 2]

    assert {row["behavioural_feedback_source_outcome"] for row in second_month_rows} == {
        "swing_pricing"
    }
    assert {row["behavioural_feedback_multiplier"] for row in second_month_rows} == {Decimal("1")}


def test_streamlit_mvp_service_rejects_behavioural_feedback_below_one() -> None:
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
            behavioural_feedback_multiplier=Decimal("0.99"),
            market_contagion_liquidity_cost_multiplier=Decimal("1"),
        )


def test_streamlit_mvp_service_applies_market_contagion_after_market_stress() -> None:
    inputs = load_app_sample_data(SAMPLE_DATA_DIR)
    fund = inputs.funds[0]
    strategy = inputs.liquidation_strategies[0]
    redemption = inputs.redemption_scenarios[0]
    market_stress = inputs.market_stresses[0]
    scenario = next(item for item in inputs.scenario_definitions if item.fund_id == fund.fund_id)
    parameters = inputs.parameters_by_key[
        (scenario.fund_id, scenario.as_of_date, scenario.lmt_parameter_set_id)
    ].model_copy(update={"minimum_buffer_rate": Decimal("0.30")})

    run = run_sample_redemption_path(
        inputs,
        fund_id=fund.fund_id,
        strategy_id=strategy.liquidation_strategy_id,
        redemption_scenario_id=redemption.redemption_scenario_id,
        lmt_parameters_override=parameters,
        stress_months=(1, 2, 3),
        random_seed=42,
        market_stress_id=market_stress.market_stress_id,
        market_stress_month=1,
        behavioural_feedback_multiplier=Decimal("1"),
        market_contagion_liquidity_cost_multiplier=Decimal("1.50"),
    )

    assert [row["market_contagion_applied"] for row in run.monthly_rows[:3]] == [
        False,
        True,
        False,
    ]
    second_month = run.monthly_rows[1]
    assert second_month["adjusted_estimated_liquidity_cost_rate"] == (
        second_month["base_estimated_liquidity_cost_rate"] * Decimal("1.50")
    )
    assert second_month["realised_execution_cost"] > Decimal("0")
    assert second_month["realised_liquidity_cost"] >= second_month["realised_execution_cost"]
    assert second_month["gross_asset_sales"] > Decimal("0")
    assert next(
        row["value"] for row in run.configuration_rows if row["setting"] == "Market contagion"
    ) == Decimal("1.50")


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
