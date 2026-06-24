# Data Conventions

## Purpose

This document defines the data conventions for the Liquidity Management Tools Calibration project.

The goal is to keep units, naming, validation, and assumptions consistent across loaders, domain models, calculation engines, audit records, and Streamlit displays.

## Data and output folders

The project separates source data, validated data, sample data, and generated outputs.

```text
data/
  raw/
  cleaned/
  sample/

outputs/
  audit/
  reports/
```

## Folder rules

* `data/raw/` contains original input files that are not modified by the app.
* `data/cleaned/` contains validated or cleaned datasets created from raw inputs.
* `data/sample/` contains synthetic sample data committed to Git for examples and tests.
* `outputs/audit/` contains generated JSON audit records for scenario runs.
* `outputs/reports/` contains generated summaries, tables, charts, or exported reports.

## Numerical representation

### Rates and ratios

Store rates and ratios as `Decimal`.

Examples:

```text
Decimal("0.05") = 5%
Decimal("0.005") = 50 bps
Decimal("1.25") = 125%
```

Use `Decimal` for:

* redemption rates
* haircut rates
* market shock rates
* liquidity capacity rates
* NAV share rates
* cash buffer use rates
* swing-pricing thresholds
* gate thresholds
* buffer thresholds
* concentration factors
* liquidation strategy weights
* beta
* duration
* spread duration
* delta

### Basis points

Store basis points as `int` only when the source is naturally expressed in basis points.

Examples:

```text
50 = 50 bps
150 = 150 bps
```

Conversion:

```text
1 bps = 0.0001 as decimal = 0.01%
150 bps = 0.015 as decimal = 1.5%
```

### Monetary values

Use `Decimal` for monetary values in domain models.

Examples:

* NAV
* market value
* cash amount
* redemption amount
* liquidation amount
* dilution cost
* shortfall
* notional amount
* entry price
* strike price

### Dates

Use ISO 8601 dates:

```text
YYYY-MM-DD
```

Example:

```text
2026-06-30
```

## Naming conventions

Field names must make the unit clear where ambiguity is possible.

Use:

```text
market_value
nav
cash_amount
redemption_rate
redemption_amount
haircut_rate
market_shock_rate
liquidity_capacity_rate
swing_threshold_rate
gate_threshold_rate
minimum_buffer_rate
settlement_days
notice_days
spread_bps
cash_buffer_use_rate
liquidation_strategy_id
redemption_scenario_id
market_stress_id
liquidity_stress_id
scenario_id
parameter_set_id
lmt_parameter_set_id
```

Avoid unclear names such as:

```text
percentage
value
amount
rate
threshold
```

unless the context is obvious and documented.

## Input files

Version 1 sample data files:

```text
data/sample/funds.csv
data/sample/positions.csv
data/sample/investor_classes.csv
data/sample/redemption_scenarios.csv
data/sample/market_stresses.csv
data/sample/liquidity_stresses.csv
data/sample/scenario_definitions.csv
data/sample/lmt_parameters.csv
data/sample/liquidation_strategies.json
```

Use CSV for flat tabular inputs:

* funds
* positions
* investor classes
* redemption scenarios
* market stresses
* liquidity stresses
* scenario definitions
* LMT parameters

Use JSON for nested or structured configuration:

* liquidation strategy configuration
* custom strategy weights
* nested strategy rules
* later scenario packs where the structure is not naturally tabular

## Fund snapshot data

Expected fields:

```text
fund_id
as_of_date
fund_name
base_currency
nav
dealing_frequency
redemption_notice_days
redemption_settlement_days
```

Rules:

* `fund_id` must be unique per `as_of_date`.
* `nav` must be positive.
* `base_currency` must use ISO-style currency codes such as `EUR`, `USD`, or `GBP`.
* `redemption_notice_days` must be zero or positive.
* `redemption_settlement_days` must be zero or positive.

## Position data

Version 1 may start with a narrow operational universe, but the canonical position schema should support later market-risk extensions.

Supported instrument groups:

```text
cash
listed_equity
listed_etf
government_bond
corporate_bond
fx_forward
equity_future
interest_rate_future
equity_option
interest_rate_swap
reverse_repo
repo_financing
```

Expected fields:

```text
position_id
fund_id
as_of_date

asset_group
instrument_type
instrument_subtype

instrument_name
ticker
currency

market_value
notional_amount

risk_factor_id
underlying_position_id
underlying_risk_factor_id

beta
duration_years
spread_duration_years
delta

entry_price
strike_price
option_type
expiry_date

benchmark_ticker

base_haircut_rate
base_liquidity_capacity_rate

settlement_days
maturity_days
```

Rules:

* `position_id` must be unique per fund and date.
* `market_value` must be non-negative for assets.
* `notional_amount` must be non-negative when required.
* Repo financing exposures must be handled as liquidity obligations, not ordinary liquid assets.
* Cash must have zero haircut.
* Cash must have full immediate liquidity capacity.
* Reverse repo maturity treatment must be explicit.
* Listed equities and listed ETFs may have beta and benchmark fields.
* Missing beta is allowed only when the scenario does not use beta-based market stress.
* Positions may reference `risk_factor_id` for direct market-factor exposure.
* Derivatives may reference `underlying_position_id` when the underlying is already held in the portfolio.
* Derivatives may reference `underlying_risk_factor_id` when the underlying is an external risk factor.
* Do not duplicate full underlying definitions inside derivative positions when `underlying_position_id` is available.
* Derivative-specific fields are optional in the flat schema but conditionally required by `instrument_subtype`.

Conditional examples:

* `listed_equity` requires `market_value`, `risk_factor_id`, and `beta`.
* `listed_etf` requires `market_value`, `risk_factor_id`, and may use `beta`.
* `government_bond` requires `market_value`, `risk_factor_id`, and `duration_years`.
* `corporate_bond` requires `market_value`, `risk_factor_id`, `duration_years`, and `spread_duration_years`.
* `equity_future` requires `notional_amount`, `entry_price`, `delta`, and `underlying_risk_factor_id`.
* `interest_rate_future` requires `notional_amount`, `entry_price`, `delta`, and `underlying_risk_factor_id`.
* `equity_option` requires `notional_amount`, `strike_price`, `option_type`, `expiry_date`, `delta`, and either `underlying_position_id` or `underlying_risk_factor_id`.
* `fx_forward` requires `notional_amount`, `entry_price`, `expiry_date`, `delta`, and `underlying_risk_factor_id`.
* `interest_rate_swap` requires `notional_amount`, `underlying_risk_factor_id`, and either `duration_years` or another documented sensitivity measure.

## Investor class data

Version 1 investor classes:

```text
retail
institutional
platform
fund_of_funds
seed_capital
```

Expected fields:

```text
fund_id
as_of_date
client_class
nav_share_rate
base_redemption_rate
stress_redemption_rate
concentration_factor
notice_days
settlement_days
```

Rules:

* `nav_share_rate` must be between 0 and 1.
* Investor-class NAV shares must sum to 1 per fund and date.
* Redemption rates must be between 0 and 1.
* `concentration_factor` must be between 0 and 1.
* `notice_days` must be zero or positive.
* `settlement_days` must be zero or positive.
* Platform or nominee investors should be treated as operationally concentrated but potentially diversified underneath.

## Redemption scenario data

A redemption scenario represents liability-side redemption assumptions only.

Redemption scenarios are reusable. They are not tied directly to `fund_id`, `as_of_date`, market stress, liquidity stress, liquidation strategy, or LMT parameter set.

Expected fields:

```text
redemption_scenario_id
version
name
description
redemption_multiplier
```

Rules:

* `redemption_scenario_id` must be unique.
* `version` is required.
* `name` is required and must use snake_case.
* `description` is required.
* `redemption_multiplier` must be positive.
* Redemption scenario data must not include `fund_id` or `as_of_date`.
* Redemption scenario data must not include `market_stress_id`, `liquidity_stress_id`, `liquidation_strategy_id`, or `lmt_parameter_set_id`.
* Investor-class redemption behaviour comes from investor class data and the selected redemption scenario multiplier.

## Market stress data

A market stress represents reusable asset-side market shock assumptions.

Expected fields:

```text
market_stress_id
version
name
description
market_shock_rate
```

Rules:

* `market_stress_id` must be unique.
* `version` is required.
* `name` is required and must use snake_case.
* `description` is required.
* `market_shock_rate` must be stored as a decimal value.
* `market_shock_rate` may be negative where it represents a price decline.
* Market stress data must not include `fund_id` or `as_of_date`.

