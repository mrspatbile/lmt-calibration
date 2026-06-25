"""Reusable scenario assumption models and scenario definitions."""

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lmt_calibration.domain.positions import AssetGroup

SNAKE_CASE_PATTERN = r"^[a-z][a-z0-9_]*$"


class VersionedAssumption(BaseModel):
    """Base fields shared by reusable assumption objects."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    version: str
    name: str = Field(pattern=SNAKE_CASE_PATTERN)
    description: str


class RedemptionScenario(VersionedAssumption):
    """Reusable liability-side redemption assumptions only."""

    redemption_scenario_id: str = Field(pattern=SNAKE_CASE_PATTERN)
    redemption_multiplier: Decimal = Field(gt=Decimal("0"))


class MarketStress(VersionedAssumption):
    """Reusable asset-side market shock assumption."""

    market_stress_id: str = Field(pattern=SNAKE_CASE_PATTERN)
    market_shock_rate: Decimal


class LiquidityStress(VersionedAssumption):
    """Reusable asset-side liquidity shock assumption."""

    liquidity_stress_id: str = Field(pattern=SNAKE_CASE_PATTERN)
    liquidity_stress_multiplier: Decimal = Field(gt=Decimal("0"))
    stress_horizon_days: int = Field(gt=0)


class ScenarioDefinition(BaseModel):
    """Link one fund snapshot to one set of reusable assumptions."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    scenario_id: str = Field(pattern=SNAKE_CASE_PATTERN)
    fund_id: str
    as_of_date: date
    redemption_scenario_id: str = Field(pattern=SNAKE_CASE_PATTERN)
    market_stress_id: str = Field(pattern=SNAKE_CASE_PATTERN)
    liquidity_stress_id: str = Field(pattern=SNAKE_CASE_PATTERN)
    liquidation_strategy_id: str = Field(pattern=SNAKE_CASE_PATTERN)
    lmt_parameter_set_id: str


class LiquidationStrategyType(StrEnum):
    """Supported Version 1 liquidation strategy types."""

    MOST_LIQUID_FIRST = "most_liquid_first"
    PRO_RATA = "pro_rata"
    HYBRID = "hybrid"
    CUSTOM_WEIGHTS = "custom_weights"


class LiquidationStrategyConfig(VersionedAssumption):
    """JSON-backed liquidation strategy configuration."""

    liquidation_strategy_id: str = Field(pattern=SNAKE_CASE_PATTERN)
    strategy_type: LiquidationStrategyType
    cash_buffer_use_rate: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    preserve_minimum_buffer: bool
    weights: dict[AssetGroup, Decimal] | None = None

    @model_validator(mode="after")
    def validate_strategy_weights(self) -> "LiquidationStrategyConfig":
        """Validate custom-weight strategy shape without implementing allocation logic."""

        if not self.preserve_minimum_buffer:
            raise ValueError("V1 liquidation strategies must preserve the minimum cash buffer")

        if self.strategy_type is LiquidationStrategyType.CUSTOM_WEIGHTS:
            if not self.weights:
                raise ValueError("custom_weights strategy requires weights")
            total_weight = sum(self.weights.values(), Decimal("0"))
            if total_weight != Decimal("1"):
                raise ValueError("custom_weights strategy weights must sum to 1")

        if self.weights is not None:
            for weight in self.weights.values():
                if weight < Decimal("0") or weight > Decimal("1"):
                    raise ValueError("liquidation strategy weights must be between 0 and 1")

        return self
