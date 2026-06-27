import csv
from pathlib import Path

import pytest

from lmt_calibration.domain import (
    AssetPosition,
    FundSnapshot,
    InvestorClassProfile,
    LiquidityStress,
    LmtParameters,
    MarketStress,
    RedemptionScenario,
    ScenarioDefinition,
)
from lmt_calibration.loaders import (
    load_funds_csv,
    load_investor_classes_csv,
    load_liquidity_stresses_csv,
    load_liquidity_stresses_json,
    load_lmt_parameters_csv,
    load_market_stresses_csv,
    load_positions_csv,
    load_redemption_scenarios_csv,
    load_scenario_definitions_csv,
)
from lmt_calibration.validation import DataValidationError


def test_csv_loaders_return_typed_domain_objects(tmp_path: Path) -> None:
    funds_path = _write_csv(
        tmp_path / "funds.csv",
        [
            {
                "fund_id": "lux_dynamic_allocation",
                "as_of_date": "2026-06-30",
                "fund_name": "Lux Dynamic Allocation Fund",
                "base_currency": "EUR",
                "nav": "100000000",
                "dealing_frequency": "daily",
                "redemption_notice_days": "1",
                "redemption_settlement_days": "3",
            }
        ],
    )
    positions_path = _write_csv(
        tmp_path / "positions.csv",
        [
            {
                "position_id": "eur_operating_cash",
                "fund_id": "lux_dynamic_allocation",
                "as_of_date": "2026-06-30",
                "asset_group": "cash",
                "instrument_type": "cash",
                "instrument_subtype": "cash",
                "instrument_name": "EUR Operating Cash",
                "currency": "EUR",
                "market_value": "10000000",
                "base_haircut_rate": "0",
                "base_liquidity_capacity_rate": "1",
                "settlement_days": "0",
            }
        ],
    )
    investor_classes_path = _write_csv(
        tmp_path / "investor_classes.csv",
        [
            {
                "fund_id": "lux_dynamic_allocation",
                "as_of_date": "2026-06-30",
                "client_class": "retail",
                "nav_share_rate": "1",
                "base_redemption_rate": "0.02",
                "stress_redemption_rate": "0.10",
                "concentration_factor": "0.20",
                "notice_days": "1",
                "settlement_days": "3",
            }
        ],
    )
    redemption_scenarios_path = _write_csv(
        tmp_path / "redemption_scenarios.csv",
        [
            {
                "redemption_scenario_id": "severe_platform_outflow",
                "version": "1.0",
                "name": "severe_platform_outflow",
                "description": "Reusable liability-side assumption.",
                "redemption_multiplier": "1.50",
            }
        ],
    )
    market_stresses_path = _write_csv(
        tmp_path / "market_stresses.csv",
        [
            {
                "market_stress_id": "europe_equity_downturn",
                "version": "1.0",
                "name": "europe_equity_downturn",
                "description": "Reusable market shock.",
                "market_shock_rate": "-0.12",
            }
        ],
    )
    liquidity_stresses_path = tmp_path / "liquidity_stresses.json"
    liquidity_stresses_path.write_text(
        """{
  "liquidity_stresses": [
    {
      "liquidity_stress_id": "reduced_equity_capacity",
      "version": "1.0",
      "name": "reduced_equity_capacity",
      "description": "Reusable liquidity shock.",
      "stress_horizon_days": 5,
      "execution_assumptions_by_asset_group": {
        "cash": {"bid_ask_spread_rate": 0.0, "transaction_cost_rate": 0.0, "market_impact_rate": 0.0, "participation_rate": 1.0, "liquidity_haircut_rate": 0.0},
        "listed_etf": {"bid_ask_spread_rate": 0.0015, "transaction_cost_rate": 0.0005, "market_impact_rate": 0.001, "participation_rate": 0.2, "liquidity_haircut_rate": 0.1}
      }
    }
  ]
}"""
    )
    scenario_definitions_path = _write_csv(
        tmp_path / "scenario_definitions.csv",
        [
            {
                "scenario_id": "severe_redemption_liquidity_shock",
                "fund_id": "lux_dynamic_allocation",
                "as_of_date": "2026-06-30",
                "redemption_scenario_id": "severe_platform_outflow",
                "market_stress_id": "europe_equity_downturn",
                "liquidity_stress_id": "reduced_equity_capacity",
                "liquidation_strategy_id": "balanced_custom_weights",
                "lmt_parameter_set_id": "board_approved_base",
            }
        ],
    )
    lmt_parameters_path = _write_csv(
        tmp_path / "lmt_parameters.csv",
        [
            {
                "fund_id": "lux_dynamic_allocation",
                "as_of_date": "2026-06-30",
                "parameter_set_id": "board_approved_base",
                "swing_threshold_rate": "0.02",
                "max_swing_factor_rate": "0.03",
                "gate_threshold_rate": "0.10",
                "minimum_buffer_rate": "0.05",
            }
        ],
    )

    assert isinstance(load_funds_csv(funds_path)[0], FundSnapshot)
    assert isinstance(load_positions_csv(positions_path)[0], AssetPosition)
    assert isinstance(load_investor_classes_csv(investor_classes_path)[0], InvestorClassProfile)
    assert isinstance(
        load_redemption_scenarios_csv(redemption_scenarios_path)[0], RedemptionScenario
    )
    assert isinstance(load_market_stresses_csv(market_stresses_path)[0], MarketStress)
    assert isinstance(load_liquidity_stresses_json(liquidity_stresses_path)[0], LiquidityStress)
    assert isinstance(
        load_scenario_definitions_csv(scenario_definitions_path)[0], ScenarioDefinition
    )
    assert isinstance(load_lmt_parameters_csv(lmt_parameters_path)[0], LmtParameters)


