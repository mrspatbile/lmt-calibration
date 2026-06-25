import json
from pathlib import Path
from typing import Any

import pytest

from lmt_calibration.domain import HistoricalMarketStressScenarioLibrary
from lmt_calibration.loaders import load_historical_market_stress_scenarios_json
from lmt_calibration.validation import DataValidationError


def test_historical_market_stress_loader_returns_typed_library(tmp_path: Path) -> None:
    path = _write_json(tmp_path / "historical_market_stress_scenarios.json", _valid_library())

    library = load_historical_market_stress_scenarios_json(path)

    assert isinstance(library, HistoricalMarketStressScenarioLibrary)
    assert set(library.scenarios) == {"historical_2020_covid"}


def test_historical_market_stress_loader_rejects_invalid_unit(tmp_path: Path) -> None:
    config = _valid_library()
    config["scenarios"]["historical_2020_covid"]["shocks"]["equity"]["unit"] = "percent"
    path = _write_json(tmp_path / "historical_market_stress_scenarios.json", config)

    with pytest.raises(DataValidationError) as error:
        load_historical_market_stress_scenarios_json(path)

    assert "unit: must be pct" in str(error.value)


def test_historical_market_stress_loader_rejects_invalid_fx_currency(tmp_path: Path) -> None:
    config = _valid_library()
    config["scenarios"]["historical_2020_covid"]["shocks"]["fx"]["shock_by_currency"] = {
        "usd": 0.05
    }
    path = _write_json(tmp_path / "historical_market_stress_scenarios.json", config)

    with pytest.raises(DataValidationError) as error:
        load_historical_market_stress_scenarios_json(path)

    assert "currency must be a 3-letter uppercase code" in str(error.value)


def test_historical_market_stress_loader_rejects_missing_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing_historical_market_stress_scenarios.json"

    with pytest.raises(DataValidationError) as error:
        load_historical_market_stress_scenarios_json(missing_path)

    message = str(error.value)
    assert str(missing_path) in message
    assert "file: file not found" in message


def test_historical_market_stress_loader_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "historical_market_stress_scenarios.json"
    path.write_text('{"schema_version": "1.0"', encoding="utf-8")

    with pytest.raises(DataValidationError) as error:
        load_historical_market_stress_scenarios_json(path)

    assert "file: malformed JSON" in str(error.value)


def _write_json(path: Path, config: dict[str, Any]) -> Path:
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def _valid_library() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "source": "Historical market stress scenario library",
        "scenario_type": "historical",
        "notes": "Synthetic examples for market stress comparison.",
        "scenarios": {
            "historical_2020_covid": {
                "test_category": "Historical",
                "scenario_name": "2020 COVID-19 Crash",
                "description": "Initial pandemic stress period.",
                "period": "February - March 2020",
                "holding_period_days": 20,
                "shocks": {
                    "equity": {
                        "shock": -0.3,
                        "unit": "pct",
                        "description": "Equity market decline.",
                    },
                    "interest_rates": {
                        "shock": -0.005,
                        "unit": "pct",
                        "description": "Parallel rate shift.",
                    },
                    "credit_spreads": {
                        "shock": 0.02,
                        "unit": "pct",
                        "description": "Credit spread widening.",
                    },
                    "fx": {
                        "shock_by_currency": {"USD": 0.05, "GBP": -0.05},
                        "unit": "pct",
                        "description": "FX movements against EUR.",
                    },
                },
            }
        },
    }
