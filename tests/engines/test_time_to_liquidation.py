from datetime import date
from decimal import Decimal
from pathlib import Path

from lmt_calibration.domain import AssetGroup, AssetPosition, InstrumentSubtype
from lmt_calibration.engines.time_to_liquidation import (
    build_ttl_sensitivity_results,
    calculate_cumulative_liquidation_curve,
    calculate_ttl_to_redemption_shock,
)
from lmt_calibration.loaders import load_funds_csv, load_positions_csv


def test_full_coverage_returns_first_business_day() -> None:
    curve = calculate_cumulative_liquidation_curve(
        (_cash("100"), _listed_etf("900", capacity_rate="1", settlement_days=0)),
        nav=Decimal("1000"),
        participation_rate=Decimal("0.50"),
        liquidity_haircut_rate=Decimal("0"),
        horizon_days=5,
    )

    assert calculate_ttl_to_redemption_shock(curve, Decimal("500")) == 1


def test_partial_coverage_reports_positive_unmet_amount() -> None:
    result = build_ttl_sensitivity_results(
        (_cash("100"), _listed_etf("900", capacity_rate="0.10", settlement_days=0)),
        nav=Decimal("1000"),
        redemption_shock_rate=Decimal("0.90"),
        horizon_days=1,
        base_participation_rate=Decimal("0.10"),
        base_liquidity_haircut_rate=Decimal("0.50"),
    )[0]

    assert result.ttl_to_redemption_shock_days is None
    assert result.unmet_amount_at_horizon > Decimal("0")


def test_cash_only_coverage_is_immediate_on_day_zero() -> None:
    curve = calculate_cumulative_liquidation_curve(
        (_cash("200"), _listed_etf("800", capacity_rate="0.10", settlement_days=2)),
        nav=Decimal("1000"),
        participation_rate=Decimal("0.10"),
        liquidity_haircut_rate=Decimal("0.40"),
        horizon_days=5,
    )

    assert calculate_ttl_to_redemption_shock(curve, Decimal("150")) == 0


def test_higher_participation_produces_equal_or_shorter_ttl() -> None:
    results = build_ttl_sensitivity_results(
        (_cash("50"), _listed_etf("950", capacity_rate="0.50", settlement_days=0)),
        nav=Decimal("1000"),
        redemption_shock_rate=Decimal("0.30"),
        horizon_days=20,
        base_participation_rate=Decimal("0.20"),
        base_liquidity_haircut_rate=Decimal("0.40"),
    )[:3]

    ttls = [result.ttl_to_redemption_shock_days for result in results]
    assert all(ttl is not None for ttl in ttls)
    assert ttls == sorted(ttls, reverse=True)


def test_higher_haircut_produces_equal_or_longer_ttl() -> None:
    results = build_ttl_sensitivity_results(
        (_cash("50"), _listed_etf("950", capacity_rate="0.50", settlement_days=0)),
        nav=Decimal("1000"),
        redemption_shock_rate=Decimal("0.30"),
        horizon_days=20,
        base_participation_rate=Decimal("0.20"),
        base_liquidity_haircut_rate=Decimal("0.40"),
    )[3:]

    ttls = [result.ttl_to_redemption_shock_days for result in results]
    assert all(ttl is not None for ttl in ttls)
    assert ttls == sorted(ttls)


def test_repo_financing_with_no_market_value_is_excluded() -> None:
    repo_financing = _repo_financing("5000")
    curve = calculate_cumulative_liquidation_curve(
        (_cash("100"), repo_financing),
        nav=Decimal("1000"),
        participation_rate=Decimal("0.20"),
        liquidity_haircut_rate=Decimal("0.40"),
        horizon_days=5,
    )

    assert all(point.cumulative_cash_raised == Decimal("100") for point in curve)


def test_reverse_repo_and_maturity_do_not_contribute_to_ttl() -> None:
    reverse_repo = _reverse_repo("500", maturity_days=1)
    curve = calculate_cumulative_liquidation_curve(
        (_cash("100"), reverse_repo),
        nav=Decimal("1000"),
        participation_rate=Decimal("0.20"),
        liquidity_haircut_rate=Decimal("0.40"),
        horizon_days=5,
    )

    assert all(point.cumulative_cash_raised == Decimal("100") for point in curve)


def test_clean_sample_has_no_repo_rows_and_reconciles_to_eur_100m() -> None:
    positions = load_positions_csv(Path("data/sample/positions.csv"))
    fund = load_funds_csv(Path("data/sample/funds.csv"))[0]

    assert not {position.asset_group for position in positions} & {
        AssetGroup.REVERSE_REPO,
        AssetGroup.REPO_FINANCING,
    }
    assert sum((position.market_value or Decimal("0") for position in positions)) == Decimal(
        "100000000"
    )
    assert fund.nav == Decimal("100000000")


def _cash(market_value: str) -> AssetPosition:
    return AssetPosition(
        position_id="cash",
        fund_id="test_fund",
        as_of_date=date(2026, 6, 30),
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


def _listed_etf(
    market_value: str,
    *,
    capacity_rate: str,
    settlement_days: int,
) -> AssetPosition:
    return AssetPosition(
        position_id="listed_etf",
        fund_id="test_fund",
        as_of_date=date(2026, 6, 30),
        asset_group=AssetGroup.LISTED_ETF,
        instrument_type="listed_etf",
        instrument_subtype=InstrumentSubtype.LISTED_ETF,
        instrument_name="iShares Core MSCI World UCITS ETF",
        currency="EUR",
        market_value=Decimal(market_value),
        risk_factor_id="msci_world_equity",
        base_haircut_rate=Decimal("0.04"),
        base_liquidity_capacity_rate=Decimal(capacity_rate),
        settlement_days=settlement_days,
    )


def _repo_financing(notional_amount: str) -> AssetPosition:
    return AssetPosition(
        position_id="repo_financing",
        fund_id="test_fund",
        as_of_date=date(2026, 6, 30),
        asset_group=AssetGroup.REPO_FINANCING,
        instrument_type="repo_financing",
        instrument_subtype=InstrumentSubtype.REPO_FINANCING,
        instrument_name="Legacy Repo Financing Obligation",
        currency="EUR",
        notional_amount=Decimal(notional_amount),
        base_haircut_rate=Decimal("0"),
        base_liquidity_capacity_rate=Decimal("0"),
        settlement_days=1,
    )


def _reverse_repo(market_value: str, *, maturity_days: int) -> AssetPosition:
    return AssetPosition(
        position_id="reverse_repo",
        fund_id="test_fund",
        as_of_date=date(2026, 6, 30),
        asset_group=AssetGroup.REVERSE_REPO,
        instrument_type="reverse_repo",
        instrument_subtype=InstrumentSubtype.REVERSE_REPO,
        instrument_name="Legacy Reverse Repo",
        currency="EUR",
        market_value=Decimal(market_value),
        base_haircut_rate=Decimal("0.01"),
        base_liquidity_capacity_rate=Decimal("1"),
        settlement_days=1,
        maturity_days=maturity_days,
    )
