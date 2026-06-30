from decimal import Decimal

import pytest

from lmt_calibration.domain import (
    AssetGroup,
    FundSnapshot,
    LiquidationStrategyConfig,
    LiquidationStrategyType,
    LmtParameters,
)
from lmt_calibration.engines import (
    LiquidationStrategyError,
    StressedLiquidationPosition,
    calculate_liquidation_strategy,
)


def test_most_liquid_first_uses_cash_above_buffer_then_assets() -> None:
    result = calculate_liquidation_strategy(
        scenario_id="cash_then_reverse_repo",
        fund=_fund(),
        positions=(
            _position("cash", AssetGroup.CASH, "150", "0", "1", 0),
            _position("reverse_repo", AssetGroup.REVERSE_REPO, "300", "0.10", "1", 0, 1),
            _position("listed_etf", AssetGroup.LISTED_ETF, "300", "0.05", "1", 2),
        ),
        redemption_amount=Decimal("200"),
        strategy=_strategy(
            "cash_then_liquid_assets",
            LiquidationStrategyType.MOST_LIQUID_FIRST,
        ),
        lmt_parameters=_parameters(),
        stress_horizon_days=5,
    )

    assert result.cash_used == Decimal("50.0")
    assert result.assets_liquidated[0].position_id == "reverse_repo"
    assert result.assets_liquidated[0].gross_sale_amount.quantize(Decimal("0.01")) == Decimal(
        "166.67"
    )
    assert result.assets_liquidated[0].post_haircut_cash_raised == Decimal(
        "150.0000000000000000000000000"
    )
    assert result.shortfall == Decimal("0E-25")
    assert result.asset_group_allocations[AssetGroup.CASH] == Decimal("50.0")
    assert result.asset_group_allocations[AssetGroup.REVERSE_REPO].quantize(
        Decimal("0.01")
    ) == Decimal("166.67")


def test_no_strategy_consumes_cash_below_minimum_buffer() -> None:
    result = calculate_liquidation_strategy(
        scenario_id="cash_below_buffer",
        fund=_fund(),
        positions=(
            _position("cash", AssetGroup.CASH, "80", "0", "1", 0),
            _position("listed_etf", AssetGroup.LISTED_ETF, "500", "0", "1", 2),
        ),
        redemption_amount=Decimal("100"),
        strategy=_strategy(
            "cash_then_liquid_assets",
            LiquidationStrategyType.MOST_LIQUID_FIRST,
        ),
        lmt_parameters=_parameters(),
        stress_horizon_days=5,
    )

    assert result.cash_used == Decimal("0")
    assert result.minimum_cash_buffer_preserved is False
    assert result.asset_group_allocations[AssetGroup.LISTED_ETF] == Decimal("100")
    assert AssetGroup.CASH not in result.asset_group_allocations


@pytest.mark.parametrize(
    (
        "strategy_id",
        "strategy_type",
        "cash_buffer_use_rate",
        "weights",
        "expected_cash_used",
    ),
    (
        (
            "cash_then_liquid_assets",
            LiquidationStrategyType.MOST_LIQUID_FIRST,
            None,
            None,
            Decimal("50.0"),
        ),
        (
            "portfolio_profile_pro_rata",
            LiquidationStrategyType.PRO_RATA,
            None,
            None,
            Decimal("0"),
        ),
        (
            "partial_cash_then_pro_rata",
            LiquidationStrategyType.HYBRID,
            Decimal("1"),
            None,
            Decimal("50.0"),
        ),
        (
            "balanced_custom_weights",
            LiquidationStrategyType.CUSTOM_WEIGHTS,
            None,
            {
                AssetGroup.CASH: Decimal("0.50"),
                AssetGroup.LISTED_ETF: Decimal("0.50"),
            },
            Decimal("50.0"),
        ),
    ),
)
def test_all_strategies_preserve_cash_above_minimum_buffer(
    strategy_id: str,
    strategy_type: LiquidationStrategyType,
    cash_buffer_use_rate: Decimal | None,
    weights: dict[AssetGroup, Decimal] | None,
    expected_cash_used: Decimal,
) -> None:
    strategy = _strategy(
        strategy_id,
        strategy_type,
        cash_buffer_use_rate=cash_buffer_use_rate,
        weights=weights,
    )

    result = calculate_liquidation_strategy(
        scenario_id="buffer_preservation",
        fund=_fund(),
        positions=(
            _position("cash", AssetGroup.CASH, "150", "0", "1", 0),
            _position("listed_etf", AssetGroup.LISTED_ETF, "500", "0", "1", 2),
        ),
        redemption_amount=Decimal("200"),
        strategy=strategy,
        lmt_parameters=_parameters(),
        stress_horizon_days=5,
    )

    assert result.cash_used == expected_cash_used
    assert result.minimum_cash_buffer_preserved is True


