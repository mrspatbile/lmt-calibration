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
    swing_pricing_receivable = ZERO
    monthly_results: list[MonthlyRedemptionPathResult] = []
    behavioural_feedback_adjustment = _neutral_behavioural_feedback_adjustment(investor_profiles)

    for month_number in range(1, assumptions.horizon_months + 1):
        period = _monthly_period(assumptions.start_date, month_number)
        opening_nav = _position_nav(carried_positions)

        # Unsettled proceeds from previous month's gate now settle and become available
        unsettled_from_previous_month = (
            monthly_results[-1].gate_period_unsettled_cash if monthly_results else ZERO
        )
        opening_cash = _cash_total(carried_positions) + unsettled_from_previous_month

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
        swing_signal = effective_redemption_rate >= lmt_parameters.swing_threshold_rate
        gate_signal = effective_redemption_rate >= lmt_parameters.gate_threshold_rate
        suspension_applied = month_number in assumptions.suspension_months
        swing_applied = not suspension_applied and (
            month_number in assumptions.swing_pricing_months
            or (assumptions.apply_lmts_in_all_signal_months and swing_signal)
        )
        gate_applied = not suspension_applied and (
            month_number in assumptions.gate_months
            or (assumptions.apply_lmts_in_all_signal_months and gate_signal)
        )
        requested_paid_amount = _requested_paid_amount(
            effective_total=effective_total,
            pre_lmt_nav=pre_lmt_nav,
            gate_applied=gate_applied,
            suspension_applied=suspension_applied,
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
            liquidation_days_per_month=assumptions.liquidation_days_per_month,
            market_contagion_liquidity_cost_multiplier=(market_contagion_liquidity_cost_multiplier),
        )

        # Calculate minimum cash buffer that must be preserved
        minimum_cash_buffer = pre_lmt_nav * lmt_parameters.minimum_buffer_rate
        available_excess_cash = max(opening_cash - minimum_cash_buffer, ZERO)

        # Determine how much can be paid from available excess cash
        cash_available_for_payment = min(available_excess_cash, requested_paid_amount)

        # Calculate liquidation needed for remainder
        liquidation_needed = requested_paid_amount - cash_available_for_payment

        # Liquidate for shortfall (if any), using existing strategy
        if liquidation_needed > ZERO:
            liquidation_result = (
                calculate_liquidation_strategy(
                    scenario_id=f"{assumptions.scenario_id}_month_{month_number}",
                    fund=fund.model_copy(
                        update={"as_of_date": period.month_start, "nav": pre_lmt_nav}
                    ),
                    positions=stressed_positions,
                    redemption_amount=liquidation_needed,
                    strategy=liquidation_strategy,
                    lmt_parameters=lmt_parameters,
                    stress_horizon_days=liquidity_stress.stress_horizon_days,
                )
                if pre_lmt_nav > ZERO
                else _zero_nav_liquidation_result(
                    scenario_id=f"{assumptions.scenario_id}_month_{month_number}",
                    strategy=liquidation_strategy,
                    requested_paid_amount=liquidation_needed,
                )
            )
            final_paid_amount = max(
                cash_available_for_payment + (liquidation_needed - liquidation_result.shortfall),
                ZERO,
            )
        else:
            # No liquidation needed
            final_paid_amount = cash_available_for_payment
            liquidation_result = _zero_nav_liquidation_result(
                scenario_id=f"{assumptions.scenario_id}_month_{month_number}",
                strategy=liquidation_strategy,
                requested_paid_amount=ZERO,
            )

        investor_states, backlog = _allocate_paid_and_deferred_by_class(
            demands=demands,
            opening_backlog=backlog,
            requested_paid_amount=requested_paid_amount,
            final_paid_amount=final_paid_amount,
            month_number=month_number,
        )
        investor_balances = {state.client_class: state.closing_balance for state in investor_states}

        # Gate-period liquidation: if gate is active, liquidate to cover backlog during deferral period
        gate_period_liquidation_result = None
        gate_period_cash_generated = ZERO
        gate_period_settled_cash = ZERO
        gate_period_unsettled_cash = ZERO

        if gate_applied:
            # Calculate backlog target (amount that should be raised during gate period)
            gate_period_liquidation_target = sum(entry.remaining_amount for entry in backlog)

            if gate_period_liquidation_target > ZERO:
                # Ask liquidation engine to raise cash for backlog target
                # Engine handles all constraints: strategy, settlement days, haircuts, etc.
                gate_period_liquidation_result = calculate_liquidation_strategy(
                    scenario_id=f"{assumptions.scenario_id}_month_{month_number}_gate_period",
                    fund=fund.model_copy(
                        update={"as_of_date": period.month_start, "nav": pre_lmt_nav}
                    ),
                    positions=stressed_positions,
                    redemption_amount=gate_period_liquidation_target,
                    strategy=liquidation_strategy,
                    lmt_parameters=lmt_parameters,
                    stress_horizon_days=liquidity_stress.stress_horizon_days,
                )

                # Liquidation engine tells us what it can raise
                gate_period_cash_generated = max(
                    gate_period_liquidation_target - gate_period_liquidation_result.shortfall, ZERO
                )

                # Split into settled vs. unsettled based on settlement timing
                # Use maximum settlement days from liquidated positions
                liquidated_position_ids = {
                    asset.position_id for asset in gate_period_liquidation_result.assets_liquidated
                }
                max_settlement_days = max(
                    (
                        pos.settlement_days
                        for pos in stressed_positions
                        if pos.position_id in liquidated_position_ids
                    ),
                    default=0,
                )

                remaining_days_in_month = (
                    assumptions.liquidation_days_per_month - max_settlement_days
                )

                if remaining_days_in_month >= max_settlement_days:
                    # All cash settles this month
                    gate_period_settled_cash = gate_period_cash_generated
                    gate_period_unsettled_cash = ZERO
                else:
                    # Partial settlement this month, rest next month
                    settlement_rate = max(
                        remaining_days_in_month / max_settlement_days
                        if max_settlement_days > 0
                        else ONE,
                        ZERO,
                    )
                    gate_period_settled_cash = gate_period_cash_generated * settlement_rate
                    gate_period_unsettled_cash = gate_period_cash_generated * (
                        ONE - settlement_rate
                    )

        liquidity_cost_breakdown = estimate_liquidity_cost_breakdown(
            final_paid_amount,
            liquidity_stress,
            _asset_group_market_values(stressed_positions),
        )
        base_estimated_liquidity_cost_rate = liquidity_cost_breakdown["total_cost_rate"]
        adjusted_estimated_liquidity_cost_rate = (
            base_estimated_liquidity_cost_rate * market_contagion_liquidity_cost_multiplier
        )
        # Economic liquidity cost = immediate liquidation cost + gate-period liquidation cost
        # All recognized in the month of liquidation, allocated via swing pricing
        immediate_liquidation_cost_after_contagion = (
            liquidation_result.total_realised_liquidity_cost
            * market_contagion_liquidity_cost_multiplier
        )

        gate_period_liquidation_cost_after_contagion = ZERO
        if gate_period_liquidation_result is not None:
            gate_period_liquidation_cost_after_contagion = (
                gate_period_liquidation_result.total_realised_execution_cost
                * market_contagion_liquidity_cost_multiplier
            )

        # Total economic cost (both components)
        realised_liquidity_cost_after_contagion = (
            immediate_liquidation_cost_after_contagion
            + gate_period_liquidation_cost_after_contagion
        )

        # Preliminary fund-borne cost for NAV calculation (will be refined below)
        # All economic costs (immediate + gate-period) allocated via swing pricing
        preliminary_fund_borne = ZERO if swing_applied else realised_liquidity_cost_after_contagion

        lmt_assessment = _monthly_lmt_assessment(
            effective_redemption_rate=effective_redemption_rate,
            effective_total=effective_total,
            requested_paid_amount=requested_paid_amount,
            final_paid_amount=final_paid_amount,
            swing_signal=swing_signal,
            swing_applied=swing_applied,
            gate_signal=gate_signal,
            gate_applied=gate_applied,
            suspension_applied=suspension_applied,
            liquidity_cost_rate=adjusted_estimated_liquidity_cost_rate,
            liquidation_result=liquidation_result,
            lmt_parameters=lmt_parameters,
            closing_nav_before_recovery=max(
                pre_lmt_nav - final_paid_amount - preliminary_fund_borne,
                ZERO,
            ),
            realised_liquidity_cost_after_contagion=realised_liquidity_cost_after_contagion,
        )

        # Calculate swing pricing receivable for deferred redemptions
        # Uses same proportional allocation as swing_received: cost per unit * deferred amount
        swing_pricing_receivable_for_deferred = ZERO
        if swing_applied and lmt_assessment.deferred_redemption_amount > ZERO:
            # Cost per unit = economic cost / total redemptions (same as in _monthly_lmt_assessment)
            cost_per_unit = (
                realised_liquidity_cost_after_contagion / effective_total
                if effective_total > ZERO
                else ZERO
            )
            # Swing receivable = cost allocation for deferred redemptions
            swing_pricing_receivable_for_deferred = (
                cost_per_unit * lmt_assessment.deferred_redemption_amount
            )

        # Allocate total economic cost (immediate + gate-period) based on swing pricing
        if swing_applied:
            # Swing pricing transfers all economic liquidity costs to redeeming investors
            investor_borne_liquidity_cost_after_contagion = realised_liquidity_cost_after_contagion
            fund_borne_liquidity_cost_after_contagion = ZERO
        else:
            # No swing pricing: all economic costs remain fund-borne
            investor_borne_liquidity_cost_after_contagion = ZERO
            fund_borne_liquidity_cost_after_contagion = realised_liquidity_cost_after_contagion
        closing_cash = _closing_cash(
            positions=carried_positions,
            liquidation_result=liquidation_result,
            final_paid_amount=final_paid_amount,
            swing_recovery_amount=lmt_assessment.swing_recovery_amount,
        )

        # Apply regular liquidation to positions
        carried_positions = _apply_liquidation_to_positions(
            positions=carried_positions,
            liquidation_result=liquidation_result,
            closing_cash=closing_cash,
        )

        # Apply gate-period liquidation to positions and add settled proceeds to closing cash
        if gate_period_liquidation_result is not None:
            closing_cash = closing_cash + gate_period_settled_cash
            carried_positions = _apply_liquidation_to_positions(
                positions=carried_positions,
                liquidation_result=gate_period_liquidation_result,
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

        # Update swing pricing receivable for deferred redemptions
        swing_pricing_receivable_closing = (
            swing_pricing_receivable + swing_pricing_receivable_for_deferred
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
                realised_liquidity_cost_after_contagion=realised_liquidity_cost_after_contagion,
                investor_borne_liquidity_cost_after_contagion=investor_borne_liquidity_cost_after_contagion,
                fund_borne_liquidity_cost_after_contagion=fund_borne_liquidity_cost_after_contagion,
                swing_pricing_receivable_opening=swing_pricing_receivable,
                swing_pricing_receivable_closing=swing_pricing_receivable_closing,
                behavioural_feedback_adjustment=behavioural_feedback_adjustment,
                investor_class_states=investor_states,
                backlog=backlog,
                positions=carried_positions,
                liquidation_result=liquidation_result,
                lmt_assessment=lmt_assessment,
                gate_period_liquidation_result=gate_period_liquidation_result,
                gate_period_cash_generated=gate_period_cash_generated,
                gate_period_settled_cash=gate_period_settled_cash,
                gate_period_unsettled_cash=gate_period_unsettled_cash,
            )
        )
        behavioural_feedback_adjustment = _next_behavioural_feedback_adjustment(
            assumptions=assumptions,
            investor_profiles=investor_profiles,
            source_outcome=lmt_assessment.priority_outcome,
        )

        # Forward swing pricing receivable to next month
        swing_pricing_receivable = swing_pricing_receivable_closing

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


