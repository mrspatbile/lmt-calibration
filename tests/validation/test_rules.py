import pytest

from lmt_calibration.validation import (
    DataValidationError,
    validate_liquidation_strategy_config,
    validate_market_stress_records,
    validate_position_records,
    validate_redemption_scenario_records,
    validate_scenario_definition_records,
)


def test_valid_liquidation_strategy_config_accepts_custom_weights() -> None:
    config = {
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
    }

    validated_config = validate_liquidation_strategy_config(config)

    assert validated_config == config


def test_liquidation_strategy_config_rejects_unknown_fields_and_bad_rates() -> None:
    config = {
        "schema_version": "1.0",
        "config_type": "liquidation_strategies",
        "name": "sample_liquidation_strategies",
        "description": "Synthetic liquidation strategy configuration.",
        "unexpected": "not_allowed",
        "strategies": [
            {
                "liquidation_strategy_id": "balanced_custom_weights",
                "version": "1.0",
                "name": "balanced_custom_weights",
                "description": "Invalid strategy field and rate format.",
                "strategy_type": "custom_weights",
                "cash_buffer_use_rate": "50%",
                "preserve_minimum_buffer": True,
                "unexpected_strategy_field": "not_allowed",
                "weights": {
                    "listed_etf": "0.60",
                    "listed_equity": "0.40",
                },
            }
        ],
    }

    with pytest.raises(DataValidationError) as error:
        validate_liquidation_strategy_config(config)

    message = str(error.value)
    assert "unexpected: unknown top-level JSON field" in message
    assert "unexpected_strategy_field: unknown strategy field" in message
    assert "cash_buffer_use_rate: must be a decimal string" in message


def test_liquidation_strategy_config_rejects_duplicate_strategy_ids_and_bad_weights() -> None:
    config = {
        "schema_version": "1.0",
        "config_type": "liquidation_strategies",
        "name": "sample_liquidation_strategies",
        "description": "Synthetic liquidation strategy configuration.",
        "strategies": [
            {
                "liquidation_strategy_id": "balanced_custom_weights",
                "version": "1.0",
                "name": "balanced_custom_weights",
                "description": "Weights do not sum to one.",
                "strategy_type": "custom_weights",
                "preserve_minimum_buffer": True,
                "weights": {
                    "listed_etf": "0.60",
                    "listed_equity": "0.30",
                },
            },
            {
                "liquidation_strategy_id": "balanced_custom_weights",
                "version": "1.0",
                "name": "balanced_custom_weights_duplicate",
                "description": "Duplicate strategy identifier.",
                "strategy_type": "pro_rata",
                "preserve_minimum_buffer": True,
            },
        ],
    }

    with pytest.raises(DataValidationError) as error:
        validate_liquidation_strategy_config(config)

    message = str(error.value)
    assert "liquidation_strategy_id: must be unique" in message
    assert "weights: must sum to 1" in message


def test_liquidation_strategy_config_rejects_disabled_minimum_buffer_preservation() -> None:
    config = {
        "schema_version": "1.0",
        "config_type": "liquidation_strategies",
        "name": "sample_liquidation_strategies",
        "description": "Synthetic liquidation strategy configuration.",
        "strategies": [
            {
                "liquidation_strategy_id": "buffer_override_not_supported",
                "version": "1.0",
                "name": "buffer_override_not_supported",
                "description": "Invalid because V1 does not support cash-buffer override.",
                "strategy_type": "most_liquid_first",
                "preserve_minimum_buffer": False,
            }
        ],
    }

    with pytest.raises(DataValidationError) as error:
        validate_liquidation_strategy_config(config)

    assert "preserve_minimum_buffer: must be true for V1 liquidation strategies" in str(error.value)


def test_scenario_definition_rejects_custom_strategy_fields_and_multiple_references() -> None:
    records = [
        {
            "scenario_id": "severe_redemption_liquidity_shock",
            "fund_id": "lux_dynamic_allocation",
            "as_of_date": "2026-06-30",
            "redemption_scenario_id": ["severe_platform_outflow", "second_redemption"],
            "market_stress_id": "europe_equity_downturn",
            "liquidity_stress_id": "reduced_equity_capacity",
            "liquidation_strategy_id": "balanced_custom_weights",
            "lmt_parameter_set_id": "board_approved_base",
            "weights": {"listed_etf": "0.60", "listed_equity": "0.40"},
        }
    ]

    with pytest.raises(DataValidationError) as error:
        validate_scenario_definition_records(records)

    message = str(error.value)
    assert "redemption_scenario_id: must reference exactly one ID" in message
    assert "weights: is not allowed here" in message


