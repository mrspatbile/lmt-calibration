# Changelog

All notable changes to this project are documented here.

## Unreleased

### Added
- Added a scenario-independent time-to-liquidation sensitivity view for the current portfolio.

### Changed
- Removed reverse repo and repo financing rows from the synthetic sample portfolio while retaining EUR 100m total market value.
- Represented deferred redemption backlog as units valued at each month’s NAV, with ownership reduced only when units execute.
- Consolidated execution-cost, liquidity-capacity, and haircut assumptions by asset group under liquidity stress; market stress remains valuation-only.
- Centralized applied swing-factor and cost-recovery calculations outside the dashboard.
- Made initial, current pre-LMT, and current post-LMT NAV bases explicit while preserving their intended uses.
- Confirmed audit writing as an explicit export action rather than a scenario-engine side effect.

## [0.5.0] - 2026-06-27

### Added
- Streamlit dashboard for LMT calibration and scenario review.
- Scenario comparison matrix across market conditions.
- LMT activation-assessment engine for simulated swing activation, simulated gate activation, and liquidity-buffer threshold checks.
- Estimated execution-cost breakdown by bid-ask spread, transaction cost, and market impact.
- Per-asset-group liquidity stress assumptions in `liquidity_stresses.json`.
- Calibration guidance panel with simulated activation status, cost recovery, and deferral indicators.

### Changed
- Added per-asset-group execution-cost assumptions to liquidity stress inputs.
- Updated sample data schemas to support the dashboard workflow.
- Refined dashboard layout, visual hierarchy, and theme handling.
- Updated documentation for methodology, data schemas, and audit records.

### Fixed
- Version consistency across package metadata and lockfile.
- CI and release checks for the dashboard workflow.

## [0.4.0] - 2026-06-26

### Added
- Audit record models for scenario-run traceability.
- JSON audit writer for file-based run evidence.
- LMT warning and threshold assessment result models.

### Changed
- Extended result models to support calibration diagnostics.

## [0.3.0] - 2026-06-25

### Added
- Liquidation strategy engine.
- Support for `most_liquid_first`, `pro_rata`, `hybrid`, and `custom_weights` strategies.
- Cash-buffer usage, shortfall, haircut cost, dilution cost, and per-asset liquidation results.

## [0.2.0] - 2026-06-24

### Added
- Typed domain models for funds, positions, investors, scenarios, LMT parameters, strategies, and results.
- CSV and JSON loaders for sample data.
- Validation layer with structured validation errors.
- Sample fund universe and stress inputs.

## [0.1.0] - 2026-06-23

### Added
- Initial project structure.
- Tooling with `uv`, `ruff`, `mypy`, `pytest`, and GitHub Actions CI.
- Base documentation structure.
