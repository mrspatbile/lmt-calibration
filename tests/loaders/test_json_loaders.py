import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from lmt_calibration.domain import LiquidationStrategyConfig, LiquidityStress
from lmt_calibration.loaders import load_liquidation_strategies_json, load_liquidity_stresses_json
from lmt_calibration.validation import DataValidationError


def test_liquidation_strategy_json_loader_returns_typed_objects(tmp_path: Path) -> None:
    path = _write_json(
        tmp_path / "liquidation_strategies.json",
        {
            "schema_version": "1.0",
            "config_type": "liquidation_strategies",
            "name": "sample_liquidation_strategies",
            "description": "Synthetic liquidation strategy configuration.",
            "strategies": [
                {
                    "liquidation_strategy_id": "balanced_custom_weights",
                    "version": "1.0",
                    "name": "balanced_custom_weights",
                    "description": "Allocates sales across eligible ETFs and equities.",
                    "strategy_type": "custom_weights",
                    "cash_buffer_use_rate": "0.50",
                    "preserve_minimum_buffer": True,
                    "weights": {
                        "listed_etf": "0.60",
                        "listed_equity": "0.40",
                    },
                }
            ],
        },
    )

    strategies = load_liquidation_strategies_json(path)

    assert isinstance(strategies[0], LiquidationStrategyConfig)
    assert strategies[0].liquidation_strategy_id == "balanced_custom_weights"


def test_liquidation_strategy_json_loader_rejects_invalid_config(tmp_path: Path) -> None:
    path = _write_json(
        tmp_path / "liquidation_strategies.json",
        {
            "schema_version": "1.0",
            "config_type": "liquidation_strategies",
            "name": "sample_liquidation_strategies",
            "description": "Synthetic liquidation strategy configuration.",
            "strategies": [
                {
                    "liquidation_strategy_id": "balanced_custom_weights",
                    "version": "1.0",
                    "name": "balanced_custom_weights",
                    "description": "Invalid decimal string.",
                    "strategy_type": "custom_weights",
                    "cash_buffer_use_rate": "50%",
                    "preserve_minimum_buffer": True,
                    "weights": {
                        "listed_etf": "0.60",
                        "listed_equity": "0.40",
                    },
                }
            ],
        },
    )

    with pytest.raises(DataValidationError) as error:
        load_liquidation_strategies_json(path)

    assert "cash_buffer_use_rate: must be a decimal string" in str(error.value)


def test_liquidation_strategy_json_loader_rejects_missing_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing_liquidation_strategies.json"

    with pytest.raises(DataValidationError) as error:
        load_liquidation_strategies_json(missing_path)

    message = str(error.value)
    assert str(missing_path) in message
    assert "file: file not found" in message


def test_liquidation_strategy_json_loader_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "liquidation_strategies.json"
    path.write_text('{"schema_version": "1.0"', encoding="utf-8")

    with pytest.raises(DataValidationError) as error:
        load_liquidation_strategies_json(path)

    assert "file: malformed JSON" in str(error.value)


def test_liquidity_stress_json_loader_accepts_execution_assumptions(tmp_path: Path) -> None:
    path = _write_json(
        tmp_path / "liquidity_stresses.json",
        {
            "liquidity_stresses": [
                {
                    "liquidity_stress_id": "reduced_equity_capacity",
                    "version": "1.0",
                    "name": "reduced_equity_capacity",
                    "description": "Reusable liquidity shock.",
                    "stress_horizon_days": 5,
                    "execution_assumptions_by_asset_group": {
                        "cash": {
                            "bid_ask_spread_rate": 0.0,
                            "transaction_cost_rate": 0.0,
                            "market_impact_rate": 0.0,
                            "participation_rate": 1.0,
                            "liquidity_haircut_rate": 0.0,
                        },
                        "listed_equity": {
                            "bid_ask_spread_rate": 0.001,
                            "transaction_cost_rate": 0.0005,
                            "market_impact_rate": 0.0005,
                            "participation_rate": 0.2,
                            "liquidity_haircut_rate": 0.1,
                        },
                    },
                }
            ]
        },
    )

    stresses = load_liquidity_stresses_json(path)

    assert isinstance(stresses[0], LiquidityStress)
    assert stresses[0].stress_horizon_days == 5


def test_liquidity_stress_json_loader_rejects_missing_execution_cost_field(
    tmp_path: Path,
) -> None:
    path = _write_json(
        tmp_path / "liquidity_stresses.json",
        {
            "liquidity_stresses": [
                {
                    "liquidity_stress_id": "reduced_equity_capacity",
                    "version": "1.0",
                    "name": "reduced_equity_capacity",
                    "description": "Missing execution-cost field.",
                    "stress_horizon_days": 5,
                    "execution_assumptions_by_asset_group": {
                        "listed_equity": {
                            "transaction_cost_rate": 0.0005,
                            "market_impact_rate": 0.0005,
                            "participation_rate": 0.2,
                            "liquidity_haircut_rate": 0.1,
                        }
                    },
                }
            ]
        },
    )

    with pytest.raises(ValidationError, match="bid_ask_spread_rate"):
        load_liquidity_stresses_json(path)


def _write_json(path: Path, config: dict[str, object]) -> Path:
    path.write_text(json.dumps(config), encoding="utf-8")
    return path
