"""Fixed monthly redemption-path engine."""

import calendar
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from random import Random

from lmt_calibration.domain import (
    AssetGroup,
    AssetPosition,
    ClientClass,
    DeferredRedemptionBacklogEntry,
    FundSnapshot,
    InvestorClassMonthlyState,
    InvestorClassProfile,
    InvestorClassRedemptionDemand,
    LiquidationResult,
    LiquidationStrategyConfig,
    LiquidityStress,
    LmtParameters,
    MarketStress,
    MonthlyBehaviouralFeedbackAdjustment,
    MonthlyPathLmtAssessment,
    MonthlyRedemptionPathResult,
    MonthlySimulationPeriod,
    PathLmtOutcome,
    PathPositionState,
    RedemptionPathAssumptions,
    RedemptionPathResult,
)
from lmt_calibration.engines.liquidation_strategy import (
    StressedLiquidationPosition,
    calculate_liquidation_strategy,
)
from lmt_calibration.engines.liquidity_cost import estimate_liquidity_cost_breakdown
from lmt_calibration.engines.redemption_behaviour import calculate_monthly_redemption_demands

ZERO = Decimal("0")
ONE = Decimal("1")
CASH_POSITION_ID = "path_cash_balance"
OUTCOME_PRIORITY = (
    PathLmtOutcome.SUSPENSION,
    PathLmtOutcome.REDEMPTION_GATE,
    PathLmtOutcome.LIQUIDITY_BUFFER_BREACH,
    PathLmtOutcome.SWING_PRICING,
    PathLmtOutcome.NONE,
)


class RedemptionPathError(ValueError):
    """Raised when a redemption path cannot be calculated."""


