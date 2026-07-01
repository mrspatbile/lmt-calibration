# Redemption Path Methodology

## Purpose

This document defines the 12-month redemption-path methodology for the
Liquidity Management Tools Calibration application, implemented as **Page 2** of the dashboard.

The redemption-path analysis extends the single-period threshold calibration (Page 1: Market scenarios & notice-period liquidity) by simulating how investor redemptions, liquidity resources, LMT effects, deferred redemptions, and NAV evolve over twelve monthly periods.

The methodology is designed as a forward-looking liquidity stress view. It is not a direct repetition of the Page 1 single-period market-scenario analysis; instead, it explores path-dependent effects where earlier LMT applications can trigger behavioural feedback and change later redemption demand and threshold signals.

## Complementary relationship with Page 1

**Page 1: Market scenarios & notice-period liquidity** — Answers "Can we meet redemptions within our notice/settlement horizon?" using static market stress and fixed redemption-scenario assumptions. Threshold calibration is deterministic: one redemption scenario × one market condition = one outcome.

**Page 2: 12-month redemption path** — Answers "How does the fund evolve across months under sustained or phased stress?" Explores path dependency: earlier LMT use can increase next-month redemptions through behavioural feedback, change NAV through swing recovery, or defer redemptions through gates, all of which become inputs to later months.

A consistent threshold set should:
* Pass Page 1 diagnostics (adequate within notice-period horizon under stress)
* Manage Page 2 dynamics (backlog doesn't accumulate indefinitely, NAV doesn't collapse, final month shortfall is contained)

The path is not a series of twelve independent Page 1 scenarios. It carries forward the end-of-month position from each month, including NAV, cash, investor-class balances, and backlog. This sequential structure allows the analysis to capture compounding effects that a single-period view would miss.

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
Assess swing-pricing, gate, and liquidity-buffer signals
        ↓
Apply user-selected LMT governance assumptions
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

The base should be the current redeemable investor-class balance, not the
original opening balance. The redeemable balance excludes amounts already
requested and carried as deferred backlog. This prevents the same investor
capital from generating another redemption request while its earlier request is
still outstanding.

Conceptually:

```text
new_redemption_amount_by_class =
    current_redeemable_investor_class_balance
    × monthly_redemption_rate
    × behavioural_feedback_multiplier
```

At month end, all new requests leave the redeemable balance whether they are
paid or deferred. Paid requests leave the fund; unpaid requests remain tracked
separately as backlog. Therefore, for each investor class:

```text
closing_redeemable_balance =
    opening_redeemable_balance - new_redemption_amount
```

Because each monthly rate is capped at 1.0, new demand cannot exceed the
redeemable balance. Effective demand, comprising new demand plus existing
backlog, cannot exceed the remaining investor capital represented by those two
balances.

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

## Threshold Signals And Applied LMT Decisions

The monthly path separates calculated threshold signals from LMT applications.
Signals identify months where an LMT may be considered; they are not governance
decisions.

The model assesses:

* swing-pricing threshold signal
* redemption-gate threshold signal
* liquidity-buffer breach

The user separately selects assumed swing-pricing, gate, and suspension months.
A signal without a selected application has no effect on paid redemption,
backlog, liquidation, swing recovery, NAV, or liquid resources.

The signal-linked option, labelled `Apply LMTs in all signal months`, applies
swing pricing and gates whenever their respective threshold signal is present.
This reproduces the rule-based path treatment as an explicit scenario choice.
It never selects suspension.

Signal-linked application is path-dependent rather than a fixed calendar lookup.
An applied gate can change paid redemption and backlog, while applied swing
pricing and behavioural feedback can change NAV or next-month demand. Those
changes become inputs to later months and can create, remove, or shift subsequent
threshold signals. The option therefore resolves signals and applications
sequentially each month using the updated fund and investor position.

The matrix distinguishes these states using hollow circles for signals, filled
circles for applied swing pricing or gates, and diamonds for assumed suspension.

## Swing Pricing

The swing-pricing signal is assessed on effective redemption demand. Swing
recovery is calculated only when swing pricing is selected for the month or the
signal-linked option applies it.

Swing recovery applies only to paid redemptions.

Deferred amounts do not generate swing recovery until they are paid in a later
month.

Applied recovery cannot exceed realised liquidation cost for the month.

The applied swing factor remains capped by the configured maximum swing factor.

## Redemption Gates

The gate signal is based on effective redemption demand. Payment restriction and
deferral occur only when the gate is selected for the month or the signal-linked
option applies it.

If the gate applies, only the paid portion is liquidated.

The unpaid portion becomes deferred backlog.

The gate result should preserve the split between paid redemption and deferred
redemption by investor class where practical, so later months can carry forward
the deferred obligation.

## Suspension

Suspension is a scenario assumption supplied explicitly by the user. The model
does not decide, recommend, or trigger suspension. Liquidity shortfall, a buffer
breach, repeated gate activation, backlog, market stress, and other calculated
results cannot activate suspension.

For each user-selected suspension month:

* paid redemption is zero
* new effective redemption demand and existing backlog remain deferred
* no redemption-funding liquidation takes place
* no swing-pricing recovery is applied because no redemption is paid
* suspension is the highest-priority monthly LMT outcome

