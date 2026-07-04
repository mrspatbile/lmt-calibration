"""Structured results for scenario-independent time-to-liquidation analysis."""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TtlSensitivityType(StrEnum):
    """Supported time-to-liquidation sensitivity dimensions."""

    PARTICIPATION_RATE = "participation_rate"
    LIQUIDITY_HAIRCUT = "liquidity_haircut"


class DailyLiquidationPoint(BaseModel):
    """Cumulative cash available at one business-day point."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    business_day: int = Field(ge=0)
    cumulative_cash_raised: Decimal = Field(ge=Decimal("0"))
    cumulative_cash_raised_rate: Decimal = Field(ge=Decimal("0"))


class TtlSensitivityResult(BaseModel):
    """One participation-rate or liquidity-haircut sensitivity result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sensitivity_type: TtlSensitivityType
    sensitivity_value: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    daily_cumulative_cash_raised: tuple[DailyLiquidationPoint, ...]
    redemption_shock_amount: Decimal = Field(ge=Decimal("0"))
    redemption_shock_rate: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    ttl_to_redemption_shock_days: int | None = Field(default=None, ge=0)
    ttl_to_full_liquidation_days: int | None = Field(default=None, ge=0)
    unmet_amount_at_horizon: Decimal = Field(ge=Decimal("0"))


class AssetClassDistribution(BaseModel):
    """Current market value and NAV share for one display asset group."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    asset_group: str
    market_value: Decimal = Field(ge=Decimal("0"))
    nav_share_rate: Decimal = Field(ge=Decimal("0"))