def test_pro_rata_allocates_once_by_eligible_stressed_market_value() -> None:
    result = calculate_liquidation_strategy(
        scenario_id="pro_rata",
        fund=_fund(),
        positions=(
            _position("listed_etf", AssetGroup.LISTED_ETF, "300", "0", "1", 2),
            _position("listed_equity", AssetGroup.LISTED_EQUITY, "100", "0", "1", 2),
        ),
        redemption_amount=Decimal("200"),
        strategy=_strategy("portfolio_profile_pro_rata", LiquidationStrategyType.PRO_RATA),
        lmt_parameters=_parameters(),
        stress_horizon_days=5,
    )

    assert result.cash_used == Decimal("0")
    assert result.asset_group_allocations == {
        AssetGroup.LISTED_ETF: Decimal("150.00"),
        AssetGroup.LISTED_EQUITY: Decimal("50.00"),
    }
    assert result.shortfall == Decimal("0.00")


def test_hybrid_uses_allowed_cash_then_simple_pro_rata() -> None:
    result = calculate_liquidation_strategy(
        scenario_id="hybrid",
        fund=_fund(),
        positions=(
            _position("cash", AssetGroup.CASH, "300", "0", "1", 0),
            _position("listed_etf", AssetGroup.LISTED_ETF, "400", "0", "1", 2),
            _position("listed_equity", AssetGroup.LISTED_EQUITY, "400", "0", "1", 2),
        ),
        redemption_amount=Decimal("300"),
        strategy=_strategy(
            "partial_cash_then_pro_rata",
            LiquidationStrategyType.HYBRID,
            cash_buffer_use_rate=Decimal("0.50"),
        ),
        lmt_parameters=_parameters(),
        stress_horizon_days=5,
    )

    assert result.cash_used == Decimal("100.00")
    assert result.asset_group_allocations == {
        AssetGroup.CASH: Decimal("100.00"),
        AssetGroup.LISTED_ETF: Decimal("100.000"),
        AssetGroup.LISTED_EQUITY: Decimal("100.000"),
    }


def test_hybrid_requires_cash_buffer_use_rate() -> None:
    with pytest.raises(LiquidationStrategyError, match="cash_buffer_use_rate"):
        calculate_liquidation_strategy(
            scenario_id="hybrid_missing_rate",
            fund=_fund(),
            positions=(_position("cash", AssetGroup.CASH, "300", "0", "1", 0),),
            redemption_amount=Decimal("100"),
            strategy=_strategy("hybrid_missing_rate", LiquidationStrategyType.HYBRID),
            lmt_parameters=_parameters(),
            stress_horizon_days=5,
        )


def test_custom_weights_allocates_by_asset_group_weights() -> None:
    result = calculate_liquidation_strategy(
        scenario_id="custom_weights",
        fund=_fund(),
        positions=(
            _position("listed_etf", AssetGroup.LISTED_ETF, "500", "0", "1", 2),
            _position("listed_equity", AssetGroup.LISTED_EQUITY, "500", "0", "1", 2),
        ),
        redemption_amount=Decimal("200"),
        strategy=_strategy(
            "balanced_custom_weights",
            LiquidationStrategyType.CUSTOM_WEIGHTS,
            weights={
                AssetGroup.LISTED_ETF: Decimal("0.75"),
                AssetGroup.LISTED_EQUITY: Decimal("0.25"),
            },
        ),
        lmt_parameters=_parameters(),
        stress_horizon_days=5,
    )

    assert result.asset_group_allocations == {
        AssetGroup.LISTED_ETF: Decimal("150.00"),
        AssetGroup.LISTED_EQUITY: Decimal("50.00"),
    }


def test_capacity_caps_create_reported_shortfall() -> None:
    result = calculate_liquidation_strategy(
        scenario_id="capacity_cap",
        fund=_fund(),
        positions=(
            _position("listed_etf", AssetGroup.LISTED_ETF, "100", "0", "0.50", 2),
            _position("listed_equity", AssetGroup.LISTED_EQUITY, "100", "0", "0.50", 2),
        ),
        redemption_amount=Decimal("200"),
        strategy=_strategy("portfolio_profile_pro_rata", LiquidationStrategyType.PRO_RATA),
        lmt_parameters=_parameters(),
        stress_horizon_days=5,
    )

    assert result.total_post_haircut_cash_raised == Decimal("100.00")
    assert result.shortfall == Decimal("100.00")


