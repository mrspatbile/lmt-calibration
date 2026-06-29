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
    MarketStress,
    RedemptionPathAssumptions,
)
from lmt_calibration.engines.redemption_path import run_redemption_path


def test_redemption_path_returns_twelve_months_and_carries_nav_forward() -> None:
    result = run_redemption_path(
        fund=_fund(),
        positions=(
            _cash("200"),
            _equity("euro_equity", "800"),
        ),
        investor_profiles=(_investor(ClientClass.RETAIL, "1", "0.02", "0"),),
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(gate_threshold="1"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="twelve_month_path",
            start_date="2026-01-01",
            random_seed=11,
        ),
    )

    assert len(result.monthly_results) == 12
    assert result.monthly_results[1].opening_nav == result.monthly_results[0].closing_nav


def test_redemption_path_is_deterministic_for_fixed_seed() -> None:
    first = _deterministic_path_result()
    second = _deterministic_path_result()

    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_market_stress_is_applied_once_in_selected_month() -> None:
    result = run_redemption_path(
        fund=_fund(),
        positions=(
            _cash("100"),
            _equity("euro_equity", "900"),
        ),
        investor_profiles=(_investor(ClientClass.RETAIL, "1", "0", "0"),),
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(gate_threshold="1"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="market_once",
            start_date="2026-01-01",
            random_seed=1,
            stress_months=(2, 3),
            market_stress_month=2,
        ),
        market_stress=MarketStress(
            market_stress_id="severe_equity_stress",
            version="1.0",
            name="severe_equity_stress",
            description="Synthetic severe equity stress.",
            market_shock_rate=Decimal("-0.10"),
        ),
    )

    assert [month.market_stress_applied for month in result.monthly_results[:3]] == [
        False,
        True,
        False,
    ]
    month_2_equity = _position_value(result.monthly_results[1].positions, "euro_equity")
    month_3_equity = _position_value(result.monthly_results[2].positions, "euro_equity")
    assert month_2_equity == Decimal("810.00")
    assert month_3_equity == Decimal("810.00")


def test_reverse_repo_maturity_becomes_cash_before_liquidation() -> None:
    result = run_redemption_path(
        fund=_fund(),
        positions=(
            _cash("0"),
            _reverse_repo("overnight_reverse_repo", "100", maturity_days=15),
            _equity("euro_equity", "900"),
        ),
        investor_profiles=(_investor(ClientClass.RETAIL, "1", "0", "0"),),
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(gate_threshold="1"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="reverse_repo_cashflow",
            start_date="2026-01-01",
            random_seed=1,
        ),
    )

    first_month = result.monthly_results[0]
    assert first_month.contractual_cashflow_amount == Decimal("100")
    assert first_month.closing_cash == Decimal("100")
    assert _position_value(first_month.positions, "overnight_reverse_repo") == Decimal("0")


def test_gate_paid_redemptions_are_allocated_pro_rata_and_backlog_carries_forward() -> None:
    result = run_redemption_path(
        fund=_fund(),
        positions=(
            _cash("300"),
            _equity("euro_equity", "700"),
        ),
        investor_profiles=(
            _investor(ClientClass.RETAIL, "0.50", "0", "0.50"),
            _investor(ClientClass.INSTITUTIONAL, "0.50", "0", "0.50"),
        ),
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(gate_threshold="0.10"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="gate_backlog",
            start_date="2026-01-01",
            random_seed=1,
            stress_months=(1,),
        ),
    )

    first_month = result.monthly_results[0]
    states = {state.client_class: state for state in first_month.investor_class_states}

    assert first_month.lmt_assessment.gate_activated is True
    assert first_month.lmt_assessment.paid_redemption_amount == Decimal("100.0")
    assert states[ClientClass.RETAIL].paid_redemption_amount == Decimal("50.00")
    assert states[ClientClass.INSTITUTIONAL].paid_redemption_amount == Decimal("50.00")
    assert states[ClientClass.RETAIL].deferred_redemption_amount == Decimal("200.00")
    assert states[ClientClass.INSTITUTIONAL].deferred_redemption_amount == Decimal("200.00")
    assert sum((entry.remaining_amount for entry in first_month.backlog), Decimal("0")) == Decimal(
        "400.00"
    )
    assert result.monthly_results[1].investor_class_states[0].opening_backlog_amount > Decimal("0")


def _fund() -> FundSnapshot:
    return FundSnapshot(
        fund_id="lux_dynamic_allocation",
        as_of_date="2026-01-01",
        fund_name="Lux Dynamic Allocation Fund",
        base_currency="EUR",
        nav=Decimal("1000"),
        dealing_frequency="daily",
        redemption_notice_days=1,
        redemption_settlement_days=3,
    )


