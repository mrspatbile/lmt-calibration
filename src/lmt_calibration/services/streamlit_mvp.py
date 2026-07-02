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
    ClientClass,
    FundSnapshot,
    HistoricalMarketStressScenarioLibrary,
    InvestorClassProfile,
    LiquidationResult,
    LiquidationStrategyConfig,
    LiquidityStress,
    LmtParameters,
    MarketStress,
    PathLmtOutcome,
    PathPositionState,
    RedemptionPathAssumptions,
    RedemptionPathResult,
    RedemptionScenario,
    ScenarioDefinition,
)
from lmt_calibration.engines import StressedLiquidationPosition, calculate_liquidation_strategy
from lmt_calibration.engines.liquidity_cost import estimate_liquidity_cost_breakdown
from lmt_calibration.engines.lmt_activation import LmtActivationResult, assess_lmt_impact
from lmt_calibration.engines.redemption_path import run_redemption_path
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

LIQUIDITY_BUCKETS = (
    "Cash",
    "0-7 days",
    "8-30 days",
    ">30 days / constrained",
)


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
    initial_snapshot_nav: Decimal
    current_pre_lmt_nav: Decimal
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
    nav_after_redemption_before_lmt: Decimal
    estimated_swing_recovery: Decimal
    cost_recovered: Decimal
    current_post_lmt_nav: Decimal
    remaining_liquid_buffer_rate_before_lmt: Decimal
    remaining_liquid_buffer_rate_after_lmt: Decimal


@dataclass(frozen=True)
class AppRedemptionPathRun:
    """Selected sample redemption-path run and presentation-ready rows."""

    scenario: ScenarioDefinition
    fund: FundSnapshot
    redemption: RedemptionScenario
    market_stress: MarketStress | None
    liquidity_stress: LiquidityStress
    strategy: LiquidationStrategyConfig
    parameters: LmtParameters
    result: RedemptionPathResult
    liquidity_profile_rows: list[dict[str, object]]
    monthly_rows: list[dict[str, object]]
    investor_rows: list[dict[str, object]]
    lmt_timeline_rows: list[dict[str, object]]
    configuration_rows: list[dict[str, object]]


