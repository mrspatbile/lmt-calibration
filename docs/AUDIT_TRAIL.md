# Audit Trail

## Purpose

This document defines how scenario runs should be recorded.

The audit trail allows each result to be traced back to inputs, assumptions, parameters, liquidation outputs, threshold values used or assessed, diagnostic warnings, and generated output files.

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

Audit records are saved as structured JSON runtime outputs under `outputs/audit/`.

Scenario summaries, tables, charts, or exports are saved under `outputs/reports/`.

Generated outputs are excluded from Git.

## Audit record content

Each scenario run should produce one audit record:

```text
outputs/audit/<run_id>_audit.json
```

The audit record should include the information needed to review and reproduce the scenario run.

### Input summary

The audit record should include:

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

The audit record should include:

* scenario ID
* redemption assumptions
* market shock assumptions
* liquidity stress assumptions
* liquidation strategy
* strategy parameters
* liquidation strategy weights, if applicable
* cash buffer rule
* cash buffer use rate, if applicable
* whether the minimum cash buffer should be preserved
* swing-pricing threshold value used or assessed
* max swing factor
* gate threshold value used or assessed
* minimum buffer threshold value used or assessed

### Result

The audit record should include:

* total redemption amount
* redemption amount by investor class
* total redemption rate
* cash used
* assets liquidated
* liquidation strategy used
* strategy allocation by asset group
* whether the minimum cash buffer was preserved
* gross sales
* haircut cost
* post-haircut cash raised
* shortfall
* dilution amount
* dilution rate
* remaining liquidity buffer
* threshold values used or assessed
* diagnostic warning flags or checks
* explanatory messages, where available

### Audit metadata

The audit record should include:

* run ID
* timestamp
* package version, if available
* input file references
* scenario reference
* parameter set reference
* liquidation strategy configuration
* validation results
* calculation summary
* threshold assessment summary
* diagnostic warnings reported
* output file paths

## Audit design rules

* Audit records should be structured data.
* Audit records should not rely on prose only.
* Audit records should not include confidential data.
* Audit records should be reproducible from the same inputs and parameters.
* Audit records should preserve enough information to explain threshold assessment diagnostics and warning flags.
* Audit records should distinguish input assumptions from calculated results.
* Audit records should be generated outputs, not source files.
* Tests should write audit records to temporary directories rather than committed output folders.

## Version 1 audit scope

Version 1 should support file-based audit records for one-period scenarios with configurable liquidation strategies.

Database persistence is not required for Version 1.

Generated audit files should be saved locally under `outputs/audit/` and excluded from Git.

## Later audit extensions

Later versions may add:

* database persistence
* scenario comparison history
* parameter change log
* user-selected scenario labels
* downloadable audit report
* 12-month redemption path records
* monthly redemption pressure by investor class
* monthly liquidity-management response
* LMT threshold assessment and diagnostic path through time