def run_redemption_path(
    *,
    fund: FundSnapshot,
    positions: Sequence[AssetPosition],
    investor_profiles: Sequence[InvestorClassProfile],
    liquidity_stress: LiquidityStress,
    liquidation_strategy: LiquidationStrategyConfig,
    lmt_parameters: LmtParameters,
    assumptions: RedemptionPathAssumptions,
    market_stress: MarketStress | None = None,
) -> RedemptionPathResult:
    """Run a fixed monthly redemption path independent of Streamlit."""

    if assumptions.market_stress_month is not None and market_stress is None:
        raise RedemptionPathError("market_stress is required when market_stress_month is set")

    rng = Random(assumptions.random_seed)
    carried_positions = _initial_position_states(positions)
    investor_balances = _initial_investor_balances(fund, investor_profiles)
    backlog: tuple[DeferredRedemptionBacklogEntry, ...] = ()
    monthly_results: list[MonthlyRedemptionPathResult] = []
    behavioural_feedback_adjustment = _neutral_behavioural_feedback_adjustment(investor_profiles)

    for month_number in range(1, assumptions.horizon_months + 1):
        period = _monthly_period(assumptions.start_date, month_number)
        opening_nav = _position_nav(carried_positions)
        opening_cash = _cash_total(carried_positions)

        market_stress_applied = (
            market_stress is not None and month_number == assumptions.market_stress_month
        )
        if market_stress_applied:
            if market_stress is None:
                raise RedemptionPathError("market_stress is required for the market-stress month")
            carried_positions = _apply_market_stress(carried_positions, market_stress)

        carried_positions, contractual_cashflow_amount = _apply_contractual_cashflows(
            carried_positions,
            days_in_period=assumptions.days_per_month,
        )
        pre_lmt_nav = _position_nav(carried_positions)

        demands = calculate_monthly_redemption_demands(
            investor_profiles=investor_profiles,
            investor_balances=investor_balances,
            month_number=month_number,
            stress_months=assumptions.stress_months,
            behavioural_feedback_multipliers=(
                behavioural_feedback_adjustment.behavioural_feedback_multipliers
            ),
            rng=rng,
        )
        effective_total = _effective_redemption_total(demands, backlog)
        effective_redemption_rate = effective_total / pre_lmt_nav if pre_lmt_nav > ZERO else ZERO
        gate_activated = effective_redemption_rate >= lmt_parameters.gate_threshold_rate
        requested_paid_amount = _requested_paid_amount(
            effective_total=effective_total,
            pre_lmt_nav=pre_lmt_nav,
            gate_activated=gate_activated,
            lmt_parameters=lmt_parameters,
        )

        market_contagion_applied = _market_contagion_applies(
            assumptions=assumptions,
            month_number=month_number,
        )
        market_contagion_liquidity_cost_multiplier = (
            assumptions.market_contagion_liquidity_cost_multiplier
            if market_contagion_applied
            else ONE
        )
        stressed_positions = _stressed_positions(
            carried_positions,
            liquidity_stress,
            market_contagion_liquidity_cost_multiplier=(market_contagion_liquidity_cost_multiplier),
        )
        liquidation_result = calculate_liquidation_strategy(
            scenario_id=f"{assumptions.scenario_id}_month_{month_number}",
            fund=fund.model_copy(update={"as_of_date": period.month_start, "nav": pre_lmt_nav}),
            positions=stressed_positions,
            redemption_amount=requested_paid_amount,
            strategy=liquidation_strategy,
            lmt_parameters=lmt_parameters,
            stress_horizon_days=liquidity_stress.stress_horizon_days,
        )
        final_paid_amount = max(requested_paid_amount - liquidation_result.shortfall, ZERO)

        investor_states, backlog = _allocate_paid_and_deferred_by_class(
            demands=demands,
            opening_backlog=backlog,
            final_paid_amount=final_paid_amount,
            month_number=month_number,
        )
        investor_balances = {state.client_class: state.closing_balance for state in investor_states}

        liquidity_cost_breakdown = estimate_liquidity_cost_breakdown(
            final_paid_amount,
            liquidity_stress,
            _asset_group_market_values(stressed_positions),
        )
        base_estimated_liquidity_cost_rate = liquidity_cost_breakdown["total_cost_rate"]
        adjusted_estimated_liquidity_cost_rate = (
            base_estimated_liquidity_cost_rate * market_contagion_liquidity_cost_multiplier
        )
        lmt_assessment = _monthly_lmt_assessment(
            effective_redemption_rate=effective_redemption_rate,
            effective_total=effective_total,
            final_paid_amount=final_paid_amount,
            gate_activated=gate_activated,
            liquidity_cost_rate=adjusted_estimated_liquidity_cost_rate,
            liquidation_result=liquidation_result,
            lmt_parameters=lmt_parameters,
            closing_nav_before_recovery=max(
                pre_lmt_nav - final_paid_amount - liquidation_result.total_realised_liquidity_cost,
                ZERO,
            ),
        )
        closing_cash = _closing_cash(
            positions=carried_positions,
            liquidation_result=liquidation_result,
            final_paid_amount=final_paid_amount,
            swing_recovery_amount=lmt_assessment.swing_recovery_amount,
        )
        carried_positions = _apply_liquidation_to_positions(
            positions=carried_positions,
            liquidation_result=liquidation_result,
            closing_cash=closing_cash,
        )
        closing_nav = _position_nav(carried_positions)
        lmt_assessment = _assessment_with_outcomes(
            lmt_assessment.model_copy(
                update={
                    "buffer_breached": (
                        lmt_assessment.remaining_liquid_buffer_rate
                        < lmt_parameters.minimum_buffer_rate
                    )
                }
            )
        )

        monthly_results.append(
            MonthlyRedemptionPathResult(
                period=period,
                market_stress_applied=market_stress_applied,
                opening_nav=opening_nav,
                pre_lmt_nav=pre_lmt_nav,
                closing_nav=closing_nav,
                opening_cash=opening_cash,
                closing_cash=closing_cash,
                contractual_cashflow_amount=contractual_cashflow_amount,
                base_estimated_liquidity_cost_rate=base_estimated_liquidity_cost_rate,
                adjusted_estimated_liquidity_cost_rate=adjusted_estimated_liquidity_cost_rate,
                market_contagion_liquidity_cost_multiplier=(
                    market_contagion_liquidity_cost_multiplier
                ),
                market_contagion_applied=market_contagion_applied,
                behavioural_feedback_adjustment=behavioural_feedback_adjustment,
                investor_class_states=investor_states,
                backlog=backlog,
                positions=carried_positions,
                liquidation_result=liquidation_result,
                lmt_assessment=lmt_assessment,
            )
        )
        behavioural_feedback_adjustment = _next_behavioural_feedback_adjustment(
            assumptions=assumptions,
            investor_profiles=investor_profiles,
            source_outcome=lmt_assessment.priority_outcome,
        )

    return RedemptionPathResult(
        scenario_id=assumptions.scenario_id,
        random_seed=assumptions.random_seed,
        monthly_results=tuple(monthly_results),
    )


