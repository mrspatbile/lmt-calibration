# Liquidity Management Tools Calibration

![Python](https://img.shields.io/badge/python-3.13-blue)
![CI](https://github.com/mrspatbile/lmt-calibration/actions/workflows/ci.yml/badge.svg)
[![ESMA](https://img.shields.io/badge/ESMA-LMT%20Guidelines-FF8C00)](https://www.esma.europa.eu/document/guidelines-liquidity-management-tools-ucits-and-open-ended-aifs)
[![CSSF](https://img.shields.io/badge/CSSF-26%2F910-blueviolet)](https://www.cssf.lu/wp-content/uploads/cssf26_910eng.pdf)


`lmt-calibration` is a fund liquidity risk project for calibrating Liquidity Management Tools under fund liquidity stress scenarios.

The parameters under review are swing-pricing thresholds, redemption-gate thresholds, and liquidity-buffer thresholds.

Calibration results are assessed across configurable liquidation strategies and supported by dilution estimates, cash-buffer usage, shortfall analysis, threshold comparisons, and diagnostic warning flags.

The stress framework combines:

* liability-side pressure from investor redemptions by client class
* asset-side pressure from market shocks, liquidity haircuts, liquidation limits, and settlement constraints

The current application focuses on a synthetic but realistic fund universe covering cash, listed equities, listed ETFs, reverse repos, repo financing exposures, retail investors, institutional investors, platforms, funds of funds, and seed capital.

---

## Regulatory context

This project uses the liquidity-management framework for UCITS and open-ended AIFs as regulatory context, including ESMA Guidelines on Liquidity Management Tools, the related EU delegated regulations and Luxembourg CSSF Circular 26/910.

It is a non-production portfolio implementation for structured liquidity stress testing, configurable liquidation strategies, and LMT calibration analysis. It is not regulatory advice and does not replicate a production ManCo risk system.

---

## Current scope

The current application is a one-period liquidity stress and LMT calibration workflow.

It combines investor-base redemption assumptions, asset market shocks, liquidity haircuts, liquidation limits, settlement constraints, configurable liquidation strategies, dilution costs, shortfall analysis, cash-buffer usage, and diagnostic threshold checks for swing pricing, redemption gates, and liquidity-buffer monitoring.

<details>
<summary>Click for a brief overview of the features listed above</summary>

- **Redemption scenarios**: mild outflow, moderate outflow, severe platform exodus.
- **Investor classes**: retail, institutional, platform/distribution channels, fund-of-funds allocators, seed capital.
- **Market conditions**: normal market conditions, moderate stress, severe stress, 2008 crisis conditions.
- **Liquidation strategies**: most-liquid-first, pro-rata, hybrid, custom allocation.
- **LMT thresholds**: swing-pricing activation threshold, gate activation threshold, internal liquidity-buffer threshold.
- **Liquidity stress evaluation**: compares how redemption pressure, market stress, liquidation strategy, and LMT settings affect liquidity needs, costs, shortfalls, and threshold indicators.

</details>

<br>

Out-of-scope extensions include multi-period redemption paths, reverse stress testing, behavioural redemption feedback, asset-side contagion effects, and strategy comparison views.

The implementation uses production-style risk-system patterns, including [typed domain models](src/lmt_calibration/domain), [input validation](src/lmt_calibration/validation), [typed loaders](src/lmt_calibration/loaders), [calculation engines](src/lmt_calibration/engines), [audit records](src/lmt_calibration/audit), and [automated tests](tests).


## Documentation

Key documentation:

* [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) describes the stress methodology.
* [`docs/DATA_REFERENCE.md`](docs/DATA_REFERENCE.md) explains the data workflow and dataset relationships.
* [`docs/DATA_SCHEMA.md`](docs/DATA_SCHEMA.md) documents the field-level schemas for input files.
* [`docs/DATA_CONVENTIONS.md`](docs/DATA_CONVENTIONS.md) defines shared naming, unit, date, and validation conventions.
* [`docs/AUDIT_TRAIL.md`](docs/AUDIT_TRAIL.md) describes scenario-run traceability.
* [`ARCHITECTURE.md`](ARCHITECTURE.md) describes module boundaries.
* [`RUNBOOK.md`](RUNBOOK.md) describes local project operations.
* [`CHANGELOG.md`](CHANGELOG.md) documents project releases.

## Setup

```bash
uv sync
```

## Streamlit app

Run the local app with sample data:

```bash
uv run streamlit run app/streamlit_app.py
```

Run checks:

```bash
uv run ruff check src tests app
uv run ruff format --check src tests app
uv run mypy src
uv run pytest tests -v
```
