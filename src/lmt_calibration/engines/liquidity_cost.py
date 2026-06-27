"""Estimated liquidity cost analysis for LMT calibration."""

from decimal import Decimal

from lmt_calibration.domain import MarketStress

ZERO = Decimal("0")


def estimate_liquidity_cost_rate(market_stress: MarketStress) -> Decimal:
    """Estimate total liquidity cost rate from market stress execution assumptions.

    Args:
        market_stress: Market stress scenario with execution assumptions.

    Returns:
        Total estimated liquidity cost as a rate (sum of spread, transaction, and impact costs).
        Formula: bid_ask_spread_rate + transaction_cost_rate + market_impact_rate
    """
    bid_ask = market_stress.bid_ask_spread_rate or ZERO
    transaction = market_stress.transaction_cost_rate or ZERO
    market_impact = market_stress.market_impact_rate or ZERO
    return bid_ask + transaction + market_impact


def estimate_liquidity_cost_amount(
    gross_redemption_amount: Decimal, market_stress: MarketStress
) -> Decimal:
    """Estimate total liquidity cost amount for a redemption under given market stress.

    Args:
        gross_redemption_amount: Redemption amount in currency units.
        market_stress: Market stress scenario with execution assumptions.

    Returns:
        Estimated liquidity cost amount in currency units.
        Formula: gross_redemption_amount * (estimated_liquidity_cost_rate)
    """
    if gross_redemption_amount <= ZERO:
        return ZERO
    return gross_redemption_amount * estimate_liquidity_cost_rate(market_stress)


def estimate_liquidity_cost_breakdown(
    gross_redemption_amount: Decimal, market_stress: MarketStress
) -> dict[str, Decimal]:
    """Estimate liquidity cost breakdown by component.

    Args:
        gross_redemption_amount: Redemption amount in currency units.
        market_stress: Market stress scenario with execution assumptions.

    Returns:
        Dictionary with cost components:
        - bid_ask_cost_amount
        - transaction_cost_amount
        - market_impact_cost_amount
        - total_cost_amount
        - total_cost_rate
    """
    total_cost_rate = estimate_liquidity_cost_rate(market_stress)

    if gross_redemption_amount <= ZERO:
        return {
            "bid_ask_cost_amount": ZERO,
            "transaction_cost_amount": ZERO,
            "market_impact_cost_amount": ZERO,
            "total_cost_amount": ZERO,
            "total_cost_rate": total_cost_rate,
        }

    bid_ask_spread = market_stress.bid_ask_spread_rate or ZERO
    transaction = market_stress.transaction_cost_rate or ZERO
    market_impact = market_stress.market_impact_rate or ZERO
    bid_ask_cost = gross_redemption_amount * bid_ask_spread
    transaction_cost = gross_redemption_amount * transaction
    market_impact_cost = gross_redemption_amount * market_impact
    total_cost = bid_ask_cost + transaction_cost + market_impact_cost

    return {
        "bid_ask_cost_amount": bid_ask_cost,
        "transaction_cost_amount": transaction_cost,
        "market_impact_cost_amount": market_impact_cost,
        "total_cost_amount": total_cost,
        "total_cost_rate": total_cost_rate,
    }
