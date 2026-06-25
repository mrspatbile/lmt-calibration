from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from lmt_calibration.audit import (
    AuditInputSummary,
    AuditLiquidationSummary,
    AuditMetadata,
    AuditParameterSummary,
    ScenarioAuditRecord,
)
from lmt_calibration.domain import (
    AssetGroup,
    LmtThresholdAssessmentResult,
    LmtThresholdDiagnosticResult,
    ThresholdAssessmentType,
)


def test_scenario_audit_record_accepts_liquidation_outputs_and_diagnostics() -> None:
    threshold_assessment = LmtThresholdAssessmentResult(
        scenario_id="platform_outflow_hybrid",
        parameter_set_id="board_approved_base",
        diagnostics=[
            LmtThresholdDiagnosticResult(
                assessment_type=ThresholdAssessmentType.SWING_PRICING,
                breached=False,
                observed_value="0.006",
                reference_threshold_value="0.015",
                quantitative_reason="Dilution rate is below the reference threshold.",
                message="Reference swing-pricing threshold diagnostic is not breached.",
            )
        ],
    )

    record = ScenarioAuditRecord(
        metadata=_metadata(),
        input_summary=_input_summary(),
        parameter_summary=_parameter_summary(),
        liquidation_summary=_liquidation_summary(),
        threshold_assessment=threshold_assessment,
    )

    assert record.metadata.run_id == "20260630_143000_platform_outflow_hybrid"
    assert record.input_summary.as_of_date == date(2026, 6, 30)
    assert record.liquidation_summary.total_redemption_amount == Decimal("10500000")
    assert record.threshold_assessment == threshold_assessment


def test_scenario_audit_record_allows_missing_threshold_assessment() -> None:
    record = ScenarioAuditRecord(
        metadata=_metadata(),
        input_summary=_input_summary(),
        parameter_summary=_parameter_summary(),
        liquidation_summary=_liquidation_summary(),
    )

    assert record.threshold_assessment is None


def test_audit_models_reject_extra_fields() -> None:
    with pytest.raises(ValidationError):
        AuditMetadata(
            run_id="20260630_143000_platform_outflow_hybrid",
            timestamp=datetime(2026, 6, 30, 14, 30, tzinfo=UTC),
            manager_activation_decision="activate_gate",
        )


def test_audit_liquidation_summary_rejects_negative_money_values() -> None:
    with pytest.raises(ValidationError):
        AuditLiquidationSummary(
            total_redemption_amount="-1",
            total_redemption_rate="0.105",
            cash_used="3500000",
            gross_sales="7600000",
            post_haircut_cash_raised="7000000",
            haircut_cost="600000",
            shortfall="0",
            dilution_amount="600000",
            dilution_rate="0.006",
            remaining_liquid_buffer_rate="0.18",
            minimum_cash_buffer_preserved=True,
        )


def _metadata() -> AuditMetadata:
    return AuditMetadata(
        run_id="20260630_143000_platform_outflow_hybrid",
        timestamp=datetime(2026, 6, 30, 14, 30, tzinfo=UTC),
        package_version="0.1.0",
        output_paths=(Path("outputs/audit/20260630_143000_platform_outflow_hybrid_audit.json"),),
    )


def _input_summary() -> AuditInputSummary:
    return AuditInputSummary(
        fund_id="lux_dynamic_allocation",
        fund_name="Lux Dynamic Allocation Fund",
        as_of_date="2026-06-30",
        source_files=(Path("data/sample/funds.csv"), Path("data/sample/positions.csv")),
        position_count=9,
        investor_class_count=5,
        total_nav="100000000",
        total_position_market_value="100000000",
        reconciliation_status="reconciled",
        validation_status="validated",
    )


def _parameter_summary() -> AuditParameterSummary:
    return AuditParameterSummary(
        scenario_id="platform_outflow_hybrid",
        redemption_scenario_id="severe_platform_outflow",
        market_stress_id="europe_equity_downturn",
        liquidity_stress_id="reduced_equity_capacity",
        liquidation_strategy_id="partial_cash_then_pro_rata",
        lmt_parameter_set_id="board_approved_base",
        swing_threshold_rate="0.015",
        max_swing_factor_rate="0.03",
        gate_threshold_rate="0.10",
        minimum_buffer_rate="0.05",
        preserve_minimum_buffer=True,
        cash_buffer_use_rate="0.50",
        strategy_weights={AssetGroup.LISTED_ETF: Decimal("0.60")},
    )


def _liquidation_summary() -> AuditLiquidationSummary:
    return AuditLiquidationSummary(
        total_redemption_amount="10500000",
        total_redemption_rate="0.105",
        cash_used="3500000",
        gross_sales="7600000",
        post_haircut_cash_raised="7000000",
        haircut_cost="600000",
        shortfall="0",
        dilution_amount="600000",
        dilution_rate="0.006",
        remaining_liquid_buffer_rate="0.18",
        minimum_cash_buffer_preserved=True,
        asset_group_allocations={AssetGroup.CASH: Decimal("3500000")},
    )
