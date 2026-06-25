"""Calculation result domain models.

These models are structured result containers only. They do not implement
liquidation, pricing, threshold calibration, or manager activation logic.
"""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from lmt_calibration.domain.positions import AssetGroup


class LiquidatedAssetResult(BaseModel):
    """Per-position liquidation allocation result."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    position_id: str
    asset_group: AssetGroup
    gross_sale_amount: Decimal = Field(ge=Decimal("0"))
    post_haircut_cash_raised: Decimal = Field(ge=Decimal("0"))
    haircut_cost: Decimal = Field(ge=Decimal("0"))


class LiquidationResult(BaseModel):
    """Structured output of a selected liquidation strategy."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    scenario_id: str
    liquidation_strategy_id: str
    total_redemption_amount: Decimal = Field(ge=Decimal("0"))
    cash_used: Decimal = Field(ge=Decimal("0"))
    assets_liquidated: tuple[LiquidatedAssetResult, ...]
    asset_group_allocations: dict[AssetGroup, Decimal] = Field(default_factory=dict)
    total_post_haircut_cash_raised: Decimal = Field(ge=Decimal("0"))
    total_haircut_cost: Decimal = Field(ge=Decimal("0"))
    shortfall: Decimal = Field(ge=Decimal("0"))
    dilution_amount: Decimal = Field(ge=Decimal("0"))
    dilution_rate: Decimal = Field(ge=Decimal("0"))
    remaining_liquid_buffer_rate: Decimal = Field(ge=Decimal("0"))
    minimum_cash_buffer_preserved: bool


class ThresholdAssessmentType(StrEnum):
    """Supported Version 1 reference-threshold assessment types."""

    SWING_PRICING = "swing_pricing"
    REDEMPTION_GATE = "redemption_gate"
    LIQUIDITY_BUFFER = "liquidity_buffer"


class LmtThresholdDiagnosticResult(BaseModel):
    """Diagnostic result for assessing a Version 1 reference threshold."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    assessment_type: ThresholdAssessmentType
    breached: bool
    observed_value: Decimal = Field(ge=Decimal("0"))
    reference_threshold_value: Decimal = Field(ge=Decimal("0"))
    quantitative_reason: str
    message: str


class LmtThresholdAssessmentResult(BaseModel):
    """Container for V1 LMT reference-threshold diagnostics."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    scenario_id: str
    parameter_set_id: str
    diagnostics: tuple[LmtThresholdDiagnosticResult, ...]


class WarningType(StrEnum):
    """Backward-compatible diagnostic warning type names.

    Prefer ``ThresholdAssessmentType`` for new V1 threshold assessment models.
    """

    SWING_PRICING = "swing_pricing"
    REDEMPTION_GATE = "redemption_gate"
    LIQUIDITY_BUFFER = "liquidity_buffer"


class LmtWarningResult(BaseModel):
    """Backward-compatible diagnostic threshold warning result.

    Prefer ``LmtThresholdDiagnosticResult`` for new V1 reference-threshold
    assessment outputs.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    warning_type: WarningType
    breached: bool
    observed_value: Decimal = Field(ge=Decimal("0"))
    threshold_value: Decimal = Field(ge=Decimal("0"))
    quantitative_reason: str
    message: str
