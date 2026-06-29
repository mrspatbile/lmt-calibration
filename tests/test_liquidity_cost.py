"""Tests for portfolio-weighted execution-cost estimation."""

from decimal import Decimal
from pathlib import Path

import pytest

from lmt_calibration.domain import AssetGroup
from lmt_calibration.engines.liquidity_cost import (
    estimate_liquidity_cost_amount,
    estimate_liquidity_cost_breakdown,
    estimate_liquidity_cost_rate,
)
from lmt_calibration.loaders import load_liquidity_stresses_json


@pytest.fixture
def normal_liquidity_stress():
    """Load the normal per-asset-group liquidity assumptions."""
    return load_liquidity_stresses_json(Path("data/sample/liquidity_stresses.json"))[0]


@pytest.fixture
def asset_group_market_values():
    """Provide a simple portfolio with transparent group weights."""
    return {
        AssetGroup.CASH: Decimal("50"),
        AssetGroup.LISTED_ETF: Decimal("30"),
        AssetGroup.LISTED_EQUITY: Decimal("20"),
    }


def test_estimate_liquidity_cost_rate_uses_weighted_asset_group_assumptions(
    normal_liquidity_stress, asset_group_market_values
):
    cost_rate = estimate_liquidity_cost_rate(normal_liquidity_stress, asset_group_market_values)

    expected = Decimal("0.3") * Decimal("0.0010") + Decimal("0.2") * Decimal("0.0020")
    assert cost_rate == expected
    assert cost_rate == Decimal("0.00070")


def test_estimate_liquidity_cost_amount_zero_redemption(
    normal_liquidity_stress, asset_group_market_values
):
    cost = estimate_liquidity_cost_amount(
        Decimal("0"), normal_liquidity_stress, asset_group_market_values
    )

    assert cost == Decimal("0")


def test_estimate_liquidity_cost_amount(normal_liquidity_stress, asset_group_market_values):
    cost = estimate_liquidity_cost_amount(
        Decimal("6000000"), normal_liquidity_stress, asset_group_market_values
    )

    assert cost == Decimal("4200.00000")


def test_estimate_liquidity_cost_breakdown(normal_liquidity_stress, asset_group_market_values):
    gross_redemption = Decimal("6000000")
    breakdown = estimate_liquidity_cost_breakdown(
        gross_redemption, normal_liquidity_stress, asset_group_market_values
    )

    assert breakdown["bid_ask_cost_amount"] == Decimal("2100.00000")
    assert breakdown["transaction_cost_amount"] == Decimal("960.00000")
    assert breakdown["market_impact_cost_amount"] == Decimal("1140.00000")
    assert breakdown["total_cost_amount"] == Decimal("4200.00000")
    assert breakdown["total_cost_rate"] == Decimal("0.00070")


def test_estimate_liquidity_cost_rate_is_zero_without_covered_market_value(
    normal_liquidity_stress,
):
    cost_rate = estimate_liquidity_cost_rate(
        normal_liquidity_stress,
        {AssetGroup.REPO_FINANCING: Decimal("100")},
    )

    assert cost_rate == Decimal("0")
