"""Scenario-independent asset-side time-to-liquidation calculations."""

from collections.abc import Sequence
from decimal import Decimal

from lmt_calibration.domain.positions import AssetGroup, AssetPosition
from lmt_calibration.domain.time_to_liquidation import (
    AssetClassDistribution,
    DailyLiquidationPoint,
    TtlSensitivityResult,
    TtlSensitivityType,
)

ZERO = Decimal("0")
ONE = Decimal("1")

PARTICIPATION_RATE_SENSITIVITIES = (
    Decimal("0.10"),
    Decimal("0.20"),
    Decimal("0.30"),
)
LIQUIDITY_HAIRCUT_SENSITIVITIES = (
    Decimal("0.30"),
    Decimal("0.40"),
    Decimal("0.50"),
)
LIQUIDATABLE_ASSET_GROUPS = frozenset({AssetGroup.LISTED_EQUITY, AssetGroup.LISTED_ETF})


class TimeToLiquidationError(ValueError):
    """Raised when time-to-liquidation assumptions are invalid."""


def calculate_daily_liquidation_capacity(
    position: AssetPosition,
    *,
    participation_rate: Decimal,
    liquidity_haircut_rate: Decimal,
) -> Decimal:
    """Return post-haircut daily cash capacity for one eligible non-cash position."""

    _validate_rate(participation_rate, "participation_rate")
    _validate_rate(liquidity_haircut_rate, "liquidity_haircut_rate")
    if position.asset_group not in LIQUIDATABLE_ASSET_GROUPS or position.market_value is None:
        return ZERO
    return (
        position.market_value
        * position.base_liquidity_capacity_rate
        * participation_rate
        * (ONE - liquidity_haircut_rate)
    )


def calculate_cumulative_liquidation_curve(
    positions: Sequence[AssetPosition],
    *,
    nav: Decimal,
    participation_rate: Decimal,
    liquidity_haircut_rate: Decimal,
    horizon_days: int,
) -> tuple[DailyLiquidationPoint, ...]:
    """Build cumulative available cash from day 0 through the selected horizon.

    Cash is available on business day 0. Non-cash trades begin on business day 1,
    and proceeds from a trade on day ``d`` become available on
    ``d + settlement_days``. Capacity is capped at each position's market value.
    Repo financing, reverse repo, missing-value, and unsupported positions do not
    contribute to the curve.
    """

    if nav <= ZERO:
        raise TimeToLiquidationError("nav must be positive")
    if horizon_days <= 0:
        raise TimeToLiquidationError("horizon_days must be positive")
    _validate_rate(participation_rate, "participation_rate")
    _validate_rate(liquidity_haircut_rate, "liquidity_haircut_rate")

    immediate_cash = sum(
        (
            position.market_value or ZERO
            for position in positions
            if position.asset_group is AssetGroup.CASH
        ),
        ZERO,
    )
    liquidatable_positions = tuple(
        position
        for position in positions
        if position.asset_group in LIQUIDATABLE_ASSET_GROUPS and position.market_value is not None
    )

    curve: list[DailyLiquidationPoint] = []
    for business_day in range(horizon_days + 1):
        cumulative_cash = immediate_cash
        for position in liquidatable_positions:
            trading_days_settled = max(business_day - position.settlement_days, 0)
            daily_capacity = calculate_daily_liquidation_capacity(
                position,
                participation_rate=participation_rate,
                liquidity_haircut_rate=liquidity_haircut_rate,
            )
            maximum_post_haircut_proceeds = (position.market_value or ZERO) * (
                ONE - liquidity_haircut_rate
            )
            cumulative_cash += min(
                daily_capacity * trading_days_settled,
                maximum_post_haircut_proceeds,
            )
        curve.append(
            DailyLiquidationPoint(
                business_day=business_day,
                cumulative_cash_raised=cumulative_cash,
                cumulative_cash_raised_rate=cumulative_cash / nav,
            )
        )
    return tuple(curve)


def calculate_ttl_to_redemption_shock(
    daily_curve: Sequence[DailyLiquidationPoint],
    redemption_shock_amount: Decimal,
) -> int | None:
    """Return the first business day that covers the target, or ``None``."""

    if redemption_shock_amount < ZERO:
        raise TimeToLiquidationError("redemption_shock_amount must be non-negative")
    return next(
        (
            point.business_day
            for point in daily_curve
            if point.cumulative_cash_raised >= redemption_shock_amount
        ),
        None,
    )


