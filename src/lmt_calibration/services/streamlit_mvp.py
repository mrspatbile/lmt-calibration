"""Thin orchestration helpers for the Streamlit MVP.

The helpers load validated sample inputs and call the existing liquidation
engine. They do not apply historical market shocks or calculate LMT thresholds.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from lmt_calibration.domain import (
    AssetGroup,
    AssetPosition,
    FundSnapshot,
    HistoricalMarketStressScenarioLibrary,
    InvestorClassProfile,
    LiquidationResult,
    LiquidationStrategyConfig,
    LiquidityStress,
    LmtParameters,
    MarketStress,
    RedemptionScenario,
    ScenarioDefinition,
)
from lmt_calibration.engines import StressedLiquidationPosition, calculate_liquidation_strategy
from lmt_calibration.loaders import (
    load_funds_csv,
    load_historical_market_stress_scenarios_json,
    load_investor_classes_csv,
    load_liquidation_strategies_json,
    load_liquidity_stresses_csv,
    load_lmt_parameters_csv,
    load_market_stresses_csv,
    load_positions_csv,
    load_redemption_scenarios_csv,
    load_scenario_definitions_csv,
)

ZERO = Decimal("0")
ONE = Decimal("1")

SELLABLE_GROUPS = {
    AssetGroup.REVERSE_REPO,
    AssetGroup.LISTED_ETF,
    AssetGroup.LISTED_EQUITY,
}


@dataclass(frozen=True)
class AppSampleData:
    """Loaded sample data and lookup maps for the Streamlit MVP."""

    funds: list[FundSnapshot]
    positions: list[AssetPosition]
    investor_classes: list[InvestorClassProfile]
    redemption_scenarios: list[RedemptionScenario]
    market_stresses: list[MarketStress]
    liquidity_stresses: list[LiquidityStress]
    scenario_definitions: list[ScenarioDefinition]
    lmt_parameters: list[LmtParameters]
    liquidation_strategies: list[LiquidationStrategyConfig]
    historical_market_stresses: HistoricalMarketStressScenarioLibrary
    fund_by_key: dict[tuple[str, date], FundSnapshot]
    redemption_by_id: dict[str, RedemptionScenario]
    market_stress_by_id: dict[str, MarketStress]
    liquidity_stress_by_id: dict[str, LiquidityStress]
    strategy_by_id: dict[str, LiquidationStrategyConfig]
    parameters_by_key: dict[tuple[str, date, str], LmtParameters]


@dataclass(frozen=True)
class AppScenarioRun:
    """Selected sample scenario and already-calculated liquidation output."""

    scenario: ScenarioDefinition
    fund: FundSnapshot
    redemption: RedemptionScenario
    market_stress: MarketStress
    liquidity_stress: LiquidityStress
    strategy: LiquidationStrategyConfig
    parameters: LmtParameters
    redemption_amount: Decimal
    positions: list[StressedLiquidationPosition]
    result: LiquidationResult


def load_app_sample_data(sample_data_dir: Path) -> AppSampleData:
    """Load all sample files used by the Streamlit MVP."""

    funds = load_funds_csv(sample_data_dir / "funds.csv")
    positions = load_positions_csv(sample_data_dir / "positions.csv")
    investor_classes = load_investor_classes_csv(sample_data_dir / "investor_classes.csv")
    redemption_scenarios = load_redemption_scenarios_csv(
        sample_data_dir / "redemption_scenarios.csv"
    )
    market_stresses = load_market_stresses_csv(sample_data_dir / "market_stresses.csv")
    liquidity_stresses = load_liquidity_stresses_csv(sample_data_dir / "liquidity_stresses.csv")
    scenario_definitions = load_scenario_definitions_csv(
        sample_data_dir / "scenario_definitions.csv"
    )
    lmt_parameters = load_lmt_parameters_csv(sample_data_dir / "lmt_parameters.csv")
    liquidation_strategies = load_liquidation_strategies_json(
        sample_data_dir / "liquidation_strategies.json"
    )
    historical_market_stresses = load_historical_market_stress_scenarios_json(
        sample_data_dir / "historical_market_stress_scenarios.json"
    )

    return AppSampleData(
        funds=funds,
        positions=positions,
        investor_classes=investor_classes,
        redemption_scenarios=redemption_scenarios,
        market_stresses=market_stresses,
        liquidity_stresses=liquidity_stresses,
        scenario_definitions=scenario_definitions,
        lmt_parameters=lmt_parameters,
        liquidation_strategies=liquidation_strategies,
        historical_market_stresses=historical_market_stresses,
        fund_by_key={(fund.fund_id, fund.as_of_date): fund for fund in funds},
        redemption_by_id={
            scenario.redemption_scenario_id: scenario for scenario in redemption_scenarios
        },
        market_stress_by_id={stress.market_stress_id: stress for stress in market_stresses},
        liquidity_stress_by_id={
            stress.liquidity_stress_id: stress for stress in liquidity_stresses
        },
        strategy_by_id={
            strategy.liquidation_strategy_id: strategy for strategy in liquidation_strategies
        },
        parameters_by_key={
            (parameters.fund_id, parameters.as_of_date, parameters.parameter_set_id): parameters
            for parameters in lmt_parameters
        },
    )


def run_selected_sample_scenario(
    inputs: AppSampleData,
    *,
    fund_id: str,
    strategy_id: str,
) -> AppScenarioRun:
    """Assemble selected sample inputs and call the existing liquidation engine."""

    scenario = _scenario_for_selection(inputs, fund_id=fund_id, strategy_id=strategy_id)
    fund = inputs.fund_by_key[(scenario.fund_id, scenario.as_of_date)]
    liquidity_stress = inputs.liquidity_stress_by_id[scenario.liquidity_stress_id]
    strategy = inputs.strategy_by_id[scenario.liquidation_strategy_id]
    parameters = inputs.parameters_by_key[
        (scenario.fund_id, scenario.as_of_date, scenario.lmt_parameter_set_id)
    ]
    redemption_amount = _total_redemption_amount(inputs, scenario)
    liquidation_positions = _stressed_positions(inputs, scenario)
    result = calculate_liquidation_strategy(
        scenario_id=scenario.scenario_id,
        fund=fund,
        positions=liquidation_positions,
        redemption_amount=redemption_amount,
        strategy=strategy,
        lmt_parameters=parameters,
        stress_horizon_days=liquidity_stress.stress_horizon_days,
    )

    return AppScenarioRun(
        scenario=scenario,
        fund=fund,
        redemption=inputs.redemption_by_id[scenario.redemption_scenario_id],
        market_stress=inputs.market_stress_by_id[scenario.market_stress_id],
        liquidity_stress=liquidity_stress,
        strategy=strategy,
        parameters=parameters,
        redemption_amount=redemption_amount,
        positions=liquidation_positions,
        result=result,
    )


def build_historical_result_rows(
    inputs: AppSampleData, run: AppScenarioRun
) -> list[dict[str, object]]:
    """Return rows pairing historical context with the current sample workflow output."""

    rows: list[dict[str, object]] = []
    for scenario_id, historical_scenario in inputs.historical_market_stresses.scenarios.items():
        rows.append(
            {
                "scenario_id": scenario_id,
                "scenario": historical_scenario.scenario_name,
                "period": historical_scenario.period,
                "holding_period_days": historical_scenario.holding_period_days,
                "cash_used": run.result.cash_used,
                "post_haircut_cash_raised": run.result.total_post_haircut_cash_raised,
                "shortfall": run.result.shortfall,
                "dilution": run.result.dilution_amount,
                "remaining_buffer": run.result.remaining_liquid_buffer_rate,
            }
        )
    return rows


def fund_positions(inputs: AppSampleData, fund: FundSnapshot) -> list[AssetPosition]:
    """Return raw loaded positions for one fund snapshot."""

    return [
        position
        for position in inputs.positions
        if position.fund_id == fund.fund_id and position.as_of_date == fund.as_of_date
    ]


def _scenario_for_selection(
    inputs: AppSampleData,
    *,
    fund_id: str,
    strategy_id: str,
) -> ScenarioDefinition:
    fund = next(fund for fund in inputs.funds if fund.fund_id == fund_id)
    template = next(
        scenario for scenario in inputs.scenario_definitions if scenario.fund_id == fund_id
    )
    return template.model_copy(
        update={
            "scenario_id": "streamlit_selected_configuration",
            "fund_id": fund_id,
            "as_of_date": fund.as_of_date,
            "liquidation_strategy_id": strategy_id,
        }
    )


def _scenario_investors(
    inputs: AppSampleData,
    scenario: ScenarioDefinition,
) -> list[InvestorClassProfile]:
    return [
        investor
        for investor in inputs.investor_classes
        if investor.fund_id == scenario.fund_id and investor.as_of_date == scenario.as_of_date
    ]


def _total_redemption_amount(inputs: AppSampleData, scenario: ScenarioDefinition) -> Decimal:
    fund = inputs.fund_by_key[(scenario.fund_id, scenario.as_of_date)]
    redemption = inputs.redemption_by_id[scenario.redemption_scenario_id]
    return sum(
        (
            fund.nav
            * investor.nav_share_rate
            * investor.stress_redemption_rate
            * redemption.redemption_multiplier
            for investor in _scenario_investors(inputs, scenario)
        ),
        ZERO,
    )


def _stressed_positions(
    inputs: AppSampleData,
    scenario: ScenarioDefinition,
) -> list[StressedLiquidationPosition]:
    liquidity_stress = inputs.liquidity_stress_by_id[scenario.liquidity_stress_id]
    return [
        StressedLiquidationPosition(
            position_id=position.position_id,
            asset_group=position.asset_group,
            stressed_market_value=position.market_value,
            stressed_haircut_rate=_stressed_haircut_rate(position, liquidity_stress),
            stressed_liquidity_capacity_rate=_stressed_liquidity_capacity_rate(
                position,
                liquidity_stress,
            ),
            settlement_days=position.settlement_days,
            maturity_days=position.maturity_days,
            notional_amount=position.notional_amount,
        )
        for position in inputs.positions
        if position.fund_id == scenario.fund_id and position.as_of_date == scenario.as_of_date
    ]


def _stressed_haircut_rate(
    position: AssetPosition,
    liquidity_stress: LiquidityStress,
) -> Decimal:
    if position.asset_group is AssetGroup.CASH:
        return ZERO
    if liquidity_stress.liquidity_stress_multiplier == Decimal("1.00"):
        return ZERO
    return min(position.base_haircut_rate * liquidity_stress.liquidity_stress_multiplier, ONE)


def _stressed_liquidity_capacity_rate(
    position: AssetPosition,
    liquidity_stress: LiquidityStress,
) -> Decimal:
    if position.asset_group is AssetGroup.CASH:
        return ONE
    return position.base_liquidity_capacity_rate / liquidity_stress.liquidity_stress_multiplier