def test_zero_haircut_gross_sale_equals_post_haircut_cash_with_no_dilution() -> None:
    result = calculate_liquidation_strategy(
        scenario_id="base_no_haircut",
        fund=_fund(),
        positions=(_position("listed_etf", AssetGroup.LISTED_ETF, "500", "0", "1", 2),),
        redemption_amount=Decimal("100"),
        strategy=_strategy("portfolio_profile_pro_rata", LiquidationStrategyType.PRO_RATA),
        lmt_parameters=_parameters(),
        stress_horizon_days=5,
    )

    assert result.assets_liquidated[0].gross_sale_amount == Decimal("100")
    assert result.assets_liquidated[0].post_haircut_cash_raised == Decimal("100")
    assert result.total_haircut_cost == Decimal("0")
    assert result.dilution_amount == Decimal("0")
    assert result.shortfall == Decimal("0")


def test_positive_haircut_with_enough_capacity_targets_post_haircut_cash_need() -> None:
    result = calculate_liquidation_strategy(
        scenario_id="haircut_cost",
        fund=_fund(),
        positions=(_position("listed_etf", AssetGroup.LISTED_ETF, "500", "0.10", "1", 2),),
        redemption_amount=Decimal("100"),
        strategy=_strategy("portfolio_profile_pro_rata", LiquidationStrategyType.PRO_RATA),
        lmt_parameters=_parameters(),
        stress_horizon_days=5,
    )

    assert result.assets_liquidated[0].gross_sale_amount.quantize(Decimal("0.01")) == Decimal(
        "111.11"
    )
    assert result.assets_liquidated[0].post_haircut_cash_raised == Decimal(
        "100.0000000000000000000000000"
    )
    assert result.assets_liquidated[0].haircut_cost.quantize(Decimal("0.01")) == Decimal("11.11")
    assert result.shortfall == Decimal("0E-25")
    assert result.dilution_amount.quantize(Decimal("0.01")) == Decimal("11.11")
    assert result.dilution_rate.quantize(Decimal("0.0001")) == Decimal("0.0111")


def test_realised_execution_cost_requires_more_gross_sales_for_same_net_cash() -> None:
    without_execution_cost = calculate_liquidation_strategy(
        scenario_id="without_execution_cost",
        fund=_fund(),
        positions=(_position("listed_etf", AssetGroup.LISTED_ETF, "500", "0", "1", 2),),
        redemption_amount=Decimal("100"),
        strategy=_strategy("portfolio_profile_pro_rata", LiquidationStrategyType.PRO_RATA),
        lmt_parameters=_parameters(),
        stress_horizon_days=5,
    )
    with_execution_cost = calculate_liquidation_strategy(
        scenario_id="with_execution_cost",
        fund=_fund(),
        positions=(
            _position(
                "listed_etf",
                AssetGroup.LISTED_ETF,
                "500",
                "0",
                "1",
                2,
                realised_execution_cost_rate="0.02",
            ),
        ),
        redemption_amount=Decimal("100"),
        strategy=_strategy("portfolio_profile_pro_rata", LiquidationStrategyType.PRO_RATA),
        lmt_parameters=_parameters(),
        stress_horizon_days=5,
    )

    assert with_execution_cost.total_net_cash_raised == Decimal("100")
    assert with_execution_cost.assets_liquidated[0].gross_sale_amount > (
        without_execution_cost.assets_liquidated[0].gross_sale_amount
    )
    assert with_execution_cost.total_realised_execution_cost > Decimal("0")
    assert with_execution_cost.total_realised_liquidity_cost == (
        with_execution_cost.total_haircut_cost + with_execution_cost.total_realised_execution_cost
    )
    assert with_execution_cost.dilution_amount == (
        with_execution_cost.total_realised_liquidity_cost
    )


def test_positive_haircut_with_insufficient_capacity_sells_capacity_and_reports_shortfall() -> None:
    result = calculate_liquidation_strategy(
        scenario_id="haircut_capacity_shortfall",
        fund=_fund(),
        positions=(_position("listed_etf", AssetGroup.LISTED_ETF, "100", "0.10", "0.50", 2),),
        redemption_amount=Decimal("100"),
        strategy=_strategy("portfolio_profile_pro_rata", LiquidationStrategyType.PRO_RATA),
        lmt_parameters=_parameters(),
        stress_horizon_days=5,
    )

    assert result.assets_liquidated[0].gross_sale_amount == Decimal("50.00")
    assert result.assets_liquidated[0].post_haircut_cash_raised == Decimal("45.0000")
    assert result.shortfall == Decimal("55.0000")


