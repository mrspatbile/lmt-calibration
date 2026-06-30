# Data Schema

## Purpose

This document describes the structure of the project input files.

It documents identifiers, required fields, formats, and relationships. It does not describe loader implementation, validation function internals, or calculation engines.

The files under [`data/sample/`](../data/sample/) are the canonical working examples for these schemas.

For workflow-level dataset relationships, see [DATA_REFERENCE.md](DATA_REFERENCE.md).

For shared units, naming, and validation principles, see [DATA_CONVENTIONS.md](DATA_CONVENTIONS.md).

## Schema Conventions

Decimal-like fields use decimal notation such as `0.05`, not raw percentage strings such as `5%`.

Dates use ISO format: `YYYY-MM-DD`

Blank cells represent missing values.

## CSV Files

### funds.csv

Purpose: fund snapshot data.

Primary identifier: `fund_id` + `as_of_date`.

Required fields:

| Field | Description | Format |
| --- | --- | --- |
| `fund_id` | Stable fund identifier | snake_case |
| `as_of_date` | Snapshot date | `YYYY-MM-DD` |
| `fund_name` | Human-readable fund name | text |
| `base_currency` | Fund base currency | 3-letter uppercase code |
| `nav` | Fund NAV | decimal string |
| `dealing_frequency` | Fund dealing frequency | text |
| `redemption_notice_days` | Redemption notice period | integer days |
| `redemption_settlement_days` | Redemption settlement timing | integer days |

Relationships:

* Referenced by `positions.csv`, `investor_classes.csv`, `lmt_parameters.csv`, and `scenario_definitions.csv`.


### positions.csv

Purpose: position-level holdings and financing exposures.

Primary identifier: `fund_id` + `as_of_date` + `position_id`.

Required common fields:

| Field | Description | Format |
| --- | --- | --- |
| `position_id` | Stable position identifier | snake_case |
| `fund_id` | Fund identifier | references `funds.csv` |
| `as_of_date` | Snapshot date | `YYYY-MM-DD` |
| `asset_group` | Position group | supported asset group |
| `instrument_type` | Instrument type label | supported instrument type |
| `instrument_subtype` | Instrument subtype driving conditional fields | supported subtype |
| `instrument_name` | Human-readable instrument name | text |
| `currency` | Position currency | 3-letter uppercase code |
| `base_haircut_rate` | Position-level liquidation haircut under normal market conditions. Used as the starting point for stressed liquidation assumptions. | decimal string, 0 to 1 |
| `base_liquidity_capacity_rate` | Share of the position that can be liquidated within the normal liquidation horizon before applying liquidity stress. | decimal string, 0 to 1 |
| `settlement_days` | Number of days between selling or unwinding the position and receiving usable cash. Used to decide whether the position is available within the scenario stress horizon. | integer days |

Optional or conditionally required fields:

| Field | Description | Format |
| --- | --- | --- |
| `ticker` | Market ticker or display identifier | text |
| `market_value` | Position market value | decimal string |
| `notional_amount` | Financing or derivative notional | decimal string |
| `risk_factor_id` | Direct market risk factor | snake_case |
| `underlying_position_id` | Referenced held underlying | position ID |
| `underlying_risk_factor_id` | Referenced external underlying factor | snake_case |
| `beta` | Equity beta or sensitivity | decimal string |
| `duration_years` | Interest-rate duration | decimal string |
| `spread_duration_years` | Credit spread duration | decimal string |
| `delta` | Derivative delta | decimal string |
| `entry_price` | Derivative entry price | decimal string |
| `strike_price` | Option strike price | decimal string |
| `option_type` | Option direction | `call` or `put` |
| `expiry_date` | Derivative expiry date | `YYYY-MM-DD` |
| `benchmark_ticker` | Benchmark or index identifier | text |
| `maturity_days` | Remaining maturity | integer days |

Current sample asset groups:

* `cash`
* `listed_equity`
* `listed_etf`
* `reverse_repo`
* `repo_financing`

Conditional requirements:

| Subtype | Required fields |
| --- | --- |
| `cash` | `market_value`; zero haircut; full capacity; zero settlement days |
| `listed_equity` | `market_value`, `risk_factor_id`, `beta` |
| `listed_etf` | `market_value`, `risk_factor_id` |
| `reverse_repo` | `market_value`, `maturity_days` |
| `repo_financing` | common fields; treated as a liquidity obligation |

Relationships:

* Belongs to one fund snapshot.
* Ordinary asset market values should reconcile to fund NAV. Repo financing is excluded from ordinary asset NAV reconciliation because it is a liquidity obligation.

#### Future position schema extensions

The current `positions.csv` schema supports the active sample universe. Later versions may extend it to support richer asset-side liquidity and market-risk modelling.

Potential future fields include:

##### Fixed income

- `issuer_name`
- `credit_rating`
- `issue_size`
- `coupon_rate`
- `maturity_date`
- `yield_to_maturity`

These fields may support liquidation-capacity estimates based on rating, issue size, sector, maturity, and spread sensitivity.

##### Listed equities and ETFs

- `average_daily_volume`
- `market_cap_bucket`
- `participation_rate`
- `bid_ask_spread_bps`

These fields may support liquidity-capacity or haircut calibration from trading activity and transaction-cost assumptions.

##### Derivatives

- `contract_multiplier`
- `initial_margin`
- `variation_margin`
- `margin_requirement`
- `gamma`
- `vega`

These fields may support futures, options, swaps, and margin-related liquidity effects.

##### Counterparty and financing exposures

- `counterparty_id`
- `counterparty_type`
- `counterparty_rating`
- `collateral_amount`
- `margin_call_frequency`

These fields may support later modelling of repo, OTC derivative, or dealer-related liquidity risks.

These fields are not required for the current workflow and should not be added to sample files until the corresponding methodology and calculation logic are designed.


### investor_classes.csv

Purpose: investor-class profiles for liability-side redemption stress.

Primary identifier: `fund_id` + `as_of_date` + `client_class`.

Required fields:

| Field | Description | Format |
| --- | --- | --- |
| `fund_id` | Fund identifier | references `funds.csv` |
| `as_of_date` | Snapshot date | `YYYY-MM-DD` |
| `client_class` | Investor class | supported class |
| `nav_share_rate` | Share of fund NAV | decimal string, 0 to 1 |
| `base_redemption_rate` | Base redemption assumption | decimal string, 0 to 1 |
| `stress_redemption_rate` | Stressed redemption assumption | decimal string, 0 to 1 |
| `concentration_factor` | Beta distribution concentration parameter for normal-period redemption sampling | positive decimal string |
| `notice_days` | Redemption notice period | integer days |
| `settlement_days` | Redemption settlement timing | integer days |

Supported investor classes:

* `retail`
* `institutional`
* `platform`
* `fund_of_funds`
* `seed_capital`

Relationships:

* Belongs to one fund snapshot.
* NAV shares should sum to 1 per `fund_id` and `as_of_date`.
* Used with the selected redemption scenario.

### redemption_scenarios.csv

Purpose: reusable liability-side redemption scenario assumptions.

Primary identifier: `redemption_scenario_id`.

Required fields:

| Field | Description | Format |
| --- | --- | --- |
| `redemption_scenario_id` | Scenario assumption identifier | snake_case |
| `version` | Assumption version | text |
| `name` | Display/config name | snake_case |
| `description` | Human-readable description | text |
| `redemption_multiplier` | Multiplier applied to investor-class stress assumptions | positive decimal string |

Relationships:

* Referenced by `scenario_definitions.csv`.
* Must not contain fund/date or liquidation strategy fields.

### market_stresses.csv

Purpose: reusable asset-side market shock assumptions.

Primary identifier: `market_stress_id`.

Required fields:

| Field | Description | Format |
| --- | --- | --- |
| `market_stress_id` | Market stress identifier | snake_case |
| `version` | Assumption version | text |
| `name` | Display/config name | snake_case |
| `description` | Human-readable description | text |
| `market_shock_rate` | Market shock rate | decimal string; may be negative |

Relationships:

* Referenced by `scenario_definitions.csv`.
* Must not contain fund/date fields.
* Market stress defines valuation shocks only. Liquidity and execution assumptions belong in `liquidity_stresses.json`.


### scenario_definitions.csv

Purpose: scenario assembly file linking one fund snapshot to reusable assumptions, a liquidation strategy, and an LMT parameter set.

Primary identifier: `scenario_id`.

Required fields:

| Field | Description | Format |
| --- | --- | --- |
| `scenario_id` | Scenario identifier | snake_case |
| `fund_id` | Fund identifier | references `funds.csv` |
| `as_of_date` | Snapshot date | `YYYY-MM-DD` |
| `redemption_scenario_id` | Selected redemption scenario | references `redemption_scenarios.csv` |
| `market_stress_id` | Selected market stress | references `market_stresses.csv` |
| `liquidity_stress_id` | Selected liquidity stress | references `liquidity_stresses.json` |
| `liquidation_strategy_id` | Selected liquidation strategy | references `liquidation_strategies.json` |
| `lmt_parameter_set_id` | Selected LMT parameter set | references `lmt_parameters.csv` |

Relationships:

* Each assumption reference must identify exactly one selected assumption.
* Custom strategy configuration and weights belong in `liquidation_strategies.json`, not in this file.

### lmt_parameters.csv

Purpose: explicit LMT threshold parameter sets for fund snapshots.

Primary identifier: `fund_id` + `as_of_date` + `parameter_set_id`.

Required fields:

| Field | Description | Format |
| --- | --- | --- |
| `fund_id` | Fund identifier | references `funds.csv` |
| `as_of_date` | Snapshot date | `YYYY-MM-DD` |
| `parameter_set_id` | Parameter set identifier | snake_case |
| `swing_threshold_rate` | Swing-pricing threshold | decimal string, 0 to 1 |
| `max_swing_factor_rate` | Maximum swing factor | decimal string, 0 to 1 |
| `gate_threshold_rate` | Redemption-gate threshold | decimal string, 0 to 1 |
| `minimum_buffer_rate` | Minimum liquidity buffer threshold | decimal string, 0 to 1 |

Relationships:

* Referenced by `scenario_definitions.csv` through `lmt_parameter_set_id`.
* `minimum_buffer_rate` is the only source for the configured minimum buffer in the current workflow.


## JSON Files

### liquidation_strategies.json

Purpose: reusable liquidation strategy configuration.

Primary identifier: `liquidation_strategy_id` inside each strategy object.

Top-level required fields:

| Field | Description | Format |
| --- | --- | --- |
| `schema_version` | JSON envelope schema version | text |
| `config_type` | Configuration type | `liquidation_strategies` |
| `name` | Configuration name | snake_case |
| `description` | Human-readable description | text |
| `strategies` | Strategy configuration list | array |

Strategy fields:

| Field | Description | Format |
| --- | --- | --- |
| `liquidation_strategy_id` | Strategy identifier | snake_case |
| `version` | Strategy version | text |
| `name` | Strategy name | snake_case |
| `description` | Human-readable strategy description | text |
| `strategy_type` | Strategy type | supported strategy |
| `preserve_minimum_buffer` | Whether strategy preserves configured buffer | boolean |
| `cash_buffer_use_rate` | Optional cash use rate above configured buffer | decimal string, 0 to 1 |
| `weights` | Custom weights by asset group | object of decimal strings summing to 1 |

Supported strategy types:

* `most_liquid_first`
* `pro_rata`
* `hybrid`
* `custom_weights`

Relationships:

* Referenced by `scenario_definitions.csv` through `liquidation_strategy_id`.
* Custom strategy weights must appear only in this JSON file.
* Strategy weights should reference supported asset groups.

<a id="liquidity-stresses-json"></a>

### liquidity_stresses.json

Purpose: reusable asset-side liquidity-capacity, haircut, and execution-cost assumptions by asset group.

Primary identifier: `liquidity_stress_id` inside each stress object.

Top-level required fields:

| Field | Description | Format |
| --- | --- | --- |
| `liquidity_stresses` | Array of liquidity stress objects | array |

Liquidity stress object fields:

