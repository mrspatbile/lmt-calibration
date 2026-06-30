# Redemption Path Methodology

## Purpose

This document defines the planned 12-month redemption-path methodology for the
Liquidity Management Tools Calibration application.

The redemption-path page extends the current single-period calibration workflow
by simulating how investor redemptions, liquidity resources, LMT effects,
deferred redemptions, and NAV evolve over twelve monthly periods.

The methodology is designed as a forward-looking liquidity stress view. It is
not a direct repetition of the current one-period scenario matrix.

## Core Design

The simulation uses a fixed 12-month horizon.

Each month updates the fund position and carries the result into the next
month. Each month-end fund position becomes the next month’s opening position.

The simulation is not twelve independent single-period shocks.

The methodology should remain consistent with the current single-period
calibration approach.

## Simulation Timeline

Each simulated month should have clear monthly dates:

* month number in the 12-month path
* month start date
* month end date

The monthly timeline is needed for:

* redemption stress months
* market stress timing
* reverse repo maturities
* future fixed-income maturities
* coupon payments, if later supported
* settlement periods
* notice periods

The first version remains monthly rather than intra-month, but each monthly
period should identify where the redemption path is in time.

## Market Stress Scenario Timing

Market stress is optional.

The user should be able to select:

* no market shock
* one configured market stress scenario

When a market stress scenario is selected, the market valuation shock is applied
once.

The market stress scenario is applied at the start of the first selected
redemption-stress month.

The same market stress scenario is not re-applied in later months. Later months
carry forward the post-shock portfolio state and evolve through redemptions,
liquidation, LMT effects, cashflows, and behavioural feedback.

Example:

* simulation horizon: 12 months
* redemption stress months: months 3, 4, and 5
* market stress scenario: severe stress

The severe market stress scenario is applied once at the start of month 3.
Months 4 to 12 carry forward the post-shock portfolio state.

If no market shock is selected, the simulation starts without a valuation shock
and evolves only through redemption dynamics and liquidity effects.

If a market stress scenario is selected but no redemption-stress month exists,
the market-stress month must be selected explicitly. The methodology should not
assume an unstated market-stress date.

## Redemption Stress Months

The user should be able to choose one or more redemption-stress months.

In normal months, investor-class redemption rates are generated from the
configured behavioural assumptions.

In stress months, the normal monthly redemption rate is replaced by the
configured stressed redemption rate for the investor class.

The redemption stress months represent periods of elevated liability-side
pressure.

## Monthly Sequence

Each month follows this sequence:

```text
Opening monthly fund position
        ↓
Apply selected market stress scenario only if this month is the market-stress month
        ↓
Apply contractual cashflows
        ↓
Generate new investor redemption demand
        ↓
Add deferred backlog from previous months
        ↓
Compute effective redemption demand
        ↓
Assess LMT thresholds and simulated LMT effects
        ↓
Determine paid and deferred redemption
        ↓
Calculate liquidation only for paid redemption
        ↓
Determine month-end cash, positions, NAV, liquid resources, and backlog
        ↓
Use month-end position as next month’s opening position
```

Cashflows occur before liquidation.

Liquidation is calculated only for paid redemption amounts, not for demand that
is gated, suspended, or deferred.

## Opening Monthly Fund Position

The first month starts from the validated fund snapshot and current position
set.

Later months start from the prior month-end state:

* closing NAV from the prior month
* cash balance
* remaining positions
* current investor-class balances
* deferred redemption backlog
* prior-month LMT assessment outcome
* behavioural feedback multipliers for the new month

The monthly view should separately show the position after market stress, after
cashflows, after LMT assessment, and at month end.

## Contractual Cashflows

Contractual cashflows are applied before liquidation.

Examples include:

* reverse repo maturities
* future fixed-income principal maturities
* coupon payments, if later supported

For the first version:

* reverse repo maturity proceeds become cash
* future fixed-income maturities become cash when fixed income enters the active
  sample scope
* coupon payments become cash only when an explicit payment schedule is
  supported
* automatic reinvestment is out of scope
* matured proceeds may fund redemptions subject to the minimum cash-buffer rule

## Investor Redemption Demand

Monthly redemption demand is generated by investor class.

The base should be the current investor-class balance, not the original opening
balance. This means that if an investor class redeems heavily in one month, its
future redemption demand is generated from its reduced remaining balance.

Conceptually:

```text
new_redemption_amount_by_class =
    current_investor_class_balance
    × monthly_redemption_rate
    × behavioural_feedback_multiplier
```

The existing methodology already distinguishes investor-class redemption
profiles. The path methodology extends that concept through time by carrying
forward investor-class balances.

## Deferred Backlog

Unpaid or deferred redemption demand is carried forward as backlog.

Backlog should be tracked by investor class and originating month.

Each month, eligible backlog is added to new redemption demand to form effective
redemption demand.

Backlog does not disappear silently. It is either:

* paid
* deferred again
* blocked by suspension or another explicit LMT state

The backlog record should allow reviewers to trace each deferred amount from
the original month of deferral through eventual payment or continued deferral.

## Threshold Assessment And Simulated LMT Effects

The monthly path uses simulated LMT assessment, not fund-manager discretion.

The model assesses:

* swing-pricing activation
* redemption-gate activation
* liquidity-buffer breach
* suspension treatment, consistent with the current project methodology

Results should be labelled as simulated LMT effects or activation assessment.

Diagnostic outputs support calibration review. They do not decide whether a fund
manager should activate an LMT.

## Swing Pricing