def _zero_nav_liquidation_result(
    *,
    scenario_id: str,
    strategy: LiquidationStrategyConfig,
    requested_paid_amount: Decimal,
) -> LiquidationResult:
    return LiquidationResult(
        scenario_id=scenario_id,
        liquidation_strategy_id=strategy.liquidation_strategy_id,
        total_redemption_amount=requested_paid_amount,
        cash_used=ZERO,
        assets_liquidated=(),
        total_post_haircut_cash_raised=ZERO,
        total_haircut_cost=ZERO,
        total_realised_execution_cost=ZERO,
        total_net_cash_raised=ZERO,
        total_realised_liquidity_cost=ZERO,
        shortfall=requested_paid_amount,
        dilution_amount=ZERO,
        dilution_rate=ZERO,
        remaining_liquid_resources=ZERO,
        remaining_liquid_buffer_rate=ZERO,
        minimum_cash_buffer_preserved=True,
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
    liquidation_days_per_month: int,
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
                liquidation_days_per_month=liquidation_days_per_month,
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
    *,
    liquidation_days_per_month: int,
) -> Decimal:
    if position.asset_group is AssetGroup.CASH:
        return ONE
    assumption = liquidity_stress.execution_assumptions_by_asset_group.get(position.asset_group)
    daily_capacity_rate = position.base_liquidity_capacity_rate
    if assumption is not None:
        daily_capacity_rate *= assumption.participation_rate
    return min(daily_capacity_rate * Decimal(liquidation_days_per_month), ONE)


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
    gate_applied: bool,
    suspension_applied: bool,
    lmt_parameters: LmtParameters,
) -> Decimal:
    if suspension_applied:
        return ZERO
    if not gate_applied:
        return effective_total
    return min(effective_total, pre_lmt_nav * lmt_parameters.gate_threshold_rate)