| Field | Description | Format |
| --- | --- | --- |
| `liquidity_stress_id` | Liquidity stress identifier | snake_case |
| `version` | Assumption version | text |
| `name` | Display/config name | snake_case |
| `description` | Human-readable description | text |
| `stress_horizon_days` | Scenario liquidity horizon | positive integer days |
| `execution_assumptions_by_asset_group` | Liquidity and execution assumptions per asset group | object |

Execution assumptions by asset group:

Current sample asset groups:

* `cash`
* `listed_equity`
* `listed_etf`
* `reverse_repo`

Each asset group contains:

| Field | Description | Format |
| --- | --- | --- |
| `bid_ask_spread_rate` | Bid-ask spread cost assumption | JSON number or decimal-compatible value |
| `transaction_cost_rate` | Transaction cost assumption | JSON number or decimal-compatible value |
| `market_impact_rate` | Market impact cost assumption | JSON number or decimal-compatible value |
| `participation_rate` | Execution participation rate under this stress | JSON number or decimal-compatible value |
| `liquidity_haircut_rate` | Liquidity-driven haircut under this stress | JSON number or decimal-compatible value |

Relationships:

* Referenced by `scenario_definitions.csv` through `liquidity_stress_id`.
* Each asset group may have different execution-cost, participation, and haircut assumptions reflecting asset-group-specific liquidity constraints.
* Used with position `settlement_days` and `maturity_days` to determine asset eligibility under the stress horizon.
* Must not contain fund/date fields.

**Note:** Liquidity stress assumptions are the source for asset-group execution costs, liquidation capacity, and stressed haircut treatment. Market stress defines valuation shocks only.

### historical_market_stress_scenarios.json

Purpose: reusable historical market stress scenario library.

Primary identifier: scenario ID keys inside the `scenarios` object.

Top-level required fields:

| Field | Description | Format |
| --- | --- | --- |
| `schema_version` | JSON envelope schema version | `1.0` |
| `source` | Data source label | text |
| `scenario_type` | Scenario library type | `historical` |
| `notes` | Human-readable library notes | text |
| `scenarios` | Historical stress scenario objects keyed by scenario ID | object |

Scenario fields:

| Field | Description | Format |
| --- | --- | --- |
| `test_category` | Scenario category | text |
| `scenario_name` | Human-readable scenario name | text |
| `description` | Human-readable scenario description | text |
| `period` | Historical reference period | text |
| `holding_period_days` | Stress holding period | positive integer |
| `shocks` | Scenario shock assumptions | object |

Required shock groups:

* `equity`
* `interest_rates`
* `credit_spreads`
* `fx`

Non-FX shock fields:

| Field | Description | Format |
| --- | --- | --- |
| `shock` | Decimal-rate shock value | number or decimal-compatible text |
| `unit` | Shock unit | `pct` |
| `description` | Human-readable shock description | text |

FX shock fields:

| Field | Description | Format |
| --- | --- | --- |
| `shock_by_currency` | Decimal-rate shock values by impacted currency | object keyed by uppercase 3-letter currency |
| `unit` | Shock unit | `pct` |
| `description` | Human-readable shock description | text |

Relationships:

* The file is a standalone historical stress library.
* It is not referenced by `scenario_definitions.csv`.
* The current calculation workflow does not directly apply these nested historical shock values.

## Relationship Summary

`scenario_definitions.csv` is the central linking file. Each row selects:

- one fund snapshot from `funds.csv`
- one redemption scenario from `redemption_scenarios.csv`
- one market stress from `market_stresses.csv`
- one liquidity stress from `liquidity_stresses.json`
- one liquidation strategy from `liquidation_strategies.json`
- one LMT parameter set from `lmt_parameters.csv`

`positions.csv`, `investor_classes.csv`, and `lmt_parameters.csv` are fund-snapshot datasets identified by `fund_id` and `as_of_date`.

Reusable assumptions are identified by their own IDs and selected through `scenario_definitions.csv`.

**Liquidity stress note:** Unlike other CSV-based reusable assumptions, liquidity stresses use JSON format because execution assumptions must be specified per asset group. This allows different asset groups to have different execution costs under the same stress scenario.
