# ARCHITECTURE.md

## Purpose

This project separates LMT methodology, validated input loading, domain models, calculation engines, audit records, and Streamlit presentation so that the finance engine can be tested independently from the user interface.

The project is designed as a focused Liquidity Management Tools calibration application for fund liquidity stress testing.

## Main layers

```text
CSV and JSON sample data / Streamlit inputs
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

Current implementation:

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
│   ├── rules.py
│   └── historical_market_stress.py
├── 📁 loaders/
│   ├── csv_loaders.py
│   └── json_loaders.py
├── 📁 engines/
│   ├── liquidation_strategy.py
│   ├── liquidity_cost.py
│   └── lmt_activation.py
├── 📁 audit/
│   ├── records.py
│   └── writer.py
└── 📁 services/
    └── streamlit_mvp.py

📁 app/
├── streamlit_app.py
└── content.py

📁 data/sample/
├── funds.csv
├── positions.csv
├── investor_classes.csv
├── redemption_scenarios.csv
├── market_stresses.csv
├── liquidity_stresses.json
├── scenario_definitions.csv
├── lmt_parameters.csv
├── liquidation_strategies.json
└── historical_market_stress_scenarios.json
```

`historical_market_stress_scenarios.json` is a loader-ready sample library for
historical market stress selection. Version 1 calculation engines do not apply
historical shocks; they are reserved for future scenario comparison views.

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

The engine handles strategy-specific liquidation allocation and returns a consistent liquidation result object regardless of selected strategy.

### Liquidity cost engine

Estimates liquidation costs decomposed by asset group.

It handles:

* bid-ask spread costs
* transaction costs
* market impact costs
* participation-rate haircuts
* cost breakdown by asset group

### LMT activation and diagnostic engine

Assesses which LMT tools activate under stress and provides diagnostic threshold comparisons.

It handles:

* swing-pricing threshold assessment
* redemption-gate threshold assessment
* liquidity-buffer threshold assessment
* estimated swing recovery and redemption deferral
* diagnostic warnings and explanatory messages
* comparison of observed stress metrics against threshold values

Warnings and diagnostic checks support calibration review; they do not decide whether a fund manager should activate an LMT.

## Services layer

The `services/streamlit_mvp.py` module orchestrates the complete workflow:

* loads and caches sample data files
* validates inputs and creates domain objects
* applies scenario assumptions (market stress, liquidity stress, redemption stress)
* calls liquidation, liquidity cost, and LMT activation engines
* returns dashboard-ready result objects for presentation

This layer decouples the Streamlit UI from core calculation engines, allowing engines to be tested and reused independently.

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
* calculate liquidity costs or dilution
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

## Current implementation

The current implementation includes:

* one-period scenario calibration
* configurable liquidation strategy (most_liquid_first, pro_rata, hybrid, custom_weights)
* investor-class redemption stress
* asset market stress and liquidity stress assumptions
* cash, listed equities, listed ETFs, reverse repos, and repo financing exposures
* liquidity cost breakdown by asset group
* LMT threshold assessment and diagnostic warnings
* structured audit record models and a JSON writer; automatic writing from the Streamlit application is not integrated
* Streamlit calibration dashboard with scenario comparison across market conditions
* theme toggle and interactive parameter adjustment

Future versions may include:

* 12-month redemption paths by investor class
* stochastic redemptions by investor class
* reverse stress testing
* strategy comparison views
* historical scenario application
* enhanced price-impact modelling

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