Later market stress designs may support a set of risk-factor shocks instead of a single `market_shock_rate`.

Examples:

```text
euro_equity
us_equity
eur_rates_5y
eur_credit_spread_ig
eur_usd
```

## Liquidity stress data

A liquidity stress represents reusable asset-side liquidity shock assumptions.

Expected fields:

```text
liquidity_stress_id
version
name
description
liquidity_stress_multiplier
stress_horizon_days
```

Rules:

* `liquidity_stress_id` must be unique.
* `version` is required.
* `name` is required and must use snake_case.
* `description` is required.
* `liquidity_stress_multiplier` must be positive.
* `stress_horizon_days` must be positive.
* Liquidity stress data must not include `fund_id` or `as_of_date`.

## Scenario definition data

A scenario definition is the object that links a fund snapshot to the selected reusable assumptions.

Expected fields:

```text
scenario_id
fund_id
as_of_date
redemption_scenario_id
market_stress_id
liquidity_stress_id
liquidation_strategy_id
lmt_parameter_set_id
```

Rules:

* `scenario_id` must be unique.
* `fund_id` and `as_of_date` must reference an existing fund snapshot.
* Each scenario definition must reference exactly one `redemption_scenario_id`.
* Each scenario definition must reference exactly one `market_stress_id`.
* Each scenario definition must reference exactly one `liquidity_stress_id`.
* Each scenario definition must reference exactly one `liquidation_strategy_id`.
* Each scenario definition must reference exactly one `lmt_parameter_set_id`.
* Nested liquidation strategy settings must be stored in JSON configuration, not in `scenario_definitions.csv`.
* Custom liquidation weights must be stored in JSON configuration, not in `scenario_definitions.csv`.
* Scenario definition data must not include custom strategy configuration fields.

## Liquidation strategy data

Version 1 liquidation strategies:

```text
most_liquid_first
pro_rata
hybrid
custom_weights
```

Strategy configuration belongs in JSON, with `data/sample/liquidation_strategies.json` as the sample configuration file.

Rules:

* Strategy IDs must use snake_case and be unique.
* Strategy types must be one of the supported strategy names.
* `minimum_buffer_rate` from LMT parameters is the only Version 1 source for the minimum cash buffer.
* All liquidation strategies must preserve the configured minimum cash buffer by default.
* `most_liquid_first` may use only cash above the configured minimum buffer before liquidating the most liquid eligible non-cash assets.
* `cash_buffer_use_rate` means the percentage of available cash above the configured minimum buffer that may be used before proportional asset sales.
* `cash_buffer_use_rate` must be between 0 and 1 when used.
* `pro_rata` preserves the configured minimum cash buffer before allocating sales across eligible non-cash assets.
* `hybrid` uses part of available cash above the configured minimum buffer, then sells eligible non-cash assets proportionally.
* `custom_weights` must define weights by asset group.
* Asset groups must refer to supported groups such as `reverse_repo`, `listed_etf`, or `listed_equity`.
* Strategy weights must sum to 1 per scenario when `custom_weights` is used.
* Strategy configuration must not override asset eligibility under the stress horizon.
* All strategies must respect available cash, minimum cash buffer, reverse repo maturity, settlement days, stressed liquidity capacity, and stressed haircut rates.

## JSON configuration standard

All JSON configuration files must include:

* `schema_version`
* `config_type`
* `name`
* `description`

Rules:

* `schema_version` is required.
* `config_type` is required.
* `name` is required and must use snake_case.
* `description` is required.
* Strategy identifiers must be unique.
* Strategy identifiers must use snake_case.
* Percentages and rates must be stored as strings representing decimals, such as `"0.25"` for 25%.
* Raw percentage strings such as `"25%"` are not allowed.
* Unknown top-level fields should fail validation unless explicitly allowed.
* Unknown strategy fields should fail validation unless explicitly allowed.
* Required fields must not use silent defaults.
* JSON/config envelope `schema_version` is separate from object-level `version`.

Example:

```json
{
  "schema_version": "1.0",
  "config_type": "liquidation_strategies",
  "name": "sample_liquidation_strategies",
  "description": "Synthetic liquidation strategy configuration for sample LMT scenarios.",
  "strategies": [
    {
      "liquidation_strategy_id": "balanced_custom_weights",
      "version": "1.0",
      "name": "balanced_custom_weights",
      "description": "Preserves the minimum cash buffer and allocates sales across eligible ETFs and equities.",
      "strategy_type": "custom_weights",
      "cash_buffer_use_rate": "0.50",
      "preserve_minimum_buffer": true,
      "weights": {
        "listed_etf": "0.60",
        "listed_equity": "0.40"
      }
    }
  ]
}
```

