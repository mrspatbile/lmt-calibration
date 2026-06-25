from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from lmt_calibration.domain import (
    HistoricalFxShock,
    HistoricalMarketStressScenarioLibrary,
    HistoricalStressShock,
)


def test_historical_market_stress_library_accepts_supported_shape() -> None:
    library = HistoricalMarketStressScenarioLibrary.model_validate(_valid_library())

    scenario = library.scenarios["historical_2020_covid"]

    assert scenario.holding_period_days == 20
    assert isinstance(scenario.shocks["equity"], HistoricalStressShock)
    assert isinstance(scenario.shocks["fx"], HistoricalFxShock)
    assert scenario.shocks["equity"].shock == Decimal("-0.3")
    assert scenario.shocks["fx"].shock_by_currency["USD"] == Decimal("0.05")


def test_historical_market_stress_library_rejects_bad_currency_code() -> None:
    config = _valid_library()
    fx_shock = config["scenarios"]["historical_2020_covid"]["shocks"]["fx"]
    fx_shock["shock_by_currency"] = {"usd": 0.05}

    with pytest.raises(ValidationError):
        HistoricalMarketStressScenarioLibrary.model_validate(config)


def test_historical_market_stress_library_rejects_missing_shock_group() -> None:
    config = _valid_library()
    del config["scenarios"]["historical_2020_covid"]["shocks"]["credit_spreads"]

    with pytest.raises(ValidationError):
        HistoricalMarketStressScenarioLibrary.model_validate(config)


def test_historical_market_stress_library_rejects_non_positive_holding_period() -> None:
    config = _valid_library()
    config["scenarios"]["historical_2020_covid"]["holding_period_days"] = 0

    with pytest.raises(ValidationError):
        HistoricalMarketStressScenarioLibrary.model_validate(config)


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
