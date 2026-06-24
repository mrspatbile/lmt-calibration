# Liquidity Management Tools Calibration

![Python](https://img.shields.io/badge/python-3.13-blue)
![CI](https://github.com/mrspatbile/lmt-calibration/actions/workflows/ci.yml/badge.svg)
![LMT](https://img.shields.io/badge/Liquidity%20Management%20Tools-UCITS%20%7C%20AIF-blueviolet)
![CSSF](https://img.shields.io/badge/context-CSSF%2026%2F910-lightgrey)

A Python and Streamlit application for calibrating Liquidity Management Tools under fund liquidity stress scenarios.

The project models both sides of fund liquidity stress:

* liability-side pressure from investor redemptions by client class
* asset-side pressure from market shocks, liquidity haircuts, liquidation limits, and settlement constraints

The first version focuses on a synthetic but realistic fund universe covering cash, listed equities, listed ETFs, reverse repos, repo financing exposures, retail investors, institutional investors, platforms, funds of funds, and seed capital.

The purpose is to test how LMT parameters behave under stress, including swing-pricing thresholds, redemption-gate warnings, liquidity-buffer breaches, dilution estimates, and configurable liquidation strategy outcomes.

---

## Regulatory context

This project is inspired by the liquidity-management framework for UCITS and open-ended AIFs, including ESMA Guidelines on Liquidity Management Tools and Luxembourg CSSF Circular 26/910.

It is a non-production portfolio implementation for structured liquidity stress testing, configurable liquidation strategies, and LMT warning analysis. It is not regulatory advice and does not replicate a production ManCo risk system.

---

## Planned scope

Version 1 will include:

* synthetic fund snapshot
* position-level sample data
* one-period scenario
* investor-class redemption scenarios
* market and liquidity stress assumptions
* configurable liquidation strategy
* dilution calculation
* swing-pricing warning
* redemption-gate warning
* liquidity-buffer warning
* structured audit trail
* Streamlit calibration interface later, after the calculation engine is stable

Supported liquidation strategy concepts include `most_liquid_first`, `pro_rata`, `hybrid`, and `custom_weights`. Each strategy must respect available cash, the configured minimum cash buffer, reverse repo maturity, settlement days, stressed liquidity capacity, stressed haircut rates, and asset eligibility under the stress horizon.

Later versions may add a 12-month redemption path by investor class, stochastic redemption draws, selected stress months, intra-month liquidation schedules, price-impact comparison across liquidation strategies, and strategy comparison views in Streamlit.

Excluded from Version 1:

* live market-data dependency
* derivatives
* corporate bonds
* private assets
* 12-month redemption path
* stochastic redemption simulation
* intra-month liquidation schedule
* full price-impact modelling
* database persistence
* Docker until the app runs locally
* cloud deployment
* Kubernetes

---

## Setup

```bash
uv sync
```

Run checks:

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest tests/
```

---

## Documentation

See:

* `ARCHITECTURE.md` for module boundaries and dependency direction
* `docs/METHODOLOGY.md` for finance methodology and assumptions
* `docs/DATA_CONVENTIONS.md` for units, fields, input schemas, and validation rules
* `docs/AUDIT_TRAIL.md` for scenario-run traceability
* `RUNBOOK.md` for day-to-day commands
* `meta/environment_setup.md` for environment and tooling conventions