def build_ttl_sensitivity_results(
    positions: Sequence[AssetPosition],
    *,
    nav: Decimal,
    redemption_shock_rate: Decimal,
    horizon_days: int,
    base_participation_rate: Decimal,
    base_liquidity_haircut_rate: Decimal,
) -> tuple[TtlSensitivityResult, ...]:
    """Build fixed participation and haircut benchmark sensitivity results."""

    _validate_rate(redemption_shock_rate, "redemption_shock_rate")
    _validate_rate(base_participation_rate, "base_participation_rate")
    _validate_rate(base_liquidity_haircut_rate, "base_liquidity_haircut_rate")
    redemption_shock_amount = nav * redemption_shock_rate

    assumptions = tuple(
        (
            TtlSensitivityType.PARTICIPATION_RATE,
            participation_rate,
            participation_rate,
            base_liquidity_haircut_rate,
        )
        for participation_rate in PARTICIPATION_RATE_SENSITIVITIES
    ) + tuple(
        (
            TtlSensitivityType.LIQUIDITY_HAIRCUT,
            liquidity_haircut_rate,
            base_participation_rate,
            liquidity_haircut_rate,
        )
        for liquidity_haircut_rate in LIQUIDITY_HAIRCUT_SENSITIVITIES
    )

    results: list[TtlSensitivityResult] = []
    for sensitivity_type, sensitivity_value, participation_rate, haircut_rate in assumptions:
        curve = calculate_cumulative_liquidation_curve(
            positions,
            nav=nav,
            participation_rate=participation_rate,
            liquidity_haircut_rate=haircut_rate,
            horizon_days=horizon_days,
        )
        full_liquidation_amount = _full_liquidation_amount(positions, haircut_rate)
        results.append(
            TtlSensitivityResult(
                sensitivity_type=sensitivity_type,
                sensitivity_value=sensitivity_value,
                daily_cumulative_cash_raised=curve,
                redemption_shock_amount=redemption_shock_amount,
                redemption_shock_rate=redemption_shock_rate,
                ttl_to_redemption_shock_days=calculate_ttl_to_redemption_shock(
                    curve, redemption_shock_amount
                ),
                ttl_to_full_liquidation_days=calculate_ttl_to_redemption_shock(
                    curve, full_liquidation_amount
                ),
                unmet_amount_at_horizon=max(
                    redemption_shock_amount - curve[-1].cumulative_cash_raised,
                    ZERO,
                ),
            )
        )
    return tuple(results)


def build_asset_class_distribution(
    positions: Sequence[AssetPosition],
    *,
    nav: Decimal,
) -> tuple[AssetClassDistribution, ...]:
    """Group current market values into Cash, Listed equity, Listed ETF, and Other."""

    if nav <= ZERO:
        raise TimeToLiquidationError("nav must be positive")
    labels = {
        AssetGroup.CASH: "Cash",
        AssetGroup.LISTED_EQUITY: "Listed equity",
        AssetGroup.LISTED_ETF: "Listed ETF",
    }
    totals: dict[str, Decimal] = {}
    for position in positions:
        if position.market_value is None:
            continue
        label = labels.get(position.asset_group, "Other")
        totals[label] = totals.get(label, ZERO) + position.market_value

    order = ("Cash", "Listed equity", "Listed ETF", "Other")
    return tuple(
        AssetClassDistribution(
            asset_group=label,
            market_value=totals[label],
            nav_share_rate=totals[label] / nav,
        )
        for label in order
        if totals.get(label, ZERO) > ZERO
    )


def _full_liquidation_amount(
    positions: Sequence[AssetPosition], liquidity_haircut_rate: Decimal
) -> Decimal:
    immediate_cash = sum(
        (
            position.market_value or ZERO
            for position in positions
            if position.asset_group is AssetGroup.CASH
        ),
        ZERO,
    )
    post_haircut_assets = sum(
        (
            (position.market_value or ZERO) * (ONE - liquidity_haircut_rate)
            for position in positions
            if position.asset_group in LIQUIDATABLE_ASSET_GROUPS
            and position.market_value is not None
        ),
        ZERO,
    )
    return immediate_cash + post_haircut_assets


def _validate_rate(value: Decimal, field_name: str) -> None:
    if value < ZERO or value > ONE:
        raise TimeToLiquidationError(f"{field_name} must be between 0 and 1")
