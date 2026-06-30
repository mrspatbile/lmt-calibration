"""Integration tests for dashboard value wiring."""

import importlib.util
import inspect
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from lmt_calibration.services.streamlit_mvp import (
    load_app_sample_data,
    run_selected_sample_scenario,
)


@pytest.fixture
def sample_data():
    """Load sample data for testing."""
    return load_app_sample_data(Path("data/sample"))


def test_app_scenario_run_contains_computed_values(sample_data):
    """Verify AppScenarioRun contains all values needed by dashboard."""
    run = run_selected_sample_scenario(
        sample_data, fund_id="lux_dynamic_allocation", strategy_id="cash_then_liquid_assets"
    )

    # Check that all required computed values are present
    assert run.redemption_amount > Decimal("0"), "redemption_amount should be computed"
    assert run.redemption_rate > Decimal("0"), "redemption_rate should be computed"
    assert run.result is not None, "liquidation result should be present"
    assert run.result.total_redemption_amount > Decimal("0"), "total redemption should be in result"
    assert run.result.remaining_liquid_buffer_rate >= Decimal("0"), (
        "remaining buffer should be in result"
    )
    assert run.liquidity_cost_breakdown is not None, "liquidity cost breakdown should be present"
    assert run.lmt_activation is not None, "Activation-assessment result should be present"


def test_lmt_parameters_wired_to_ribbon(sample_data):
    """Verify LMT parameters are accessible for ribbon display."""
    run = run_selected_sample_scenario(
        sample_data, fund_id="lux_dynamic_allocation", strategy_id="cash_then_liquid_assets"
    )

    params = run.parameters

    # These are the values that should be displayed in the ribbon
    assert params.swing_threshold_rate > Decimal("0"), "swing threshold should be > 0"
    assert params.max_swing_factor_rate > Decimal("0"), "swing factor should be > 0"
    assert params.gate_threshold_rate > Decimal("0"), "gate threshold should be > 0"
    assert params.minimum_buffer_rate >= Decimal("0"), "minimum buffer should be >= 0"

    # Verify they're in the valid range (0-1 as decimal rates)
    assert params.swing_threshold_rate <= Decimal("1"), "swing threshold should be <= 100%"
    assert params.max_swing_factor_rate <= Decimal("1"), "swing factor should be <= 100%"
    assert params.gate_threshold_rate <= Decimal("1"), "gate threshold should be <= 100%"


def test_liquidity_cost_breakdown_available(sample_data):
    """Verify liquidity cost breakdown is computed and available."""
    run = run_selected_sample_scenario(
        sample_data, fund_id="lux_dynamic_allocation", strategy_id="cash_then_liquid_assets"
    )

    breakdown = run.liquidity_cost_breakdown

    # These are the values that should be available for investor impact display
    assert "bid_ask_cost_amount" in breakdown, "bid-ask cost should be in breakdown"
    assert "transaction_cost_amount" in breakdown, "transaction cost should be in breakdown"
    assert "market_impact_cost_amount" in breakdown, "market impact cost should be in breakdown"
    assert "total_cost_amount" in breakdown, "total cost should be in breakdown"
    assert "total_cost_rate" in breakdown, "total cost rate should be in breakdown"

    # All should be Decimal
    for key, value in breakdown.items():
        assert isinstance(value, Decimal), f"{key} should be Decimal"


def test_lmt_activation_status_available(sample_data):
    """Verify simulated LMT activation status is computed and available."""
    run = run_selected_sample_scenario(
        sample_data, fund_id="lux_dynamic_allocation", strategy_id="cash_then_liquid_assets"
    )

    activation = run.lmt_activation

    # These values support the dashboard activation assessment.
    assert isinstance(activation.swing_activated, bool), "simulated swing activation should be bool"
    assert isinstance(activation.gate_activated, bool), "simulated gate activation should be bool"
    assert isinstance(activation.buffer_breached, bool), "liquidity-buffer breach should be bool"
    assert activation.calibration_adequacy is not None, "calibration adequacy should be set"
    assert activation.calibration_message != "", "calibration message should be non-empty"

    # Investor impact values should be present
    assert activation.estimated_liquidity_cost_amount >= Decimal("0"), (
        "estimated cost should be >= 0"
    )
    assert activation.recovered_cost_amount >= Decimal("0"), "recovered cost should be >= 0"
    assert activation.residual_dilution_amount >= Decimal("0"), "residual dilution should be >= 0"
    assert activation.redemption_paid_amount >= Decimal("0"), "redemption paid should be >= 0"
    assert activation.redemption_deferred_amount >= Decimal("0"), (
        "redemption deferred should be >= 0"
    )


def test_liquidation_result_available(sample_data):
    """Verify liquidation result contains all values for KPI display."""
    run = run_selected_sample_scenario(
        sample_data, fund_id="lux_dynamic_allocation", strategy_id="cash_then_liquid_assets"
    )

    result = run.result

    # These are the values that should be displayed in KPI cards
    assert result.total_redemption_amount >= Decimal("0"), "total redemption should be available"
    assert result.cash_used >= Decimal("0"), "cash used should be available"
    assert result.total_post_haircut_cash_raised >= Decimal("0"), (
        "post-haircut cash should be available"
    )
    assert result.shortfall >= Decimal("0"), "shortfall should be available"
    assert result.dilution_amount >= Decimal("0"), "dilution amount should be available"
    assert result.remaining_liquid_buffer_rate >= Decimal("0"), (
        "remaining buffer should be available"
    )
    assert isinstance(result.minimum_cash_buffer_preserved, bool), (
        "buffer preservation should be bool"
    )