def test_csv_loader_rejects_invalid_records_through_validation(tmp_path: Path) -> None:
    funds_path = _write_csv(
        tmp_path / "funds.csv",
        [
            {
                "fund_id": "lux_dynamic_allocation",
                "as_of_date": "2026-06-30",
                "fund_name": "Lux Dynamic Allocation Fund",
                "base_currency": "EUR",
                "dealing_frequency": "daily",
                "redemption_notice_days": "1",
                "redemption_settlement_days": "3",
            }
        ],
    )

    with pytest.raises(DataValidationError) as error:
        load_funds_csv(funds_path)

    assert "nav: is required" in str(error.value)


def test_csv_loader_rejects_invalid_integer_fields(tmp_path: Path) -> None:
    liquidity_stresses_path = _write_csv(
        tmp_path / "liquidity_stresses.csv",
        [
            {
                "liquidity_stress_id": "reduced_equity_capacity",
                "version": "1.0",
                "name": "reduced_equity_capacity",
                "description": "Reusable liquidity shock.",
                "liquidity_stress_multiplier": "2",
                "stress_horizon_days": "five",
            }
        ],
    )

    with pytest.raises(DataValidationError) as error:
        load_liquidity_stresses_csv(liquidity_stresses_path)

    assert "stress_horizon_days: must be integer" in str(error.value)


def test_csv_loader_rejects_missing_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing_funds.csv"

    with pytest.raises(DataValidationError) as error:
        load_funds_csv(missing_path)

    message = str(error.value)
    assert str(missing_path) in message
    assert "file: file not found" in message


def test_csv_loader_rejects_malformed_csv(tmp_path: Path) -> None:
    malformed_path = tmp_path / "funds.csv"
    malformed_path.write_text('fund_id,as_of_date\n"broken\n', encoding="utf-8")

    with pytest.raises(DataValidationError) as error:
        load_funds_csv(malformed_path)

    assert "file: malformed CSV" in str(error.value)


def _write_csv(path: Path, records: list[dict[str, object]]) -> Path:
    fieldnames = list(records[0])
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    return path
