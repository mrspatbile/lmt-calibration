"""Tests for valuation-only market stress assumptions."""

from decimal import Decimal
from pathlib import Path

from lmt_calibration.loaders import load_market_stresses_csv


def test_load_market_stresses_as_valuation_shocks() -> None:
    stresses = load_market_stresses_csv(Path("data/sample/market_stresses.csv"))

    assert len(stresses) == 4
    assert stresses[0].market_stress_id == "normal_market_conditions"
    assert stresses[0].market_shock_rate == Decimal("0.00")
    assert stresses[3].market_stress_id == "historical_crisis_2008"
    assert stresses[3].market_shock_rate == Decimal("-0.35")


def test_market_stress_is_not_execution_cost_source() -> None:
    normal = load_market_stresses_csv(Path("data/sample/market_stresses.csv"))[0]

    assert not hasattr(normal, "bid_ask_spread_rate")
    assert not hasattr(normal, "transaction_cost_rate")
    assert not hasattr(normal, "market_impact_rate")
    assert not hasattr(normal, "participation_rate")
    assert not hasattr(normal, "liquidity_haircut_rate")
