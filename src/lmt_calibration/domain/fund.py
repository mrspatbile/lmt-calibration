"""Fund snapshot domain model.

Rates and monetary values follow the project convention: monetary values are
stored as Decimal and dates use ISO-compatible ``date`` values.
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class FundSnapshot(BaseModel):
    """Validated fund state for one fund and one as-of date."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    fund_id: str
    as_of_date: date
    fund_name: str
    base_currency: str = Field(pattern=r"^[A-Z]{3}$")
    nav: Decimal = Field(gt=Decimal("0"))
    dealing_frequency: str
    redemption_notice_days: int = Field(ge=0)
    redemption_settlement_days: int = Field(ge=0)
