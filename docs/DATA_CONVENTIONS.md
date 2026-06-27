# Data Conventions

## Purpose

This document defines shared data conventions for the Liquidity Management Tools Calibration project.

Use it for naming, units, date formats, decimal representation, validation principles, missing-value handling, and synthetic data rules.

For the current data workflow, see [DATA_REFERENCE.md](DATA_REFERENCE.md).

For field-level input schemas, see [DATA_SCHEMA.md](DATA_SCHEMA.md).

## Naming Conventions

Field names should be lowercase `snake_case`.

Identifiers should be stable and descriptive:

```text
fund_id
position_id
scenario_id
redemption_scenario_id
market_stress_id
liquidity_stress_id
liquidation_strategy_id
parameter_set_id
lmt_parameter_set_id
```

Field names should include units where ambiguity is possible:

```text
market_value
notional_amount
redemption_rate
haircut_rate
market_shock_rate
liquidity_capacity_rate
swing_threshold_rate
gate_threshold_rate
minimum_buffer_rate
settlement_days
notice_days
spread_bps
cash_buffer_use_rate
bid_ask_spread_rate
transaction_cost_rate
market_impact_rate
participation_rate
liquidity_haircut_rate
stress_horizon_days
maturity_days
```

Avoid vague names such as:

```text
percentage
value
amount
rate
threshold
```

Use them only where the surrounding dataset makes the meaning explicit.

Use **asset group** consistently for the classification represented by `asset_group` and for asset-group-specific assumptions.

## Input Formats

Use CSV for flat tabular datasets.

Use JSON where configuration is nested, including liquidation strategy weights, asset-group execution assumptions, and historical stress scenario libraries.

Each input file must follow its documented schema. Shared conventions do not replace the field-level requirements in [DATA_SCHEMA.md](DATA_SCHEMA.md).

## Decimal Representation

Rates, ratios, sensitivities, haircuts, thresholds, weights, and monetary values become `Decimal` values in domain models.

Examples:

```text
Decimal("0.05") = 5%
Decimal("0.005") = 50 bps
Decimal("1.25") = 125%
```

CSV values use decimal notation. JSON values use the numeric or string representation required by the relevant schema. Raw percentage strings such as `5%` are not allowed in either format.

For historical market stress JSON, `unit: "pct"` uses the same decimal-rate convention. For example, `-0.4` means a 40% decline.

Use decimal representation for:

* redemption rates
* haircut rates
* market shock rates
* liquidity capacity rates
* NAV share rates
* cash buffer use rates
* swing-pricing thresholds
* gate thresholds
* buffer thresholds
* concentration factors
* liquidation strategy weights
* beta, duration, spread duration, and delta

## Shared Rate Conventions

Rates use decimal representation:

```text
0.05 = 5%
0.005 = 50 basis points
-0.20 = a 20% decline
```

Market shock rates may be negative. Execution-cost rates represent proportions of the relevant amount. Participation rates represent the usable share of liquidation capacity. Liquidity haircut rates represent additional stressed haircuts.

Swing-pricing, redemption-gate, and liquidity-buffer thresholds use decimal rates.

Exact field requirements and permitted ranges belong in [DATA_SCHEMA.md](DATA_SCHEMA.md), not in this conventions document.

## Monetary Values

Use `Decimal` for monetary values in domain models.

Examples:

* NAV
* market value
* cash amount
* redemption amount
* liquidation amount
* dilution cost
* shortfall
* notional amount
* entry price
* strike price

Monetary values and obligation amounts should be non-negative unless a dataset explicitly defines a signed field.

## Basis Points

Basis points are reserved guidance for fields naturally expressed in basis points. Store such fields as `int` and use a `_bps` suffix.

Examples:

```text
50 = 50 bps
150 = 150 bps
```

Conversion:

```text
1 bps = 0.0001 as decimal = 0.01%
150 bps = 0.015 as decimal = 1.5%
```

## Dates

Use ISO 8601 dates:

```text
YYYY-MM-DD
```

Example:

```text
2026-06-30
```

Domain models should use date objects after validation and loading.

Descriptive historical periods may remain text when explicitly defined that way by the relevant schema.

## Missing Values

Blank cells in flat files mean missing values.

Loaders may normalize blank CSV cells to `None` at the file boundary before validation and domain object creation.

In JSON inputs, an omitted field or `null` value means missing. Missing required values should fail validation. Optional values may remain blank, absent, or `null` when allowed by the relevant schema.

Do not use hidden defaults for required methodology parameters.

## Validation Philosophy

External data must be validated before domain object creation.

Validation should check structure, units, ranges, identifiers, missing values, and documented relationships. Validation errors should state what failed and where.

Field-level requirements, conditional rules, and ranges belong in [DATA_SCHEMA.md](DATA_SCHEMA.md) and the validation layer.

Validation must not silently coerce invalid dates, invalid percentages, malformed monetary values, or missing required fields.

Loaders may perform narrow file-parsing hygiene, such as reading CSV or JSON files and converting blank cells to missing values. Business validation belongs in the validation layer, and business calculations belong in engines.

## Synthetic Data Principles

Sample data must be synthetic but realistic.

Do not use placeholder names such as:

```text
Asset A
Entity B
Fund 1
Client X
```

Use realistic but clearly synthetic examples, such as:

```text
Lux Dynamic Allocation Fund
EUR Operating Cash
SAP SE Ordinary Shares
EUR Overnight Reverse Repo BNP Paribas Synthetic
Platform Distribution Channel
```

Sample data should be small enough for demonstrations and tests while still reflecting the current data relationships.

## Related Documents

* [DATA_REFERENCE.md](DATA_REFERENCE.md) explains the current data flow and dataset relationships.
* [DATA_SCHEMA.md](DATA_SCHEMA.md) documents the field-level schema for each current input file.
* [METHODOLOGY.md](METHODOLOGY.md) defines the finance methodology and assumptions.
* [AUDIT_TRAIL.md](AUDIT_TRAIL.md) defines generated audit records and output traceability.
