"""Investor class profile domain model.

Rates such as NAV share and redemption assumptions are Decimal values where
``Decimal("0.05")`` means 5%.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ClientClass(StrEnum):
    """Supported Version 1 investor classes."""

    RETAIL = "retail"
    INSTITUTIONAL = "institutional"
    PLATFORM = "platform"
    FUND_OF_FUNDS = "fund_of_funds"
    SEED_CAPITAL = "seed_capital"


class InvestorClassProfile(BaseModel):
    """Investor-class redemption profile for one fund snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    fund_id: str
    as_of_date: date
    client_class: ClientClass
    nav_share_rate: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    base_redemption_rate: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    stress_redemption_rate: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    concentration_factor: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    notice_days: int = Field(ge=0)
    settlement_days: int = Field(ge=0)