def _allocate_paid_and_deferred_by_class(
    *,
    demands: Sequence[InvestorClassRedemptionDemand],
    opening_backlog: Sequence[DeferredRedemptionBacklogEntry],
    requested_paid_amount: Decimal,
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
            class_effective
            if final_paid_amount >= total_effective
            else (
                final_paid_amount * class_effective / total_effective
                if total_effective > ZERO
                else ZERO
            )
        )
        class_requested_paid = (
            class_effective
            if requested_paid_amount >= total_effective
            else (
                requested_paid_amount * class_effective / total_effective
                if total_effective > ZERO
                else ZERO
            )
        )
        class_backlog = ZERO
        for origin_month, amount in components:
            component_not_deferred = (
                class_requested_paid * amount / class_effective if class_effective > ZERO else ZERO
            )
            remaining = max(amount - component_not_deferred, ZERO)
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
    requested_paid_amount: Decimal,
    final_paid_amount: Decimal,
    swing_signal: bool,
    swing_applied: bool,
    gate_signal: bool,
    gate_applied: bool,
    suspension_applied: bool,
    liquidity_cost_rate: Decimal,
    liquidation_result: LiquidationResult,
    lmt_parameters: LmtParameters,
    closing_nav_before_recovery: Decimal,
    realised_liquidity_cost_after_contagion: Decimal | None = None,
) -> MonthlyPathLmtAssessment:
    applied_swing_factor_rate = (
        ZERO
        if not swing_applied
        else min(liquidity_cost_rate, lmt_parameters.max_swing_factor_rate)
    )
    economic_cost = (
        realised_liquidity_cost_after_contagion
        if realised_liquidity_cost_after_contagion is not None
        else liquidation_result.total_realised_liquidity_cost
    )

    # Calculate swing pricing adjustment received: proportional share of economic cost
    # When swing is applied, economic cost is allocated to investors proportionally to redemption amount
    # cost_per_unit = economic_cost / effective_total
    # swing_received = cost_per_unit * final_paid_amount (only for paid redemptions this month)
    # This ensures: swing_received + swing_receivable = economic_cost when swing applied
    cost_per_unit = (
        economic_cost / effective_total if swing_applied and effective_total > ZERO else ZERO
    )
    swing_pricing_adjustment_received = cost_per_unit * final_paid_amount if swing_applied else ZERO

    # Legacy swing_recovery_amount (for backwards compatibility in cash calculation)
    # Note: This now represents the actual swing cost transfer, capped at economic cost
    swing_recovery_amount = min(swing_pricing_adjustment_received, economic_cost)

    closing_nav = max(closing_nav_before_recovery + swing_recovery_amount, ZERO)
    remaining_liquid_buffer_rate = (
        liquidation_result.remaining_liquid_resources / closing_nav if closing_nav > ZERO else ZERO
    )

    # Deferred amount accounts for redemptions deferred due to LMT rules (gate/suspension)
    # Note: this does not include shortfalls, which are tracked separately
    deferred_amount = max(effective_total - requested_paid_amount, ZERO)

    return MonthlyPathLmtAssessment(
        swing_signal=swing_signal,
        swing_applied=swing_applied,
        gate_signal=gate_signal,
        gate_applied=gate_applied,
        buffer_breached=remaining_liquid_buffer_rate < lmt_parameters.minimum_buffer_rate,
        suspension_applied=suspension_applied,
        effective_redemption_rate=effective_redemption_rate,
        paid_redemption_amount=final_paid_amount,
        deferred_redemption_amount=deferred_amount,
        applied_swing_factor_rate=applied_swing_factor_rate,
        swing_recovery_amount=swing_recovery_amount,
        swing_pricing_adjustment_received=swing_pricing_adjustment_received,
        remaining_liquid_buffer_rate=remaining_liquid_buffer_rate,
    )


def _assessment_with_outcomes(
    assessment: MonthlyPathLmtAssessment,
) -> MonthlyPathLmtAssessment:
    outcomes: list[PathLmtOutcome] = []
    if assessment.suspension_applied:
        outcomes.append(PathLmtOutcome.SUSPENSION)
    if assessment.gate_applied:
        outcomes.append(PathLmtOutcome.REDEMPTION_GATE)
    if assessment.swing_applied:
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
