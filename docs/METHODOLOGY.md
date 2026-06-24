# Methodology

## Purpose

This document defines the simplified Liquidity Management Tools calibration methodology used in this project.

The project is a methodology prototype for structured liquidity stress testing, configurable liquidation strategies, and LMT warning analysis. It does not replicate a production ManCo risk framework and does not provide regulatory advice.

## Core question

The application should answer:

```text
Given a fund liquidity profile, investor redemption behaviour, market stress, and liquidity stress assumptions, which LMT warnings or triggers activate and why?
```

## Version 1 scope

Version 1 uses a one-period scenario.

It includes:

* configurable liquidation strategy
* investor-class redemption stress
* asset market stress
* asset liquidity stress
* cash, listed equities, listed ETFs, reverse repos, and repo financing exposures
* swing-pricing warning
* redemption-gate warning
* liquidity-buffer warning
* audit trail for scenario runs

## Version 1 exclusions

Version 1 does not include:

* 12-month redemption paths
* stochastic redemption simulation
* intra-month liquidation schedules
* full price-impact modelling
* live market data
* database persistence
* Docker
* Kubernetes
* cloud deployment

## Stress dimensions

The methodology uses three stress dimensions:

* liability-side stress
* asset market stress
* asset liquidity stress

## Liability-side stress

Liability-side stress models investor redemptions.

The Version 1 model uses investor classes:

* retail
* institutional
* platform
* fund_of_funds
* seed_capital

Each class has a NAV share and stressed redemption behaviour.

Total redemption pressure is calculated from investor-class behaviour.

```text
redemption_amount_by_class = NAV × nav_share_rate × stress_redemption_rate × redemption_multiplier

total_redemption_amount = sum(redemption_amount_by_class)

total_redemption_rate = total_redemption_amount / NAV
```

## Asset market stress

Asset market stress models price pressure before or during the redemption event.

For listed equities and listed ETFs, market stress may use beta:

```text
stressed_market_value = market_value × (1 + beta × benchmark_shock_rate)
```

If beta is not provided, a direct asset-class shock may be used.

Cash is not market-stressed.

Reverse repos are not market-stressed in Version 1 unless explicitly configured later.

Repo financing exposures are treated as liquidity obligations, not ordinary assets.

## Asset liquidity stress

Asset liquidity stress models reduced ability to sell assets and higher sale costs.

The model uses:

* haircut rate
* liquidity capacity rate
* settlement days
* maturity days for reverse repos
* repo liquidity obligations where applicable

Example:

```text
stressed_haircut_rate = base_haircut_rate × liquidity_stress_multiplier
```

The stressed haircut rate must be capped at 1.

Example:

```text
stressed_liquidity_capacity_rate = base_liquidity_capacity_rate / liquidity_stress_multiplier
```

The stressed liquidity capacity rate must remain between 0 and 1.

## Liquidation strategy

Liquidation is configurable. The model must not assume that a fund automatically depletes the most liquid assets first.

Version 1 supports:

* `most_liquid_first`
* `pro_rata`
* `hybrid`
* `custom_weights`

The structured output may be called a liquidation result or waterfall result, but the methodology remains strategy-based, not fixed waterfall-based.

## Minimum cash buffer

Version 1 uses `minimum_buffer_rate` from LMT parameters as the only source for the minimum cash buffer.

All liquidation strategies must preserve the configured minimum cash buffer by default.

The model must not automatically drain all cash or all liquid assets.

Cash below the configured minimum buffer must not be used unless a later explicit override is designed.

## Strategy definitions

### most_liquid_first

`most_liquid_first` uses only cash above the configured minimum buffer first, then liquidates the most liquid eligible non-cash assets.

It must not use cash below the configured minimum buffer.

### pro_rata

`pro_rata` preserves the configured minimum cash buffer, then sells eligible non-cash assets proportionally to preserve the portfolio liquidity profile.

Cash is not part of the proportional sale allocation.

Cash above the minimum buffer may be available only when the strategy configuration allows it.

### hybrid

`hybrid` uses part of available cash above the configured minimum buffer, then sells eligible non-cash assets proportionally.

For `hybrid`, `cash_buffer_use_rate` means the percentage of available cash above the configured minimum buffer that may be used before proportional asset sales.

### custom_weights

`custom_weights` allocates liquidation needs according to user-defined weights by asset group.

Custom weights must be stored in JSON strategy configuration, not in redemption scenario CSV files.

## Strategy constraints

Each strategy must respect:

* available cash
* minimum cash buffer
* reverse repo maturity
* settlement days
* stressed liquidity capacity
* stressed haircut rate
* asset eligibility under the stress horizon

