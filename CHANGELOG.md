# Changelog

All notable changes to this project are documented here.

## [0.5.0] - 2026-06-27

### Added
- Streamlit dashboard for LMT calibration and scenario review.
- Scenario comparison matrix across market conditions.
- LMT activation engine for swing pricing, redemption gates, and liquidity-buffer threshold checks.
- Liquidity cost breakdown by asset group.
- Per-asset-group liquidity stress assumptions in `liquidity_stresses.json`.
- Calibration guidance panel with activation status, cost recovery, and deferral indicators.

### Changed
- Expanded market stress inputs with execution-cost assumptions.
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