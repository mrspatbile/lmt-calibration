"""Reusable scenario assumption models and scenario definitions."""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from lmt_calibration.domain.positions import AssetGroup

SNAKE_CASE_PATTERN = r"^[a-z][a-z0-9_]*$"
HISTORICAL_SHOCK_GROUPS = {"equity", "interest_rates", "credit_spreads", "fx"}


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
    market_shock_rate: Decimal = Field(ge=Decimal("-1"), le=Decimal("1"))
    bid_ask_spread_rate: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    transaction_cost_rate: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    market_impact_rate: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    participation_rate: Decimal | None = Field(default=None, gt=Decimal("0"), le=Decimal("1"))
    liquidity_haircut_rate: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))


class LiquidityExecutionAssumption(BaseModel):
    """Execution and tradability assumptions for an asset class under liquidity stress."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    bid_ask_spread_rate: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    transaction_cost_rate: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    market_impact_rate: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    participation_rate: Decimal = Field(gt=Decimal("0"), le=Decimal("1"))
    liquidity_haircut_rate: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))


class LiquidityStress(VersionedAssumption):
    """Reusable asset-side liquidity shock assumption with execution assumptions by asset class."""

    liquidity_stress_id: str = Field(pattern=SNAKE_CASE_PATTERN)
    stress_horizon_days: int = Field(gt=0)
    execution_assumptions_by_asset_group: dict[AssetGroup, LiquidityExecutionAssumption] = Field(
        min_length=1
    )

    @field_validator("execution_assumptions_by_asset_group")
    @classmethod
    def validate_execution_assumptions(
        cls, value: dict[AssetGroup, LiquidityExecutionAssumption]
    ) -> dict[AssetGroup, LiquidityExecutionAssumption]:
        """Ensure all asset groups have valid execution assumptions."""
        if not value:
            raise ValueError("execution_assumptions_by_asset_group must not be empty")
        return value


class HistoricalStressShock(BaseModel):
    """One non-FX historical market stress shock."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    shock: Decimal
    unit: Literal["pct"]
    description: str


class HistoricalFxShock(BaseModel):
    """Historical FX shocks keyed by impacted currency."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    shock_by_currency: dict[str, Decimal] = Field(min_length=1)
    unit: Literal["pct"]
    description: str

    @field_validator("shock_by_currency")
    @classmethod
    def validate_currency_codes(cls, value: dict[str, Decimal]) -> dict[str, Decimal]:
        """Require ISO-style uppercase currency keys."""

        for currency in value:
            if len(currency) != 3 or not currency.isalpha() or not currency.isupper():
                raise ValueError("FX shock currency keys must be 3-letter uppercase codes")
        return value


class HistoricalMarketStressScenario(BaseModel):
    """One historical market stress scenario definition."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    test_category: str
    scenario_name: str
    description: str
    period: str
    holding_period_days: int = Field(gt=0)
    shocks: dict[str, HistoricalStressShock | HistoricalFxShock] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_shock_groups(self) -> "HistoricalMarketStressScenario":
        """Validate the supported V1 historical stress shock group shape."""

        if set(self.shocks) != HISTORICAL_SHOCK_GROUPS:
            raise ValueError(
                "historical market stress scenarios must include equity, "
                "interest_rates, credit_spreads, and fx shocks"
            )
        if not isinstance(self.shocks["fx"], HistoricalFxShock):
            raise ValueError("fx shock must use shock_by_currency")
        for shock_group in ("equity", "interest_rates", "credit_spreads"):
            if not isinstance(self.shocks[shock_group], HistoricalStressShock):
                raise ValueError(f"{shock_group} shock must use shock")
        return self


class HistoricalMarketStressScenarioLibrary(BaseModel):
    """Versioned historical market stress scenario library."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    schema_version: Literal["1.0"]
    source: str
    scenario_type: Literal["historical"]
    notes: str
    scenarios: dict[str, HistoricalMarketStressScenario] = Field(min_length=1)

    @field_validator("scenarios")
    @classmethod
    def validate_scenario_ids(
        cls, value: dict[str, HistoricalMarketStressScenario]
    ) -> dict[str, HistoricalMarketStressScenario]:
        """Require simple snake_case scenario identifiers."""

        allowed_characters = set("abcdefghijklmnopqrstuvwxyz0123456789_")
        for scenario_id in value:
            if (
                not scenario_id
                or scenario_id[0] == "_"
                or scenario_id[-1] == "_"
                or "__" in scenario_id
                or any(character not in allowed_characters for character in scenario_id)
            ):
                raise ValueError("historical scenario IDs must use snake_case")
        return value


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