Eligible assets are assets that can provide usable liquidity within the scenario stress horizon after maturity and settlement constraints.

Repo financing exposures are treated separately as liquidity obligations.

## Scenario to strategy mapping

Each redemption scenario references exactly one `liquidation_strategy_id` in Version 1.

Nested liquidation strategy configuration and custom strategy weights belong in `data/sample/liquidation_strategies.json`, not in `redemption_scenarios.csv`.

Future scenario comparison runs can be handled by a separate run configuration or scenario pack.

## Cash raised

For each liquidated asset:

```text
available_liquidation_amount = stressed_market_value × stressed_liquidity_capacity_rate

gross_sale_amount = min(strategy_allocated_sale_amount, available_liquidation_amount)

post_haircut_cash_raised = gross_sale_amount × (1 - stressed_haircut_rate)

dilution_cost = gross_sale_amount - post_haircut_cash_raised
```

Strategy allocation must be capped by available liquidity and by the remaining redemption need.

## Shortfall

```text
shortfall = redemption_amount - cash_used - post_haircut_cash_raised
```

Final reported shortfall cannot be negative.

If more cash is raised than needed, liquidation should be capped or excess cash should be reported separately.

## Dilution

```text
dilution_rate = total_dilution_cost / NAV
```

Dilution is used to assess whether swing-pricing warnings should activate.

## Remaining liquidity buffer

The remaining liquidity buffer compares liquid resources after the redemption event with NAV.

Version 1 may define liquid resources as:

```text
remaining_liquid_resources = remaining_cash + remaining_assets_available_within_stress_horizon

remaining_liquid_buffer_rate = remaining_liquid_resources / NAV
```

The remaining cash amount must reflect the configured minimum cash buffer rule.

## LMT warnings

Version 1 reports warnings. It does not decide whether a fund manager should activate an LMT.

### Swing-pricing warning

A swing-pricing warning activates when estimated dilution exceeds the configured threshold.

```text
dilution_rate > swing_threshold_rate
```

The warning should report:

* observed dilution rate
* configured threshold
* estimated dilution cost
* liquidation strategy used
* reason for activation

### Redemption-gate warning

A gate warning may activate when redemption pressure exceeds the configured gate threshold or when the liquidation strategy produces a shortfall.

```text
total_redemption_rate > gate_threshold_rate
```

or:

```text
shortfall > 0
```

The warning should report:

* total redemption rate
* configured gate threshold
* shortfall, if any
* main driver of redemption pressure

### Liquidity-buffer warning

A liquidity-buffer warning activates when remaining liquid resources fall below the configured minimum buffer.

```text
remaining_liquid_buffer_rate < minimum_buffer_rate
```

The warning should report:

* remaining buffer
* configured minimum
* assets consumed by the liquidation strategy
* whether the configured minimum cash buffer was preserved

## Calibration approach

Version 1 calibration is scenario-based.

The user changes:

* investor-class redemption assumptions
* market shock assumptions
* liquidity stress assumptions
* liquidation strategy
* swing-pricing threshold
* gate threshold
* minimum liquidity buffer

The app reports how the LMT warnings change.

## Audit trail

Each scenario run should produce a structured audit record.

The audit record should include:

* selected liquidation strategy
* strategy parameters
* cash buffer rule
* custom weights, if used
* whether the minimum cash buffer was preserved
* liquidation allocation by asset group
* input files
* scenario parameters
* LMT warnings and reasons
* output file paths

Audit records are saved as generated runtime outputs, not source files.

## Path-based redemption stress

Version 1 uses a one-period scenario.

Later versions should support a 12-month redemption path by investor class, including:

* monthly base redemption rates by investor class
* beta-distribution parameters for random redemption draws
* selected stress months
* stressed redemption rates by investor class during stress months
* cumulative redemption pressure
* monthly liquidity-management response
* LMT warning path through time

## Later methodology extensions

Later versions may include:

* stochastic redemptions by investor class
* selected stress months
* intra-month liquidation schedule
* price impact comparison across liquidation strategies
* strategy comparison view in Streamlit
* reverse stress testing for the redemption rate or market shock that first causes a warning
* historical or synthetic redemption-flow calibration by investor class

Historical calibration is not required for Version 1 because new funds may not have enough history.

## Methodology limits

The model is simplified.

Version 1 does not cover:

* corporate bonds
* derivatives
* private assets
* side pockets
* live market data
* tax effects
* full transaction cost models
* legal fund-document constraints
* 12-month redemption paths
* stochastic redemption simulation
* intra-month liquidation schedules
* full price-impact modelling

The project should state these limits clearly in README and methodology documentation.
