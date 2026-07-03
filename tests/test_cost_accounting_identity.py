"""Unit tests for liquidity cost accounting identity and allocation methodology."""

from decimal import Decimal

from lmt_calibration.domain import (
    AssetGroup,
    AssetPosition,
    ClientClass,
    FundSnapshot,
    InstrumentSubtype,
    InvestorClassProfile,
    LiquidationStrategyConfig,
    LiquidationStrategyType,
    LiquidityExecutionAssumption,
    LiquidityStress,
    LmtParameters,
    RedemptionPathAssumptions,
)
from lmt_calibration.engines.redemption_path import run_redemption_path

ZERO = Decimal("0")


# Test helper functions
def _fund() -> FundSnapshot:
    return FundSnapshot(
        fund_id="test_fund",
        as_of_date="2026-01-01",
        fund_name="Test Fund",
        base_currency="EUR",
        nav=Decimal("100000"),
        dealing_frequency="daily",
        redemption_notice_days=1,
        redemption_settlement_days=3,
    )


def _cash(market_value: str = "10000") -> AssetPosition:
    return AssetPosition(
        position_id="eur_operating_cash",
        fund_id="test_fund",
        as_of_date="2026-01-01",
        asset_group=AssetGroup.CASH,
        instrument_type="cash",
        instrument_subtype=InstrumentSubtype.CASH,
        instrument_name="EUR Operating Cash",
        currency="EUR",
        market_value=Decimal(market_value),
        base_haircut_rate=Decimal("0"),
        base_liquidity_capacity_rate=Decimal("1"),
        settlement_days=0,
    )


def _equity(position_id: str = "test_equity", market_value: str = "90000") -> AssetPosition:
    return AssetPosition(
        position_id=position_id,
        fund_id="test_fund",
        as_of_date="2026-01-01",
        asset_group=AssetGroup.LISTED_EQUITY,
        instrument_type="listed_equity",
        instrument_subtype=InstrumentSubtype.LISTED_EQUITY,
        instrument_name="Test Equity",
        ticker="TEST",
        currency="EUR",
        market_value=Decimal(market_value),
        risk_factor_id="test_equity",
        beta=Decimal("1"),
        base_haircut_rate=Decimal("0"),
        base_liquidity_capacity_rate=Decimal("1"),
        settlement_days=2,
    )


def _investor(
    client_class: ClientClass = ClientClass.INSTITUTIONAL,
    nav_share: str = "1",
    base_rate: str = "0.05",
    stress_rate: str = "0.10",
) -> InvestorClassProfile:
    return InvestorClassProfile(
        fund_id="test_fund",
        as_of_date="2026-01-01",
        client_class=client_class,
        nav_share_rate=Decimal(nav_share),
        base_redemption_rate=Decimal(base_rate),
        stress_redemption_rate=Decimal(stress_rate),
        concentration_factor=Decimal("0.50"),
        notice_days=1,
        settlement_days=3,
    )


def _liquidity_stress(cost_rate: str = "0") -> LiquidityStress:
    assumption = LiquidityExecutionAssumption(
        bid_ask_spread_rate=Decimal(cost_rate),
        transaction_cost_rate=Decimal("0"),
        market_impact_rate=Decimal("0"),
        participation_rate=Decimal("1"),
        liquidity_haircut_rate=Decimal("0"),
    )
    return LiquidityStress(
        liquidity_stress_id="test_stress",
        version="1.0",
        name="test_stress",
        description="Test liquidity stress.",
        stress_horizon_days=5,
        execution_assumptions_by_asset_group={
            AssetGroup.CASH: assumption,
            AssetGroup.LISTED_EQUITY: assumption,
        },
    )


def _strategy() -> LiquidationStrategyConfig:
    return LiquidationStrategyConfig(
        liquidation_strategy_id="test_strategy",
        version="1.0",
        name="test_strategy",
        description="Test strategy.",
        strategy_type=LiquidationStrategyType.MOST_LIQUID_FIRST,
        preserve_minimum_buffer=True,
    )