def _market_contagion_applies(
    *,
    assumptions: RedemptionPathAssumptions,
    month_number: int,
) -> bool:
    return (
        assumptions.market_contagion_liquidity_cost_multiplier > ONE
        and assumptions.market_stress_month is not None
        and month_number == assumptions.market_stress_month + 1
    )


def _neutral_behavioural_feedback_adjustment(
    investor_profiles: Sequence[InvestorClassProfile],
) -> MonthlyBehaviouralFeedbackAdjustment:
    return MonthlyBehaviouralFeedbackAdjustment(
        source_outcome=PathLmtOutcome.NONE,
        behavioural_feedback_multipliers={
            investor.client_class: ONE for investor in investor_profiles
        },
    )


def _next_behavioural_feedback_adjustment(
    *,
    assumptions: RedemptionPathAssumptions,
    investor_profiles: Sequence[InvestorClassProfile],
    source_outcome: PathLmtOutcome,
) -> MonthlyBehaviouralFeedbackAdjustment:
    behavioural_feedback_multipliers = assumptions.behavioural_feedback_multipliers_by_outcome.get(
        source_outcome,
        {},
    )
    return MonthlyBehaviouralFeedbackAdjustment(
        source_outcome=source_outcome,
        behavioural_feedback_multipliers={
            investor.client_class: behavioural_feedback_multipliers.get(
                investor.client_class,
                ONE,
            )
            for investor in investor_profiles
        },
    )


def _monthly_period(start_date: date, month_number: int) -> MonthlySimulationPeriod:
    month_start = _add_months(start_date, month_number - 1)
    last_day = calendar.monthrange(month_start.year, month_start.month)[1]
    return MonthlySimulationPeriod(
        month_number=month_number,
        month_start=month_start,
        month_end=date(month_start.year, month_start.month, last_day),
    )


