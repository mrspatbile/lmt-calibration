# Liquidity Management Tools Calibration

![Python](https://img.shields.io/badge/python-3.13-blue)
![CI](https://github.com/mrspatbile/lmt-calibration/actions/workflows/ci.yml/badge.svg)
![LMT](https://img.shields.io/badge/Liquidity%20Management%20Tools-UCITS%20%7C%20AIF-blueviolet)
![CSSF](https://img.shields.io/badge/context-CSSF%2026%2F910-lightgrey)

`lmt-calibration` is a fund liquidity risk project for calibrating Liquidity Management Tools under fund liquidity stress scenarios.

The calibrated parameters are swing-pricing thresholds, redemption-gate thresholds, and liquidity-buffer thresholds.

Calibration results are tested across configurable liquidation strategies and reported through dilution estimates, cash-buffer usage, shortfall analysis, and LMT warning flags.

The stress framework combines:
* liability-side pressure from investor redemptions by client class
* asset-side pressure from market shocks, liquidity haircuts, liquidation limits, and settlement constraints

The first version focuses on a synthetic but realistic fund universe covering cash, listed equities, listed ETFs, reverse repos, repo financing exposures, retail investors, institutional investors, platforms, funds of funds, and seed capital.

---

## Regulatory context

This project uses the liquidity-management framework for UCITS and open-ended AIFs as regulatory context, including ESMA Guidelines on Liquidity Management Tools and Luxembourg CSSF Circular 26/910.

It is a non-production portfolio implementation for structured liquidity stress testing, configurable liquidation strategies, and LMT calibration analysis. It is not regulatory advice and does not replicate a production ManCo risk system.

---
## Version 1 scope

Version 1 is a one-period liquidity stress and LMT calibration workflow.

It covers investor-class redemption stress, asset market and liquidity stress, configurable liquidation strategies, dilution, shortfall, cash-buffer analysis, and LMT threshold checks.

Later versions may add multi-period redemption paths, reverse stress testing, behavioural redemption feedback, asset-side contagion effects, and strategy comparison views.

## Documentation

For methodology and implementation details, see [`docs/`](docs/), [`ARCHITECTURE.md`](ARCHITECTURE.md), and [`RUNBOOK.md`](RUNBOOK.md).

## Setup

```bash
uv sync
```

Run checks:

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest tests -v
```
