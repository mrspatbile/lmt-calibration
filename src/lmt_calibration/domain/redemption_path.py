"""Domain models for fixed monthly redemption-path analysis."""

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from lmt_calibration.domain.investors import ClientClass
from lmt_calibration.domain.positions import AssetGroup
from lmt_calibration.domain.results import LiquidationResult

ZERO = Decimal("0")
ONE = Decimal("1")


class PathLmtOutcome(StrEnum):
    """LMT outcome used for one-month behavioural feedback."""

    SUSPENSION = "suspension"
    REDEMPTION_GATE = "redemption_gate"
    LIQUIDITY_BUFFER_BREACH = "liquidity_buffer_breach"
    SWING_PRICING = "swing_pricing"
    NONE = "none"


class MonthlySimulationPeriod(BaseModel):
    """Calendar metadata for one month in a redemption path."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    month_number: int = Field(ge=1)
    month_start: date
    month_end: date

    @model_validator(mode="after")
    def validate_month_dates(self) -> "MonthlySimulationPeriod":
        """Require a monthly period with an inclusive start and end date."""

        if self.month_end < self.month_start:
            raise ValueError("month_end must be on or after month_start")
        return self


class BetaDistributionParameters(BaseModel):
    """Beta parameters estimated from a redemption-rate mean and concentration."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    mean_rate: Decimal = Field(ge=ZERO, le=ONE)
    concentration_factor: Decimal = Field(gt=ZERO)
    alpha: Decimal = Field(ge=ZERO)
    beta: Decimal = Field(ge=ZERO)


class InvestorClassRedemptionRate(BaseModel):
    """Monthly redemption rate selected for one investor class."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    client_class: ClientClass
    month_number: int = Field(ge=1)
    sampled_redemption_rate: Decimal = Field(ge=ZERO, le=ONE)
    applied_redemption_rate: Decimal = Field(ge=ZERO, le=ONE)
    stress_override_applied: bool
    behavioural_feedback_multiplier: Decimal = Field(ge=ONE)


class InvestorClassRedemptionDemand(BaseModel):
    """New monthly redemption demand for one investor class."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    client_class: ClientClass
    month_number: int = Field(ge=1)
    opening_balance: Decimal = Field(ge=ZERO)
    redemption_rate: Decimal = Field(ge=ZERO, le=ONE)
    redemption_amount: Decimal = Field(ge=ZERO)
    rate_detail: InvestorClassRedemptionRate


class RedemptionPathAssumptions(BaseModel):
    """Configuration for a fixed monthly redemption path run."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    scenario_id: str
    start_date: date
    horizon_months: int = Field(default=12, gt=0)
    stress_months: tuple[int, ...] = ()
    swing_pricing_months: tuple[int, ...] = ()
    gate_months: tuple[int, ...] = ()
    suspension_months: tuple[int, ...] = ()
    apply_lmts_in_all_signal_months: bool = False
    market_stress_month: int | None = None
    random_seed: int = Field(ge=0)
    behavioural_feedback_multipliers_by_outcome: dict[
        PathLmtOutcome, dict[ClientClass, Decimal]
    ] = Field(default_factory=dict)
    market_contagion_liquidity_cost_multiplier: Decimal = Field(default=ONE, ge=ONE)
    days_per_month: int = Field(default=30, gt=0)
    liquidation_days_per_month: int = Field(default=20, gt=0)

    @field_validator("behavioural_feedback_multipliers_by_outcome")
    @classmethod
    def validate_behavioural_feedback_multipliers(
        cls,
        value: dict[PathLmtOutcome, dict[ClientClass, Decimal]],
    ) -> dict[PathLmtOutcome, dict[ClientClass, Decimal]]:
        """Require behavioural feedback multipliers of at least 1."""

        for multipliers_by_class in value.values():
            for multiplier in multipliers_by_class.values():
                if multiplier < ONE:
                    raise ValueError("behavioural feedback multipliers must be at least 1")
        return value

    @model_validator(mode="after")
    def validate_month_selections(self) -> "RedemptionPathAssumptions":
        """Ensure selected months fall inside the fixed path horizon."""

        if self.horizon_months != 12:
            raise ValueError("horizon_months must be 12 for the fixed redemption path")
        selected_months = {
            "stress_months": self.stress_months,
            "swing_pricing_months": self.swing_pricing_months,
            "gate_months": self.gate_months,
            "suspension_months": self.suspension_months,
        }
        for field_name, month_numbers in selected_months.items():
            if any(
                month_number < 1 or month_number > self.horizon_months
                for month_number in month_numbers
            ):
                raise ValueError(f"{field_name} must be within the path horizon")
        if self.market_stress_month is not None and (
            self.market_stress_month < 1 or self.market_stress_month > self.horizon_months
        ):
            raise ValueError("market_stress_month must be within the path horizon")
        if (
            self.market_contagion_liquidity_cost_multiplier > ONE
            and self.market_stress_month is None
        ):
            raise ValueError(
                "market_stress_month is required when market contagion is above neutral"
            )
        return self


class PathPositionState(BaseModel):
    """Position values carried through a redemption path."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    position_id: str
    asset_group: AssetGroup
    market_value: Decimal = Field(ge=ZERO)
    base_haircut_rate: Decimal = Field(ge=ZERO, le=ONE)
    base_liquidity_capacity_rate: Decimal = Field(ge=ZERO, le=ONE)
    settlement_days: int = Field(ge=0)
    maturity_days: int | None = Field(default=None, ge=0)
    notional_amount: Decimal | None = Field(default=None, ge=ZERO)


