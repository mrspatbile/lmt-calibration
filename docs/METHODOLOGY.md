# Methodology

## Purpose

This document defines the simplified Liquidity Management Tools calibration methodology used in this project.

The project supports structured liquidity stress testing, configurable liquidation strategies, and LMT threshold analysis. It does not replicate a production ManCo risk framework, provide regulatory advice, or make fund-manager activation decisions.

## Core question

The application should answer:

```text
Given a fund liquidity profile, investor redemption behaviour, asset market stress,
and liquidity stress assumptions, what LMT thresholds are coherent for swing pricing,
redemption gates, and liquidity buffers under the tested stress case, and what
diagnostic warnings explain the result?
```

## Current methodology scope

The current methodology is a single-period liquidity stress workflow. It includes:

* investor-class redemption stress
* direct asset market shocks
* per-asset-group liquidity stress assumptions
* configurable liquidation strategies
* liquidation capacity, settlement, and maturity constraints
* realised haircut and dilution cost
* shortfall and remaining-liquidity analysis
* swing-pricing, redemption-gate, and liquidity-buffer threshold diagnostics
* structured audit record models and JSON output support

## Out of current scope

The current methodology does not include:

* multi-period or 12-month redemption paths
* stochastic redemption simulation
* intra-period liquidation schedules
* deferred-redemption backlogs across periods
* reverse stress testing
* market contagion beyond the one-month liquidity-cost and net-proceeds
  adjustment defined for the 12-month redemption path
* nonlinear price-impact or market-volume models
* live market data
* production legal, tax, or regulatory decision rules
* database or cloud persistence

## Scenario design

A scenario combines one fund snapshot with a redemption scenario, market stress, liquidity stress, liquidation strategy, and LMT parameter set.

The single-period design represents one redemption event under selected market and liquidity conditions. Market valuation stress is applied before the redemption-rate diagnostics. Liquidation then determines whether redemption requests can be met, the realised cost of asset sales, and the remaining liquidity position.

## Stress dimensions

The methodology separates three stress dimensions:

* liability-side redemption stress
* asset-side market valuation stress
* asset-side liquidity and execution stress

### Liability-side redemption stress

Redemption pressure is assembled from investor-class assumptions:

```text
redemption_amount_by_class =
    fund_snapshot_NAV
    × nav_share_rate
    × stress_redemption_rate
    × redemption_multiplier

gross_redemption_amount = sum(redemption_amount_by_class)
```

The supported investor classes are retail, institutional, platform, fund of funds, and seed capital.

The redemption rate used for swing-pricing and gate threshold diagnostics is:

```text
redemption_rate =
    gross_redemption_amount
    / current_pre_LMT_NAV
```

`current_pre_LMT_NAV` reflects the market valuation shock but does not include redemption payment, liquidation cost, or LMT effects.

### Asset-side market valuation stress

The methodology applies a direct market shock to listed equities and listed ETFs:

```text
stressed_market_value = market_value × (1 + market_shock_rate)
```

Cash and reverse repos are not market-stressed. Repo financing exposures are treated as liquidity obligations rather than ordinary liquid assets.

Beta-based revaluation is not part of the active methodology.

### Asset-side liquidity and execution stress

Liquidity stress is specified by asset group. It controls:

* participation rate, which reduces liquidation capacity
* liquidity haircut, which increases stressed haircut treatment
* bid-ask spread, transaction cost, and market impact, which provide execution-cost assumptions
* settlement days
* reverse-repo maturity days
* the scenario stress horizon

Current stressed liquidation capacity is:

```text
stressed_liquidity_capacity_rate =
    base_liquidity_capacity_rate × participation_rate

available_liquidation_amount =
    stressed_market_value × stressed_liquidity_capacity_rate
```

Current stressed haircut treatment is:

```text
stressed_haircut_rate =
    min(base_haircut_rate + liquidity_haircut_rate, 1)
```

