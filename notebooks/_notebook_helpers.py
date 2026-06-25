"""Shared notebook helpers for educational liquidation notebooks."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from lmt_calibration.domain import (
    AssetGroup,  # Supported asset group labels, such as cash and listed_equity
    AssetPosition,  # Validated position-level holding or financing exposure
    FundSnapshot,  # Validated fund snapshot with NAV, currency, and dealing terms
    InvestorClassProfile,  # Validated investor-class redemption profile
    LiquidationResult,  # Structured output returned by the liquidation engine
    LiquidationStrategyConfig,  # Validated liquidation strategy configuration
    LiquidityStress,  # Reusable liquidity stress assumption
    LmtParameters,  # LMT threshold and minimum-buffer parameter set
    MarketStress,  # Reusable market stress assumption
    RedemptionScenario,  # Reusable redemption scenario assumption
    ScenarioDefinition,  # Scenario assembly linking fund, assumptions, strategy, and parameters
)
from lmt_calibration.engines import StressedLiquidationPosition, calculate_liquidation_strategy
from lmt_calibration.loaders import (
    load_funds_csv,
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
class SampleInputs:
    """Loaded sample objects and lookup maps used by notebooks."""

    funds: list[FundSnapshot]
    positions: list[AssetPosition]
    investor_classes: list[InvestorClassProfile]
    redemption_scenarios: list[RedemptionScenario]
    market_stresses: list[MarketStress]
    liquidity_stresses: list[LiquidityStress]
    scenario_definitions: list[ScenarioDefinition]
    lmt_parameters: list[LmtParameters]
    liquidation_strategies: list[LiquidationStrategyConfig]
    fund_by_key: dict[tuple[str, date], FundSnapshot]
    redemption_by_id: dict[str, RedemptionScenario]
    market_stress_by_id: dict[str, MarketStress]
    liquidity_stress_by_id: dict[str, LiquidityStress]
    strategy_by_id: dict[str, LiquidationStrategyConfig]
    parameters_by_key: dict[tuple[str, date, str], LmtParameters]


@dataclass(frozen=True)
class ScenarioRun:
    """A notebook-ready scenario assembled from loaded sample objects."""

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


def money(value: Decimal | int | float | None) -> str:
    """Format a money-like value for display."""

    if value is None:
        return ""
    return f"{Decimal(value):,.2f}"


def rate(value: Decimal | int | float | None) -> str:
    """Format a decimal rate for display."""

    if value is None:
        return ""
    return f"{Decimal(value) * Decimal('100'):.2f}%"


def days(value: int | None) -> str:
    """Format optional day counts for display."""

    if value is None:
        return ""
    return str(value)


def yes_no(value: bool) -> str:
    """Format booleans as reviewer-friendly labels."""

    return "yes" if value else "no"


def print_profile(profile: dict[str, object]) -> None:
    """Print a compact right-aligned key/value profile."""

    if not profile:
        return

    key_width = max(len(str(key)) for key in profile) + 2
    value_width = max(len(str(value)) for value in profile.values())

    for key, value in profile.items():
        label = f"{key}:"
        print(f"{label:>{key_width}} {str(value):>{value_width}}")


def load_sample_inputs(sample_data_dir: Path) -> SampleInputs:
    """Load all V1 sample files through the existing project loaders."""

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

    return SampleInputs(
        funds=funds,
        positions=positions,
        investor_classes=investor_classes,
        redemption_scenarios=redemption_scenarios,
        market_stresses=market_stresses,
        liquidity_stresses=liquidity_stresses,
        scenario_definitions=scenario_definitions,
        lmt_parameters=lmt_parameters,
        liquidation_strategies=liquidation_strategies,
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


def scenario_investors(
    inputs: SampleInputs,
    scenario: ScenarioDefinition,
) -> list[InvestorClassProfile]:
    """Return investor profiles matching a scenario fund snapshot."""

    return [
        investor
        for investor in inputs.investor_classes
        if investor.fund_id == scenario.fund_id and investor.as_of_date == scenario.as_of_date
    ]


def redemption_rows(
    inputs: SampleInputs,
    scenario: ScenarioDefinition,
) -> list[dict[str, object]]:
    """Build display rows for investor-class redemption contributions."""

    fund = inputs.fund_by_key[(scenario.fund_id, scenario.as_of_date)]
    redemption = inputs.redemption_by_id[scenario.redemption_scenario_id]
    rows: list[dict[str, object]] = []
    for investor in scenario_investors(inputs, scenario):
        redemption_amount = (
            fund.nav
            * investor.nav_share_rate
            * investor.stress_redemption_rate
            * redemption.redemption_multiplier
        )
        rows.append(
            {
                "client_class": investor.client_class.value,
                "nav_share_rate": investor.nav_share_rate,
                "stress_redemption_rate": investor.stress_redemption_rate,
                "redemption_multiplier": redemption.redemption_multiplier,
                "notice_days": investor.notice_days,
                "settlement_days": investor.settlement_days,
                "redemption_amount": redemption_amount,
            }
        )
    return rows


def total_redemption_amount(
    inputs: SampleInputs,
    scenario: ScenarioDefinition,
) -> Decimal:
    """Return total redemption amount for a loaded scenario."""

    return sum((row["redemption_amount"] for row in redemption_rows(inputs, scenario)), ZERO)


def scenario_positions(
    inputs: SampleInputs,
    scenario: ScenarioDefinition,
) -> list[StressedLiquidationPosition]:
    """Build stressed liquidation positions from loaded sample records."""

    liquidity_stress = inputs.liquidity_stress_by_id[scenario.liquidity_stress_id]
    return [
        StressedLiquidationPosition(
            position_id=position.position_id,
            asset_group=position.asset_group,
            stressed_market_value=position.market_value,
            stressed_haircut_rate=stressed_haircut_rate(position, liquidity_stress),
            stressed_liquidity_capacity_rate=stressed_liquidity_capacity_rate(
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


def stressed_haircut_rate(
    position: AssetPosition,
    liquidity_stress: LiquidityStress,
) -> Decimal:
    """Apply the sample liquidity stress haircut convention used by notebooks."""

    if position.asset_group is AssetGroup.CASH:
        return ZERO
    if liquidity_stress.liquidity_stress_multiplier == Decimal("1.00"):
        return ZERO
    return min(position.base_haircut_rate * liquidity_stress.liquidity_stress_multiplier, ONE)


def stressed_liquidity_capacity_rate(
    position: AssetPosition,
    liquidity_stress: LiquidityStress,
) -> Decimal:
    """Apply the sample liquidity stress capacity convention used by notebooks."""

    if position.asset_group is AssetGroup.CASH:
        return ONE
    return position.base_liquidity_capacity_rate / liquidity_stress.liquidity_stress_multiplier


def is_eligible(
    position: StressedLiquidationPosition,
    stress_horizon_days: int,
) -> bool:
    """Return whether a stressed position is sellable within the stress horizon."""

    if position.asset_group not in SELLABLE_GROUPS:
        return False
    if position.stressed_market_value is None or position.stressed_market_value <= ZERO:
        return False
    if position.asset_group is AssetGroup.REVERSE_REPO:
        if position.maturity_days is None:
            return False
        return position.maturity_days + position.settlement_days <= stress_horizon_days
    return position.settlement_days <= stress_horizon_days


def run_liquidation_scenario(
    inputs: SampleInputs,
    scenario: ScenarioDefinition,
) -> ScenarioRun:
    """Assemble loaded sample inputs and call the existing liquidation engine."""

    fund = inputs.fund_by_key[(scenario.fund_id, scenario.as_of_date)]
    liquidity_stress = inputs.liquidity_stress_by_id[scenario.liquidity_stress_id]
    strategy = inputs.strategy_by_id[scenario.liquidation_strategy_id]
    parameters = inputs.parameters_by_key[
        (scenario.fund_id, scenario.as_of_date, scenario.lmt_parameter_set_id)
    ]
    redemption_amount = total_redemption_amount(inputs, scenario)
    liquidation_positions = scenario_positions(inputs, scenario)
    result = calculate_liquidation_strategy(
        scenario_id=scenario.scenario_id,
        fund=fund,
        positions=liquidation_positions,
        redemption_amount=redemption_amount,
        strategy=strategy,
        lmt_parameters=parameters,
        stress_horizon_days=liquidity_stress.stress_horizon_days,
    )

    return ScenarioRun(
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


def scenario_from_selected_ids(
    inputs: SampleInputs,
    *,
    fund_id: str,
    redemption_scenario_id: str,
    liquidity_stress_id: str,
    lmt_parameter_id: str,
    strategy_id: str,
) -> ScenarioDefinition:
    """Create a notebook scenario from selected reusable sample IDs."""

    fund = next(fund for fund in inputs.funds if fund.fund_id == fund_id)
    template = next(
        scenario for scenario in inputs.scenario_definitions if scenario.fund_id == fund_id
    )
    return template.model_copy(
        update={
            "scenario_id": "notebook_selected_configuration",
            "fund_id": fund_id,
            "as_of_date": fund.as_of_date,
            "redemption_scenario_id": redemption_scenario_id,
            "liquidity_stress_id": liquidity_stress_id,
            "liquidation_strategy_id": strategy_id,
            "lmt_parameter_set_id": lmt_parameter_id,
        }
    )


def fund_positions(inputs: SampleInputs, fund: FundSnapshot) -> list[AssetPosition]:
    """Return raw loaded positions for a fund snapshot."""

    return [
        position
        for position in inputs.positions
        if position.fund_id == fund.fund_id and position.as_of_date == fund.as_of_date
    ]


def cash_total(positions: list[AssetPosition] | list[StressedLiquidationPosition]) -> Decimal:
    """Return the total cash market value in a position list."""

    return sum(
        (
            position.market_value
            if isinstance(position, AssetPosition)
            else position.stressed_market_value
        )
        or ZERO
        for position in positions
        if position.asset_group is AssetGroup.CASH
    )


def ordinary_portfolio_value(positions: list[AssetPosition]) -> Decimal:
    """Return market value excluding repo financing obligations."""

    return sum(
        (position.market_value or ZERO)
        for position in positions
        if position.asset_group is not AssetGroup.REPO_FINANCING
    )


def gross_sales(result: LiquidationResult) -> Decimal:
    """Return total gross sales from a liquidation result."""

    return sum((asset.gross_sale_amount for asset in result.assets_liquidated), ZERO)
