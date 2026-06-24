# Data Reference

## Purpose

This document explains the project data model at workflow level.

It describes where data comes from, what each dataset represents, how datasets relate to each other, and how data moves through loaders, validation, domain models, calculation engines, and outputs.

* For field-level schemas, see [DATA_SCHEMA.md](DATA_SCHEMA.md).
* For shared units and naming conventions, see [DATA_CONVENTIONS.md](DATA_CONVENTIONS.md).

---

## Data Flow

```text
data/raw/ or data/sample/
↓
loaders
↓
validation
↓
domain models
↓
calculation engines
↓
result objects
↓
outputs/audit/ and outputs/reports/
```

Loaders read files and pass parsed records through validation before creating typed domain models. The workflow is designed so later calculation engines consume domain models, not raw CSV rows or DataFrames. Generated audit and report files are runtime outputs, not source data.

---

## Folder Structure

```text
📁 data/
  📁 raw/
  📁 cleaned/
  📁 sample/

📁 outputs/
  📁 audit/
  📁 reports/

```
| Folder | Role |
| --- | --- |
| [`data/raw/`](../data/raw/) | Original external input files, kept unchanged. |
| [`data/cleaned/`](../data/cleaned/) | Validated or cleaned datasets derived from raw inputs. |
| [`data/sample/`](../data/sample/) | Committed synthetic sample data used for examples and tests. |
| [`outputs/audit/`](../outputs/audit/) | Generated audit records for scenario runs. |
| [`outputs/reports/`](../outputs/reports/) | Generated reports, summaries, tables, or exports. |

---

## Input Datasets

The current sample input set is:

```text
data/sample/
├── funds.csv
├── positions.csv
├── investor_classes.csv
├── redemption_scenarios.csv
├── market_stresses.csv
├── liquidity_stresses.csv
├── scenario_definitions.csv
├── lmt_parameters.csv
└── liquidation_strategies.json
```

Dataset sections:

