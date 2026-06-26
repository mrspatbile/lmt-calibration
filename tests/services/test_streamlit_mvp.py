from decimal import Decimal
from pathlib import Path

from lmt_calibration.services import (
    build_historical_result_rows,
    load_app_sample_data,
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