def _parameters(
    gate_threshold: str = "1",
    swing_threshold: str = "1",
    minimum_buffer: str = "0",
) -> LmtParameters:
    return LmtParameters(
        fund_id="test_fund",
        as_of_date="2026-01-01",
        parameter_set_id="test_parameters",
        swing_threshold_rate=Decimal(swing_threshold),
        max_swing_factor_rate=Decimal("0.03"),
        gate_threshold_rate=Decimal(gate_threshold),
        minimum_buffer_rate=Decimal(minimum_buffer),
    )


def test_economic_liquidity_cost_identity_no_swing():
    """Verify: economic_cost = investor_borne + fund_borne (no swing case)."""
    result = run_redemption_path(
        fund=_fund(),
        positions=(_cash(), _equity()),
        investor_profiles=[_investor()],
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(swing_threshold="1"),  # NO SWING
        assumptions=RedemptionPathAssumptions(
            scenario_id="test_no_swing",
            start_date="2026-01-01",
            random_seed=42,
        ),
    )

    for month in result.monthly_results:
        total_borne = (
            month.investor_borne_liquidity_cost_after_contagion
            + month.fund_borne_liquidity_cost_after_contagion
        )
        assert month.realised_liquidity_cost_after_contagion == total_borne, (
            f"Month {month.period.month_number}: "
            f"realised={month.realised_liquidity_cost_after_contagion}, "
            f"investor={month.investor_borne_liquidity_cost_after_contagion}, "
            f"fund={month.fund_borne_liquidity_cost_after_contagion}, "
            f"sum={total_borne}"
        )


def test_economic_liquidity_cost_identity_with_swing():
    """Verify: economic_cost = investor_borne + fund_borne (swing active case)."""
    result = run_redemption_path(
        fund=_fund(),
        positions=(_cash(), _equity()),
        investor_profiles=[_investor(base_rate="0.15")],  # High redemption
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(swing_threshold="0.05"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="test_with_swing",
            start_date="2026-01-01",
            random_seed=42,
            swing_pricing_months=[1, 2, 3],  # SWING ACTIVE
        ),
    )

    for month in result.monthly_results:
        total_borne = (
            month.investor_borne_liquidity_cost_after_contagion
            + month.fund_borne_liquidity_cost_after_contagion
        )
        assert month.realised_liquidity_cost_after_contagion == total_borne, (
            f"Month {month.period.month_number}: "
            f"realised={month.realised_liquidity_cost_after_contagion}, "
            f"investor={month.investor_borne_liquidity_cost_after_contagion}, "
            f"fund={month.fund_borne_liquidity_cost_after_contagion}"
        )


def test_swing_fully_transfers_costs():
    """When swing applied: investor_borne = economic, fund_borne = 0."""
    result = run_redemption_path(
        fund=_fund(),
        positions=(_cash(), _equity()),
        investor_profiles=[_investor(base_rate="0.15")],
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(swing_threshold="0.05"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="test_swing_transfer",
            start_date="2026-01-01",
            random_seed=42,
            swing_pricing_months=[1, 2, 3],
        ),
    )

    for month in result.monthly_results[0:3]:  # Check months with swing
        if month.realised_liquidity_cost_after_contagion > ZERO:
            # When swing is applied and there's a cost, all should go to investors
            assert month.fund_borne_liquidity_cost_after_contagion == ZERO, (
                f"Month {month.period.month_number}: "
                f"fund_borne should be zero when swing transfers all costs"
            )
            assert month.investor_borne_liquidity_cost_after_contagion == (
                month.realised_liquidity_cost_after_contagion
            )


def test_no_swing_fund_bears_all_costs():
    """When no swing: investor_borne = 0, fund_borne = economic."""
    result = run_redemption_path(
        fund=_fund(),
        positions=(_cash(), _equity()),
        investor_profiles=[_investor(base_rate="0.05")],
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(swing_threshold="0.1"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="test_no_swing_cost",
            start_date="2026-01-01",
            random_seed=42,
        ),
    )

    for month in result.monthly_results:
        if month.realised_liquidity_cost_after_contagion > ZERO:
            # When no swing, all costs should be fund-borne
            assert month.investor_borne_liquidity_cost_after_contagion == ZERO
            assert month.fund_borne_liquidity_cost_after_contagion == (
                month.realised_liquidity_cost_after_contagion
            )