## LMT parameter data

Expected fields:

```text
fund_id
as_of_date
parameter_set_id
swing_threshold_rate
max_swing_factor_rate
gate_threshold_rate
minimum_buffer_rate
```

Rules:

* `parameter_set_id` must be explicit and traceable.
* Threshold rates must be between 0 and 1.
* `max_swing_factor_rate` must be between 0 and 1.
* `minimum_buffer_rate` must be between 0 and 1.
* `minimum_buffer_rate` is the only Version 1 source for the minimum cash buffer.
* Required LMT parameters must not use hidden defaults.
* Parameter sets are linked to scenario runs through `lmt_parameter_set_id` in scenario definition data.

## Validation rules

All external data must be validated before domain object creation.

Validation must check:

* required columns
* date parsing
* duplicate identifiers
* positive NAV
* non-negative asset values
* valid currencies
* valid instrument groups
* valid instrument types
* valid instrument subtypes
* rates between 0 and 1 where applicable
* positive multipliers where applicable
* basis-point fields as integers
* investor-class NAV shares summing to 1
* position values reconciling to NAV within documented tolerance
* conditional position fields required by `instrument_subtype`
* derivative references to `underlying_position_id` or `underlying_risk_factor_id`
* scenario definition references matching existing fund snapshots
* scenario definition references exactly one redemption scenario
* scenario definition references exactly one market stress
* scenario definition references exactly one liquidity stress
* scenario definition references exactly one liquidation strategy
* scenario definition references exactly one LMT parameter set
* redemption scenarios do not contain fund/date or strategy fields
* market stresses do not contain fund/date fields
* liquidity stresses do not contain fund/date fields
* LMT parameters existing for each scenario definition
* liquidation strategies using supported strategy names
* custom liquidation weights summing to 1 per scenario where applicable
* liquidation strategy inputs respecting asset eligibility, maturity, settlement, stressed capacity, and stressed haircut constraints
* JSON configuration files containing required metadata
* JSON strategy IDs using unique snake_case values
* JSON rates stored as decimal strings, not raw percentage strings
* unknown JSON fields rejected unless explicitly allowed
* required configuration fields present without hidden defaults

## Future path-based data

Later versions may add 12-month redemption path inputs by investor class.

Expected concepts:

```text
scenario_id
month_index
client_class
monthly_base_redemption_rate
beta_alpha
beta_beta
is_stress_month
stress_redemption_rate
```

Rules:

* `month_index` should identify the month in the path.
* Monthly rates must be between 0 and 1.
* Beta-distribution parameters must be positive.
* Stress months must identify where stressed redemption rates replace or augment base monthly assumptions.
* Path results must support cumulative redemption pressure, monthly liquidity-management response, and LMT warning status through time.

## Future fixed-income rollover convention

Later multi-period versions may need an explicit maturity and reinvestment convention for fixed-income instruments.

In a multi-period liquidity simulation, fixed-income instruments may mature before the end of the simulation horizon. If no reinvestment rule is defined, the portfolio may lose duration, spread exposure, and interest-rate sensitivity for reasons unrelated to market movements or investor redemptions.

A future methodology may define a rollover rule where maturing principal is reinvested into a synthetic replacement exposure that preserves selected risk characteristics, such as:

* asset class
* currency
* issuer or rating bucket
* duration target
* spread duration
* liquidity profile
* haircut assumptions
* liquidation capacity assumptions

This rule is not part of Version 1.

## Synthetic data rules

Sample data must be synthetic but realistic.

Do not use placeholder names such as:

```text
Asset A
Entity B
Fund 1
Client X
```

Use realistic but clearly synthetic examples.

Example style:

```text
Lux Dynamic Allocation Fund
European Large-Cap Equity Sleeve
Global Equity ETF Position
EUR Overnight Reverse Repo
Institutional Mandate Investors
Platform Distribution Channel
```

## Documentation rules

Each module dealing with data should include:

* module-level docstring explaining unit conventions
* field-level descriptions for non-obvious fields
* examples where values could be misread
