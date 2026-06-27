"""Simulated LMT activation assessment and investor impact analysis."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from lmt_calibration.domain import LmtParameters, MarketStress
from lmt_calibration.engines.liquidity_cost import (
    estimate_liquidity_cost_amount,
    estimate_liquidity_cost_rate,
)

ZERO = Decimal("0")
THRESHOLD_UNDER = Decimal("0.80")
THRESHOLD_ALIGNED_LOW = Decimal("0.80")
THRESHOLD_ALIGNED_HIGH = Decimal("1.20")
THRESHOLD_CONSERVATIVE = Decimal("2.00")


class CalibrationAdequacy(str, Enum):
    """Calibration adequacy classification based on coverage ratio."""

    UNDER_CALIBRATED = "Under-calibrated"
    ALIGNED = "Aligned"
    CONSERVATIVE = "Conservative"
    OVER_CALIBRATED = "Over-calibrated"
    NO_LIQUIDITY_COST = "No liquidity cost"


@dataclass(frozen=True)
class LmtActivationResult:
    """Simulated activation assessment and investor impact for a redemption scenario."""

    swing_activated: bool
    gate_activated: bool
    buffer_breached: bool
    estimated_liquidity_cost_rate: Decimal
    selected_swing_factor_rate: Decimal
    coverage_ratio: Decimal
    residual_dilution_rate: Decimal
    estimated_liquidity_cost_amount: Decimal
    recovered_cost_amount: Decimal
    residual_dilution_amount: Decimal
    redemption_paid_amount: Decimal
    redemption_deferred_amount: Decimal
    calibration_adequacy: CalibrationAdequacy = None  # type: ignore
    calibration_message: str = ""


def classify_calibration_adequacy(
    estimated_liquidity_cost_amount: Decimal,
    recovered_cost_amount: Decimal,
    coverage_ratio: Decimal,
) -> CalibrationAdequacy:
    """Classify calibration adequacy based on coverage ratio.

    Args:
        estimated_liquidity_cost_amount: Estimated cost in currency units.
        recovered_cost_amount: Amount recovered by selected ADT.
        coverage_ratio: Ratio of recovered to estimated cost.

    Returns:
        Calibration adequacy classification.
    """
    # Both zero: no cost to cover
    if estimated_liquidity_cost_amount == ZERO and recovered_cost_amount == ZERO:
        return CalibrationAdequacy.NO_LIQUIDITY_COST

    # Estimated cost is zero but recovery is positive (shouldn't happen, but handle it)
    if estimated_liquidity_cost_amount == ZERO and recovered_cost_amount > ZERO:
        return CalibrationAdequacy.OVER_CALIBRATED

    # Estimated cost is zero: no cost to cover
    if estimated_liquidity_cost_amount == ZERO:
        return CalibrationAdequacy.NO_LIQUIDITY_COST

    # Use coverage ratio bands
    if coverage_ratio < THRESHOLD_UNDER:
        return CalibrationAdequacy.UNDER_CALIBRATED
    if THRESHOLD_ALIGNED_LOW <= coverage_ratio <= THRESHOLD_ALIGNED_HIGH:
        return CalibrationAdequacy.ALIGNED
    if THRESHOLD_ALIGNED_HIGH < coverage_ratio <= THRESHOLD_CONSERVATIVE:
        return CalibrationAdequacy.CONSERVATIVE
    return CalibrationAdequacy.OVER_CALIBRATED


def get_calibration_message(adequacy: CalibrationAdequacy) -> str:
    """Get the message for a calibration adequacy classification.

    Args:
        adequacy: Calibration adequacy classification.

    Returns:
        Explanatory message.
    """
    messages = {
        CalibrationAdequacy.UNDER_CALIBRATED: "Selected factor does not fully cover estimated liquidity cost.",
        CalibrationAdequacy.ALIGNED: "Selected factor broadly matches estimated liquidity cost.",
        CalibrationAdequacy.CONSERVATIVE: "Selected factor is above estimated liquidity cost.",
        CalibrationAdequacy.OVER_CALIBRATED: "Selected factor materially exceeds estimated liquidity cost.",
        CalibrationAdequacy.NO_LIQUIDITY_COST: "No estimated liquidity cost under this scenario.",
    }
    return messages.get(adequacy, "")


def assess_lmt_impact(
    *,
    nav: Decimal,
    redemption_rate: Decimal,
    market_stress: MarketStress,
    lmt_parameters: LmtParameters,
    remaining_liquid_buffer_rate: Decimal | None = None,
) -> LmtActivationResult:
    """Assess simulated LMT activation and investor impact for a redemption scenario.

    Args:
        nav: Current NAV after market valuation shock and before LMT effects.
        redemption_rate: Gross redemption amount divided by current pre-LMT NAV.
        market_stress: Market stress scenario with execution assumptions.
        lmt_parameters: LMT calibration parameters.
        remaining_liquid_buffer_rate: Remaining liquidity buffer rate (optional).

    Returns:
        LmtActivationResult with simulated activation states and investor impact metrics.
    """
    # Calculate gross redemption amount
    gross_redemption_amount = nav * redemption_rate

    # Estimate liquidity cost
    estimated_cost_rate = estimate_liquidity_cost_rate(market_stress)
    estimated_cost_amount = estimate_liquidity_cost_amount(gross_redemption_amount, market_stress)

    # Evaluate the simulated swing activation threshold comparison.
    swing_factor_rate = lmt_parameters.max_swing_factor_rate
    swing_activated = redemption_rate >= lmt_parameters.swing_threshold_rate

    # Calculate cost recovery through swing pricing when the simulated condition is met.
    # Swing pricing applies the selected factor to the redemption amount
    recovered_cost_amount = gross_redemption_amount * swing_factor_rate if swing_activated else ZERO

    # Calculate residual dilution after simulated LMT effects.
    residual_dilution_amount = max(estimated_cost_amount - recovered_cost_amount, ZERO)
    residual_dilution_rate = residual_dilution_amount / nav if nav > ZERO else ZERO

    # Calculate coverage ratio
    coverage_ratio = (
        (recovered_cost_amount / estimated_cost_amount)
        if estimated_cost_amount > ZERO
        else Decimal("1")
    )

    # Evaluate the simulated gate activation threshold comparison.
    gate_activated = redemption_rate >= lmt_parameters.gate_threshold_rate

    # Calculate redemption paid vs deferred
    # Defer redemption when the simulated gate activation condition is met.
    if gate_activated:
        gate_capacity_rate = lmt_parameters.gate_threshold_rate
        redemption_paid_amount = nav * gate_capacity_rate
        redemption_deferred_amount = gross_redemption_amount - redemption_paid_amount
    else:
        redemption_paid_amount = gross_redemption_amount
        redemption_deferred_amount = ZERO

    # Check buffer breach (if remaining buffer provided)
    buffer_breached = (
        remaining_liquid_buffer_rate is not None
        and remaining_liquid_buffer_rate < lmt_parameters.minimum_buffer_rate
    )

    # Classify calibration adequacy
    adequacy = classify_calibration_adequacy(
        estimated_cost_amount, recovered_cost_amount, coverage_ratio
    )
    message = get_calibration_message(adequacy)

    return LmtActivationResult(
        swing_activated=swing_activated,
        gate_activated=gate_activated,
        buffer_breached=buffer_breached,
        estimated_liquidity_cost_rate=estimated_cost_rate,
        selected_swing_factor_rate=swing_factor_rate,
        coverage_ratio=coverage_ratio,
        residual_dilution_rate=residual_dilution_rate,
        estimated_liquidity_cost_amount=estimated_cost_amount,
        recovered_cost_amount=recovered_cost_amount,
        residual_dilution_amount=residual_dilution_amount,
        redemption_paid_amount=redemption_paid_amount,
        redemption_deferred_amount=redemption_deferred_amount,
        calibration_adequacy=adequacy,
        calibration_message=message,
    )
