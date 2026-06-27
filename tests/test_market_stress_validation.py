"""Tests for market stress validation with new execution assumptions."""

from decimal import Decimal
from pathlib import Path

from lmt_calibration.loaders import load_market_stresses_csv


def test_load_market_stresses_with_execution_assumptions():
    """Test loading market stresses with new execution cost fields."""
    stresses = load_market_stresses_csv(Path("data/sample/market_stresses.csv"))

    assert len(stresses) == 4
    assert stresses[0].market_stress_id == "normal_market_conditions"
    assert stresses[1].market_stress_id == "moderate_market_stress"
    assert stresses[2].market_stress_id == "severe_market_stress"
    assert stresses[3].market_stress_id == "historical_crisis_2008"


def test_market_stress_has_required_execution_fields():
    """Test that loaded market stresses have all execution assumption fields."""
    stresses = load_market_stresses_csv(Path("data/sample/market_stresses.csv"))
    normal = stresses[0]

    # Required new fields
    assert hasattr(normal, "bid_ask_spread_rate")
    assert hasattr(normal, "transaction_cost_rate")
    assert hasattr(normal, "market_impact_rate")
    assert hasattr(normal, "participation_rate")
    assert hasattr(normal, "liquidity_haircut_rate")

    # Verify types
    assert isinstance(normal.bid_ask_spread_rate, Decimal)
    assert isinstance(normal.transaction_cost_rate, Decimal)
    assert isinstance(normal.market_impact_rate, Decimal)
    assert isinstance(normal.participation_rate, Decimal)
    assert isinstance(normal.liquidity_haircut_rate, Decimal)


def test_market_stress_normal_execution_costs():
    """Test normal market conditions have reasonable execution costs."""
    stresses = load_market_stresses_csv(Path("data/sample/market_stresses.csv"))
    normal = stresses[0]

    # Normal market should have low costs
    assert normal.market_shock_rate == Decimal("0.00")
    assert normal.bid_ask_spread_rate == Decimal("0.0010")  # 0.1%
    assert normal.transaction_cost_rate == Decimal("0.0005")  # 0.05%
    assert normal.market_impact_rate == Decimal("0.0005")  # 0.05%
    assert normal.participation_rate == Decimal("0.50")  # 50% daily
    assert normal.liquidity_haircut_rate == Decimal("0.05")  # 5%


def test_market_stress_crisis_execution_costs():
    """Test crisis market conditions have higher execution costs."""
    stresses = load_market_stresses_csv(Path("data/sample/market_stresses.csv"))
    crisis = stresses[3]

    # Crisis market should have high costs
    assert crisis.market_stress_id == "historical_crisis_2008"
    assert crisis.market_shock_rate == Decimal("-0.35")
    assert crisis.bid_ask_spread_rate == Decimal("0.0100")  # 1.0%
    assert crisis.transaction_cost_rate == Decimal("0.0050")  # 0.5%
    assert crisis.market_impact_rate == Decimal("0.0075")  # 0.75%
    assert crisis.participation_rate == Decimal("0.05")  # 5% daily
    assert crisis.liquidity_haircut_rate == Decimal("0.25")  # 25%
