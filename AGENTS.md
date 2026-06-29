# AGENTS.md

## Project overview

This repository implements **Liquidity Management Tools Calibration** for fund liquidity risk.

The project is a Python and Streamlit application for calibrating and assessing LMT thresholds under redemption and asset-side liquidity stress scenarios. It models both sides of liquidity stress:

- liability-side stress: investor redemptions by client class
- asset-side stress: market shocks, liquidation capacity, haircuts, and settlement constraints

The current implementation focuses on a realistic but narrow sample fund universe:

- cash
- listed equities
- listed ETFs
- reverse repos
- repo financing exposures

The project must avoid generic placeholder assets such as "Asset A" or "Entity B". Sample data should be synthetic but realistic.

Read these files before implementing any module:

- `ARCHITECTURE.md`
- `docs/METHODOLOGY.md`
- `docs/DATA_REFERENCE.md`
- `docs/DATA_SCHEMA.md`
- `docs/DATA_CONVENTIONS.md`
- `docs/AUDIT_TRAIL.md`

If any of these files are missing or incomplete, ask before implementing business logic.

---

## Core product goal

The application should answer:

> Given a fund liquidity profile, investor redemption behaviour, asset market stress, and liquidity stress assumptions, what LMT thresholds are coherent for swing pricing, redemption gates, and liquidity buffers under the tested stress case, and what diagnostic warnings explain the result?

The project calibrates and assesses Liquidity Management Tool thresholds for a fund under liquidity stress assumptions. The current implementation uses single-fund, single-period stress cases and liquidation outputs to assess reference thresholds for swing pricing, redemption gates, and liquidity buffers. Warning checks are diagnostic outputs that support calibration review; they are not the central product objective.

The project does not decide whether a fund manager should activate an LMT.

The current implementation supports:

- investor-class redemption scenarios
- asset-side market shocks
- asset-side liquidity haircuts
- liquidation capacity constraints
- configurable liquidation strategy
- dilution estimate
- swing pricing threshold assessment and diagnostic warning
- redemption gate threshold assessment and diagnostic warning
- liquidity buffer threshold assessment and diagnostic warning
- structured audit trail for scenario runs
- Streamlit interface for scenario calibration

---

## Commit rules

- Do not commit anything.
- Do not stage files.
- Do not push changes.
- Do not add co-author attribution in commit messages.
- Do not add Codex, Claude, ChatGPT, OpenAI, or AI references in commit messages.
- Use only the repository author identity configured in Git.
- When asked, provide only the relevant `git add` command and a concise commit message.
- Commit messages should describe the domain reason for the change, not only the code change.

Good commit message examples:

- `add investor class redemption scenario model`
- `add configurable liquidation strategy with haircut-adjusted cash raised`
- `validate liquidity bucket capacity assumptions`
- `add swing activation assessment using the redemption-rate threshold`

---

## How we work together

### Session start

At the start of every coding session:

1. State which module or file group is being worked on.
2. Confirm the relevant project documents have been read.
3. Confirm the current state of the repo before adding files.
4. Explain the proposed changes before implementing anything.
5. Wait for approval before broad or risky changes.

### Implementation style

- Work in small steps.
- Keep each change focused on one domain concern.
- Do not jump to another module unless explicitly instructed.
- After each step, explain what changed and why.
- If a design decision is ambiguous, ask before inventing business logic.
- Follow existing repository patterns before introducing new ones.

---

## Current module map

The implemented dependency flow is:

1. Project documentation
   - `ARCHITECTURE.md`
   - `docs/METHODOLOGY.md`
   - `docs/DATA_REFERENCE.md`
   - `docs/DATA_SCHEMA.md`
   - `docs/DATA_CONVENTIONS.md`
   - `docs/AUDIT_TRAIL.md`

2. Domain models under `src/lmt_calibration/domain/`
   - fund snapshots and asset positions
   - investor class profiles
   - redemption, market, and liquidity scenarios
   - liquidation strategy configuration
   - LMT parameters and result objects

3. Validation and loaders under `src/lmt_calibration/validation/` and `src/lmt_calibration/loaders/`
   - schema, unit, range, identifier, and reconciliation validation
   - CSV and JSON conversion into typed domain objects

