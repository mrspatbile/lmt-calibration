from decimal import Decimal
from random import Random

import pytest

from lmt_calibration.domain import ClientClass, InvestorClassProfile
from lmt_calibration.engines.redemption_behaviour import (
    RedemptionBehaviourError,
    calculate_monthly_redemption_demands,
    estimate_beta_parameters,
    monthly_redemption_rate_for_class,
)


def test_estimate_beta_parameters_uses_approved_formula() -> None:
    parameters = estimate_beta_parameters(
        mean_rate=Decimal("0.20"),
        concentration_factor=Decimal("150"),
    )

    assert parameters.alpha == Decimal("30.00")
    assert parameters.beta == Decimal("120.00")


def test_estimate_beta_parameters_requires_valid_inputs() -> None:
    with pytest.raises(RedemptionBehaviourError, match="mean_rate"):
        estimate_beta_parameters(
            mean_rate=Decimal("1.10"),
            concentration_factor=Decimal("150"),
        )

    with pytest.raises(RedemptionBehaviourError, match="concentration_factor"):
        estimate_beta_parameters(
            mean_rate=Decimal("0.20"),
            concentration_factor=Decimal("0"),
        )


def test_monthly_rate_is_deterministic_for_fixed_seed() -> None:
    investor = _investor(ClientClass.RETAIL, base_rate="0.08", stress_rate="0.25")

    first = monthly_redemption_rate_for_class(
        investor=investor,
        month_number=1,
        stress_months=(),
        behavioural_multiplier=Decimal("1"),
        contagion_multiplier=Decimal("1"),
        rng=Random(11),
    )
    second = monthly_redemption_rate_for_class(
        investor=investor,
        month_number=1,
        stress_months=(),
        behavioural_multiplier=Decimal("1"),
        contagion_multiplier=Decimal("1"),
        rng=Random(11),
    )

    assert first.sampled_redemption_rate == second.sampled_redemption_rate
    assert first.applied_redemption_rate == second.applied_redemption_rate


def test_stress_month_replaces_sample_then_applies_multipliers_and_cap() -> None:
    investor = _investor(ClientClass.PLATFORM, base_rate="0.01", stress_rate="0.80")

    rate = monthly_redemption_rate_for_class(
        investor=investor,
        month_number=2,
        stress_months=(2,),
        behavioural_multiplier=Decimal("1.50"),
        contagion_multiplier=Decimal("1.10"),
        rng=Random(4),
    )

    assert rate.stress_override_applied is True
    assert rate.applied_redemption_rate == Decimal("1")


def test_monthly_demands_use_current_investor_balances() -> None:
    investors = (
        _investor(ClientClass.RETAIL, base_rate="0", stress_rate="0.10"),
        _investor(ClientClass.INSTITUTIONAL, base_rate="0", stress_rate="0.20"),
    )

    demands = calculate_monthly_redemption_demands(
        investor_profiles=investors,
        investor_balances={
            ClientClass.RETAIL: Decimal("400"),
            ClientClass.INSTITUTIONAL: Decimal("600"),
        },
        month_number=1,
        stress_months=(1,),
        behavioural_multipliers={ClientClass.RETAIL: Decimal("2")},
        contagion_multiplier=Decimal("1"),
        rng=Random(3),
    )

    by_class = {demand.client_class: demand for demand in demands}
    assert by_class[ClientClass.RETAIL].redemption_amount == Decimal("80.0")
    assert by_class[ClientClass.INSTITUTIONAL].redemption_amount == Decimal("120.0")


def _investor(
    client_class: ClientClass,
    *,
    base_rate: str,
    stress_rate: str,
) -> InvestorClassProfile:
    return InvestorClassProfile(
        fund_id="lux_dynamic_allocation",
        as_of_date="2026-01-01",
        client_class=client_class,
        nav_share_rate=Decimal("0.50"),
        base_redemption_rate=Decimal(base_rate),
        stress_redemption_rate=Decimal(stress_rate),
        concentration_factor=Decimal("150"),
        notice_days=1,
        settlement_days=3,
    )