Swing pricing is assessed on effective redemption demand.

Swing recovery applies only to paid redemptions.

Deferred amounts do not generate swing recovery until they are paid in a later
month.

Applied recovery cannot exceed realised liquidation cost for the month.

The applied swing factor remains capped by the configured maximum swing factor.

## Redemption Gates

Gate assessment is based on effective redemption demand.

If the gate applies, only the paid portion is liquidated.

The unpaid portion becomes deferred backlog.

The gate result should preserve the split between paid redemption and deferred
redemption by investor class where practical, so later months can carry forward
the deferred obligation.

## Suspension

The first version should reuse the existing project suspension methodology.

Do not introduce a new suspension methodology without a separate issue.

Suspension treatment may evolve in a later version.

## Behavioural Feedback

Behavioural feedback must be configurable.

Do not hardcode assumptions such as:

* gate increases redemptions
* swing decreases redemptions

Use a configurable relationship:

```text
LMT or stress outcome + investor class = next-month redemption multiplier
```

A multiplier above 1 increases next-month demand. A multiplier equal to 1 leaves
demand unchanged. Calming effects represented by multipliers below 1 are out of
scope.

Behavioural feedback multipliers should be explicit inputs or parameters.
Behavioural assumptions should not be implied or unstated.

## Market Contagion

Market contagion is not implemented in the 12-month redemption path.

Market contagion is separate from behavioural feedback. Behavioural feedback
affects future investor redemption demand. Market contagion would affect
asset-side market or liquidity conditions under a separately approved
methodology.

This methodology does not decide whether future market contagion should affect
prices, spreads, transaction costs, market impact, haircuts, participation
rates, liquidation capacity, settlement, or liquidity cost.

## Path-Level Behavioural Feedback Assumptions

The first month starts with neutral behavioural feedback multipliers of 1.0.

Behavioural feedback applies to the next month only. After applying for one
month, the multiplier returns to neutral (1.0) unless another LMT outcome occurs.

When multiple LMT outcomes occur in a month, the priority order determines which
outcome generates behavioural feedback for the following month:

1. suspension
2. redemption gate
3. liquidity-buffer breach
4. swing pricing
5. none

Only the highest-priority outcome applies behavioural feedback; lower-priority
outcomes are not multiplied again.

Behavioural feedback can vary by investor class. The same LMT or stress outcome
may trigger different redemption multipliers for different investor classes in
the following month.

Deferred backlog is not multiplied again by behavioural feedback. Backlog
carries forward at its original amount and joins new monthly redemption demand.
The current month’s behavioural feedback multiplier applies only to that new
demand.

Suspension treatment follows the existing project methodology. No new suspension
methodology is implemented in this version.

## Liquidation

Liquidation happens after paid redemption is determined.

Liquidation should be calculated using the paid redemption amount, not gross
effective demand if part of the demand is gated, suspended, or deferred.

The current configurable liquidation strategies remain applicable:

* `most_liquid_first`
* `pro_rata`
* `hybrid`
* `custom_weights`

Liquidation must respect:

* available cash after contractual cashflows
* minimum buffer
* asset eligibility
* settlement timing
* maturity timing
* stressed liquidity capacity
* stressed haircut rate
* selected liquidation strategy assumptions

Asset sales reduce carried-forward position values. Cash balances should reflect
contractual cashflows, cash used, liquidation proceeds, redemption payments, and
the approved treatment of swing recovery.

## Liquidation Capacity Across Months

The methodology should explicitly document how liquidation capacity evolves.

Option A:

* liquidation capacity is recalculated every month

Option B:

* unused or used liquidation capacity is tracked across months

For the first version, use Option A.

This means each month’s capacity is calculated from the current remaining
positions and liquidity stress assumptions. Prior sales affect future capacity
through smaller remaining positions, not through a separate adjustment for
prior-month trading activity.

Option B may be considered in a later version if persistent market-liquidity
stress needs to constrain future trading capacity beyond the reduced position
balance.

## Month-End State

At month end, the methodology determines:

* cash
* remaining positions
* investor-class balances
* NAV
* liquid resources
* deferred backlog
* LMT assessment outcome
* behavioural feedback multipliers for the next month

The month-end position becomes the opening position for the next simulation
month.

## Maturity And Reinvestment Policy

For the first version:

* reverse repo maturities become cash
* fixed-income principal maturities become cash when fixed income enters the
  active sample scope
* coupon payments become cash only where coupon schedule data exists
* matured proceeds may fund redemptions before liquidation
* automatic reinvestment is out of scope

This avoids introducing synthetic replacement instruments before fixed-income
methodology is approved.

## Scenario Assumptions And Parameters

The path methodology should preserve the current calibration approach as much as
possible.

Prefer extending existing scenario definitions and LMT parameter sets over
adding many new configuration files.

Path assumptions should remain explicit and validated before they become
methodology inputs. Required methodology assumptions should not be left unstated
in the methodology.

## Relationship To The Single-Period Methodology

The current dashboard workflow performs one-period calibration across selected
market conditions.

The planned redemption-path page will simulate one selected scenario through
time.

## Out Of Scope

For the first 12-month redemption-path version, exclude:

* reverse stress testing
* full Monte Carlo distribution output
* intra-month liquidation scheduling
* automatic reinvestment of maturities
* synthetic replacement bonds
* amortising bonds and partial maturities
* coupon accrual without explicit payment schedule
* market contagion
* calming effects represented by behavioural feedback multipliers below 1
* hardcoded behavioural economics
* new suspension methodology
* live market data
* production fund-document rules