4. Calculation engines under `src/lmt_calibration/engines/`
   - `liquidation_strategy.py`: cash treatment, asset eligibility, strategy allocation, haircut-adjusted cash, shortfall, dilution, and remaining liquidity
   - `liquidity_cost.py`: portfolio-weighted estimated execution cost from per-asset-group liquidity-stress bid-ask spread, transaction cost, and market-impact assumptions
   - `lmt_activation.py`: reference-threshold assessment, diagnostic checks, estimated recovery, redemption deferral, and liquidity-buffer diagnostics

5. Audit trail under `src/lmt_calibration/audit/`
   - structured scenario records and JSON output

6. Application orchestration under `src/lmt_calibration/services/streamlit_mvp.py`
   - validated sample-data loading
   - market, liquidity, and liability stress preparation
   - calculation-engine calls
   - dashboard-ready scenario outcomes

7. Streamlit presentation under `app/streamlit_app.py`
   - selectors and threshold controls
   - scenario comparison matrix
   - calibration diagnostics and supporting content

Standalone asset-side and liability-side engine modules are not part of the current package. Their current preparation steps belong to `services/streamlit_mvp.py` unless a dedicated engine boundary is explicitly designed and implemented.

---

## Architecture rules

- Keep business logic independent from Streamlit.
- Streamlit may collect inputs, call services, and display outputs.
- `services/streamlit_mvp.py` is the orchestration boundary between Streamlit, loaders, scenario preparation, calculation engines, and dashboard-ready outputs.
- Streamlit must not calculate liquidation strategy logic, dilution, haircuts, threshold-comparison logic, or calibration results.
- Calculations must operate on domain objects where practical, not raw DataFrames.
- Raw DataFrames are allowed in loaders and validation only.
- External data must pass through loaders and validators before becoming domain objects.
- Domain models should be explicit and typed.
- Use composition over deep inheritance.
- Use abstract base classes only where there is a real boundary, such as loaders, audit writers, or data providers.
- Do not create abstract classes for single-use logic.
- Keep methodology parameters explicit. Do not hide required assumptions in silent defaults.
- No hardcoded methodology assumptions inside calculation code.
- Centralized constants are allowed for stable labels, column names, enum values, and display names.
- Required calibration parameters must come from validated inputs, scenario objects, or config objects.

---

## Code standards

- Python 3.13
- Use `uv` for dependency management
- Type hints throughout
- No untyped functions
- Pydantic v2 or dataclasses for domain objects
- Use Pydantic v2 syntax with `model_config = ConfigDict(...)`, not `class Config`
- Use `pathlib` for file paths
- No string path concatenation
- Use `pytest` for tests
- Use fixtures where useful
- Use logging for runtime messages
- No `print` statements in production code
- No `from __future__ import annotations`
- No business logic inside dashboard code
- Custom exceptions for domain errors
- Avoid unnecessary dependencies

Before marking a task done, run:

```bash
uv run ruff check src tests app
uv run ruff format --check src tests app
uv run mypy src
uv run pytest
```

---

## Data conventions

Rates, ratios, and haircuts must be stored as `Decimal`.

Examples:

* `Decimal("0.05")` means 5%
* `Decimal("1.50")` means 150%
* `Decimal("0.005")` means 50 bps

Basis points must be stored as `int`.

Examples:

* `50` means 50 bps
* `150` means 150 bps

Never store raw percentage strings in domain models.

Field names must make units explicit:

* `haircut_rate`
* `redemption_rate`
* `market_shock_rate`
* `liquidity_capacity_rate`
* `swing_threshold_rate`
* `spread_bps`
* `settlement_days`
* `market_value`

External inputs may contain human-readable values, but loaders must validate and convert them before creating domain objects.

---

## Required data validation

All external data must be validated before domain object creation.

Validation must check:

