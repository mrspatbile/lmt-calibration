from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from lmt_calibration.domain import (
    AssetGroup,
    AssetPosition,
    FundSnapshot,
    InstrumentSubtype,
    LiquidationStrategyConfig,
    LiquidationStrategyType,
    LmtParameters,
    LmtThresholdAssessmentResult,
    LmtThresholdDiagnosticResult,
    MarketStress,
    RedemptionScenario,
    ScenarioDefinition,
    ThresholdAssessmentType,
)


def test_fund_snapshot_accepts_decimal_strings() -> None:
    fund = FundSnapshot(
        fund_id="lux_dynamic_allocation",
        as_of_date="2026-06-30",
        fund_name="Lux Dynamic Allocation Fund",
        base_currency="EUR",
        nav="125000000.50",
        dealing_frequency="daily",
        redemption_notice_days=1,
        redemption_settlement_days=3,
    )

    assert fund.as_of_date == date(2026, 6, 30)
    assert fund.nav == Decimal("125000000.50")


def test_missing_required_lmt_parameter_field_fails() -> None:
    with pytest.raises(ValidationError):
        LmtParameters(
            fund_id="lux_dynamic_allocation",
            as_of_date="2026-06-30",
            parameter_set_id="board_approved_base",
            swing_threshold_rate="0.02",
            max_swing_factor_rate="0.03",
            gate_threshold_rate="0.10",
        )


def test_redemption_scenario_is_reusable_and_rejects_fund_date_fields() -> None:
    redemption_scenario = RedemptionScenario(
        redemption_scenario_id="severe_platform_outflow",
        version="1.0",
        name="severe_platform_outflow",
        description="Severe synthetic redemption pressure across platform investors.",
        redemption_multiplier="1.50",
    )

    assert redemption_scenario.redemption_multiplier == Decimal("1.50")
    assert not hasattr(redemption_scenario, "fund_id")
    assert not hasattr(redemption_scenario, "as_of_date")

    with pytest.raises(ValidationError):
        RedemptionScenario(
            redemption_scenario_id="invalid_fund_bound_redemption",
            version="1.0",
            name="invalid_fund_bound_redemption",
            description="Invalid because reusable assumptions cannot be fund-bound.",
            redemption_multiplier="1.00",
            fund_id="lux_dynamic_allocation",
        )


def test_scenario_definition_requires_all_assumption_ids() -> None:
    scenario_definition = ScenarioDefinition(
        scenario_id="severe_redemption_liquidity_shock",
        fund_id="lux_dynamic_allocation",
        as_of_date="2026-06-30",
        redemption_scenario_id="severe_platform_outflow",
        market_stress_id="europe_equity_downturn",
        liquidity_stress_id="reduced_equity_capacity",
        liquidation_strategy_id="balanced_custom_weights",
        lmt_parameter_set_id="board_approved_base",
    )

    assert scenario_definition.redemption_scenario_id == "severe_platform_outflow"
    assert scenario_definition.market_stress_id == "europe_equity_downturn"
    assert scenario_definition.liquidity_stress_id == "reduced_equity_capacity"
    assert scenario_definition.liquidation_strategy_id == "balanced_custom_weights"
    assert scenario_definition.lmt_parameter_set_id == "board_approved_base"

    with pytest.raises(ValidationError):
        ScenarioDefinition(
            scenario_id="missing_market_stress",
            fund_id="lux_dynamic_allocation",
            as_of_date="2026-06-30",
            redemption_scenario_id="severe_platform_outflow",
            liquidity_stress_id="reduced_equity_capacity",
            liquidation_strategy_id="balanced_custom_weights",
            lmt_parameter_set_id="board_approved_base",
        )


def test_market_stress_decimal_string_is_stored_as_decimal() -> None:
    market_stress = MarketStress(
        market_stress_id="europe_equity_downturn",
        version="1.0",
        name="europe_equity_downturn",
        description="Synthetic European equity benchmark decline.",
        market_shock_rate="-0.12",
    )

    assert market_stress.market_shock_rate == Decimal("-0.12")


def test_listed_equity_position_requires_direct_asset_fields() -> None:
    position = AssetPosition(
        position_id="sap_equity_position",
        fund_id="lux_dynamic_allocation",
        as_of_date="2026-06-30",
        asset_group=AssetGroup.LISTED_EQUITY,
        instrument_type="listed_equity",
        instrument_subtype=InstrumentSubtype.LISTED_EQUITY,
        instrument_name="SAP SE Ordinary Shares",
        ticker="SAP GY",
        currency="EUR",
        market_value="15000000",
        risk_factor_id="sap_equity",
        beta="1.05",
        benchmark_ticker="SX5E",
        base_haircut_rate="0.05",
        base_liquidity_capacity_rate="0.20",
        settlement_days=2,
    )

    assert position.market_value == Decimal("15000000")
    assert position.beta == Decimal("1.05")

    with pytest.raises(ValidationError):
        AssetPosition(
            position_id="missing_beta_equity",
            fund_id="lux_dynamic_allocation",
            as_of_date="2026-06-30",
            asset_group=AssetGroup.LISTED_EQUITY,
            instrument_type="listed_equity",
            instrument_subtype=InstrumentSubtype.LISTED_EQUITY,
            instrument_name="ASML Holding NV Ordinary Shares",
            ticker="ASML NA",
            currency="EUR",
            market_value="12000000",
            risk_factor_id="asml_equity",
            base_haircut_rate="0.05",
            base_liquidity_capacity_rate="0.20",
            settlement_days=2,
        )


