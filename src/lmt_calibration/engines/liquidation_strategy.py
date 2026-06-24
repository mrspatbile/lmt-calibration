"""Liquidation strategy service for already-stressed redemption scenarios."""

from collections.abc import Sequence
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from lmt_calibration.domain import (
    AssetGroup,
    FundSnapshot,
    LiquidatedAssetResult,
    LiquidationResult,
    LiquidationStrategyConfig,
    LiquidationStrategyType,
    LmtParameters,
)

ZERO = Decimal("0")
ONE = Decimal("1")

SELLABLE_GROUPS = {
    AssetGroup.REVERSE_REPO,
    AssetGroup.LISTED_ETF,
    AssetGroup.LISTED_EQUITY,
}

MOST_LIQUID_FIRST_ORDER = (
    AssetGroup.REVERSE_REPO,
    AssetGroup.LISTED_ETF,
    AssetGroup.LISTED_EQUITY,
)

CUSTOM_WEIGHT_ORDER = (
    AssetGroup.CASH,
    AssetGroup.REVERSE_REPO,
    AssetGroup.LISTED_ETF,
    AssetGroup.LISTED_EQUITY,
)


class LiquidationStrategyError(ValueError):
    """Raised when a liquidation strategy configuration cannot be applied."""


class StressedLiquidationPosition(BaseModel):
    """Position-level input after market and liquidity stress have been applied."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    position_id: str
    asset_group: AssetGroup
    stressed_market_value: Decimal | None = Field(default=None, ge=ZERO)
    stressed_haircut_rate: Decimal = Field(ge=ZERO, le=ONE)
    stressed_liquidity_capacity_rate: Decimal = Field(ge=ZERO, le=ONE)
    settlement_days: int = Field(ge=0)
    maturity_days: int | None = Field(default=None, ge=0)
    notional_amount: Decimal | None = Field(default=None, ge=ZERO)


def calculate_liquidation_strategy(
    *,
    scenario_id: str,
    fund: FundSnapshot,
    positions: Sequence[StressedLiquidationPosition],
    redemption_amount: Decimal,
    strategy: LiquidationStrategyConfig,
    lmt_parameters: LmtParameters,
    stress_horizon_days: int,
) -> LiquidationResult:
    """Apply the selected V1 liquidation strategy to already-stressed positions."""

    if redemption_amount < ZERO:
        raise LiquidationStrategyError("redemption_amount must be non-negative")
    if stress_horizon_days <= 0:
        raise LiquidationStrategyError("stress_horizon_days must be positive")

    cash_total = _cash_total(positions)
    minimum_cash_buffer = fund.nav * lmt_parameters.minimum_buffer_rate
    cash_available = max(cash_total - minimum_cash_buffer, ZERO)
    eligible_assets = _eligible_assets(positions, stress_horizon_days)

    cash_used = ZERO
    liquidated_assets: list[LiquidatedAssetResult] = []

    if strategy.strategy_type is LiquidationStrategyType.MOST_LIQUID_FIRST:
        cash_used = min(redemption_amount, cash_available)
        remaining_need = redemption_amount - cash_used
        liquidated_assets = _allocate_most_liquid_first(eligible_assets, remaining_need)

    elif strategy.strategy_type is LiquidationStrategyType.PRO_RATA:
        liquidated_assets = _allocate_pro_rata(eligible_assets, redemption_amount)

    elif strategy.strategy_type is LiquidationStrategyType.HYBRID:
        cash_buffer_use_rate = _required_cash_buffer_use_rate(strategy)
        cash_used = min(redemption_amount, cash_available * cash_buffer_use_rate)
        remaining_need = redemption_amount - cash_used
        liquidated_assets = _allocate_pro_rata(eligible_assets, remaining_need)

    elif strategy.strategy_type is LiquidationStrategyType.CUSTOM_WEIGHTS:
        cash_used = _custom_weight_cash_used(strategy, redemption_amount, cash_available)
        liquidated_assets = _allocate_custom_weights(eligible_assets, strategy, redemption_amount)

    else:
        raise LiquidationStrategyError(f"unsupported strategy type: {strategy.strategy_type}")

    total_post_haircut_cash_raised = sum(
        (asset.post_haircut_cash_raised for asset in liquidated_assets),
        ZERO,
    )
    total_haircut_cost = sum((asset.haircut_cost for asset in liquidated_assets), ZERO)
    total_cash_raised = cash_used + total_post_haircut_cash_raised
    shortfall = max(redemption_amount - total_cash_raised, ZERO)
    asset_group_allocations = _asset_group_allocations(cash_used, liquidated_assets)
    remaining_cash = cash_total - cash_used

    return LiquidationResult(
        scenario_id=scenario_id,
        liquidation_strategy_id=strategy.liquidation_strategy_id,
        total_redemption_amount=redemption_amount,
        cash_used=cash_used,
        assets_liquidated=tuple(liquidated_assets),
        asset_group_allocations=asset_group_allocations,
        total_post_haircut_cash_raised=total_post_haircut_cash_raised,
        total_haircut_cost=total_haircut_cost,
        shortfall=shortfall,
        dilution_amount=total_haircut_cost,
        dilution_rate=total_haircut_cost / fund.nav,
        remaining_liquid_buffer_rate=_remaining_liquid_buffer_rate(
            fund=fund,
            remaining_cash=remaining_cash,
            eligible_assets=eligible_assets,
            liquidated_assets=liquidated_assets,
        ),
        minimum_cash_buffer_preserved=remaining_cash >= minimum_cash_buffer,
    )


def _required_cash_buffer_use_rate(strategy: LiquidationStrategyConfig) -> Decimal:
    if strategy.cash_buffer_use_rate is None:
        raise LiquidationStrategyError("hybrid strategy requires cash_buffer_use_rate")
    return strategy.cash_buffer_use_rate


def _cash_total(positions: Sequence[StressedLiquidationPosition]) -> Decimal:
    return sum(
        (
            position.stressed_market_value or ZERO
            for position in positions
            if position.asset_group is AssetGroup.CASH
        ),
        ZERO,
    )


def _eligible_assets(
    positions: Sequence[StressedLiquidationPosition],
    stress_horizon_days: int,
) -> tuple[StressedLiquidationPosition, ...]:
    return tuple(
        position
        for position in positions
        if position.asset_group in SELLABLE_GROUPS
        and position.stressed_market_value is not None
        and position.stressed_market_value > ZERO
        and _is_eligible_under_horizon(position, stress_horizon_days)
    )


def _is_eligible_under_horizon(
    position: StressedLiquidationPosition,
    stress_horizon_days: int,
) -> bool:
    if position.asset_group is AssetGroup.REVERSE_REPO:
        if position.maturity_days is None:
            return False
        return position.maturity_days + position.settlement_days <= stress_horizon_days
    return position.settlement_days <= stress_horizon_days


def _allocate_most_liquid_first(
    eligible_assets: Sequence[StressedLiquidationPosition],
    redemption_need: Decimal,
) -> list[LiquidatedAssetResult]:
    remaining_need = redemption_need
    results: list[LiquidatedAssetResult] = []

    for asset_group in MOST_LIQUID_FIRST_ORDER:
        ordered_assets = sorted(
            (asset for asset in eligible_assets if asset.asset_group is asset_group),
            key=lambda asset: (asset.settlement_days, asset.position_id),
        )
        for asset in ordered_assets:
            if remaining_need <= ZERO:
                return results
            gross_sale_amount = min(remaining_need, _available_capacity(asset))
            if gross_sale_amount <= ZERO:
                continue
            results.append(_liquidated_asset_result(asset, gross_sale_amount))
            remaining_need -= gross_sale_amount

    return results


def _allocate_pro_rata(
    eligible_assets: Sequence[StressedLiquidationPosition],
    redemption_need: Decimal,
) -> list[LiquidatedAssetResult]:
    if redemption_need <= ZERO:
        return []

    total_stressed_market_value = sum(
        (_stressed_market_value(asset) for asset in eligible_assets),
        ZERO,
    )
    if total_stressed_market_value <= ZERO:
        return []

    results: list[LiquidatedAssetResult] = []
    for asset in sorted(eligible_assets, key=lambda item: item.position_id):
        target_sale_amount = (
            redemption_need * _stressed_market_value(asset) / total_stressed_market_value
        )
        gross_sale_amount = min(target_sale_amount, _available_capacity(asset))
        if gross_sale_amount > ZERO:
            results.append(_liquidated_asset_result(asset, gross_sale_amount))
    return results


def _custom_weight_cash_used(
    strategy: LiquidationStrategyConfig,
    redemption_amount: Decimal,
    cash_available: Decimal,
) -> Decimal:
    if strategy.weights is None:
        return ZERO
    cash_weight = strategy.weights.get(AssetGroup.CASH, ZERO)
    return min(redemption_amount * cash_weight, cash_available)


def _allocate_custom_weights(
    eligible_assets: Sequence[StressedLiquidationPosition],
    strategy: LiquidationStrategyConfig,
    redemption_amount: Decimal,
) -> list[LiquidatedAssetResult]:
    if strategy.weights is None:
        raise LiquidationStrategyError("custom_weights strategy requires weights")

    results: list[LiquidatedAssetResult] = []
    for asset_group in CUSTOM_WEIGHT_ORDER:
        if asset_group is AssetGroup.CASH or asset_group not in strategy.weights:
            continue
        group_assets = tuple(asset for asset in eligible_assets if asset.asset_group is asset_group)
        group_need = redemption_amount * strategy.weights[asset_group]
        results.extend(_allocate_group_pro_rata(group_assets, group_need))
    return results


def _allocate_group_pro_rata(
    group_assets: Sequence[StressedLiquidationPosition],
    group_need: Decimal,
) -> list[LiquidatedAssetResult]:
    if group_need <= ZERO:
        return []

    total_stressed_market_value = sum(
        (_stressed_market_value(asset) for asset in group_assets),
        ZERO,
    )
    if total_stressed_market_value <= ZERO:
        return []

    results: list[LiquidatedAssetResult] = []
    for asset in sorted(group_assets, key=lambda item: item.position_id):
        target_sale_amount = (
            group_need * _stressed_market_value(asset) / total_stressed_market_value
        )
        gross_sale_amount = min(target_sale_amount, _available_capacity(asset))
        if gross_sale_amount > ZERO:
            results.append(_liquidated_asset_result(asset, gross_sale_amount))
    return results


def _liquidated_asset_result(
    asset: StressedLiquidationPosition,
    gross_sale_amount: Decimal,
) -> LiquidatedAssetResult:
    post_haircut_cash_raised = gross_sale_amount * (ONE - asset.stressed_haircut_rate)
    return LiquidatedAssetResult(
        position_id=asset.position_id,
        asset_group=asset.asset_group,
        gross_sale_amount=gross_sale_amount,
        post_haircut_cash_raised=post_haircut_cash_raised,
        haircut_cost=gross_sale_amount - post_haircut_cash_raised,
    )


def _available_capacity(asset: StressedLiquidationPosition) -> Decimal:
    return _stressed_market_value(asset) * asset.stressed_liquidity_capacity_rate


def _stressed_market_value(asset: StressedLiquidationPosition) -> Decimal:
    return asset.stressed_market_value or ZERO


def _asset_group_allocations(
    cash_used: Decimal,
    liquidated_assets: Sequence[LiquidatedAssetResult],
) -> dict[AssetGroup, Decimal]:
    allocations: dict[AssetGroup, Decimal] = {}
    if cash_used > ZERO:
        allocations[AssetGroup.CASH] = cash_used

    for asset in liquidated_assets:
        allocations[asset.asset_group] = (
            allocations.get(asset.asset_group, ZERO) + asset.gross_sale_amount
        )
    return allocations


def _remaining_liquid_buffer_rate(
    *,
    fund: FundSnapshot,
    remaining_cash: Decimal,
    eligible_assets: Sequence[StressedLiquidationPosition],
    liquidated_assets: Sequence[LiquidatedAssetResult],
) -> Decimal:
    sold_by_position = {asset.position_id: asset.gross_sale_amount for asset in liquidated_assets}
    remaining_asset_liquidity = sum(
        (
            max(_available_capacity(asset) - sold_by_position.get(asset.position_id, ZERO), ZERO)
            * (ONE - asset.stressed_haircut_rate)
            for asset in eligible_assets
        ),
        ZERO,
    )
    return (remaining_cash + remaining_asset_liquidity) / fund.nav
