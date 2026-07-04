from decimal import Decimal

import pytest
from pydantic import ValidationError

from lmt_calibration.domain import (
    BetaDistributionParameters,
    ClientClass,
    DeferredRedemptionBacklogEntry,
    MonthlySimulationPeriod,
    PathLmtOutcome,
    RedemptionPathAssumptions,
)


def test_deferred_backlog_stores_units_and_values_them_at_current_nav() -> None:
    entry = DeferredRedemptionBacklogEntry(
        client_class=ClientClass.INSTITUTIONAL,
        origin_month=2,
        remaining_units=Decimal("125"),
        nav_at_deferral=Decimal("1.04"),
    )

    assert entry.remaining_units == Decimal("125")
    assert entry.nav_at_deferral == Decimal("1.04")
    assert entry.cash_value(Decimal("1.10")) == Decimal("137.50")
    assert entry.cash_value(Decimal("0.90")) == Decimal("112.50")

    with pytest.raises(ValidationError, match="remaining_amount"):
        DeferredRedemptionBacklogEntry(
            client_class=ClientClass.INSTITUTIONAL,
            origin_month=2,
            remaining_amount=Decimal("125"),
            nav_at_deferral=Decimal("1.04"),
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
        swing_pricing_months=(2,),
        gate_months=(3,),
        market_stress_month=1,
    )

    assert assumptions.horizon_months == 12
    assert assumptions.stress_months == (1, 3)
    assert assumptions.swing_pricing_months == (2,)
    assert assumptions.gate_months == (3,)
    assert assumptions.apply_lmts_in_all_signal_months is False
    assert assumptions.liquidation_days_per_month == 20
    assert assumptions.gate_period_liquidation_enabled is True

    with pytest.raises(ValidationError, match="stress_months"):
        RedemptionPathAssumptions(
            scenario_id="bad_path",
            start_date="2026-01-01",
            random_seed=7,
            stress_months=(13,),
        )

    with pytest.raises(ValidationError, match="greater than 0"):
        RedemptionPathAssumptions(
            scenario_id="invalid_liquidation_days",
            start_date="2026-01-01",
            random_seed=7,
            liquidation_days_per_month=0,
        )


def test_redemption_path_assumptions_reject_non_twelve_month_horizon() -> None:
    with pytest.raises(ValidationError, match="horizon_months"):
        RedemptionPathAssumptions(
            scenario_id="bad_horizon",
            start_date="2026-01-01",
            random_seed=7,
            horizon_months=6,
        )


def test_redemption_path_assumptions_validate_suspension_months() -> None:
    assumptions = RedemptionPathAssumptions(
        scenario_id="suspension_path",
        start_date="2026-01-01",
        random_seed=7,
        suspension_months=(2, 5),
    )

    assert assumptions.suspension_months == (2, 5)

    with pytest.raises(ValidationError, match="suspension_months"):
        RedemptionPathAssumptions(
            scenario_id="invalid_suspension_path",
            start_date="2026-01-01",
            random_seed=7,
            suspension_months=(13,),
        )

    with pytest.raises(ValidationError, match="swing_pricing_months"):
        RedemptionPathAssumptions(
            scenario_id="invalid_swing_month",
            start_date="2026-01-01",
            random_seed=7,
            swing_pricing_months=(0,),
        )

    with pytest.raises(ValidationError, match="gate_months"):
        RedemptionPathAssumptions(
            scenario_id="invalid_gate_month",
            start_date="2026-01-01",
            random_seed=7,
            gate_months=(13,),
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


def test_redemption_path_assumptions_validate_market_contagion() -> None:
    with pytest.raises(ValidationError, match="market_stress_month is required"):
        RedemptionPathAssumptions(
            scenario_id="missing_market_stress_month",
            start_date="2026-01-01",
            random_seed=7,
            market_contagion_liquidity_cost_multiplier=Decimal("1.50"),
        )

    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        RedemptionPathAssumptions(
            scenario_id="invalid_market_contagion",
            start_date="2026-01-01",
            random_seed=7,
            market_stress_month=1,
            market_contagion_liquidity_cost_multiplier=Decimal("0.99"),
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