class DeferredRedemptionBacklogEntry(BaseModel):
    """Unpaid redemption demand carried into a later month."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    client_class: ClientClass
    origin_month: int = Field(ge=1)
    remaining_amount: Decimal = Field(ge=ZERO)


class InvestorClassMonthlyState(BaseModel):
    """Redeemable investor-class balance and redemption result for one month."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    client_class: ClientClass
    opening_balance: Decimal = Field(ge=ZERO)
    new_redemption_amount: Decimal = Field(ge=ZERO)
    opening_backlog_amount: Decimal = Field(ge=ZERO)
    effective_redemption_amount: Decimal = Field(ge=ZERO)
    paid_redemption_amount: Decimal = Field(ge=ZERO)
    deferred_redemption_amount: Decimal = Field(ge=ZERO)
    closing_balance: Decimal = Field(ge=ZERO)
    redemption_rate: Decimal = Field(ge=ZERO, le=ONE)


class MonthlyBehaviouralFeedbackAdjustment(BaseModel):
    """Behavioural feedback multipliers applied to new redemption demand."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    source_outcome: PathLmtOutcome
    behavioural_feedback_multipliers: dict[ClientClass, Decimal]

    @field_validator("behavioural_feedback_multipliers")
    @classmethod
    def validate_monthly_behavioural_feedback_multipliers(
        cls, value: dict[ClientClass, Decimal]
    ) -> dict[ClientClass, Decimal]:
        """Require monthly behavioural feedback multipliers of at least 1."""

        for multiplier in value.values():
            if multiplier < ONE:
                raise ValueError("monthly behavioural feedback multipliers must be at least 1")
        return value


class MonthlyPathLmtAssessment(BaseModel):
    """Monthly LMT signals, applied decisions, and redemption treatment."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    swing_signal: bool
    swing_applied: bool
    gate_signal: bool
    gate_applied: bool
    buffer_breached: bool
    suspension_applied: bool = False
    outcomes: tuple[PathLmtOutcome, ...] = ()
    priority_outcome: PathLmtOutcome = PathLmtOutcome.NONE
    effective_redemption_rate: Decimal = Field(ge=ZERO)
    paid_redemption_amount: Decimal = Field(ge=ZERO)
    deferred_redemption_amount: Decimal = Field(ge=ZERO)
    applied_swing_factor_rate: Decimal = Field(ge=ZERO, le=ONE)
    swing_recovery_amount: Decimal = Field(ge=ZERO)
    remaining_liquid_buffer_rate: Decimal = Field(ge=ZERO)


class MonthlyRedemptionPathResult(BaseModel):
    """Result for one monthly period in a redemption path."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    period: MonthlySimulationPeriod
    market_stress_applied: bool
    opening_nav: Decimal = Field(ge=ZERO)
    pre_lmt_nav: Decimal = Field(ge=ZERO)
    closing_nav: Decimal = Field(ge=ZERO)
    opening_cash: Decimal = Field(ge=ZERO)
    closing_cash: Decimal = Field(ge=ZERO)
    contractual_cashflow_amount: Decimal = Field(ge=ZERO)
    base_estimated_liquidity_cost_rate: Decimal = Field(ge=ZERO)
    adjusted_estimated_liquidity_cost_rate: Decimal = Field(ge=ZERO)
    market_contagion_liquidity_cost_multiplier: Decimal = Field(ge=ONE)
    market_contagion_applied: bool
    realised_liquidity_cost_after_contagion: Decimal = Field(ge=ZERO)
    behavioural_feedback_adjustment: MonthlyBehaviouralFeedbackAdjustment
    investor_class_states: tuple[InvestorClassMonthlyState, ...]
    backlog: tuple[DeferredRedemptionBacklogEntry, ...]
    positions: tuple[PathPositionState, ...]
    liquidation_result: LiquidationResult
    lmt_assessment: MonthlyPathLmtAssessment


class RedemptionPathResult(BaseModel):
    """Complete fixed-horizon redemption path result."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    scenario_id: str
    random_seed: int = Field(ge=0)
    monthly_results: tuple[MonthlyRedemptionPathResult, ...]