def _deterministic_path_result():
    return run_redemption_path(
        fund=_fund(),
        positions=(
            _cash("200"),
            _equity("euro_equity", "800"),
        ),
        investor_profiles=(_investor(ClientClass.RETAIL, "1", "0.02", "0"),),
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(gate_threshold="1"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="deterministic_path",
            start_date="2026-01-01",
            random_seed=42,
        ),
    )


def _cash(market_value: str) -> AssetPosition:
    return AssetPosition(
        position_id="eur_operating_cash",
        fund_id="lux_dynamic_allocation",
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


def _equity(position_id: str, market_value: str) -> AssetPosition:
    return AssetPosition(
        position_id=position_id,
        fund_id="lux_dynamic_allocation",
        as_of_date="2026-01-01",
        asset_group=AssetGroup.LISTED_EQUITY,
        instrument_type="listed_equity",
        instrument_subtype=InstrumentSubtype.LISTED_EQUITY,
        instrument_name="Synthetic European Equity Holding",
        ticker="SYN GY",
        currency="EUR",
        market_value=Decimal(market_value),
        risk_factor_id="europe_equity",
        beta=Decimal("1"),
        base_haircut_rate=Decimal("0"),
        base_liquidity_capacity_rate=Decimal("1"),
        settlement_days=2,
    )


def _reverse_repo(position_id: str, market_value: str, maturity_days: int) -> AssetPosition:
    return AssetPosition(
        position_id=position_id,
        fund_id="lux_dynamic_allocation",
        as_of_date="2026-01-01",
        asset_group=AssetGroup.REVERSE_REPO,
        instrument_type="reverse_repo",
        instrument_subtype=InstrumentSubtype.REVERSE_REPO,
        instrument_name="EUR Reverse Repo Synthetic",
        currency="EUR",
        market_value=Decimal(market_value),
        base_haircut_rate=Decimal("0"),
        base_liquidity_capacity_rate=Decimal("1"),
        settlement_days=1,
        maturity_days=maturity_days,
    )


def _investor(
    client_class: ClientClass,
    nav_share: str,
    base_rate: str,
    stress_rate: str,
) -> InvestorClassProfile:
    return InvestorClassProfile(
        fund_id="lux_dynamic_allocation",
        as_of_date="2026-01-01",
        client_class=client_class,
        nav_share_rate=Decimal(nav_share),
        base_redemption_rate=Decimal(base_rate),
        stress_redemption_rate=Decimal(stress_rate),
        concentration_factor=Decimal("0.50"),
        notice_days=1,
        settlement_days=3,
    )


def _liquidity_stress() -> LiquidityStress:
    assumptions = {
        AssetGroup.CASH: _execution_assumption(),
        AssetGroup.LISTED_EQUITY: _execution_assumption(),
        AssetGroup.REVERSE_REPO: _execution_assumption(),
    }
    return LiquidityStress(
        liquidity_stress_id="normal_liquidity",
        version="1.0",
        name="normal_liquidity",
        description="Synthetic normal liquidity.",
        stress_horizon_days=5,
        execution_assumptions_by_asset_group=assumptions,
    )


def _execution_assumption() -> LiquidityExecutionAssumption:
    return LiquidityExecutionAssumption(
        bid_ask_spread_rate=Decimal("0"),
        transaction_cost_rate=Decimal("0"),
        market_impact_rate=Decimal("0"),
        participation_rate=Decimal("1"),
        liquidity_haircut_rate=Decimal("0"),
    )


def _strategy() -> LiquidationStrategyConfig:
    return LiquidationStrategyConfig(
        liquidation_strategy_id="cash_then_liquid_assets",
        version="1.0",
        name="cash_then_liquid_assets",
        description="Synthetic most-liquid-first strategy.",
        strategy_type=LiquidationStrategyType.MOST_LIQUID_FIRST,
        preserve_minimum_buffer=True,
    )


def _parameters(gate_threshold: str) -> LmtParameters:
    return LmtParameters(
        fund_id="lux_dynamic_allocation",
        as_of_date="2026-01-01",
        parameter_set_id="path_parameters",
        swing_threshold_rate=Decimal("1"),
        max_swing_factor_rate=Decimal("0.03"),
        gate_threshold_rate=Decimal(gate_threshold),
        minimum_buffer_rate=Decimal("0"),
    )


def _position_value(positions: tuple, position_id: str) -> Decimal:
    return next(
        position.market_value for position in positions if position.position_id == position_id
    )