Existing backlog keeps its original investor class and origin month. New demand
is added as backlog for the suspension month. Investor capital already represented
by a redemption request is not requested again in later months.

Threshold diagnostics and risk or escalation indicators remain separate from the
user-selected suspension status. They may identify shortfall, persistent backlog,
buffer pressure, extreme demand, or repeated simulated LMT activation, but they
must not be described as suspension decisions.

Suspension is shown in the activation timeline only for explicitly selected
months and uses a distinct marker from swing pricing and redemption gates.
Suspension-related behavioural feedback is out of scope: a suspension month does
not create an additional redemption-demand multiplier unless a separately
approved behavioural assumption is introduced.

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

Market contagion is separate from behavioural feedback. Behavioural feedback
affects future investor redemption demand. The implemented market-contagion
boundary affects the estimated liquidity-cost rate used by the monthly
activation assessment and the incremental realised execution cost of asset
sales in the same month.

Market stress remains a one-time valuation shock. When the market-contagion
multiplier is above its neutral value of 1.0, it applies only in the month
immediately following the selected market-stress month:

```text
adjusted_estimated_liquidity_cost_rate =
    base_estimated_liquidity_cost_rate
    × market_contagion_liquidity_cost_multiplier
```

A multiplier of 1.0 is neutral. A multiplier above 1.0 increases the estimated
liquidity-cost rate. If the selected market-stress month is month 12, there is
no following month inside the fixed path and no market-contagion adjustment is
applied.

For each asset group, only the cost increment above the base execution-cost rate
is realised through liquidation:

```text
incremental_realised_execution_cost_rate =
    base_execution_cost_rate
    × (market_contagion_liquidity_cost_multiplier - 1)

net_liquidation_proceeds =
    gross_sale_amount
    × (1 - stressed_haircut_rate - incremental_realised_execution_cost_rate)
```

Lower net proceeds require higher gross asset sales to fund the same paid
redemption. The incremental realised execution cost reduces NAV and is included
in total realised liquidity cost and dilution.

This adjustment does not change the redemption demand, market valuation shock,
haircut assumption, participation rate, liquidation-capacity limit, or
settlement assumption. Broader market-contagion effects require a separately
approved methodology.

## Path-Level Behavioural Feedback Assumptions

The first month starts with neutral behavioural feedback multipliers of 1.0.

Behavioural feedback applies to the next month only. After applying for one
month, the multiplier returns to neutral (1.0) unless another LMT outcome occurs.
Each subsequent LMT activation creates its own next-month feedback effect. If
LMTs are activated in several periods, behavioural feedback therefore continues
after each activation rather than being limited to the first occurrence.

When multiple applied LMT outcomes occur in a month, the priority order determines
which outcome generates behavioural feedback for the following month:

1. user-selected suspension
2. applied redemption gate
3. applied swing pricing
4. none

Only the highest-priority outcome applies behavioural feedback; lower-priority
outcomes are not multiplied again. Threshold signals and liquidity-buffer
breaches do not create behavioural feedback unless an LMT is applied.

Behavioural feedback can vary by investor class. The same LMT or stress outcome
may trigger different redemption multipliers for different investor classes in
the following month.

Deferred backlog is not multiplied again by behavioural feedback. Backlog
carries forward at its original amount and joins new monthly redemption demand.
The current month’s behavioural feedback multiplier applies only to that new
demand.

User-selected suspension retains a neutral next-month behavioural multiplier.
The model does not infer investor reaction to suspension.

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

The path aggregates daily redemptions and liquidation activity into monthly
periods. Participation rates are daily market participation assumptions. Monthly
capacity therefore scales daily capacity by the available liquidation days:

```text
monthly_liquidation_capacity_rate = min(
    base_liquidity_capacity_rate
    × participation_rate
    × liquidation_days_per_month,
    1,
)
```

`liquidation_days_per_month` defaults to 20 and is configurable for a path run.
It is distinct from `days_per_month`, which controls the simplified calendar
period used for contractual maturity cashflows.

Capacity is recalculated each month from the current remaining positions. Prior
sales affect future capacity through smaller remaining positions, not through a
separate adjustment for prior-month trading activity. The one-period scenario
matrix continues to apply its existing stress-window capacity without monthly
scaling.

## Month-End State

At month end, the methodology determines:

* cash
* remaining positions
* investor-class balances
* NAV
* liquid resources
* deferred backlog
* LMT threshold signals and applied outcome
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

The one-month view is a rule-based impact diagnostic. Configured swing-pricing
and gate thresholds are applied mechanically when breached.

The 12-month path is a governance scenario simulation. Thresholds create signals,
while swing pricing, gates, and suspension affect the path only in user-selected
months. The signal-linked option can apply swing pricing and gates in every
signal month. Suspension remains explicitly selected.

## Out Of Scope

For the first 12-month redemption-path version, exclude:

* reverse stress testing
* full Monte Carlo distribution output
* intra-month liquidation scheduling
* automatic reinvestment of maturities
* synthetic replacement bonds
* amortising bonds and partial maturities
* coupon accrual without explicit payment schedule
* market contagion beyond the one-month liquidity-cost and net-proceeds adjustment
* calming effects represented by behavioural feedback multipliers below 1
* hardcoded behavioural economics
* automatic suspension triggers or recommendations
* governance or regulatory decision rules for suspension
* live market data
* production fund-document rules