def test_scenario_definition_rejects_missing_assumption_reference() -> None:
    records = [
        {
            "scenario_id": "severe_redemption_liquidity_shock",
            "fund_id": "lux_dynamic_allocation",
            "as_of_date": "2026-06-30",
            "redemption_scenario_id": "severe_platform_outflow",
            "liquidity_stress_id": "reduced_equity_capacity",
            "liquidation_strategy_id": "balanced_custom_weights",
            "lmt_parameter_set_id": "board_approved_base",
        }
    ]

    with pytest.raises(DataValidationError) as error:
        validate_scenario_definition_records(records)

    assert "market_stress_id: is required" in str(error.value)


def test_redemption_scenario_rejects_fund_date_and_strategy_fields() -> None:
    records = [
        {
            "redemption_scenario_id": "severe_platform_outflow",
            "version": "1.0",
            "name": "severe_platform_outflow",
            "description": "Reusable liability-side assumption.",
            "redemption_multiplier": "1.50",
            "fund_id": "lux_dynamic_allocation",
            "as_of_date": "2026-06-30",
            "liquidation_strategy_id": "balanced_custom_weights",
        }
    ]

    with pytest.raises(DataValidationError) as error:
        validate_redemption_scenario_records(records)

    message = str(error.value)
    assert "fund_id: is not allowed here" in message
    assert "as_of_date: is not allowed here" in message
    assert "liquidation_strategy_id: is not allowed here" in message


def test_reusable_assumption_rejects_missing_version_name_or_description() -> None:
    records = [
        {
            "market_stress_id": "europe_equity_downturn",
            "market_shock_rate": "-0.12",
        }
    ]

    with pytest.raises(DataValidationError) as error:
        validate_market_stress_records(records)

    message = str(error.value)
    assert "version: is required" in message
    assert "name: is required" in message
    assert "description: is required" in message


def test_position_validation_accepts_direct_asset_and_derivative_records() -> None:
    records = [
        {
            "position_id": "sap_equity_position",
            "fund_id": "lux_dynamic_allocation",
            "as_of_date": "2026-06-30",
            "asset_group": "listed_equity",
            "instrument_type": "listed_equity",
            "instrument_subtype": "listed_equity",
            "instrument_name": "SAP SE Ordinary Shares",
            "currency": "EUR",
            "market_value": "15000000",
            "risk_factor_id": "sap_equity",
            "beta": "1.05",
            "base_haircut_rate": "0.05",
            "base_liquidity_capacity_rate": "0.20",
            "settlement_days": 2,
        },
        {
            "position_id": "sx5e_put_option",
            "fund_id": "lux_dynamic_allocation",
            "as_of_date": "2026-06-30",
            "asset_group": "equity_option",
            "instrument_type": "equity_option",
            "instrument_subtype": "equity_option",
            "instrument_name": "EURO STOXX 50 Put Option",
            "currency": "EUR",
            "notional_amount": "5000000",
            "strike_price": "3600",
            "option_type": "put",
            "expiry_date": "2026-09-18",
            "delta": "-0.35",
            "underlying_risk_factor_id": "euro_stoxx_50",
            "base_haircut_rate": "0.15",
            "base_liquidity_capacity_rate": "0.10",
            "settlement_days": 1,
        },
    ]

    assert validate_position_records(records) == records


def test_position_validation_rejects_missing_conditional_fields() -> None:
    records = [
        {
            "position_id": "option_without_underlying",
            "fund_id": "lux_dynamic_allocation",
            "as_of_date": "2026-06-30",
            "asset_group": "equity_option",
            "instrument_type": "equity_option",
            "instrument_subtype": "equity_option",
            "instrument_name": "EURO STOXX 50 Call Option",
            "currency": "EUR",
            "notional_amount": "5000000",
            "strike_price": "4600",
            "option_type": "call",
            "expiry_date": "2026-09-18",
            "delta": "0.25",
            "base_haircut_rate": "0.15",
            "base_liquidity_capacity_rate": "0.10",
            "settlement_days": 1,
        }
    ]

    with pytest.raises(DataValidationError) as error:
        validate_position_records(records)

    assert "underlying_position_id: or underlying_risk_factor_id is required" in str(error.value)