def test_equity_option_position_requires_derivative_reference_fields() -> None:
    position = AssetPosition(
        position_id="sx5e_put_option",
        fund_id="lux_dynamic_allocation",
        as_of_date="2026-06-30",
        asset_group=AssetGroup.EQUITY_OPTION,
        instrument_type="equity_option",
        instrument_subtype=InstrumentSubtype.EQUITY_OPTION,
        instrument_name="EURO STOXX 50 Put Option",
        ticker="SX5E P 3600",
        currency="EUR",
        notional_amount="5000000",
        strike_price="3600",
        option_type="put",
        expiry_date="2026-09-18",
        delta="-0.35",
        underlying_risk_factor_id="euro_stoxx_50",
        base_haircut_rate="0.15",
        base_liquidity_capacity_rate="0.10",
        settlement_days=1,
    )

    assert position.notional_amount == Decimal("5000000")
    assert position.delta == Decimal("-0.35")

    with pytest.raises(ValidationError):
        AssetPosition(
            position_id="option_without_underlying",
            fund_id="lux_dynamic_allocation",
            as_of_date="2026-06-30",
            asset_group=AssetGroup.EQUITY_OPTION,
            instrument_type="equity_option",
            instrument_subtype=InstrumentSubtype.EQUITY_OPTION,
            instrument_name="EURO STOXX 50 Call Option",
            ticker="SX5E C 4600",
            currency="EUR",
            notional_amount="5000000",
            strike_price="4600",
            option_type="call",
            expiry_date="2026-09-18",
            delta="0.25",
            base_haircut_rate="0.15",
            base_liquidity_capacity_rate="0.10",
            settlement_days=1,
        )


def test_custom_weight_strategy_requires_weights_sum_to_one() -> None:
    strategy = LiquidationStrategyConfig(
        liquidation_strategy_id="balanced_custom_weights",
        version="1.0",
        name="balanced_custom_weights",
        description="Synthetic strategy allocating across eligible ETFs and equities.",
        strategy_type=LiquidationStrategyType.CUSTOM_WEIGHTS,
        cash_buffer_use_rate="0.50",
        preserve_minimum_buffer=True,
        weights={
            "listed_etf": "0.60",
            "listed_equity": "0.40",
        },
    )

    assert strategy.cash_buffer_use_rate == Decimal("0.50")
    assert strategy.weights == {
        AssetGroup.LISTED_ETF: Decimal("0.60"),
        AssetGroup.LISTED_EQUITY: Decimal("0.40"),
    }

    with pytest.raises(ValidationError):
        LiquidationStrategyConfig(
            liquidation_strategy_id="invalid_custom_weights",
            version="1.0",
            name="invalid_custom_weights",
            description="Invalid because weights do not sum to one.",
            strategy_type=LiquidationStrategyType.CUSTOM_WEIGHTS,
            preserve_minimum_buffer=True,
            weights={
                "listed_etf": "0.60",
                "listed_equity": "0.30",
            },
        )


def test_liquidation_strategy_requires_minimum_buffer_preservation_for_v1() -> None:
    with pytest.raises(ValidationError):
        LiquidationStrategyConfig(
            liquidation_strategy_id="buffer_override_not_supported",
            version="1.0",
            name="buffer_override_not_supported",
            description="Invalid because V1 does not support cash-buffer override.",
            strategy_type=LiquidationStrategyType.MOST_LIQUID_FIRST,
            preserve_minimum_buffer=False,
        )


def test_lmt_threshold_diagnostic_result_accepts_reference_threshold_values() -> None:
    diagnostic = LmtThresholdDiagnosticResult(
        assessment_type="swing_pricing",
        breached=True,
        observed_value="0.018",
        reference_threshold_value="0.015",
        quantitative_reason="Redemption rate exceeds the reference swing activation threshold.",
        message="Reference swing activation threshold diagnostic breach.",
    )

    assert diagnostic.assessment_type is ThresholdAssessmentType.SWING_PRICING
    assert diagnostic.observed_value == Decimal("0.018")
    assert diagnostic.reference_threshold_value == Decimal("0.015")


def test_lmt_threshold_diagnostic_result_rejects_negative_values() -> None:
    with pytest.raises(ValidationError):
        LmtThresholdDiagnosticResult(
            assessment_type="redemption_gate",
            breached=False,
            observed_value="-0.01",
            reference_threshold_value="0.10",
            quantitative_reason="Invalid negative observed value.",
            message="Invalid diagnostic.",
        )

    with pytest.raises(ValidationError):
        LmtThresholdDiagnosticResult(
            assessment_type="liquidity_buffer",
            breached=True,
            observed_value="0.04",
            reference_threshold_value="-0.05",
            quantitative_reason="Invalid negative reference threshold.",
            message="Invalid diagnostic.",
        )


def test_lmt_threshold_diagnostic_result_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        LmtThresholdDiagnosticResult(
            assessment_type="swing_pricing",
            breached=False,
            observed_value="0.010",
            reference_threshold_value="0.015",
            quantitative_reason="Redemption rate is below the reference threshold.",
            message="No diagnostic breach.",
            proposed_threshold_value="0.020",
        )


def test_lmt_threshold_assessment_result_contains_diagnostics_only() -> None:
    diagnostic = LmtThresholdDiagnosticResult(
        assessment_type=ThresholdAssessmentType.REDEMPTION_GATE,
        breached=False,
        observed_value="0.085",
        reference_threshold_value="0.10",
        quantitative_reason="Total redemption rate is below the reference gate threshold.",
        message="Reference gate threshold diagnostic is not breached.",
    )

    result = LmtThresholdAssessmentResult(
        scenario_id="platform_outflow_hybrid",
        parameter_set_id="board_approved_base",
        diagnostics=[diagnostic],
    )

    assert result.scenario_id == "platform_outflow_hybrid"
    assert result.parameter_set_id == "board_approved_base"
    assert result.diagnostics == (diagnostic,)
