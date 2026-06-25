import json
from datetime import UTC, datetime

from lmt_calibration.audit import (
    AuditInputSummary,
    AuditLiquidationSummary,
    AuditMetadata,
    AuditParameterSummary,
    JsonAuditWriter,
    ScenarioAuditRecord,
)
from lmt_calibration.domain import LmtThresholdAssessmentResult, LmtThresholdDiagnosticResult


def test_json_audit_writer_writes_record_to_generated_path(tmp_path) -> None:
    record = _audit_record()
    writer = JsonAuditWriter(tmp_path / "audit")

    output_path = writer.write(record)

    assert output_path == tmp_path / "audit" / f"{record.metadata.run_id}_audit.json"
    assert output_path.is_file()

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["run_id"] == "20260630_143000_platform_outflow_hybrid"
    assert payload["metadata"]["timestamp"] == "2026-06-30T14:30:00Z"
    assert payload["input_summary"]["as_of_date"] == "2026-06-30"
    assert payload["liquidation_summary"]["total_redemption_amount"] == "10500000"
    assert payload["threshold_assessment"]["diagnostics"][0]["assessment_type"] == "swing_pricing"
    assert payload["threshold_assessment"]["diagnostics"][0]["reference_threshold_value"] == "0.015"


def test_json_audit_writer_creates_nested_output_directory(tmp_path) -> None:
    output_dir = tmp_path / "nested" / "audit"
    writer = JsonAuditWriter(output_dir)

    output_path = writer.write(_audit_record())

    assert output_dir.is_dir()
    assert output_path.parent == output_dir


def _audit_record() -> ScenarioAuditRecord:
    return ScenarioAuditRecord(
        metadata=AuditMetadata(
            run_id="20260630_143000_platform_outflow_hybrid",
            timestamp=datetime(2026, 6, 30, 14, 30, tzinfo=UTC),
        ),
        input_summary=AuditInputSummary(
            fund_id="lux_dynamic_allocation",
            fund_name="Lux Dynamic Allocation Fund",
            as_of_date="2026-06-30",
            position_count=9,
            investor_class_count=5,
            total_nav="100000000",
            total_position_market_value="100000000",
            reconciliation_status="reconciled",
            validation_status="validated",
        ),
        parameter_summary=AuditParameterSummary(
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
        ),
        liquidation_summary=AuditLiquidationSummary(
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
        ),
        threshold_assessment=LmtThresholdAssessmentResult(
            scenario_id="platform_outflow_hybrid",
            parameter_set_id="board_approved_base",
            diagnostics=[
                LmtThresholdDiagnosticResult(
                    assessment_type="swing_pricing",
                    breached=False,
                    observed_value="0.006",
                    reference_threshold_value="0.015",
                    quantitative_reason="Dilution rate is below the reference threshold.",
                    message="Reference swing-pricing threshold diagnostic is not breached.",
                )
            ],
        ),
    )