def _add_months(input_date: date, months: int) -> date:
    month_index = input_date.month - 1 + months
    year = input_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(input_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _initial_position_states(positions: Sequence[AssetPosition]) -> tuple[PathPositionState, ...]:
    states = tuple(
        PathPositionState(
            position_id=position.position_id,
            asset_group=position.asset_group,
            market_value=position.market_value or ZERO,
            base_haircut_rate=position.base_haircut_rate,
            base_liquidity_capacity_rate=position.base_liquidity_capacity_rate,
            settlement_days=position.settlement_days,
            maturity_days=position.maturity_days,
            notional_amount=position.notional_amount,
        )
        for position in positions
    )
    if any(position.asset_group is AssetGroup.CASH for position in states):
        return states
    return (
        *states,
        PathPositionState(
            position_id=CASH_POSITION_ID,
            asset_group=AssetGroup.CASH,
            market_value=ZERO,
            base_haircut_rate=ZERO,
            base_liquidity_capacity_rate=ONE,
            settlement_days=0,
        ),
    )


def _initial_investor_balances(
    fund: FundSnapshot,
    investor_profiles: Sequence[InvestorClassProfile],
) -> dict[ClientClass, Decimal]:
    return {
        investor.client_class: fund.nav * investor.nav_share_rate for investor in investor_profiles
    }


def _apply_market_stress(
    positions: Sequence[PathPositionState],
    market_stress: MarketStress,
) -> tuple[PathPositionState, ...]:
    shocked_positions: list[PathPositionState] = []
    for position in positions:
        if position.asset_group in {AssetGroup.LISTED_EQUITY, AssetGroup.LISTED_ETF}:
            market_value = max(
                position.market_value * (ONE + market_stress.market_shock_rate), ZERO
            )
            shocked_positions.append(position.model_copy(update={"market_value": market_value}))
        else:
            shocked_positions.append(position)
    return tuple(shocked_positions)


def _apply_contractual_cashflows(
    positions: Sequence[PathPositionState],
    *,
    days_in_period: int,
) -> tuple[tuple[PathPositionState, ...], Decimal]:
    cashflow_amount = ZERO
    updated_positions: list[PathPositionState] = []
    for position in positions:
        if (
            position.asset_group is AssetGroup.REVERSE_REPO
            and position.maturity_days is not None
            and position.market_value > ZERO
        ):
            if position.maturity_days <= days_in_period:
                cashflow_amount += position.market_value
                updated_positions.append(
                    position.model_copy(update={"market_value": ZERO, "maturity_days": 0})
                )
            else:
                updated_positions.append(
                    position.model_copy(
                        update={"maturity_days": position.maturity_days - days_in_period}
                    )
                )
        else:
            updated_positions.append(position)
    if cashflow_amount > ZERO:
        updated_positions = list(
            _set_cash_total(updated_positions, _cash_total(updated_positions) + cashflow_amount)
        )
    return tuple(updated_positions), cashflow_amount


def _stressed_positions(
    positions: Sequence[PathPositionState],
    liquidity_stress: LiquidityStress,
    *,
    market_contagion_liquidity_cost_multiplier: Decimal = ONE,
) -> tuple[StressedLiquidationPosition, ...]:
    return tuple(
        StressedLiquidationPosition(
            position_id=position.position_id,
            asset_group=position.asset_group,
            stressed_market_value=position.market_value,
            stressed_haircut_rate=_stressed_haircut_rate(position, liquidity_stress),
            realised_execution_cost_rate=_market_contagion_execution_cost_rate(
                position,
                liquidity_stress,
                market_contagion_liquidity_cost_multiplier,
            ),
            stressed_liquidity_capacity_rate=_stressed_liquidity_capacity_rate(
                position,
                liquidity_stress,
            ),
            settlement_days=position.settlement_days,
            maturity_days=position.maturity_days,
            notional_amount=position.notional_amount,
        )
        for position in positions
    )


def _market_contagion_execution_cost_rate(
    position: PathPositionState,
    liquidity_stress: LiquidityStress,
    multiplier: Decimal,
) -> Decimal:
    if position.asset_group is AssetGroup.CASH or multiplier <= ONE:
        return ZERO
    assumption = liquidity_stress.execution_assumptions_by_asset_group.get(position.asset_group)
    if assumption is None:
        return ZERO
    base_execution_cost_rate = (
        assumption.bid_ask_spread_rate
        + assumption.transaction_cost_rate
        + assumption.market_impact_rate
    )
    return min(base_execution_cost_rate * (multiplier - ONE), ONE)


def _stressed_haircut_rate(
    position: PathPositionState,
    liquidity_stress: LiquidityStress,
) -> Decimal:
    if position.asset_group is AssetGroup.CASH:
        return ZERO
    assumption = liquidity_stress.execution_assumptions_by_asset_group.get(position.asset_group)
    if assumption is None:
        return position.base_haircut_rate
    return min(position.base_haircut_rate + assumption.liquidity_haircut_rate, ONE)


def _stressed_liquidity_capacity_rate(
    position: PathPositionState,
    liquidity_stress: LiquidityStress,
) -> Decimal:
    if position.asset_group is AssetGroup.CASH:
        return ONE
    assumption = liquidity_stress.execution_assumptions_by_asset_group.get(position.asset_group)
    if assumption is None:
        return position.base_liquidity_capacity_rate
    return position.base_liquidity_capacity_rate * assumption.participation_rate


def _effective_redemption_total(
    demands: Sequence[InvestorClassRedemptionDemand],
    backlog: Sequence[DeferredRedemptionBacklogEntry],
) -> Decimal:
    return sum((demand.redemption_amount for demand in demands), ZERO) + sum(
        (entry.remaining_amount for entry in backlog), ZERO
    )


def _requested_paid_amount(
    *,
    effective_total: Decimal,
    pre_lmt_nav: Decimal,
    gate_activated: bool,
    lmt_parameters: LmtParameters,
) -> Decimal:
    if not gate_activated:
        return effective_total
    return min(effective_total, pre_lmt_nav * lmt_parameters.gate_threshold_rate)


def _allocate_paid_and_deferred_by_class(
    *,
    demands: Sequence[InvestorClassRedemptionDemand],
    opening_backlog: Sequence[DeferredRedemptionBacklogEntry],
    final_paid_amount: Decimal,
    month_number: int,
) -> tuple[tuple[InvestorClassMonthlyState, ...], tuple[DeferredRedemptionBacklogEntry, ...]]:
    components_by_class = _redemption_components_by_class(demands, opening_backlog, month_number)
    total_effective = sum(
        (amount for components in components_by_class.values() for _, amount in components),
        ZERO,
    )
    states: list[InvestorClassMonthlyState] = []
    closing_backlog: list[DeferredRedemptionBacklogEntry] = []

    for demand in sorted(demands, key=lambda item: item.client_class.value):
        components = components_by_class.get(demand.client_class, ())
        class_effective = sum((amount for _, amount in components), ZERO)
        class_paid = (
            final_paid_amount * class_effective / total_effective
            if total_effective > ZERO
            else ZERO
        )
        class_backlog = ZERO
        for origin_month, amount in components:
            component_paid = (
                class_paid * amount / class_effective if class_effective > ZERO else ZERO
            )
            remaining = max(amount - component_paid, ZERO)
            class_backlog += remaining
            if remaining > ZERO:
                closing_backlog.append(
                    DeferredRedemptionBacklogEntry(
                        client_class=demand.client_class,
                        origin_month=origin_month,
                        remaining_amount=remaining,
                    )
                )
        states.append(
            InvestorClassMonthlyState(
                client_class=demand.client_class,
                opening_balance=demand.opening_balance,
                new_redemption_amount=demand.redemption_amount,
                opening_backlog_amount=class_effective - demand.redemption_amount,
                effective_redemption_amount=class_effective,
                paid_redemption_amount=class_paid,
                deferred_redemption_amount=class_backlog,
                closing_balance=max(
                    demand.opening_balance - demand.redemption_amount,
                    ZERO,
                ),
                redemption_rate=demand.redemption_rate,
            )
        )

    return tuple(states), tuple(closing_backlog)


def _redemption_components_by_class(
    demands: Sequence[InvestorClassRedemptionDemand],
    opening_backlog: Sequence[DeferredRedemptionBacklogEntry],
    month_number: int,
) -> dict[ClientClass, tuple[tuple[int, Decimal], ...]]:
    components: dict[ClientClass, list[tuple[int, Decimal]]] = {}
    for entry in opening_backlog:
        components.setdefault(entry.client_class, []).append(
            (entry.origin_month, entry.remaining_amount)
        )
    for demand in demands:
        components.setdefault(demand.client_class, []).append(
            (month_number, demand.redemption_amount)
        )
    return {
        client_class: tuple((origin, amount) for origin, amount in entries if amount > ZERO)
        for client_class, entries in components.items()
    }


def _monthly_lmt_assessment(
    *,
    effective_redemption_rate: Decimal,
    effective_total: Decimal,
    final_paid_amount: Decimal,
    gate_activated: bool,
    liquidity_cost_rate: Decimal,
    liquidation_result: LiquidationResult,
    lmt_parameters: LmtParameters,
    closing_nav_before_recovery: Decimal,
) -> MonthlyPathLmtAssessment:
    swing_activated = effective_redemption_rate >= lmt_parameters.swing_threshold_rate
    applied_swing_factor_rate = min(liquidity_cost_rate, lmt_parameters.max_swing_factor_rate)
    theoretical_recovery = (
        final_paid_amount * applied_swing_factor_rate if swing_activated else ZERO
    )
    swing_recovery_amount = min(
        theoretical_recovery,
        liquidation_result.total_realised_liquidity_cost,
    )
    closing_nav = max(closing_nav_before_recovery + swing_recovery_amount, ZERO)
    remaining_liquid_buffer_rate = (
        liquidation_result.remaining_liquid_resources / closing_nav if closing_nav > ZERO else ZERO
    )
    return MonthlyPathLmtAssessment(
        swing_activated=swing_activated,
        gate_activated=gate_activated,
        buffer_breached=remaining_liquid_buffer_rate < lmt_parameters.minimum_buffer_rate,
        effective_redemption_rate=effective_redemption_rate,
        paid_redemption_amount=final_paid_amount,
        deferred_redemption_amount=max(effective_total - final_paid_amount, ZERO),
        applied_swing_factor_rate=applied_swing_factor_rate,
        swing_recovery_amount=swing_recovery_amount,
        remaining_liquid_buffer_rate=remaining_liquid_buffer_rate,
    )


def _assessment_with_outcomes(
    assessment: MonthlyPathLmtAssessment,
) -> MonthlyPathLmtAssessment:
    outcomes: list[PathLmtOutcome] = []
    if assessment.suspension_applied:
        outcomes.append(PathLmtOutcome.SUSPENSION)
    if assessment.gate_activated:
        outcomes.append(PathLmtOutcome.REDEMPTION_GATE)
    if assessment.buffer_breached:
        outcomes.append(PathLmtOutcome.LIQUIDITY_BUFFER_BREACH)
    if assessment.swing_activated:
        outcomes.append(PathLmtOutcome.SWING_PRICING)
    if not outcomes:
        outcomes.append(PathLmtOutcome.NONE)

    priority_outcome = next(outcome for outcome in OUTCOME_PRIORITY if outcome in outcomes)
    return assessment.model_copy(
        update={
            "outcomes": tuple(outcomes),
            "priority_outcome": priority_outcome,
        }
    )


def _closing_cash(
    *,
    positions: Sequence[PathPositionState],
    liquidation_result: LiquidationResult,
    final_paid_amount: Decimal,
    swing_recovery_amount: Decimal,
) -> Decimal:
    return max(
        _cash_total(positions)
        + liquidation_result.total_net_cash_raised
        - final_paid_amount
        + swing_recovery_amount,
        ZERO,
    )


def _apply_liquidation_to_positions(
    *,
    positions: Sequence[PathPositionState],
    liquidation_result: LiquidationResult,
    closing_cash: Decimal,
) -> tuple[PathPositionState, ...]:
    sold_by_position = {
        asset.position_id: asset.gross_sale_amount for asset in liquidation_result.assets_liquidated
    }
    updated_positions: list[PathPositionState] = []
    for position in positions:
        if position.asset_group is AssetGroup.CASH:
            updated_positions.append(position.model_copy(update={"market_value": closing_cash}))
            continue
        updated_positions.append(
            position.model_copy(
                update={
                    "market_value": max(
                        position.market_value - sold_by_position.get(position.position_id, ZERO),
                        ZERO,
                    )
                }
            )
        )
    return tuple(updated_positions)


def _asset_group_market_values(
    positions: Sequence[StressedLiquidationPosition],
) -> dict[AssetGroup, Decimal]:
    values: dict[AssetGroup, Decimal] = {}
    for position in positions:
        values[position.asset_group] = values.get(position.asset_group, ZERO) + (
            position.stressed_market_value or ZERO
        )
    return values


def _position_nav(positions: Sequence[PathPositionState]) -> Decimal:
    return sum((position.market_value for position in positions), ZERO)


def _cash_total(positions: Sequence[PathPositionState]) -> Decimal:
    return sum(
        (
            position.market_value
            for position in positions
            if position.asset_group is AssetGroup.CASH
        ),
        ZERO,
    )


def _set_cash_total(
    positions: Sequence[PathPositionState],
    cash_total: Decimal,
) -> tuple[PathPositionState, ...]:
    updated_positions: list[PathPositionState] = []
    cash_set = False
    for position in positions:
        if position.asset_group is AssetGroup.CASH and not cash_set:
            updated_positions.append(position.model_copy(update={"market_value": cash_total}))
            cash_set = True
        elif position.asset_group is AssetGroup.CASH:
            updated_positions.append(position.model_copy(update={"market_value": ZERO}))
        else:
            updated_positions.append(position)
    if not cash_set:
        updated_positions.append(
            PathPositionState(
                position_id=CASH_POSITION_ID,
                asset_group=AssetGroup.CASH,
                market_value=cash_total,
                base_haircut_rate=ZERO,
                base_liquidity_capacity_rate=ONE,
                settlement_days=0,
            )
        )
    return tuple(updated_positions)
