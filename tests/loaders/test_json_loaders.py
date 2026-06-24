import json
from pathlib import Path

import pytest

from lmt_calibration.domain import LiquidationStrategyConfig
from lmt_calibration.loaders import load_liquidation_strategies_json
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


def _write_json(path: Path, config: dict[str, object]) -> Path:
    path.write_text(json.dumps(config), encoding="utf-8")
    return path