* [funds.csv](#funds-csv)
* [positions.csv](#positions-csv)
* [investor_classes.csv](#investor-classes-csv)
* [redemption_scenarios.csv](#redemption-scenarios-csv)
* [market_stresses.csv](#market-stresses-csv)
* [liquidity_stresses.csv](#liquidity-stresses-csv)
* [scenario_definitions.csv](#scenario-definitions-csv)
* [lmt_parameters.csv](#lmt-parameters-csv)
* [liquidation_strategies.json](#liquidation-strategies-json)

---

<a id="funds-csv"></a>

### funds.csv

`funds.csv` defines fund snapshots. It is used to identify the fund, as-of date, base currency, NAV, and dealing terms for a scenario run.

Relationships:

* `positions.csv` rows reference the same `fund_id` and `as_of_date`.
* `investor_classes.csv` rows reference the same `fund_id` and `as_of_date`.
* `lmt_parameters.csv` rows reference the same `fund_id` and `as_of_date`.
* `scenario_definitions.csv` links a scenario to one fund snapshot.

---

<a id="positions-csv"></a>

### positions.csv

`positions.csv` defines position-level holdings and financing exposures for a fund snapshot. In the current sample data, positions stay within the active universe:

* cash
* listed equities
* listed ETFs
* reverse repos
* repo financing exposures

Positions are designed for later asset-side stress and liquidation strategy engines. Repo financing exposures are treated as liquidity obligations, not ordinary liquid assets.

Relationships:

* Each position belongs to one `fund_id` and `as_of_date`.
* Position values should reconcile to fund NAV for ordinary assets, excluding repo financing obligations.
* Position liquidity fields are used with liquidity stress assumptions.

<a id="investor-classes-csv"></a>

---

### investor_classes.csv

`investor_classes.csv` defines liability-side investor profiles for a fund snapshot. Each row represents one investor class and its NAV share, redemption assumptions, concentration factor, notice days, and settlement days.

Relationships:

* Investor class rows belong to one `fund_id` and `as_of_date`.
* NAV shares should sum to 1 for each fund snapshot.
* Redemption scenarios multiply investor-class redemption assumptions.

---

<a id="redemption-scenarios-csv"></a>

### redemption_scenarios.csv

`redemption_scenarios.csv` defines reusable liability-side redemption scenario assumptions. Redemption scenarios are not tied directly to a fund, as-of date, market stress, liquidity stress, liquidation strategy, or LMT parameter set.

Relationships:

* `scenario_definitions.csv` selects exactly one `redemption_scenario_id`.
* The selected redemption scenario is applied to investor-class redemption assumptions.

---

<a id="market-stresses-csv"></a>

### market_stresses.csv

`market_stresses.csv` defines reusable asset-side market shock assumptions. Market stresses are reusable and not tied directly to a fund snapshot.

Relationships:

* `scenario_definitions.csv` selects exactly one `market_stress_id`.
* The selected market stress is designed to be applied to eligible asset positions by the asset-side engine.

---

<a id="liquidity-stresses-csv"></a>

### liquidity_stresses.csv

`liquidity_stresses.csv` defines reusable asset-side liquidity stress assumptions. Liquidity stresses include the liquidity stress multiplier and stress horizon.

Relationships:

* `scenario_definitions.csv` selects exactly one `liquidity_stress_id`.
* Liquidity stress is designed to affect haircut and capacity treatment in asset-side and liquidation engines.

---

<a id="scenario-definitions-csv"></a>

### scenario_definitions.csv

`scenario_definitions.csv` links one fund snapshot to one selected set of reusable assumptions and parameters. It is the scenario assembly file.

Each scenario references exactly one:

* `redemption_scenario_id`
* `market_stress_id`
* `liquidity_stress_id`
* `liquidation_strategy_id`
* `lmt_parameter_set_id`

Scenario definitions do not contain nested liquidation strategy configuration or custom strategy weights. Those belong in `liquidation_strategies.json`.

---

<a id="lmt-parameters-csv"></a>

### lmt_parameters.csv

`lmt_parameters.csv` defines explicit LMT threshold parameter sets for a fund snapshot. It contains swing-pricing thresholds, redemption-gate thresholds, and minimum buffer thresholds.

Relationships:

* Parameter rows belong to one `fund_id` and `as_of_date`.
* `scenario_definitions.csv` selects exactly one `lmt_parameter_set_id`.
* `minimum_buffer_rate` is the source for the configured minimum liquidity buffer.

---

<a id="liquidation-strategies-json"></a>

### liquidation_strategies.json

`liquidation_strategies.json` defines reusable liquidation strategy configurations. JSON is used because strategy configuration may contain nested fields such as custom asset-group weights.

Relationships:

* `scenario_definitions.csv` selects exactly one `liquidation_strategy_id`.
* Custom strategy weights belong only in this JSON file.
* Strategy outputs should be comparable through a consistent liquidation result object.

---


## Relationship Summary

* `scenario_definitions.csv` is the central assembly file. It selects the fund snapshot, redemption scenario, market stress, liquidity stress, liquidation strategy, and LMT parameter set used in each scenario run.

* `positions.csv`, `investor_classes.csv`, and `lmt_parameters.csv` are fund-snapshot datasets linked by `fund_id` and `as_of_date`.

* `redemption_scenarios.csv`, `market_stresses.csv`, `liquidity_stresses.csv`, and `liquidation_strategies.json` contain reusable assumptions selected by `scenario_definitions.csv`.

---


## Runtime Outputs

Scenario runs should produce generated outputs under:

```text
outputs/audit/
outputs/reports/
```

Audit records preserve input references, selected assumptions, parameter references, liquidation strategy references, result summaries, warning flags, and output paths. For detailed audit content, see [AUDIT_TRAIL.md](AUDIT_TRAIL.md).

---


## Related Documents

* [DATA_SCHEMA.md](DATA_SCHEMA.md) documents field-level input schemas.
* [DATA_CONVENTIONS.md](DATA_CONVENTIONS.md) defines shared naming, unit, date, and validation conventions.
* [METHODOLOGY.md](METHODOLOGY.md) explains the stress methodology.
* [AUDIT_TRAIL.md](AUDIT_TRAIL.md) explains generated audit records.
