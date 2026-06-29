"""Investor redemption behaviour calculations for monthly redemption paths."""

from collections.abc import Mapping, Sequence
from decimal import Decimal
from random import Random

from lmt_calibration.domain import (
    BetaDistributionParameters,
    ClientClass,
    InvestorClassProfile,
    InvestorClassRedemptionDemand,
    InvestorClassRedemptionRate,
)

ZERO = Decimal("0")
ONE = Decimal("1")


class RedemptionBehaviourError(ValueError):
    """Raised when redemption behaviour assumptions cannot be applied."""


def estimate_beta_parameters(
    *,
    mean_rate: Decimal,
    concentration_factor: Decimal,
) -> BetaDistributionParameters:
    """Estimate beta distribution parameters from the approved path formula."""

    if mean_rate < ZERO or mean_rate > ONE:
        raise RedemptionBehaviourError("mean_rate must be between 0 and 1")
    if concentration_factor <= ZERO:
        raise RedemptionBehaviourError("concentration_factor must be greater than 0")

    return BetaDistributionParameters(
        mean_rate=mean_rate,
        concentration_factor=concentration_factor,
        alpha=mean_rate * concentration_factor,
        beta=(ONE - mean_rate) * concentration_factor,
    )


def sample_monthly_redemption_rate(
    parameters: BetaDistributionParameters,
    rng: Random,
) -> Decimal:
    """Sample one monthly redemption rate from beta parameters."""

    if parameters.mean_rate == ZERO or parameters.mean_rate == ONE:
        return parameters.mean_rate
    sampled_rate = rng.betavariate(float(parameters.alpha), float(parameters.beta))
    return Decimal(str(sampled_rate))


def monthly_redemption_rate_for_class(
    *,
    investor: InvestorClassProfile,
    month_number: int,
    stress_months: Sequence[int],
    behavioural_multiplier: Decimal,
    contagion_multiplier: Decimal,
    rng: Random,
) -> InvestorClassRedemptionRate:
    """Return the monthly redemption rate selected for one investor class."""

    if month_number < 1:
        raise RedemptionBehaviourError("month_number must be positive")
    if behavioural_multiplier < ZERO:
        raise RedemptionBehaviourError("behavioural_multiplier must be non-negative")
    if contagion_multiplier < ZERO:
        raise RedemptionBehaviourError("contagion_multiplier must be non-negative")

    beta_parameters = estimate_beta_parameters(
        mean_rate=investor.base_redemption_rate,
        concentration_factor=investor.concentration_factor,
    )
    sampled_redemption_rate = sample_monthly_redemption_rate(beta_parameters, rng)
    stress_override_applied = month_number in stress_months
    starting_rate = (
        investor.stress_redemption_rate if stress_override_applied else sampled_redemption_rate
    )
    applied_redemption_rate = min(
        starting_rate * behavioural_multiplier * contagion_multiplier,
        ONE,
    )

    return InvestorClassRedemptionRate(
        client_class=investor.client_class,
        month_number=month_number,
        sampled_redemption_rate=sampled_redemption_rate,
        applied_redemption_rate=applied_redemption_rate,
        stress_override_applied=stress_override_applied,
        behavioural_multiplier=behavioural_multiplier,
        contagion_multiplier=contagion_multiplier,
    )


def calculate_monthly_redemption_demands(
    *,
    investor_profiles: Sequence[InvestorClassProfile],
    investor_balances: Mapping[ClientClass, Decimal],
    month_number: int,
    stress_months: Sequence[int],
    behavioural_multipliers: Mapping[ClientClass, Decimal],
    contagion_multiplier: Decimal,
    rng: Random,
) -> tuple[InvestorClassRedemptionDemand, ...]:
    """Aggregate monthly redemption demand across investor classes."""

    demands: list[InvestorClassRedemptionDemand] = []
    for investor in sorted(investor_profiles, key=lambda item: item.client_class.value):
        opening_balance = max(investor_balances.get(investor.client_class, ZERO), ZERO)
        rate_detail = monthly_redemption_rate_for_class(
            investor=investor,
            month_number=month_number,
            stress_months=stress_months,
            behavioural_multiplier=behavioural_multipliers.get(investor.client_class, ONE),
            contagion_multiplier=contagion_multiplier,
            rng=rng,
        )
        redemption_amount = opening_balance * rate_detail.applied_redemption_rate
        demands.append(
            InvestorClassRedemptionDemand(
                client_class=investor.client_class,
                month_number=month_number,
                opening_balance=opening_balance,
                redemption_rate=rate_detail.applied_redemption_rate,
                redemption_amount=redemption_amount,
                rate_detail=rate_detail,
            )
        )
    return tuple(demands)
