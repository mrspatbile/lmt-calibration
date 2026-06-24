"""LMT parameter domain model."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class LmtParameters(BaseModel):
    """Explicit LMT thresholds for a fund snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    fund_id: str
    as_of_date: date
    parameter_set_id: str
    swing_threshold_rate: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    max_swing_factor_rate: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    gate_threshold_rate: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    minimum_buffer_rate: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
