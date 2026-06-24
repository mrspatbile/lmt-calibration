"""Asset position domain model.

Monetary values, sensitivities, haircuts, and capacity rates use Decimal.
Conditional field validation follows the position rules in
``docs/DATA_CONVENTIONS.md``.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AssetGroup(StrEnum):
    """Supported instrument groups in the canonical position schema."""

    CASH = "cash"
    LISTED_EQUITY = "listed_equity"
    LISTED_ETF = "listed_etf"
    GOVERNMENT_BOND = "government_bond"
    CORPORATE_BOND = "corporate_bond"
    FX_FORWARD = "fx_forward"
    EQUITY_FUTURE = "equity_future"
    INTEREST_RATE_FUTURE = "interest_rate_future"
    EQUITY_OPTION = "equity_option"
    INTEREST_RATE_SWAP = "interest_rate_swap"
    REVERSE_REPO = "reverse_repo"
    REPO_FINANCING = "repo_financing"


class InstrumentSubtype(StrEnum):
    """Instrument subtypes with documented conditional field requirements."""

    CASH = "cash"
    LISTED_EQUITY = "listed_equity"
    LISTED_ETF = "listed_etf"
    GOVERNMENT_BOND = "government_bond"
    CORPORATE_BOND = "corporate_bond"
    FX_FORWARD = "fx_forward"
    EQUITY_FUTURE = "equity_future"
    INTEREST_RATE_FUTURE = "interest_rate_future"
    EQUITY_OPTION = "equity_option"
    INTEREST_RATE_SWAP = "interest_rate_swap"
    REVERSE_REPO = "reverse_repo"
    REPO_FINANCING = "repo_financing"


class OptionType(StrEnum):
    """Supported option direction labels."""

    CALL = "call"
    PUT = "put"


class AssetPosition(BaseModel):
    """Position-level fund holding or financing exposure."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    position_id: str
    fund_id: str
    as_of_date: date

    asset_group: AssetGroup
    instrument_type: str
    instrument_subtype: InstrumentSubtype

    instrument_name: str
    ticker: str | None = None
    currency: str = Field(pattern=r"^[A-Z]{3}$")

    market_value: Decimal | None = Field(default=None, ge=Decimal("0"))
    notional_amount: Decimal | None = Field(default=None, ge=Decimal("0"))

    risk_factor_id: str | None = None
    underlying_position_id: str | None = None
    underlying_risk_factor_id: str | None = None

    beta: Decimal | None = None
    duration_years: Decimal | None = None
    spread_duration_years: Decimal | None = None
    delta: Decimal | None = None

    entry_price: Decimal | None = Field(default=None, ge=Decimal("0"))
    strike_price: Decimal | None = Field(default=None, ge=Decimal("0"))
    option_type: OptionType | None = None
    expiry_date: date | None = None

    benchmark_ticker: str | None = None

    base_haircut_rate: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    base_liquidity_capacity_rate: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))

    settlement_days: int = Field(ge=0)
    maturity_days: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_conditional_position_fields(self) -> "AssetPosition":
        """Apply conditional field requirements documented for position subtypes."""

        required_by_subtype: dict[InstrumentSubtype, tuple[str, ...]] = {
            InstrumentSubtype.CASH: ("market_value",),
            InstrumentSubtype.LISTED_EQUITY: ("market_value", "risk_factor_id", "beta"),
            InstrumentSubtype.LISTED_ETF: ("market_value", "risk_factor_id"),
            InstrumentSubtype.GOVERNMENT_BOND: ("market_value", "risk_factor_id", "duration_years"),
            InstrumentSubtype.CORPORATE_BOND: (
                "market_value",
                "risk_factor_id",
                "duration_years",
                "spread_duration_years",
            ),
            InstrumentSubtype.EQUITY_FUTURE: (
                "notional_amount",
                "entry_price",
                "delta",
                "underlying_risk_factor_id",
            ),
            InstrumentSubtype.INTEREST_RATE_FUTURE: (
                "notional_amount",
                "entry_price",
                "delta",
                "underlying_risk_factor_id",
            ),
            InstrumentSubtype.FX_FORWARD: (
                "notional_amount",
                "entry_price",
                "expiry_date",
                "delta",
                "underlying_risk_factor_id",
            ),
            InstrumentSubtype.INTEREST_RATE_SWAP: ("notional_amount", "underlying_risk_factor_id"),
            InstrumentSubtype.REVERSE_REPO: ("market_value", "maturity_days"),
        }

        self._require_fields(required_by_subtype.get(self.instrument_subtype, ()))

        if self.instrument_subtype is InstrumentSubtype.CASH:
            self._validate_cash_terms()

        if self.instrument_subtype is InstrumentSubtype.EQUITY_OPTION:
            self._validate_equity_option()

        if (
            self.instrument_subtype is InstrumentSubtype.INTEREST_RATE_SWAP
            and self.duration_years is None
        ):
            raise ValueError("interest_rate_swap requires duration_years")

        return self

    def _require_fields(self, field_names: tuple[str, ...]) -> None:
        missing_fields = [field_name for field_name in field_names if self._is_missing(field_name)]
        if missing_fields:
            missing = ", ".join(missing_fields)
            raise ValueError(f"{self.instrument_subtype} requires {missing}")

    def _validate_cash_terms(self) -> None:
        if self.base_haircut_rate != Decimal("0"):
            raise ValueError("cash must have zero base_haircut_rate")
        if self.base_liquidity_capacity_rate != Decimal("1"):
            raise ValueError("cash must have full base_liquidity_capacity_rate")
        if self.settlement_days != 0:
            raise ValueError("cash must have zero settlement_days")

    def _validate_equity_option(self) -> None:
        self._require_fields(
            (
                "notional_amount",
                "strike_price",
                "option_type",
                "expiry_date",
                "delta",
            )
        )
        if self.underlying_position_id is None and self.underlying_risk_factor_id is None:
            raise ValueError(
                "equity_option requires underlying_position_id or underlying_risk_factor_id"
            )

    def _is_missing(self, field_name: str) -> bool:
        value: Any = getattr(self, field_name)
        return value is None or value == ""
