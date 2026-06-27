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
from lmt_calibration.engines.liquidity_cost import estimate_liquidity_cost_breakdown
from lmt_calibration.engines.lmt_activation import LmtActivationResult, assess_lmt_impact
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
    current_nav_before_lmt_effects: Decimal
    redemption_amount: Decimal
    redemption_rate: Decimal
    positions: list[StressedLiquidationPosition]
    result: LiquidationResult
    liquidity_cost_breakdown: dict[str, Decimal]
    lmt_activation: LmtActivationResult


@dataclass(frozen=True)
class ScenarioMatrixOutcome:
    """Strategy-dependent financial values displayed in the scenario matrix."""

    realised_liquidity_cost: Decimal
    nav_before_lmt: Decimal
    estimated_swing_recovery: Decimal
    cost_recovered: Decimal
    nav_after_lmt: Decimal


def build_scenario_matrix_outcome(run: AppScenarioRun) -> ScenarioMatrixOutcome:
    """Reconcile matrix NAV values from the realised liquidation result."""

    gross_redemption_amount = run.result.total_redemption_amount
    realised_liquidity_cost = run.result.total_haircut_cost
    nav_before_lmt = max(
        run.current_nav_before_lmt_effects - gross_redemption_amount - realised_liquidity_cost,
        ZERO,
    )
    estimated_swing_recovery = (
        gross_redemption_amount * run.lmt_activation.estimated_liquidity_cost_rate
        if run.lmt_activation.swing_activated
        else ZERO
    )
    cost_recovered = min(estimated_swing_recovery, realised_liquidity_cost)
    nav_after_lmt = max(
        nav_before_lmt + run.lmt_activation.redemption_deferred_amount + cost_recovered,
        ZERO,
    )

    return ScenarioMatrixOutcome(
        realised_liquidity_cost=realised_liquidity_cost,
        nav_before_lmt=nav_before_lmt,
        estimated_swing_recovery=estimated_swing_recovery,
        cost_recovered=cost_recovered,
        nav_after_lmt=nav_after_lmt,
    )


def load_app_sample_data(sample_data_dir: Path) -> AppSampleData:
    """Load all sample files used by the Streamlit MVP."""

    funds = load_funds_csv(sample_data_dir / "funds.csv")
    positions = load_positions_csv(sample_data_dir / "positions.csv")
    investor_classes = load_investor_classes_csv(sample_data_dir / "investor_classes.csv")
    redemption_scenarios = load_redemption_scenarios_csv(
        sample_data_dir / "redemption_scenarios.csv"
    )
    market_stresses = load_market_stresses_csv(sample_data_dir / "market_stresses.csv")
    liquidity_stresses = load_liquidity_stresses_json(sample_data_dir / "liquidity_stresses.json")
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
    market_stress: MarketStress | None = None,
    lmt_parameters_override: LmtParameters | None = None,
    redemption_scenario_id_override: str | None = None,
) -> AppScenarioRun:
    """Assemble selected sample inputs and call the existing liquidation engine.

    Args:
        inputs: Sample data loaded from files.
        fund_id: Fund to run.
        strategy_id: Liquidation strategy to use.
        market_stress: Optional market stress to override the scenario's market stress.
            If provided, runs the scenario under this market condition instead.
        lmt_parameters_override: Optional LmtParameters to override loaded parameters.
            If provided, uses these parameters instead of loading from data.
        redemption_scenario_id_override: Optional RedemptionScenario ID to override the scenario's redemption scenario.
            If provided, uses this redemption scenario instead of the scenario's default.

    Returns:
        AppScenarioRun with computed results for the selected inputs.
    """

    scenario = _scenario_for_selection(inputs, fund_id=fund_id, strategy_id=strategy_id)
    fund = inputs.fund_by_key[(scenario.fund_id, scenario.as_of_date)]
    liquidity_stress = inputs.liquidity_stress_by_id[scenario.liquidity_stress_id]
    strategy = inputs.strategy_by_id[scenario.liquidation_strategy_id]
    parameters = (
        lmt_parameters_override
        or inputs.parameters_by_key[
            (scenario.fund_id, scenario.as_of_date, scenario.lmt_parameter_set_id)
        ]
    )

    # Use provided market stress or load from scenario
    if market_stress is None:
        market_stress = inputs.market_stress_by_id[scenario.market_stress_id]

    # Override redemption scenario if provided, then compute redemption amount
    if redemption_scenario_id_override:
        scenario = scenario.model_copy(
            update={"redemption_scenario_id": redemption_scenario_id_override}
        )

    liquidation_positions = _stressed_positions(inputs, scenario, market_stress=market_stress)
    current_nav_before_lmt_effects = sum(
        (position.stressed_market_value or ZERO for position in liquidation_positions),
        ZERO,
    )
    redemption_amount = _total_redemption_amount(inputs, scenario)
    redemption_rate = (
        redemption_amount / current_nav_before_lmt_effects
        if current_nav_before_lmt_effects > ZERO
        else ZERO
    )
    result = calculate_liquidation_strategy(
        scenario_id=scenario.scenario_id,
        fund=fund,
        positions=liquidation_positions,
        redemption_amount=redemption_amount,
        strategy=strategy,
        lmt_parameters=parameters,
        stress_horizon_days=liquidity_stress.stress_horizon_days,
    )

    # Calculate estimated liquidity costs and LMT activation
    liquidity_cost_breakdown = estimate_liquidity_cost_breakdown(redemption_amount, market_stress)
    lmt_activation = assess_lmt_impact(
        nav=current_nav_before_lmt_effects,
        redemption_rate=redemption_rate,
        market_stress=market_stress,
        lmt_parameters=parameters,
        remaining_liquid_buffer_rate=result.remaining_liquid_buffer_rate,
    )

    return AppScenarioRun(
        scenario=scenario,
        fund=fund,
        redemption=inputs.redemption_by_id[scenario.redemption_scenario_id],
        market_stress=market_stress,
        liquidity_stress=liquidity_stress,
        strategy=strategy,
        parameters=parameters,
        current_nav_before_lmt_effects=current_nav_before_lmt_effects,
        redemption_amount=redemption_amount,
        redemption_rate=redemption_rate,
        positions=liquidation_positions,
        result=result,
        liquidity_cost_breakdown=liquidity_cost_breakdown,
        lmt_activation=lmt_activation,
    )


