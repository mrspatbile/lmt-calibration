"""Tests for liquidity cost estimation."""

from decimal import Decimal
from pathlib import Path

import pytest

from lmt_calibration.engines.liquidity_cost import (
    estimate_liquidity_cost_amount,
    estimate_liquidity_cost_breakdown,
    estimate_liquidity_cost_rate,
)
from lmt_calibration.loaders import load_market_stresses_csv


@pytest.fixture
def market_stresses():
    """Load market stresses for testing."""
    return load_market_stresses_csv(Path("data/sample/market_stresses.csv"))


def test_estimate_liquidity_cost_rate_normal(market_stresses):
    """Test cost rate calculation for normal market."""
    normal = market_stresses[0]
    cost_rate = estimate_liquidity_cost_rate(normal)

    # Should sum bid-ask + transaction + market impact
    expected = Decimal("0.0010") + Decimal("0.0005") + Decimal("0.0005")
    assert cost_rate == expected
    assert cost_rate == Decimal("0.0020")  # 0.2%


def test_estimate_liquidity_cost_rate_crisis(market_stresses):
    """Test cost rate calculation for crisis market."""
    crisis = market_stresses[3]  # 2008 crisis
    cost_rate = estimate_liquidity_cost_rate(crisis)

    expected = Decimal("0.0100") + Decimal("0.0050") + Decimal("0.0075")
    assert cost_rate == expected
    assert cost_rate == Decimal("0.0225")  # 2.25%


def test_estimate_liquidity_cost_amount_zero_redemption(market_stresses):
    """Test that zero redemption results in zero cost."""
    normal = market_stresses[0]
    cost = estimate_liquidity_cost_amount(Decimal("0"), normal)

    assert cost == Decimal("0")


def test_estimate_liquidity_cost_amount_normal(market_stresses):
    """Test cost amount calculation for normal market."""
    normal = market_stresses[0]
    nav = Decimal("100000000")  # 100M EUR
    redemption_rate = Decimal("0.06")  # 6%
    gross_redemption = nav * redemption_rate

    cost = estimate_liquidity_cost_amount(gross_redemption, normal)

    # Cost = 6M * 0.002 = 12,000
    expected = gross_redemption * Decimal("0.0020")
    assert cost == expected
    assert cost == Decimal("12000")


def test_estimate_liquidity_cost_amount_crisis(market_stresses):
    """Test cost amount calculation for crisis market."""
    crisis = market_stresses[3]  # 2008 crisis
    nav = Decimal("100000000")
    redemption_rate = Decimal("0.06")  # 6%
    gross_redemption = nav * redemption_rate

    cost = estimate_liquidity_cost_amount(gross_redemption, crisis)

    # Cost = 6M * 0.0225 = 135,000
    expected = gross_redemption * Decimal("0.0225")
    assert cost == expected
    assert cost == Decimal("135000")


def test_estimate_liquidity_cost_breakdown_normal(market_stresses):
    """Test cost breakdown for normal market."""
    normal = market_stresses[0]
    nav = Decimal("100000000")
    redemption_rate = Decimal("0.06")
    gross_redemption = nav * redemption_rate

    breakdown = estimate_liquidity_cost_breakdown(gross_redemption, normal)

    # Check each component
    assert breakdown["bid_ask_cost_amount"] == gross_redemption * Decimal("0.0010")  # 6,000
    assert breakdown["transaction_cost_amount"] == gross_redemption * Decimal("0.0005")  # 3,000
    assert breakdown["market_impact_cost_amount"] == gross_redemption * Decimal("0.0005")  # 3,000
    assert breakdown["total_cost_amount"] == Decimal("12000")
    assert breakdown["total_cost_rate"] == Decimal("0.0020")


def test_estimate_liquidity_cost_breakdown_zero_redemption(market_stresses):
    """Test that zero redemption results in zero costs."""
    normal = market_stresses[0]
    breakdown = estimate_liquidity_cost_breakdown(Decimal("0"), normal)

    assert breakdown["bid_ask_cost_amount"] == Decimal("0")
    assert breakdown["transaction_cost_amount"] == Decimal("0")
    assert breakdown["market_impact_cost_amount"] == Decimal("0")
    assert breakdown["total_cost_amount"] == Decimal("0")
    assert breakdown["total_cost_rate"] == Decimal("0.0020")  # Rate is still computed
