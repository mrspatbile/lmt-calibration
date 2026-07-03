# Audit Trail

## Purpose

This document defines how scenario runs should be recorded.

The audit trail allows each result to be traced back to inputs, assumptions, parameters, liquidation outputs, threshold values used or assessed, diagnostic warnings, and generated output files.

## Current integration status

The audit trail infrastructure is implemented as structured audit models and a JSON writer. Automatic writing during Streamlit dashboard runs is not currently integrated. Manual audit record creation is possible via the audit writer class for programmatic scenario runs or external workflows.

## Audit objective

Each scenario run should answer:

- which fund was tested
- which data snapshot was used
- which scenario was run
- which assumptions were applied
- which liquidation strategy was used
- which LMT threshold values were used or assessed
- which liquidation outputs supported threshold assessment
- which diagnostic warnings or checks were reported
- why diagnostic outputs were reported
- when the run happened
- which output files were written

## Run identifier

Each scenario run should have a unique `run_id`.

Format:

```text
YYYYMMDD_HHMMSS_<scenario_id>
```

Example:

```text
20260630_143000_severe_redemption
```

## Suggested output structure

```text
📁 outputs/
├── 📁 audit/
│   └── <run_id>_audit.json
└── 📁 reports/
    ├── <run_id>_summary.json
    └── <run_id>_results.csv
```

Audit records may be written as structured JSON runtime outputs under `outputs/audit/`.

Scenario summaries, tables, charts, or exports may be written under `outputs/reports/` when reporting output is implemented or explicitly produced.

Generated outputs are excluded from Git.

## Audit record structure

An audit record can be written for any scenario run to support review and reproducibility:

```text
outputs/audit/<run_id>_audit.json
```

The audit record includes the information needed to review and reproduce the scenario run. It is structured as nested summaries of input, parameters, and liquidation results, with optional threshold assessment diagnostics.

### Input summary

The audit record includes:

* fund ID
* fund name
* as-of date
* source files
* number of positions
* number of investor classes
* total NAV
* total position market value
* reconciliation status
* validation status

### Parameters

The audit record includes:

* scenario ID
* redemption scenario reference
* market stress reference
* liquidity stress reference
* liquidation strategy reference
* liquidation strategy weights, if applicable
* minimum cash buffer requirement
* whether the minimum cash buffer is preserved
* swing-pricing threshold value
* max swing factor
* gate threshold value
* minimum buffer threshold value

### Result

The audit record includes summary-level liquidation totals:

* total redemption amount
* total redemption rate
* cash used
* liquidation strategy used
* strategy allocation by asset group
* whether the minimum cash buffer was preserved
* gross sales (total)
* haircut cost (total)
* post-haircut cash raised (total)
* strategy-deviation amount raised through fallback allocation
* shortfall
* dilution amount
* dilution rate
* remaining liquidity buffer

When threshold assessment is performed, the audit record also includes:

* threshold assessment diagnostics
* diagnostic flags (swing-pricing, redemption-gate, liquidity-buffer)
* observed values and reference thresholds
* explanatory messages

### Audit metadata

The audit record includes:

* run ID
* timestamp
* package version, if available
* output file paths (where the audit record and related files are written)

## Audit design rules

* Audit records should be structured data.
* Audit records should not rely on prose only.
* Audit records should not include confidential data.
* Audit records should be reproducible from the same inputs and parameters.
* Audit records should preserve enough information to explain threshold assessment diagnostics and warning flags.
* Audit records should distinguish input assumptions from calculated results.
* Audit records should be generated outputs, not source files.
* Tests should write audit records to temporary directories rather than committed output folders.

## Current audit scope

The current audit scope supports:

**Page 1: Market scenarios & notice-period liquidity**
* File-based audit records for single-period scenarios with configurable liquidation strategies
* Structured JSON objects containing input summaries, parameter summaries, liquidation totals, and threshold assessment results

**Page 2: 12-month redemption path**
* Structured records capturing configuration (stress months, market stress, LMT applications)
* Monthly simulation parameters and inputs
* Support for audit trail of monthly results, unit-based backlog evolution,
  current backlog cash value, deferral NAV, and LMT applications

Records can be written to any output directory using the JSON audit writer.

Database persistence is not implemented.

## Later audit extensions

Future versions may add:

* automatic audit record writing during Streamlit dashboard runs
* per-investor-class redemption breakdowns
* per-position liquidation details (asset-by-asset allocation and cost)
* monthly breakdown in redemption-path audit records (investor-class demand, backlog, LMT applications)
* database persistence
* scenario comparison history
* parameter change log
* user-selected scenario labels
* downloadable audit reports for both pages
