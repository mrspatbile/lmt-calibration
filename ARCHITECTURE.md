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
* fallback allocation across remaining eligible capacity
* strategy-deviation amount
* haircut-adjusted cash raised
* shortfall
* dilution cost

The engine handles strategy-specific liquidation allocation and returns a consistent liquidation result object regardless of selected strategy.

The liquidation engine can also apply an explicit realised execution-cost rate
to asset sales. The default rate is zero, preserving the single-period
workflow. The 12-month redemption path supplies only the incremental
market-contagion execution cost in the month after the selected market stress;
the resulting lower net proceeds can require higher gross sales and reduce NAV.

### Liquidity cost engine

Estimates portfolio-weighted ex-ante execution cost from per-asset-group liquidity-stress assumptions and stressed market values. This calibration context is separate from strategy-dependent realised liquidation cost.

It handles:

* bid-ask spread costs
* transaction costs
* market impact costs
* component and total estimated execution cost

### LMT activation-assessment and diagnostic engine

Evaluates simulated LMT activation conditions under stress and provides diagnostic threshold comparisons. It does not make fund-manager activation decisions.

It handles:

* swing-pricing threshold assessment
* redemption-gate threshold assessment
* liquidity-buffer threshold assessment
* estimated swing recovery and redemption deferral
* applied swing factor capped by the configured maximum
* applied cost recovery capped by realised liquidation cost
* diagnostic warnings and explanatory messages
* comparison of observed stress metrics against threshold values

Warnings and diagnostic checks support calibration review; they do not decide whether a fund manager should activate an LMT.

### Redemption-path engine

The fixed 12-month engine keeps threshold signals separate from applied LMT
scenario assumptions. Swing-pricing and gate signals are calculated from the
configured thresholds. Paid redemption, deferral, liquidation, swing recovery,
and behavioural feedback change only when the corresponding LMT is applied.

The application may link swing pricing and gates to every signal month through
an explicit signal-linked mode. Suspension remains an independently selected
scenario assumption and is never inferred from a model signal.

## Services layer

The `services/streamlit_mvp.py` module orchestrates the complete workflow:

* loads and caches sample data files
* validates inputs and creates domain objects
* applies scenario assumptions (market stress, liquidity stress, redemption stress)
* calls liquidation, liquidity cost, and LMT activation-assessment engines
* returns dashboard-ready result objects for presentation

This layer decouples the Streamlit UI from core calculation engines, allowing engines to be tested and reused independently.

Swing recovery is calculated in the activation-assessment engine and passed through service result objects. Streamlit displays these returned values and does not recalculate recovery.

## Streamlit responsibilities

### Market scenarios & notice-period liquidity page (Page 1)

Streamlit may:

* render LMT parameter configuration (sliders for swing threshold, gate threshold, buffer target)
* collect fund, redemption scenario, liquidation strategy, and market condition selections
* call service layer to build scenario runs across market conditions
* display scenario matrix table with threshold comparisons
* show diagnostic warnings and guidance

### 12-month redemption path page (Page 2)

Streamlit may:

* render path controls (stress months, market stress selection, behavioural feedback, market contagion multipliers)
* collect suspension and LMT application assumptions
* call service layer to build redemption path runs
* render matplotlib charts for redemptions, NAV evolution, and LMT timeline
* display path KPIs and configuration summary
* sync signal-linked LMT applications across months

### Both pages

Streamlit must not:

* calculate haircuts
* calculate market stress
* calculate liquidation strategy results
* calculate liquidity costs or dilution
* decide whether an LMT should be activated
* validate raw CSV schemas directly
* calculate redemption paths
* compute monthly backlog or investor-class balance evolution

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

Scenario engines and services do not write audit files automatically. Audit writing remains an explicit application or export action through the JSON writer.

## Current implementation

### Page 1: Market scenarios & notice-period liquidity

Single-period liquidity stress analysis for threshold calibration:

* configurable liquidation strategy (most_liquid_first, pro_rata, hybrid, custom_weights)
* investor-class redemption stress
* asset market stress and liquidity stress assumptions
* cash, listed equities, listed ETFs, reverse repos, and repo financing exposures
* portfolio-weighted estimated execution-cost breakdown by bid-ask spread, transaction cost, and market impact
* LMT threshold assessment and diagnostic warnings for swing pricing, redemption gates, and liquidity buffers
* scenario comparison across market conditions

### Page 2: 12-month redemption path

Forward-looking multi-period simulation:

* fixed 12-month horizon with monthly liquidation capacity scaling
* monthly threshold signals (swing pricing, redemption gates, liquidity buffer) separated from user-selected LMT applications
* deferred redemption backlog tracking and evolution
* optional market stress with one-month liquidity-cost and net-proceeds adjustment (market contagion)
* behavioural feedback multiplier (applied after LMT use, increases next-month demand)
* fund NAV, cash, position, and investor-class balance evolution month-to-month
* matplotlib charts rendering redemptions, NAV, and LMT timeline
* user controls for stress months, market stress scenario, behavioural feedback, and market contagion

### Shared features

* structured audit record models and a JSON writer; automatic writing from the Streamlit application is not integrated
* Streamlit dashboard with two-page interface
* theme toggle and interactive parameter adjustment

Future versions may include:

* redemption paths stratified by investor class
* stochastic redemptions with explicit deterministic random seeds
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
