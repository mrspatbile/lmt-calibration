"""Smoke tests for application-aligned notebooks."""

import importlib.util
import json
from pathlib import Path

WALKTHROUGH_NOTEBOOK = Path("notebooks/liquidation_strategy_walkthrough.ipynb")
INSPECTION_NOTEBOOK = Path("notebooks/liquidation_strategy_inspection.ipynb")
NOTEBOOK_HELPERS = Path("notebooks/_notebook_helpers.py")

OBSOLETE_HELPER_NAMES = {
    "load_sample_inputs",
    "redemption_rows",
    "total_redemption_amount",
    "scenario_positions",
    "stressed_haircut_rate",
    "stressed_liquidity_capacity_rate",
    "run_liquidation_scenario",
    "scenario_from_selected_ids",
}


def test_notebook_service_imports_resolve() -> None:
    """Verify notebook-facing service imports and display helpers resolve."""

    from lmt_calibration.services import (  # noqa: PLC0415
        load_app_sample_data,
        run_sample_redemption_path,
        run_selected_sample_scenario,
    )

    spec = importlib.util.spec_from_file_location("notebook_helpers", NOTEBOOK_HELPERS)
    assert spec is not None
    assert spec.loader is not None
    notebook_helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(notebook_helpers)

    assert callable(load_app_sample_data)
    assert callable(run_selected_sample_scenario)
    assert callable(run_sample_redemption_path)
    assert callable(notebook_helpers.money)
    assert callable(notebook_helpers.rate)


def test_walkthrough_notebook_uses_application_services() -> None:
    """Verify the primary walkthrough references the application workflow services."""

    source = _notebook_source(WALKTHROUGH_NOTEBOOK)

    assert "run_selected_sample_scenario" in source
    assert "run_sample_redemption_path" in source
    assert "load_app_sample_data" in source


def test_walkthrough_notebook_does_not_use_obsolete_calculation_helpers() -> None:
    """Verify obsolete notebook-local calculation paths are not used."""

    source = _notebook_source(WALKTHROUGH_NOTEBOOK)
    helper_source = NOTEBOOK_HELPERS.read_text()

    for helper_name in OBSOLETE_HELPER_NAMES:
        assert f"{helper_name}(" not in source
        assert f"import {helper_name}" not in source
        assert f"def {helper_name}" not in helper_source


def test_inspection_notebook_is_marked_as_low_level_diagnostic() -> None:
    """Verify the inspection notebook is clearly distinguished from app workflow."""

    source = _notebook_source(INSPECTION_NOTEBOOK)

    assert "low-level diagnostic notebook" in source
    assert "This notebook is not the application workflow" in source
    assert "application-aligned walkthrough" in source


def _notebook_source(path: Path) -> str:
    notebook = json.loads(path.read_text())
    return "\n".join("".join(cell.get("source", [])) for cell in notebook.get("cells", []))
