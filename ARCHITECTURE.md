# ARCHITECTURE.md

## Purpose

This project separates LMT methodology, validated input loading, domain models, calculation engines, audit records, and Streamlit presentation so that the finance engine can be tested independently from the user interface.

The project is designed as a focused Liquidity Management Tools calibration application for fund liquidity stress testing.

## Main layers

```text
CSV sample data / Streamlit inputs
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
audit records / Streamlit display
```

## Package structure

Implemented structure:

```text
📁 src/lmt_calibration/
├── 📁 domain/
│   ├── fund.py
│   ├── positions.py
│   ├── investors.py
│   ├── scenarios.py
│   ├── parameters.py
│   └── results.py
├── 📁 validation/
│   ├── errors.py
│   ├── field_checks.py
│   ├── liquidation_config.py
│   └── rules.py
├── 📁 loaders/
│   ├── csv_loaders.py
│   └── json_loaders.py
```

Planned later:

```text
📁 src/lmt_calibration/
├── 📁 engines/
│   ├── asset_stress.py
│   ├── liability_stress.py
│   ├── liquidation_strategy.py
│   └── lmt_calibration.py
├── 📁 audit/
│   ├── records.py
│   └── writer.py
└── 📁 reporting/
    └── summaries.py

📁 app/
└── streamlit_app.py
```

Sample data:

```text
📁 data/sample/
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

## Dependency direction

Core calculation code must not depend on Streamlit.

Allowed direction:

```text
app/streamlit_app.py
  imports src/lmt_calibration services
```

Not allowed:

```text
src/lmt_calibration
  imports streamlit
```

## Domain model responsibilities

Domain models represent validated business objects.

Expected domain objects:

* fund snapshot
* asset position
* investor class profile
* redemption scenario
* asset stress scenario
* liquidation strategy configuration
* LMT parameter set
* liquidation result
* LMT calibration and diagnostic result
* audit record

Domain models should contain data and simple derived properties only. Complex calculations belong in engines.

## Loader responsibilities

Loaders read external files and convert raw rows into validated objects.

Loaders may use DataFrames internally, but raw DataFrames should not be passed through the calculation engines.

## Validation responsibilities

Validation checks input structure, units, ranges, identifiers, reconciliations, and missing values before domain object creation.

Validation errors must explain what failed and where.

## Engine responsibilities

### Asset stress engine

Applies market and liquidity stress to asset positions.

It handles:

* market shock effects
* beta-based sensitivity where provided
* stressed haircut rates
* stressed liquidation capacity
* settlement and maturity treatment

### Liability stress engine

Calculates redemption pressure from investor classes.

It handles:

* redemption amount by client class
* total redemption amount
* concentration warnings
* notice-period effects where relevant

### Liquidation strategy engine

Calculates how redemption needs are met under the selected liquidation strategy.

It handles:

* strategy selection such as `most_liquid_first`, `pro_rata`, `hybrid`, or `custom_weights`
* available cash treatment
* minimum cash buffer preservation
* reverse repo maturity treatment
* asset eligibility under the stress horizon
* stressed liquidity capacity
* stressed haircut rates
* settlement constraints
* haircut-adjusted cash raised
* shortfall
* dilution cost

The engine handles strategy-specific liquidation allocation and returns a consistent liquidation result object regardless of selected strategy. The structured output may be called a liquidation result or waterfall result, but the engine must not assume that selling the most liquid assets first is the only valid method.

### LMT calibration and diagnostic layer

Uses stress and liquidation outputs to assess proposed or reference LMT thresholds. Diagnostic checks compare observed stress metrics against threshold values and explain warning flags where relevant.

Conceptually, this layer supports:

* swing-pricing threshold assessment
* redemption-gate threshold assessment
* liquidity-buffer threshold assessment
* diagnostic warnings, breach flags, and explanatory messages
* comparison of observed stress metrics against threshold values

Warnings and breach checks are diagnostic support for calibration and review; they are not the main architectural output. The project does not decide whether a fund manager should activate an LMT.

## Streamlit responsibilities

Streamlit may:

* collect scenario inputs
* show sliders and controls
* call application services
* display tables, charts, metrics, and warnings

Streamlit must not:

* calculate haircuts
* calculate market stress
* calculate liquidation strategy results
* calculate dilution
* decide whether an LMT should be activated
* validate raw CSV schemas directly

## Audit responsibilities

Every scenario run should be traceable to:

* input files
* assumptions
* scenario parameters
* liquidation strategy configuration
* calculation results
* threshold values used or assessed
* diagnostic checks and warnings
* timestamp
* run identifier

Audit output should be structured data, not prose only.

## Version scope

Version 1 includes:

* one-period scenario calibration
* configurable liquidation strategy
* investor-class redemption stress
* asset market stress
* asset liquidity stress
* cash, listed equities, listed ETFs, reverse repos, and repo financing exposures
* LMT threshold assessment diagnostics
* file-based audit records
* Streamlit calibration interface later, after the calculation engine is stable

Later versions may include:

* 12-month redemption paths by investor class
* stochastic redemptions by investor class
* selected stress months
* intra-month liquidation schedules
* price impact comparison across liquidation strategies
* strategy comparison views in Streamlit
* historical or synthetic redemption-flow calibration

## Design rules

* Use Python 3.13.
* Use `uv` for dependency management.
* Use typed domain models.
* Use `Decimal` for rates, ratios, haircuts, and money-like values where precision matters.
* Keep business logic out of Streamlit.
* Keep methodology parameters explicit.
* Do not hide required assumptions in silent defaults.
* Use abstract base classes only where there is a real boundary.
* Prefer small services and composition over deep inheritance.
* Add tests for calculation logic before expanding the UI.