* required columns exist
* dates parse correctly
* monetary values are non-negative unless the field explicitly allows liabilities
* rates are between 0 and 1 unless explicitly documented otherwise
* basis-point fields are integers
* NAV is positive
* cash is non-negative
* liquidity capacity rates are between 0 and 1
* haircut rates are between 0 and 1
* redemption rates are between 0 and 1
* investor-class NAV shares sum to 1 per fund and date
* position market values reconcile to fund NAV within a documented tolerance
* repo financing exposures are handled separately from liquid assets
* reverse repo maturity treatment is explicit
* no duplicate primary keys exist
* scenario fund IDs exist in the relevant input files
* required LMT parameters exist for each scenario

Do not silently coerce invalid dates, percentages, monetary values, or missing fields.

Validation errors must be explicit and domain-specific.

---

## Asset-side modelling rules

The currently supported sample asset universe is:

* cash
* listed equities
* listed ETFs
* reverse repos
* repo financing exposures

For listed equities and ETFs, the model may use:

* market value
* beta
* benchmark
* base haircut rate
* stressed haircut rate
* base liquidation capacity rate
* stressed liquidation capacity rate
* settlement days

The workflow must separate:

* market stress: price or market value impact
* liquidity stress: haircut and liquidation capacity impact
* redemption stress: liability-side outflow

`services/streamlit_mvp.py` currently prepares market-stressed values, liquidity haircuts, liquidation capacity, settlement constraints, and maturity constraints before calling the calculation engines.

Do not rely on live market data. Use synthetic but realistic sample data. Live or optional market-data enrichment is outside the current supported workflow and must not be required for the core simulator.

---

## Liability-side modelling rules

Liability stress must be built from investor classes, not only a single generic redemption number.

The currently supported investor classes are:

* retail
* institutional
* platform
* fund_of_funds
* seed_capital

Each investor class may have:

* NAV share
* base redemption rate
* stressed redemption rate
* concentration factor
* notice days
* settlement days

`services/streamlit_mvp.py` currently prepares investor-class redemption assumptions and aggregates total redemption pressure for the selected scenario.

Liability-side calculations and result extensions should support:

* redemption amount by investor class
* total redemption amount
* largest redeeming class
* concentration warning
* notice-period effect where relevant

Platform or nominee investors should be treated as operationally concentrated but potentially diversified underneath.

---

## Liquidation strategy rules

Liquidation must be treated as a configurable strategy, not only a fixed most-liquid-first waterfall.

The current implementation supports:

* `most_liquid_first`: uses cash and the most liquid eligible assets first
* `pro_rata`: preserves the configured minimum cash buffer, then sells eligible non-cash assets proportionally
* `hybrid`: uses part of available cash above the configured minimum buffer, then sells eligible non-cash assets proportionally
* `custom_weights`: allocates liquidation needs according to user-defined weights by asset group

Each strategy must respect:

* available cash
* minimum cash buffer
* reverse repo maturity
* settlement days
* stressed liquidity capacity
* stressed haircut rate
* asset eligibility under the stress horizon

The model should not automatically drain all cash or all liquid assets. It must be able to preserve a configured minimum liquidity buffer.

The structured output may be called a waterfall result where useful, but implementation must not assume that the fund automatically depletes the most liquid assets first.

---

## LMT calibration and diagnostic rules

The current threshold assessment and diagnostic engine assesses reference thresholds for:

* swing pricing
* redemption gate
* liquidity buffer

`engines/lmt_activation.py` provides threshold assessment and diagnostics for scenario review. Diagnostic outputs should support threshold calibration and reviewer interpretation. They may include:

* reported warning flags
* quantitative reason
* explanatory message
* relevant thresholds
* relevant observed values

Warning flags, observed values, threshold comparisons, and messages are diagnostic outputs. They are not the central project objective.

The project does not decide whether a fund manager should activate an LMT.

Do not hardcode the thresholds inside the engine. Thresholds must come from validated LMT parameter objects.

---

## Audit trail rules

Every scenario run must be traceable.

The result must be able to answer:

* which inputs were used
* which assumptions were applied
* which scenario was run
* which parameters were used
* which threshold values were used or assessed
* which diagnostic warnings or checks were reported
* why diagnostic outputs were reported
* when the run happened
* where outputs were written

Audit records should be structured data, not prose only.

A scenario run may write outputs such as:

```text
outputs/audit/
  <run_id>_audit.json

outputs/reports/
  <run_id>_summary.json
  <run_id>_results.csv
```