Listed assets are eligible when their settlement period is within the stress horizon. A reverse repo is eligible when maturity days plus settlement days are within the stress horizon. Cash remains immediately available, subject to the minimum cash-buffer rule.

## Liquidation strategy

Liquidation is configurable and does not assume that the fund always depletes its most liquid assets first.

The implemented strategies are:

* `most_liquid_first`: uses cash above the minimum buffer, then the most liquid eligible assets
* `pro_rata`: sells eligible non-cash assets proportionally
* `hybrid`: uses a configured share of cash above the minimum buffer, then sells eligible assets proportionally
* `custom_weights`: allocates liquidation needs by configured asset-group weights

Each strategy respects available cash, the minimum cash buffer, stressed capacity, stressed haircuts, settlement, reverse-repo maturity, and the stress horizon.

### Minimum cash buffer

`minimum_buffer_rate` from the selected LMT parameter set is the source of the minimum cash-buffer requirement:

```text
minimum_cash_buffer = fund_snapshot_NAV × minimum_buffer_rate
```

Cash below this amount is not available to the implemented strategies.

### Cash raised and shortfall

For each liquidated asset:

```text
gross_sale_amount =
    min(strategy_allocated_sale_amount, available_liquidation_amount)

post_haircut_cash_raised =
    gross_sale_amount × (1 - stressed_haircut_rate)

realised_haircut_cost =
    gross_sale_amount - post_haircut_cash_raised
```

The scenario shortfall is:

```text
shortfall = max(
    gross_redemption_amount
    - cash_used
    - total_post_haircut_cash_raised,
    0,
)
```

Shortfall is a liquidation result. It is not part of the current gate activation threshold comparison.

## Realised cost and estimated execution-cost context

Realised liquidation cost is strategy-dependent. It is the total haircut cost produced by the selected asset sales and is also reported as dilution amount:

```text
dilution_amount = total_realised_haircut_cost
dilution_rate = dilution_amount / fund_snapshot_NAV
```

The matrix uses realised haircut cost when reporting asset-side liquidity impact and fund state before and after LMT effects.

Estimated execution cost is separate calibration context. For each asset group, bid-ask spread, transaction cost, and market impact are combined and then weighted by the stressed market value represented by that group:

```text
asset_group_execution_cost_rate =
    bid_ask_spread_rate
    + transaction_cost_rate
    + market_impact_rate

estimated_execution_cost_rate =
    sum(asset_group_weight × asset_group_execution_cost_rate)

estimated_execution_cost_amount =
    gross_redemption_amount × estimated_execution_cost_rate
```

This estimate supports swing-factor context and calibration review. It is not the realised strategy outcome.

The 12-month redemption path has one narrow exception: in the month immediately
after the selected market stress, a market-contagion multiplier above its neutral
value of 1.0 makes the incremental execution cost above the base estimate a
realised cost of asset sales. That increment reduces net proceeds, can require
higher gross sales, and reduces the path NAV. The single-period scenario matrix
continues to treat estimated execution cost as calibration context only.

## NAV bases

The single-period methodology uses explicit NAV bases for different purposes:

* `initial_snapshot_nav` is the validated fund NAV before the market shock. Gross redemption amount, minimum cash buffer, and liquidation dilution rate use this basis.
* `current_pre_lmt_nav` is NAV after market valuation stress and before redemption payment, liquidation cost, or LMT effects. Swing and gate activation rates use this basis.
* `nav_after_redemption_before_lmt` is current pre-LMT NAV after gross redemption demand and realised liquidation cost, before simulated LMT effects.
* `current_post_lmt_nav` is the scenario NAV after redemption payment, realised liquidation cost, redemption deferral, and applied swing recovery.

The opening-NAV basis keeps redemption amounts, minimum cash requirements, and dilution rates comparable across market-condition columns. The current pre-LMT basis makes activation assessments responsive to the market-shocked fund value.

