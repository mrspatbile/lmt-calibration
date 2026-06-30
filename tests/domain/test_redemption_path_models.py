from decimal import Decimal

import pytest
from pydantic import ValidationError

from lmt_calibration.domain import (
    BetaDistributionParameters,
    ClientClass,
    MonthlySimulationPeriod,
    PathLmtOutcome,
    RedemptionPathAssumptions,
)


def test_monthly_simulation_period_rejects_end_before_start() -> None:
    with pytest.raises(ValidationError, match="month_end"):
        MonthlySimulationPeriod(
            month_number=1,
            month_start="2026-02-28",
            month_end="2026-02-01",
        )


def test_redemption_path_assumptions_validate_selected_months() -> None:
    assumptions = RedemptionPathAssumptions(
        scenario_id="path_test",
        start_date="2026-01-01",
        random_seed=7,
        stress_months=(1, 3),
        market_stress_month=1,
    )

    assert assumptions.horizon_months == 12
    assert assumptions.stress_months == (1, 3)

    with pytest.raises(ValidationError, match="stress_months"):
        RedemptionPathAssumptions(
            scenario_id="bad_path",
            start_date="2026-01-01",
            random_seed=7,
            stress_months=(13,),
        )


def test_redemption_path_assumptions_reject_non_twelve_month_horizon() -> None:
    with pytest.raises(ValidationError, match="horizon_months"):
        RedemptionPathAssumptions(
            scenario_id="bad_horizon",
            start_date="2026-01-01",
            random_seed=7,
            horizon_months=6,
        )


def test_redemption_path_assumptions_reject_behavioural_feedback_below_one() -> None:
    with pytest.raises(ValidationError, match="at least 1"):
        RedemptionPathAssumptions(
            scenario_id="invalid_feedback",
            start_date="2026-01-01",
            random_seed=7,
            behavioural_feedback_multipliers_by_outcome={
                PathLmtOutcome.SWING_PRICING: {
                    ClientClass.RETAIL: Decimal("0.99"),
                }
            },
        )


def test_beta_distribution_parameters_allow_boundary_means() -> None:
    parameters = BetaDistributionParameters(
        mean_rate="0",
        concentration_factor="0.50",
        alpha="0",
        beta="0.50",
    )

    assert parameters.mean_rate == Decimal("0")
    assert parameters.alpha == Decimal("0")
