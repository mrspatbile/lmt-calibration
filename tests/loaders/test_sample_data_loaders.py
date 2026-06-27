from decimal import Decimal
from pathlib import Path

from lmt_calibration.domain import AssetGroup, LiquidationStrategyType
from lmt_calibration.loaders import (
    load_funds_csv,
    load_historical_market_stress_scenarios_json,
    load_investor_classes_csv,
    load_liquidation_strategies_json,
    load_liquidity_stresses_json,
    load_lmt_parameters_csv,
    load_market_stresses_csv,
    load_positions_csv,
    load_redemption_scenarios_csv,
    load_scenario_definitions_csv,
)

SAMPLE_DATA_DIR = Path("data/sample")


def test_sample_files_load_through_v1_loaders() -> None:
    funds = load_funds_csv(SAMPLE_DATA_DIR / "funds.csv")
    positions = load_positions_csv(SAMPLE_DATA_DIR / "positions.csv")
    investor_classes = load_investor_classes_csv(SAMPLE_DATA_DIR / "investor_classes.csv")
    redemption_scenarios = load_redemption_scenarios_csv(
        SAMPLE_DATA_DIR / "redemption_scenarios.csv"
    )
    market_stresses = load_market_stresses_csv(SAMPLE_DATA_DIR / "market_stresses.csv")
    liquidity_stresses = load_liquidity_stresses_json(SAMPLE_DATA_DIR / "liquidity_stresses.json")
    scenario_definitions = load_scenario_definitions_csv(
        SAMPLE_DATA_DIR / "scenario_definitions.csv"
    )
    lmt_parameters = load_lmt_parameters_csv(SAMPLE_DATA_DIR / "lmt_parameters.csv")
    liquidation_strategies = load_liquidation_strategies_json(
        SAMPLE_DATA_DIR / "liquidation_strategies.json"
    )
    historical_market_stress_scenarios = load_historical_market_stress_scenarios_json(
        SAMPLE_DATA_DIR / "historical_market_stress_scenarios.json"
    )

    assert funds
    assert positions
    assert investor_classes
    assert redemption_scenarios
    assert market_stresses
    assert liquidity_stresses
    assert scenario_definitions
    assert lmt_parameters
    assert liquidation_strategies
    assert historical_market_stress_scenarios.scenarios


def test_sample_position_values_reconcile_to_nav_excluding_repo_financing() -> None:
    fund = load_funds_csv(SAMPLE_DATA_DIR / "funds.csv")[0]
    positions = load_positions_csv(SAMPLE_DATA_DIR / "positions.csv")

    ordinary_asset_value = sum(
        position.market_value or Decimal("0")
        for position in positions
        if position.asset_group is not AssetGroup.REPO_FINANCING
    )
    repo_financing_positions = [
        position for position in positions if position.asset_group is AssetGroup.REPO_FINANCING
    ]

    assert ordinary_asset_value == fund.nav
    assert repo_financing_positions
    assert repo_financing_positions[0].notional_amount == Decimal("5000000")


def test_sample_investor_class_nav_shares_sum_to_one() -> None:
    investor_classes = load_investor_classes_csv(SAMPLE_DATA_DIR / "investor_classes.csv")

    total_nav_share = sum(investor_class.nav_share_rate for investor_class in investor_classes)

    assert total_nav_share == Decimal("1.00")


def test_sample_data_uses_only_v1_asset_universe() -> None:
    positions = load_positions_csv(SAMPLE_DATA_DIR / "positions.csv")
    v1_asset_groups = {
        AssetGroup.CASH,
        AssetGroup.LISTED_EQUITY,
        AssetGroup.LISTED_ETF,
        AssetGroup.REVERSE_REPO,
        AssetGroup.REPO_FINANCING,
    }

    assert {position.asset_group for position in positions} <= v1_asset_groups


def test_sample_scenarios_cover_all_v1_liquidation_strategies() -> None:
    scenario_definitions = load_scenario_definitions_csv(
        SAMPLE_DATA_DIR / "scenario_definitions.csv"
    )
    liquidation_strategies = load_liquidation_strategies_json(
        SAMPLE_DATA_DIR / "liquidation_strategies.json"
    )

    strategy_ids = {strategy.liquidation_strategy_id for strategy in liquidation_strategies}
    scenario_strategy_ids = {scenario.liquidation_strategy_id for scenario in scenario_definitions}
    strategy_types = {strategy.strategy_type for strategy in liquidation_strategies}

    assert scenario_strategy_ids == strategy_ids
    assert strategy_types == {
        LiquidationStrategyType.MOST_LIQUID_FIRST,
        LiquidationStrategyType.PRO_RATA,
        LiquidationStrategyType.HYBRID,
        LiquidationStrategyType.CUSTOM_WEIGHTS,
    }