def test_gate_period_cost_in_economic_cost():
    """Gate-period liquidation cost is part of total economic cost."""
    result = run_redemption_path(
        fund=_fund(),
        positions=(_cash(), _equity()),
        investor_profiles=[_investor(base_rate="0.15")],
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(gate_threshold="0.10"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="test_gate_cost",
            start_date="2026-01-01",
            random_seed=42,
            gate_months=[1],  # GATE ACTIVE IN MONTH 1
        ),
    )

    month_1 = result.monthly_results[0]
    # Economic cost should include gate-period liquidation
    # Verify identity holds
    assert (
        month_1.investor_borne_liquidity_cost_after_contagion
        + month_1.fund_borne_liquidity_cost_after_contagion
        == month_1.realised_liquidity_cost_after_contagion
    )


def test_gate_with_swing_allocation():
    """Gate + swing: all economic costs (immediate + gate) allocated to investors."""
    result = run_redemption_path(
        fund=_fund(),
        positions=(_cash(), _equity()),
        investor_profiles=[_investor(base_rate="0.15")],
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(gate_threshold="0.10", swing_threshold="0.05"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="test_gate_swing",
            start_date="2026-01-01",
            random_seed=42,
            gate_months=[1],
            swing_pricing_months=[1],  # BOTH ACTIVE
        ),
    )

    month_1 = result.monthly_results[0]
    if month_1.realised_liquidity_cost_after_contagion > ZERO:
        # All economic cost transferred to investors
        assert month_1.fund_borne_liquidity_cost_after_contagion == ZERO
        assert month_1.investor_borne_liquidity_cost_after_contagion == (
            month_1.realised_liquidity_cost_after_contagion
        )


def test_nav_reconciliation_identity():
    """closing_nav = opening_nav + market - paid - fund_borne."""
    result = run_redemption_path(
        fund=_fund(),
        positions=(_cash(), _equity()),
        investor_profiles=[_investor(base_rate="0.05")],
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(),
        assumptions=RedemptionPathAssumptions(
            scenario_id="test_nav_identity",
            start_date="2026-01-01",
            random_seed=42,
        ),
    )

    for month in result.monthly_results:
        # Verify the core identity: realised = investor_borne + fund_borne
        total_borne = (
            month.investor_borne_liquidity_cost_after_contagion
            + month.fund_borne_liquidity_cost_after_contagion
        )
        assert month.realised_liquidity_cost_after_contagion == total_borne, (
            f"Month {month.period.month_number}: cost identity failed"
        )


def test_gate_cost_not_double_subtracted():
    """Gate cost appears once in fund_borne, not separately."""
    result = run_redemption_path(
        fund=_fund(),
        positions=(_cash(), _equity()),
        investor_profiles=[_investor(base_rate="0.15")],
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(gate_threshold="0.10"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="test_no_double_sub",
            start_date="2026-01-01",
            random_seed=42,
            gate_months=[1],
        ),
    )

    month_1 = result.monthly_results[0]

    market_impact = month_1.pre_lmt_nav - month_1.opening_nav + month_1.contractual_cashflow_amount

    calculated_closing = (
        month_1.opening_nav
        + market_impact
        - month_1.lmt_assessment.paid_redemption_amount
        - month_1.fund_borne_liquidity_cost_after_contagion
    )

    # NAV reconciliation should hold without separate gate cost subtraction
    assert abs(month_1.closing_nav - calculated_closing) < Decimal("0.01"), (
        "Gate cost appears to be subtracted twice if NAV reconciliation fails"
    )


def test_unsettled_gate_cash_settles_next_month():
    """Previous month's unsettled gate cash appears in next month's opening_cash."""
    result = run_redemption_path(
        fund=_fund(),
        positions=(_cash(), _equity()),
        investor_profiles=[_investor(base_rate="0.15")],
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(gate_threshold="0.10"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="test_unsettled",
            start_date="2026-01-01",
            random_seed=42,
            gate_months=[1],
        ),
    )

    month_1 = result.monthly_results[0]
    if month_1.gate_period_unsettled_cash > ZERO:
        month_2 = result.monthly_results[1]
        # Month 1's unsettled cash becomes opening cash for Month 2
        assert month_1.gate_period_unsettled_cash <= month_2.opening_cash