def run_scenario_across_market_conditions(
    inputs: AppSampleData,
    *,
    fund_id: str,
    strategy_id: str,
    lmt_parameters_override: LmtParameters | None = None,
    redemption_scenario_id_override: str | None = None,
) -> list[AppScenarioRun]:
    """Run the same scenario across different market conditions for comparison.

    Args:
        inputs: Sample data loaded from files.
        fund_id: Fund to run.
        strategy_id: Liquidation strategy to use.
        lmt_parameters_override: Optional LmtParameters to override loaded parameters.
            If provided, uses these parameters for all runs.
        redemption_scenario_id_override: Optional RedemptionScenario ID to override the scenario's redemption scenario.
            If provided, uses this redemption scenario for all runs.

    Returns:
        List of AppScenarioRun objects, one for each market condition:
        1. Normal Market Conditions
        2. Moderate Market Stress
        3. Severe Market Stress
        4. Historical Crisis 2008

    All runs use the same fund, redemption scenario, liquidity stress, liquidation
    strategy, and LMT calibration, but vary the market shock applied.
    """
    market_condition_ids = [
        "normal_market_conditions",
        "moderate_market_stress",
        "severe_market_stress",
        "historical_crisis_2008",
    ]

    runs = []
    for market_stress_id in market_condition_ids:
        if market_stress_id in inputs.market_stress_by_id:
            market_stress = inputs.market_stress_by_id[market_stress_id]
            run = run_selected_sample_scenario(
                inputs,
                fund_id=fund_id,
                strategy_id=strategy_id,
                market_stress=market_stress,
                lmt_parameters_override=lmt_parameters_override,
                redemption_scenario_id_override=redemption_scenario_id_override,
            )
            runs.append(run)

    return runs


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
                "status": "Context only",
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
    market_stress: MarketStress | None = None,
) -> list[StressedLiquidationPosition]:
    liquidity_stress = inputs.liquidity_stress_by_id[scenario.liquidity_stress_id]

    # Use provided market stress or load from scenario
    if market_stress is None:
        market_stress = inputs.market_stress_by_id[scenario.market_stress_id]

    # Apply market shock to position values based on asset group sensitivity
    positions = [
        p
        for p in inputs.positions
        if p.fund_id == scenario.fund_id and p.as_of_date == scenario.as_of_date
    ]

    return [
        StressedLiquidationPosition(
            position_id=position.position_id,
            asset_group=position.asset_group,
            stressed_market_value=_shocked_market_value(position, market_stress),
            stressed_haircut_rate=_stressed_haircut_rate(position, liquidity_stress),
            stressed_liquidity_capacity_rate=_stressed_liquidity_capacity_rate(
                position,
                liquidity_stress,
            ),
            settlement_days=position.settlement_days,
            maturity_days=position.maturity_days,
            notional_amount=position.notional_amount,
        )
        for position in positions
    ]


def _shocked_market_value(
    position: AssetPosition,
    market_stress: MarketStress,
) -> Decimal:
    """Apply market shock to position value based on asset group sensitivity.

    Shock sensitivity:
    - cash, reverse_repo: 0 (no shock)
    - listed_etf, listed_equity: 1 (full shock)
    """
    # Handle positions without market value (e.g., repo_financing)
    if position.market_value is None:
        return ZERO

    shock_sensitivity = {
        AssetGroup.CASH: ZERO,
        AssetGroup.REVERSE_REPO: ZERO,
        AssetGroup.LISTED_ETF: ONE,
        AssetGroup.LISTED_EQUITY: ONE,
    }

    sensitivity = shock_sensitivity.get(position.asset_group, ZERO)
    shock_factor = ONE + (market_stress.market_shock_rate * sensitivity)
    return max(position.market_value * shock_factor, ZERO)


def _stressed_haircut_rate(
    position: AssetPosition,
    liquidity_stress: LiquidityStress,
) -> Decimal:
    if position.asset_group is AssetGroup.CASH:
        return ZERO

    # Get execution assumptions for this position's asset class
    execution_assumptions = liquidity_stress.execution_assumptions_by_asset_group.get(
        position.asset_group
    )
    if not execution_assumptions:
        # Fallback to base if not found (shouldn't happen with proper sample data)
        return position.base_haircut_rate

    # Apply liquidity haircut from execution assumptions
    return min(position.base_haircut_rate + execution_assumptions.liquidity_haircut_rate, ONE)


def _stressed_liquidity_capacity_rate(
    position: AssetPosition,
    liquidity_stress: LiquidityStress,
) -> Decimal:
    if position.asset_group is AssetGroup.CASH:
        return ONE

    # Get execution assumptions for this position's asset class
    execution_assumptions = liquidity_stress.execution_assumptions_by_asset_group.get(
        position.asset_group
    )
    if not execution_assumptions:
        # Fallback to base if not found (shouldn't happen with proper sample data)
        return position.base_liquidity_capacity_rate

    # Apply participation rate to base capacity
    return position.base_liquidity_capacity_rate * execution_assumptions.participation_rate