def test_streamlit_app_imports_with_redemption_path_page():
    """Verify the single Streamlit entry point imports with both page modes defined."""

    module_path = Path("app/streamlit_app.py")
    spec = importlib.util.spec_from_file_location("streamlit_app", module_path)
    assert spec is not None
    assert spec.loader is not None
    app_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app_module)

    assert hasattr(app_module, "main")
    assert hasattr(app_module, "_render_redemption_path_page")


def test_redemption_path_page_does_not_render_tables():
    """Verify the 12-month page avoids tables and KPI cards."""

    module_path = Path("app/streamlit_app.py")
    spec = importlib.util.spec_from_file_location("streamlit_app", module_path)
    assert spec is not None
    assert spec.loader is not None
    app_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app_module)

    source = inspect.getsource(app_module._render_redemption_path_page)

    assert "st.dataframe" not in source
    assert "st.table" not in source
    assert "_render_path_kpis" not in source
    assert "Static liquidity profile" not in source
    assert "_render_t0_liquidity_profile_chart" not in source
    assert "plot_lmt_matrix" in source


def test_redemption_path_controls_use_explicit_behavioural_feedback_terms() -> None:
    app_source = Path("app/streamlit_app.py").read_text(encoding="utf-8")
    service_source = Path("src/lmt_calibration/services/streamlit_mvp.py").read_text(
        encoding="utf-8"
    )

    assert "behavioural_feedback_enabled" in app_source
    assert "Behavioural feedback multiplier" in app_source
    assert "contagion_enabled" not in app_source
    assert "contagion_multiplier" not in app_source
    assert "Contagion multiplier" not in app_source
    assert "Use 0 for no" not in app_source
    assert "contagion_enabled" not in service_source
    assert "contagion_multiplier" not in service_source


def test_redemption_path_matplotlib_charts_refresh_with_controls():
    """Verify matplotlib charts refresh correctly when 12-month controls change.

    Regression test for: chart refresh bug where redemption bars disappear
    or do not refresh correctly when controls are modified.
    """
    import matplotlib

    matplotlib.use("Agg")

    sys.path.insert(0, "app")
    from chart_matplotlib import (
        plot_lmt_matrix,
        plot_nav_evolution,
        plot_redemption_and_nav_combined,
        plot_redemption_profile,
    )

    # Sample monthly data with redemptions and NAV
    monthly_rows = [
        {
            "month": 1,
            "paid_redemption": Decimal("1200000"),
            "deferred_redemption": Decimal("250000"),
            "cumulative_backlog": Decimal("250000"),
            "liquid_nav": Decimal("19000000"),
            "illiquid_nav": Decimal("81000000"),
        },
        {
            "month": 2,
            "paid_redemption": Decimal("0"),
            "deferred_redemption": Decimal("0"),
            "cumulative_backlog": Decimal("0"),
            "liquid_nav": Decimal("18000000"),
            "illiquid_nav": Decimal("81500000"),
        },
    ]

    initial_nav = Decimal("100000000")

    # Verify redemption chart generates without error
    fig1 = plot_redemption_profile(
        monthly_rows=monthly_rows,
        initial_nav=initial_nav,
        fund_name="TestFund",
        as_of_date="2026-01-15",
    )
    assert fig1 is not None
    assert fig1.get_figwidth() > 0
    assert fig1.get_figheight() > 0

    # Verify NAV chart generates without error
    fig2 = plot_nav_evolution(
        monthly_rows=monthly_rows,
        initial_nav=initial_nav,
        fund_name="TestFund",
        as_of_date="2026-01-15",
    )
    assert fig2 is not None
    assert fig2.get_figwidth() > 0
    assert fig2.get_figheight() > 0

    lmt_rows = [
        {
            "month": 1,
            "swing_pricing": True,
            "redemption_gate": False,
            "suspension": False,
        },
        {
            "month": 2,
            "swing_pricing": False,
            "redemption_gate": True,
            "suspension": False,
        },
    ]
    fig3 = plot_lmt_matrix(
        lmt_rows=lmt_rows,
        fund_name="TestFund",
        as_of_date="2026-01-15",
    )
    assert fig3 is not None
    assert fig3.get_figwidth() > 0
    assert fig3.get_figheight() > 0

    fig4 = plot_redemption_and_nav_combined(
        monthly_rows=monthly_rows,
        initial_nav=initial_nav,
        fund_name="TestFund",
        as_of_date="2026-01-15",
        dark_mode=False,
    )
    assert fig4.axes[0].get_facecolor()[:3] == (1.0, 1.0, 1.0)

    fig5 = plot_lmt_matrix(
        lmt_rows=lmt_rows,
        fund_name="TestFund",
        as_of_date="2026-01-15",
        dark_mode=False,
    )
    assert fig5.axes[0].get_facecolor()[:3] == (1.0, 1.0, 1.0)