---

## Sample data rules

Sample data must be synthetic but realistic.

Do not use placeholder names such as:

* Asset A
* Entity B
* Fund 1
* Client X

Use realistic fund and instrument names, while making clear that the data is synthetic.

Sample data should include:

* at least one fund snapshot
* listed equity positions
* listed ETF positions
* cash
* reverse repo exposure
* repo financing exposure
* investor-class mix
* redemption scenarios
* liquidation strategy configuration
* LMT parameter sets

Nested liquidation strategy configuration and custom weights should use JSON, such as:

```text
data/sample/liquidation_strategies.json
```

Asset-group execution-cost, liquidity-capacity, and haircut assumptions use JSON:

```text
data/sample/liquidity_stresses.json
```

The current sample uses one fund and one snapshot. Additional funds and snapshots are outside the current sample scope unless explicitly requested.

---

## Streamlit rules

Streamlit code belongs outside the core package at the implemented entry point:

```text
app/streamlit_app.py
```

Streamlit code may:

* display controls
* collect selected identifiers and parameter overrides
* call application services
* display result tables
* display charts
* display warning panels

Streamlit code must not:

* calculate market stress
* calculate liquidity haircuts
* calculate liquidation strategy results
* calculate dilution
* decide whether an LMT should be activated
* validate raw input schemas directly

---

## Documentation rules

Update documentation when implementation decisions change.

Use:

* `README.md` for project purpose and usage
* `ARCHITECTURE.md` for module boundaries and dependency direction
* `docs/METHODOLOGY.md` for finance methodology and assumptions
* `docs/DATA_REFERENCE.md` for data flow and dataset relationships
* `docs/DATA_SCHEMA.md` for input file fields and formats
* `docs/DATA_CONVENTIONS.md` for shared units, naming, formats, and validation principles
* `docs/AUDIT_TRAIL.md` for scenario-run traceability
* `CHANGELOG.md` for release history and user-visible changes

Avoid migration-style wording such as "new" or "now" in documentation intended for first-time readers.

For educational notebooks and walkthroughs, avoid self-referential phrasing such as "this notebook", "the notebook shows", or "the notebook explains". Prefer direct wording such as "this walkthrough", "the sample inputs", "the analysis", or an active sentence about the reader, scenario, loader, or engine.

---

## Naming rules

The repository name is:

```text
lmt-calibration
```

The package name is:

```text
lmt_calibration
```

The public project title is:

```text
Liquidity Management Tools Calibration
```

Use the full phrase in README and documentation so that the regulatory and fund-risk context is clear.

---

## Current supported scope

The current implementation remains focused on:

* one synthetic fund snapshot
* one-period scenarios
* cash, listed equities, listed ETFs, reverse repo, and repo financing exposure
* investor-class redemption stress
* market stress and asset-side liquidity stress preparation in `services/streamlit_mvp.py`
* configurable `most_liquid_first`, `pro_rata`, `hybrid`, and `custom_weights` liquidation strategies
* strategy-dependent haircut cost, dilution, shortfall, and remaining-liquidity results
* portfolio-weighted estimated execution-cost context separated from realised liquidation cost
* swing pricing, redemption gate, and liquidity buffer reference-threshold diagnostics
* structured audit records and JSON audit output
* Streamlit selectors, threshold controls, market-condition comparison, diagnostic display, and supporting guidance
* historical market stress scenario data loaded as sample and reference context, without implying that every historical-library shock is applied by the active dashboard workflow

Out of current scope:

* corporate bonds
* derivatives
* private debt
* real estate
* side pockets
* 12-month redemption path
* stochastic redemptions by investor class
* selected stress months
* intra-month liquidation schedule
* price impact comparison across liquidation strategies
* strategy comparison view in Streamlit
* full price-impact modelling
* live market-data dependency
* database persistence
* Kubernetes
* cloud deployment
* containerized deployment

---

## When stuck

If the specification is incomplete, stop and ask.

Do not invent:

* LMT methodology
* calibration thresholds
* regulatory interpretations
* hidden default assumptions
* new asset classes
* new investor classes
* extra workflow layers

Prefer a small tested implementation over a broad but unclear one.
