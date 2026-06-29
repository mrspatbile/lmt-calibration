"""Estimated execution-cost analysis for LMT calibration."""

from collections.abc import Mapping
from decimal import Decimal

from lmt_calibration.domain import AssetGroup, LiquidityStress

ZERO = Decimal("0")


def estimate_liquidity_cost_rate(
    liquidity_stress: LiquidityStress,
    asset_group_market_values: Mapping[AssetGroup, Decimal],
) -> Decimal:
    """Estimate the portfolio-weighted execution-cost rate."""

    return _weighted_component_rates(liquidity_stress, asset_group_market_values)["total_cost_rate"]


def estimate_liquidity_cost_amount(
    gross_redemption_amount: Decimal,
    liquidity_stress: LiquidityStress,
    asset_group_market_values: Mapping[AssetGroup, Decimal],
) -> Decimal:
    """Estimate execution cost for a redemption from liquidity-stress assumptions."""

    if gross_redemption_amount <= ZERO:
        return ZERO
    return gross_redemption_amount * estimate_liquidity_cost_rate(
        liquidity_stress,
        asset_group_market_values,
    )


def estimate_liquidity_cost_breakdown(
    gross_redemption_amount: Decimal,
    liquidity_stress: LiquidityStress,
    asset_group_market_values: Mapping[AssetGroup, Decimal],
) -> dict[str, Decimal]:
    """Estimate portfolio-weighted execution cost by component."""

    rates = _weighted_component_rates(liquidity_stress, asset_group_market_values)
    bid_ask_cost = gross_redemption_amount * rates["bid_ask_cost_rate"]
    transaction_cost = gross_redemption_amount * rates["transaction_cost_rate"]
    market_impact_cost = gross_redemption_amount * rates["market_impact_cost_rate"]

    return {
        "bid_ask_cost_amount": bid_ask_cost,
        "transaction_cost_amount": transaction_cost,
        "market_impact_cost_amount": market_impact_cost,
        "total_cost_amount": bid_ask_cost + transaction_cost + market_impact_cost,
        "total_cost_rate": rates["total_cost_rate"],
    }


def _weighted_component_rates(
    liquidity_stress: LiquidityStress,
    asset_group_market_values: Mapping[AssetGroup, Decimal],
) -> dict[str, Decimal]:
    included_values = {
        asset_group: max(market_value, ZERO)
        for asset_group, market_value in asset_group_market_values.items()
        if asset_group in liquidity_stress.execution_assumptions_by_asset_group
    }
    total_market_value = sum(included_values.values(), ZERO)
    if total_market_value == ZERO:
        return {
            "bid_ask_cost_rate": ZERO,
            "transaction_cost_rate": ZERO,
            "market_impact_cost_rate": ZERO,
            "total_cost_rate": ZERO,
        }

    bid_ask_rate = ZERO
    transaction_rate = ZERO
    market_impact_rate = ZERO
    for asset_group, market_value in included_values.items():
        weight = market_value / total_market_value
        assumptions = liquidity_stress.execution_assumptions_by_asset_group[asset_group]
        bid_ask_rate += weight * assumptions.bid_ask_spread_rate
        transaction_rate += weight * assumptions.transaction_cost_rate
        market_impact_rate += weight * assumptions.market_impact_rate

    return {
        "bid_ask_cost_rate": bid_ask_rate,
        "transaction_cost_rate": transaction_rate,
        "market_impact_cost_rate": market_impact_rate,
        "total_cost_rate": bid_ask_rate + transaction_rate + market_impact_rate,
    }