def test_remaining_liquid_buffer_rate_uses_post_haircut_eligible_liquidity() -> None:
    result = calculate_liquidation_strategy(
        scenario_id="remaining_buffer_post_haircut",
        fund=_fund(),
        positions=(
            _position("cash", AssetGroup.CASH, "200", "0", "1", 0),
            _position("listed_etf", AssetGroup.LISTED_ETF, "500", "0.10", "1", 2),
        ),
        redemption_amount=Decimal("100"),
        strategy=_strategy("portfolio_profile_pro_rata", LiquidationStrategyType.PRO_RATA),
        lmt_parameters=_parameters(),
        stress_horizon_days=5,
    )

    expected_nav_after_redemption = Decimal("700") - Decimal("100") - result.total_haircut_cost
    assert result.remaining_liquid_resources == Decimal("550.0000000000000000000000000")
    assert result.remaining_liquid_buffer_rate == (
        result.remaining_liquid_resources / expected_nav_after_redemption
    )


def test_repo_financing_is_not_liquidated() -> None:
    result = calculate_liquidation_strategy(
        scenario_id="repo_financing_excluded",
        fund=_fund(),
        positions=(
            _position("repo_financing", AssetGroup.REPO_FINANCING, "1000", "0", "1", 0),
            _position("listed_etf", AssetGroup.LISTED_ETF, "100", "0", "1", 2),
        ),
        redemption_amount=Decimal("100"),
        strategy=_strategy(
            "cash_then_liquid_assets",
            LiquidationStrategyType.MOST_LIQUID_FIRST,
        ),
        lmt_parameters=_parameters(),
        stress_horizon_days=5,
    )

    assert [asset.position_id for asset in result.assets_liquidated] == ["listed_etf"]
    assert AssetGroup.REPO_FINANCING not in result.asset_group_allocations


def test_ineligible_assets_are_excluded_by_horizon() -> None:
    result = calculate_liquidation_strategy(
        scenario_id="horizon_filter",
        fund=_fund(),
        positions=(
            _position("slow_etf", AssetGroup.LISTED_ETF, "500", "0", "1", 10),
            _position("late_reverse_repo", AssetGroup.REVERSE_REPO, "500", "0", "1", 1, 5),
            _position("eligible_equity", AssetGroup.LISTED_EQUITY, "500", "0", "1", 2),
        ),
        redemption_amount=Decimal("100"),
        strategy=_strategy(
            "cash_then_liquid_assets",
            LiquidationStrategyType.MOST_LIQUID_FIRST,
        ),
        lmt_parameters=_parameters(),
        stress_horizon_days=5,
    )

    assert [asset.position_id for asset in result.assets_liquidated] == ["eligible_equity"]
    assert result.asset_group_allocations == {AssetGroup.LISTED_EQUITY: Decimal("100")}


def _fund() -> FundSnapshot:
    return FundSnapshot(
        fund_id="lux_dynamic_allocation",
        as_of_date="2026-06-30",
        fund_name="Lux Dynamic Allocation Fund",
        base_currency="EUR",
        nav=Decimal("1000"),
        dealing_frequency="daily",
        redemption_notice_days=1,
        redemption_settlement_days=3,
    )


def _parameters() -> LmtParameters:
    return LmtParameters(
        fund_id="lux_dynamic_allocation",
        as_of_date="2026-06-30",
        parameter_set_id="board_approved_base",
        swing_threshold_rate=Decimal("0.015"),
        max_swing_factor_rate=Decimal("0.03"),
        gate_threshold_rate=Decimal("0.10"),
        minimum_buffer_rate=Decimal("0.10"),
    )


def _strategy(
    strategy_id: str,
    strategy_type: LiquidationStrategyType,
    *,
    cash_buffer_use_rate: Decimal | None = None,
    weights: dict[AssetGroup, Decimal] | None = None,
) -> LiquidationStrategyConfig:
    return LiquidationStrategyConfig(
        liquidation_strategy_id=strategy_id,
        version="1.0",
        name=strategy_id,
        description=f"Synthetic {strategy_id} strategy.",
        strategy_type=strategy_type,
        cash_buffer_use_rate=cash_buffer_use_rate,
        preserve_minimum_buffer=True,
        weights=weights,
    )


def _position(
    position_id: str,
    asset_group: AssetGroup,
    stressed_market_value: str,
    stressed_haircut_rate: str,
    stressed_liquidity_capacity_rate: str,
    settlement_days: int,
    maturity_days: int | None = None,
    *,
    realised_execution_cost_rate: str = "0",
) -> StressedLiquidationPosition:
    return StressedLiquidationPosition(
        position_id=position_id,
        asset_group=asset_group,
        stressed_market_value=Decimal(stressed_market_value),
        stressed_haircut_rate=Decimal(stressed_haircut_rate),
        realised_execution_cost_rate=Decimal(realised_execution_cost_rate),
        stressed_liquidity_capacity_rate=Decimal(stressed_liquidity_capacity_rate),
        settlement_days=settlement_days,
        maturity_days=maturity_days,
    )