## Remaining liquidity buffer

Remaining liquid resources include remaining cash and the post-haircut capacity of eligible assets after sales:

```text
remaining_liquid_resources =
    remaining_cash
    + remaining_post_haircut_eligible_capacity

remaining_liquid_buffer_rate_before_LMT =
    remaining_liquid_resources / NAV_after_redemption_before_LMT

remaining_liquid_buffer_rate_after_LMT =
    remaining_liquid_resources / current_post_LMT_NAV
```

The displayed ratio uses the NAV for the corresponding post-redemption fund state. The remaining-cash amount reflects the configured minimum cash-buffer rule.

## LMT threshold diagnostics

Threshold results are diagnostic scenario states. They support calibration review and do not decide whether a fund manager should activate an LMT.

### Swing-pricing threshold diagnostic

```text
swing_threshold_diagnostic =
    redemption_rate >= swing_threshold_rate
```

The diagnostic reports the observed redemption rate and selected reference threshold. Estimated execution cost and realised haircut cost provide supporting calibration context.

When simulated swing activation occurs, recovery is calculated once:

```text
applied_swing_factor =
    min(estimated_execution_cost_rate, maximum_swing_factor_rate)

theoretical_recovery =
    gross_redemption_amount × applied_swing_factor

applied_cost_recovery =
    min(theoretical_recovery, realised_liquidation_cost)
```

Applied recovery reduces dilution to remaining investors but cannot exceed the realised strategy-dependent liquidation cost.

### Redemption-gate threshold diagnostic

```text
gate_threshold_diagnostic =
    redemption_rate >= gate_threshold_rate
```

When the simulated gate activation condition is met, the current model calculates paid and deferred redemption amounts for that single period. It does not model a deferred-redemption backlog through time.

Shortfall remains a separate liquidation result and does not independently satisfy the gate activation condition.

### Liquidity-buffer threshold diagnostic

```text
buffer_threshold_diagnostic =
    remaining_liquid_buffer_rate < minimum_buffer_rate
```

The diagnostic reports the remaining liquidity rate and whether the minimum cash buffer was preserved.

## Calibration approach

The application allows the user to select or adjust:

* fund
* redemption scenario
* liquidation strategy
* swing-pricing threshold
* redemption-gate threshold
* internal liquidity-buffer threshold

The dashboard compares fixed market-condition columns using the same selected fund, redemption scenario, liquidation strategy, and LMT thresholds. Liquidity stress comes from the selected scenario configuration rather than a separate dashboard control.

The resulting matrix compares market-stressed NAV, redemption need, realised liquidation cost, fund state before and after LMT effects, and remaining liquidity.

## Audit trail

Structured audit domain models and a JSON audit writer are implemented. They support:

* run metadata and output paths
* validated input summaries
* scenario, strategy, and threshold parameter summaries
* liquidation amounts, costs, shortfall, and remaining liquidity
* asset-group allocations
* optional threshold-assessment diagnostics

The writer creates `<run_id>_audit.json` in a selected output directory. Automatic construction and writing of an audit record for every application scenario run is not currently integrated.

## Out-of-scope methodology extensions

Potential extensions outside the current methodology include:

* multi-period redemption paths and deferred-redemption backlogs
* stochastic redemption behaviour with explicit deterministic random seeds
* intra-period liquidation schedules
* reverse stress testing
* nonlinear or volume-based market impact
* market contagion beyond the redemption path's one-month liquidity-cost and
  net-proceeds adjustment
* simultaneous liquidation-strategy comparison
* live market-data calibration

## Methodology limits

The model uses synthetic sample data and simplified rate-based stress assumptions. It does not model full trading-volume curves, order-book depth, legal fund-document constraints, tax effects, or production management decisions.

The active liquidation workflow is limited to cash, listed equities, listed ETFs, reverse repos, and repo financing exposures. Additional modelled asset categories do not imply active methodology support.
