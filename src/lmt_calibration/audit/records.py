"""Structured audit record models for scenario runs."""

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from lmt_calibration.domain import (
    AssetGroup,
    LmtThresholdAssessmentResult,
)


class AuditMetadata(BaseModel):
    """Run metadata and generated output references."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    run_id: str
    timestamp: datetime
    package_version: str | None = None
    output_paths: tuple[Path, ...] = ()


class AuditInputSummary(BaseModel):
    """Validated input snapshot summary for a scenario run."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    fund_id: str
    fund_name: str
    as_of_date: date
    source_files: tuple[Path, ...] = ()
    position_count: int = Field(ge=0)
    investor_class_count: int = Field(ge=0)
    total_nav: Decimal = Field(gt=Decimal("0"))
    total_position_market_value: Decimal = Field(ge=Decimal("0"))
    reconciliation_status: str
    validation_status: str


class AuditParameterSummary(BaseModel):
    """Scenario assumptions and reference threshold values used or assessed."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    scenario_id: str
    redemption_scenario_id: str
    market_stress_id: str
    liquidity_stress_id: str
    liquidation_strategy_id: str
    lmt_parameter_set_id: str
    swing_threshold_rate: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    max_swing_factor_rate: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    gate_threshold_rate: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    minimum_buffer_rate: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    preserve_minimum_buffer: bool
    cash_buffer_use_rate: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    strategy_weights: dict[AssetGroup, Decimal] | None = None


class AuditLiquidationSummary(BaseModel):
    """Already-calculated liquidation outputs used for threshold assessment."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    total_redemption_amount: Decimal = Field(ge=Decimal("0"))
    total_redemption_rate: Decimal = Field(ge=Decimal("0"))
    cash_used: Decimal = Field(ge=Decimal("0"))
    gross_sales: Decimal = Field(ge=Decimal("0"))
    post_haircut_cash_raised: Decimal = Field(ge=Decimal("0"))
    haircut_cost: Decimal = Field(ge=Decimal("0"))
    strategy_deviation_amount: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    shortfall: Decimal = Field(ge=Decimal("0"))
    dilution_amount: Decimal = Field(ge=Decimal("0"))
    dilution_rate: Decimal = Field(ge=Decimal("0"))
    remaining_liquid_buffer_rate: Decimal = Field(ge=Decimal("0"))
    minimum_cash_buffer_preserved: bool
    asset_group_allocations: dict[AssetGroup, Decimal] = Field(default_factory=dict)


class ScenarioAuditRecord(BaseModel):
    """Complete structured audit record for one V1 scenario run."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    metadata: AuditMetadata
    input_summary: AuditInputSummary
    parameter_summary: AuditParameterSummary
    liquidation_summary: AuditLiquidationSummary
    threshold_assessment: LmtThresholdAssessmentResult | None = None