def build_scenario_matrix_outcome(run: AppScenarioRun) -> ScenarioMatrixOutcome:
    """Reconcile matrix NAV values from the realised liquidation result."""

    realised_liquidity_cost = run.result.total_haircut_cost
    estimated_swing_recovery = run.lmt_activation.theoretical_recovery_amount
    cost_recovered = run.lmt_activation.applied_cost_recovery_amount

    return ScenarioMatrixOutcome(
        realised_liquidity_cost=realised_liquidity_cost,
        nav_after_redemption_before_lmt=run.lmt_activation.nav_after_redemption_before_lmt,
        estimated_swing_recovery=estimated_swing_recovery,
        cost_recovered=cost_recovered,
        current_post_lmt_nav=run.lmt_activation.current_post_lmt_nav,
        remaining_liquid_buffer_rate_before_lmt=run.result.remaining_liquid_buffer_rate,
        remaining_liquid_buffer_rate_after_lmt=run.lmt_activation.remaining_liquid_buffer_rate,
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
    current_pre_lmt_nav = sum(
        (position.stressed_market_value or ZERO for position in liquidation_positions),
        ZERO,
    )
    redemption_amount = _total_redemption_amount(inputs, scenario)
    redemption_rate = (
        redemption_amount / current_pre_lmt_nav if current_pre_lmt_nav > ZERO else ZERO
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

    asset_group_market_values = _asset_group_market_values(liquidation_positions)
    liquidity_cost_breakdown = estimate_liquidity_cost_breakdown(
        redemption_amount,
        liquidity_stress,
        asset_group_market_values,
    )
    lmt_activation = assess_lmt_impact(
        nav=current_pre_lmt_nav,
        redemption_rate=redemption_rate,
        estimated_execution_cost_rate=liquidity_cost_breakdown["total_cost_rate"],
        lmt_parameters=parameters,
        realised_liquidation_cost=result.total_haircut_cost,
        remaining_liquid_resources=result.remaining_liquid_resources,
    )

    return AppScenarioRun(
        scenario=scenario,
        fund=fund,
        redemption=inputs.redemption_by_id[scenario.redemption_scenario_id],
        market_stress=market_stress,
        liquidity_stress=liquidity_stress,
        strategy=strategy,
        parameters=parameters,
        initial_snapshot_nav=fund.nav,
        current_pre_lmt_nav=current_pre_lmt_nav,
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

    outcome = build_scenario_matrix_outcome(run)
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
                "remaining_buffer": outcome.remaining_liquid_buffer_rate_after_lmt,
                "status": "Context only",
            }
        )
    return rows


def run_sample_redemption_path(
    inputs: AppSampleData,
    *,
    fund_id: str,
    strategy_id: str,
    redemption_scenario_id: str,
    lmt_parameters_override: LmtParameters | None,
    stress_months: tuple[int, ...],
    random_seed: int,
    market_stress_id: str | None,
    market_stress_month: int | None,
    behavioural_feedback_multiplier: Decimal,
    market_contagion_liquidity_cost_multiplier: Decimal,
    swing_pricing_months: tuple[int, ...] = (),
    gate_months: tuple[int, ...] = (),
    suspension_months: tuple[int, ...] = (),
    apply_lmts_in_all_signal_months: bool = False,
    liquidation_days_per_month: int = 20,
) -> AppRedemptionPathRun:
    """Assemble sample inputs and run the fixed monthly redemption path."""

    scenario = _scenario_for_selection(inputs, fund_id=fund_id, strategy_id=strategy_id)
    scenario = scenario.model_copy(update={"redemption_scenario_id": redemption_scenario_id})
    fund = inputs.fund_by_key[(scenario.fund_id, scenario.as_of_date)]
    redemption = inputs.redemption_by_id[redemption_scenario_id]
    liquidity_stress = inputs.liquidity_stress_by_id[scenario.liquidity_stress_id]
    strategy = inputs.strategy_by_id[strategy_id]
    parameters = (
        lmt_parameters_override
        or inputs.parameters_by_key[
            (scenario.fund_id, scenario.as_of_date, scenario.lmt_parameter_set_id)
        ]
    )
    market_stress = (
        inputs.market_stress_by_id[market_stress_id] if market_stress_id is not None else None
    )
    investor_profiles = _path_investors(inputs, scenario, redemption)
    positions = fund_positions(inputs, fund)
    assumptions = RedemptionPathAssumptions(
        scenario_id=f"{scenario.scenario_id}_redemption_path",
        start_date=fund.as_of_date,
        stress_months=stress_months,
        swing_pricing_months=swing_pricing_months,
        gate_months=gate_months,
        suspension_months=suspension_months,
        apply_lmts_in_all_signal_months=apply_lmts_in_all_signal_months,
        market_stress_month=market_stress_month,
        random_seed=random_seed,
        liquidation_days_per_month=liquidation_days_per_month,
        market_contagion_liquidity_cost_multiplier=(market_contagion_liquidity_cost_multiplier),
        behavioural_feedback_multipliers_by_outcome=(
            _behavioural_feedback_multipliers_by_outcome(
                investor_profiles,
                behavioural_feedback_multiplier=behavioural_feedback_multiplier,
            )
        ),
    )
    result = run_redemption_path(
        fund=fund,
        positions=positions,
        investor_profiles=investor_profiles,
        liquidity_stress=liquidity_stress,
        liquidation_strategy=strategy,
        lmt_parameters=parameters,
        assumptions=assumptions,
        market_stress=market_stress,
    )

    liquidity_profile_rows = build_t0_liquidity_profile_rows(positions)
    monthly_rows = build_redemption_path_monthly_rows(result)
    investor_rows = build_redemption_path_investor_rows(result)
    lmt_timeline_rows = build_redemption_path_lmt_timeline_rows(result)
    configuration_rows = build_redemption_path_configuration_rows(
        run=result,
        market_stress=market_stress,
        redemption=redemption,
        strategy=strategy,
        parameters=parameters,
        stress_months=stress_months,
        liquidation_days_per_month=liquidation_days_per_month,
        apply_lmts_in_all_signal_months=apply_lmts_in_all_signal_months,
        behavioural_feedback_multiplier=behavioural_feedback_multiplier,
        market_contagion_liquidity_cost_multiplier=(market_contagion_liquidity_cost_multiplier),
    )

    return AppRedemptionPathRun(
        scenario=scenario,
        fund=fund,
        redemption=redemption,
        market_stress=market_stress,
        liquidity_stress=liquidity_stress,
        strategy=strategy,
        parameters=parameters,
        result=result,
        liquidity_profile_rows=liquidity_profile_rows,
        monthly_rows=monthly_rows,
        investor_rows=investor_rows,
        lmt_timeline_rows=lmt_timeline_rows,
        configuration_rows=configuration_rows,
    )


def build_t0_liquidity_profile_rows(
    positions: list[AssetPosition],
) -> list[dict[str, object]]:
    """Return t0 liquid-resource rows by liquidity bucket for display."""

    rows_by_bucket: dict[str, dict[str, object]] = {
        bucket: {
            "liquidity_bucket": bucket,
            "nav_amount": ZERO,
            "liquid_resources": ZERO,
            "unavailable_nav": ZERO,
            "bucket_order": _liquidity_bucket_order(bucket),
        }
        for bucket in LIQUIDITY_BUCKETS
    }
    for position in positions:
        market_value = position.market_value or ZERO
        if market_value <= ZERO:
            continue
        bucket = _liquidity_bucket(position)
        liquid_resources = _t0_liquid_resources(position, market_value)
        row = rows_by_bucket[bucket]
        row["nav_amount"] = Decimal(str(row["nav_amount"])) + market_value
        row["liquid_resources"] = Decimal(str(row["liquid_resources"])) + liquid_resources
        row["unavailable_nav"] = Decimal(str(row["unavailable_nav"])) + max(
            market_value - liquid_resources,
            ZERO,
        )

    return sorted(
        rows_by_bucket.values(),
        key=lambda row: _liquidity_bucket_order(str(row["liquidity_bucket"])),
    )


def build_redemption_path_monthly_rows(
    result: RedemptionPathResult,
) -> list[dict[str, object]]:
    """Return monthly redemption-path rows for charts and tables."""

    rows: list[dict[str, object]] = []
    for month in result.monthly_results:
        new_demand = sum(
            (state.new_redemption_amount for state in month.investor_class_states),
            ZERO,
        )
        effective_demand = sum(
            (state.effective_redemption_amount for state in month.investor_class_states),
            ZERO,
        )
        paid_redemption = sum(
            (state.paid_redemption_amount for state in month.investor_class_states),
            ZERO,
        )
        deferred_redemption = sum(
            (state.deferred_redemption_amount for state in month.investor_class_states),
            ZERO,
        )
        backlog_amount = sum((entry.remaining_amount for entry in month.backlog), ZERO)
        liquid_nav = _liquid_nav(month.positions)
        rows.append(
            {
                "month": month.period.month_number,
                "month_start": month.period.month_start,
                "month_end": month.period.month_end,
                "new_redemption_demand": new_demand,
                "effective_redemption_demand": effective_demand,
                "paid_redemption": paid_redemption,
                "deferred_redemption": deferred_redemption,
                "cumulative_backlog": backlog_amount,
                "liquidity_shortfall": month.liquidation_result.shortfall,
                "opening_nav": month.opening_nav,
                "pre_lmt_nav": month.pre_lmt_nav,
                "closing_nav": month.closing_nav,
                "opening_cash": month.opening_cash,
                "closing_cash": month.closing_cash,
                "remaining_liquid_resources": month.liquidation_result.remaining_liquid_resources,
                "remaining_liquid_buffer_rate": (month.lmt_assessment.remaining_liquid_buffer_rate),
                "liquid_nav": liquid_nav,
                "illiquid_nav": max(month.closing_nav - liquid_nav, ZERO),
                "market_stress_applied": month.market_stress_applied,
                "base_estimated_liquidity_cost_rate": (month.base_estimated_liquidity_cost_rate),
                "adjusted_estimated_liquidity_cost_rate": (
                    month.adjusted_estimated_liquidity_cost_rate
                ),
                "market_contagion_liquidity_cost_multiplier": (
                    month.market_contagion_liquidity_cost_multiplier
                ),
                "market_contagion_applied": month.market_contagion_applied,
                "realised_execution_cost": (month.liquidation_result.total_realised_execution_cost),
                "realised_liquidity_cost": month.realised_liquidity_cost_after_contagion,
                "fund_borne_liquidity_cost": month.fund_borne_liquidity_cost_after_contagion,
                "strategy_deviation_amount": (month.liquidation_result.strategy_deviation_amount),
                "gross_asset_sales": sum(
                    (
                        asset.gross_sale_amount
                        for asset in month.liquidation_result.assets_liquidated
                    ),
                    ZERO,
                ),
                "priority_outcome": month.lmt_assessment.priority_outcome.value,
                "behavioural_feedback_source_outcome": (
                    month.behavioural_feedback_adjustment.source_outcome.value
                ),
                "swing_signal": month.lmt_assessment.swing_signal,
                "swing_applied": month.lmt_assessment.swing_applied,
                "gate_signal": month.lmt_assessment.gate_signal,
                "gate_applied": month.lmt_assessment.gate_applied,
                "buffer_breached": month.lmt_assessment.buffer_breached,
            }
        )
    return rows


def build_redemption_path_investor_rows(
    result: RedemptionPathResult,
) -> list[dict[str, object]]:
    """Return investor-class monthly rows for charts and tables."""

    rows: list[dict[str, object]] = []
    for month in result.monthly_results:
        for state in month.investor_class_states:
            rows.append(
                {
                    "month": month.period.month_number,
                    "client_class": state.client_class.value,
                    "opening_balance": state.opening_balance,
                    "new_redemption_demand": state.new_redemption_amount,
                    "opening_backlog": state.opening_backlog_amount,
                    "effective_redemption_demand": state.effective_redemption_amount,
                    "paid_redemption": state.paid_redemption_amount,
                    "deferred_redemption": state.deferred_redemption_amount,
                    "closing_balance": state.closing_balance,
                    "redemption_rate": state.redemption_rate,
                    "behavioural_feedback_multiplier": (
                        month.behavioural_feedback_adjustment.behavioural_feedback_multipliers.get(
                            state.client_class,
                            ONE,
                        )
                    ),
                    "behavioural_feedback_source_outcome": (
                        month.behavioural_feedback_adjustment.source_outcome.value
                    ),
                }
            )
    return rows


def build_redemption_path_lmt_timeline_rows(
    result: RedemptionPathResult,
) -> list[dict[str, object]]:
    """Return month-level LMT outcome rows."""

    return [
        {
            "month": month.period.month_number,
            "swing_signal": month.lmt_assessment.swing_signal,
            "swing_applied": month.lmt_assessment.swing_applied,
            "gate_signal": month.lmt_assessment.gate_signal,
            "gate_applied": month.lmt_assessment.gate_applied,
            "liquidity_buffer_breach": month.lmt_assessment.buffer_breached,
            "suspension_applied": month.lmt_assessment.suspension_applied,
            "priority_outcome": month.lmt_assessment.priority_outcome.value,
            "paid_redemption": month.lmt_assessment.paid_redemption_amount,
            "deferred_redemption": month.lmt_assessment.deferred_redemption_amount,
            "swing_recovery": month.lmt_assessment.swing_recovery_amount,
        }
        for month in result.monthly_results
    ]


def build_redemption_path_configuration_rows(
    *,
    run: RedemptionPathResult,
    market_stress: MarketStress | None,
    redemption: RedemptionScenario,
    strategy: LiquidationStrategyConfig,
    parameters: LmtParameters,
    stress_months: tuple[int, ...],
    liquidation_days_per_month: int,
    apply_lmts_in_all_signal_months: bool,
    behavioural_feedback_multiplier: Decimal,
    market_contagion_liquidity_cost_multiplier: Decimal,
) -> list[dict[str, object]]:
    """Return compact configuration rows for display."""

    return [
        {"setting": "Scenario", "value": run.scenario_id},
        {"setting": "Redemption scenario", "value": redemption.name},
        {"setting": "Redemption-stress months", "value": _month_list_label(stress_months)},
        {"setting": "Liquidation days per month", "value": liquidation_days_per_month},
        {
            "setting": "LMT application mode",
            "value": (
                "All signal months"
                if apply_lmts_in_all_signal_months
                else "Manually selected months"
            ),
        },
        {
            "setting": "Applied swing pricing months",
            "value": _month_list_label(
                tuple(
                    month.period.month_number
                    for month in run.monthly_results
                    if month.lmt_assessment.swing_applied
                )
            ),
        },
        {
            "setting": "Applied gate months",
            "value": _month_list_label(
                tuple(
                    month.period.month_number
                    for month in run.monthly_results
                    if month.lmt_assessment.gate_applied
                )
            ),
        },
        {
            "setting": "Applied suspension months",
            "value": _month_list_label(
                tuple(
                    month.period.month_number
                    for month in run.monthly_results
                    if month.lmt_assessment.suspension_applied
                )
            ),
        },
        {
            "setting": "Market stress scenario",
            "value": market_stress.name if market_stress is not None else "No market stress",
        },
        {"setting": "Liquidation strategy", "value": strategy.name},
        {"setting": "Random seed", "value": run.random_seed},
        {"setting": "Swing threshold", "value": parameters.swing_threshold_rate},
        {"setting": "Gate threshold", "value": parameters.gate_threshold_rate},
        {"setting": "Liquidity buffer target", "value": parameters.minimum_buffer_rate},
        {
            "setting": "Behavioural feedback",
            "value": (
                behavioural_feedback_multiplier
                if behavioural_feedback_multiplier > ONE
                else "Neutral (1.0×)"
            ),
        },
        {
            "setting": "Market contagion",
            "value": (
                market_contagion_liquidity_cost_multiplier
                if market_contagion_liquidity_cost_multiplier > ONE
                else "Neutral (1.0×)"
            ),
        },
    ]


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


def _path_investors(
    inputs: AppSampleData,
    scenario: ScenarioDefinition,
    redemption: RedemptionScenario,
) -> list[InvestorClassProfile]:
    """Return investor assumptions adjusted by the selected redemption scenario."""

    investors = _scenario_investors(inputs, scenario)
    return [
        investor.model_copy(
            update={
                "stress_redemption_rate": min(
                    investor.stress_redemption_rate * redemption.redemption_multiplier,
                    ONE,
                )
            }
        )
        for investor in investors
    ]


def _behavioural_feedback_multipliers_by_outcome(
    investor_profiles: list[InvestorClassProfile],
    *,
    behavioural_feedback_multiplier: Decimal,
) -> dict[PathLmtOutcome, dict[ClientClass, Decimal]]:
    if behavioural_feedback_multiplier < ONE:
        raise ValueError("behavioural_feedback_multiplier must be at least 1")
    if behavioural_feedback_multiplier == ONE:
        return {}

    multipliers_by_class = {
        investor.client_class: behavioural_feedback_multiplier for investor in investor_profiles
    }
    return {
        PathLmtOutcome.SWING_PRICING: multipliers_by_class,
        PathLmtOutcome.REDEMPTION_GATE: multipliers_by_class,
    }


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


def _asset_group_market_values(
    positions: list[StressedLiquidationPosition],
) -> dict[AssetGroup, Decimal]:
    values: dict[AssetGroup, Decimal] = {}
    for position in positions:
        if position.stressed_market_value is None:
            continue
        values[position.asset_group] = (
            values.get(position.asset_group, ZERO) + position.stressed_market_value
        )
    return values


def _liquid_nav(positions: tuple[PathPositionState, ...]) -> Decimal:
    liquid_groups = {
        AssetGroup.CASH,
        AssetGroup.REVERSE_REPO,
        AssetGroup.LISTED_ETF,
        AssetGroup.LISTED_EQUITY,
    }
    return sum(
        (position.market_value for position in positions if position.asset_group in liquid_groups),
        ZERO,
    )


def _liquidity_bucket(position: AssetPosition) -> str:
    if position.asset_group is AssetGroup.CASH:
        return "Cash"

    liquidity_days = _liquidity_days(position)
    if liquidity_days <= 7:
        return "0-7 days"
    if liquidity_days <= 30:
        return "8-30 days"
    return ">30 days / constrained"


def _liquidity_days(position: AssetPosition) -> int:
    maturity_days = position.maturity_days or 0
    if position.asset_group is AssetGroup.REVERSE_REPO:
        return maturity_days + position.settlement_days
    return position.settlement_days


def _t0_liquid_resources(position: AssetPosition, market_value: Decimal) -> Decimal:
    if position.asset_group is AssetGroup.CASH:
        return market_value
    if position.asset_group not in SELLABLE_GROUPS:
        return ZERO
    return market_value * position.base_liquidity_capacity_rate


def _liquidity_bucket_order(bucket: str) -> int:
    order_by_bucket = {
        "Cash": 1,
        "0-7 days": 2,
        "8-30 days": 3,
        ">30 days / constrained": 4,
    }
    return order_by_bucket[bucket]


def _month_list_label(months: tuple[int, ...]) -> str:
    if not months:
        return "None"
    return ", ".join(str(month) for month in months)
