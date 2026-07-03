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


def test_redemption_path_controls_separate_feedback_and_market_contagion() -> None:
    app_source = Path("app/streamlit_app.py").read_text(encoding="utf-8")
    service_source = Path("src/lmt_calibration/services/streamlit_mvp.py").read_text(
        encoding="utf-8"
    )

    controls_source = app_source.split("def _capture_redemption_path_controls", 1)[1].split(
        "def _capture_lmt_thresholds_from_sliders", 1
    )[0]

    assert "behavioural_feedback_enabled" not in app_source
    assert "path_behavioural_feedback_multiplier" in app_source
    assert "market_contagion_enabled" not in app_source
    assert "path_market_contagion_multiplier" in app_source
    assert "Redemption behaviour" in app_source
    assert "LMT Activation Decisions" in app_source
    assert "Market and liquidity stress" in app_source
    assert "lmt-seed-label" in app_source
    assert (
        controls_source.index("Redemption behaviour")
        < controls_source.index("Market and liquidity stress")
        < controls_source.index("LMT Activation Decisions")
    )
    assert controls_source.count("lmt-path-block-heading") == 3
    assert '"Behavioural feedback multiplier"' in controls_source
    assert '"Contagion ×"' in controls_source
    assert "Swing pricing" in controls_source
    assert "Gate" in controls_source
    assert "Suspension months" in controls_source
    assert '"Auto-apply LMTs when thresholds are breached"' in controls_source
    assert "Automatically activates LMTs in months where thresholds are breached" in controls_source
    assert "threshold breaches and activation months are shown separately" in controls_source
    assert "_sync_signal_linked_lmt_months(baseline_path_run, path_run)" in app_source
    assert "path_swing_signal_months" in controls_source
    assert "path_swing_applied_months" in controls_source
    assert "path_gate_signal_months" in controls_source
    assert "path_gate_applied_months" in controls_source
    assert "st.rerun()" in controls_source
    assert "suspension. Selecting a month simulates zero redemption payments" in app_source
    assert (
        "suspension_spacer_height = 7.5 if apply_lmts_in_all_signal_months else 22.5" in app_source
    )
    assert "suspension trigger" not in app_source.lower()
    assert "automatic suspension" not in app_source.lower()
    sidebar_group_rule = app_source.split(".lmt-sidebar-group-label {", 1)[1].split("}", 1)[0]
    threshold_group_rule = app_source.split(".lmt-threshold-subsection-title {", 1)[1].split(
        "}", 1
    )[0]
    assert "font-size: 11px" in sidebar_group_rule
    assert "font-size: 11px" in threshold_group_rule
    assert "text-transform: uppercase" in sidebar_group_rule
    path_block_rule = app_source.split(".lmt-path-block-heading {", 1)[1].split("}", 1)[0]
    assert "font-size: 11px" in path_block_rule
    assert "border-bottom: 2px solid $text" in path_block_rule
    assert "padding-bottom: 6px" in path_block_rule
    assert "margin: 0 0 0.75rem" in path_block_rule
    assert controls_source.count("st.container(key=") == 3
    assert 'key="path_redemption_behaviour_panel"' in controls_source
    assert 'key="path_market_liquidity_panel"' in controls_source
    assert 'key="path_lmt_activation_panel"' in controls_source
    assert "lmt-path-controls-lift" in controls_source
    assert '[data-testid="stColumn"]:has(.lmt-path-controls-lift)' in app_source
    assert "transform: translateY(-3px)" in app_source
    assert "lmt-governance-note" in controls_source
    assert "lmt-market-stress-hint" in controls_source
    market_hint_rule = app_source.split(".lmt-market-stress-hint {", 1)[1].split("}", 1)[0]
    assert "margin-top: -0.625rem" in market_hint_rule
    assert "color: $text" in app_source.split(".lmt-governance-note {", 1)[1].split("}", 1)[0]
    assert '[aria-disabled="true"] span' in app_source
    assert 'div[data-baseweb="select"] > div span' in app_source
    assert "-webkit-text-fill-color: $text" in app_source
    multiselect_tag_rule = app_source.split(
        '[data-testid="stMultiSelect"] [data-baseweb="tag"] {', 1
    )[1].split("}", 1)[0]
    assert "background: transparent" in multiselect_tag_rule
    assert "border: 0" in multiselect_tag_rule
    assert "box-shadow: none" in multiselect_tag_rule
    assert "st.columns([0.72, 0.28]" in app_source
    assert "st.columns([0.9, 10, 0.9]" in app_source
    assert "Applies after an LMT is applied. Increases next-month redemption demand." in app_source
    assert "It does not change liquidity costs, prices," in app_source
    assert "Applies after a market stress month. Increases next-month realised" in app_source
    assert "Higher values mean the fund must sell more assets" in app_source
    assert "st.toggle(" not in controls_source
    assert "st.checkbox(" in controls_source
    assert '[0.70, 0.30], gap="small", vertical_alignment="top"' in controls_source
    assert 'key="path_random_seed"' in controls_source
    assert 'label_visibility="collapsed"' in controls_source
    assert ".st-key-path_random_seed button" in app_source
    assert "height: 30px !important" in app_source
    assert "width=80" in controls_source
    assert "max_value=15.0" in app_source
    assert "value=15.0" in app_source
    assert controls_source.count('label_visibility="collapsed"') == 5
    assert "if selected_market_id is not None:" in controls_source
    assert "Turn on behavioural feedback to edit this multiplier." not in app_source
    assert (
        "Select a stressed market scenario to configure the stress month and the market contagion multiplier for the following month."
        in app_source
    )
    assert "Use 0 for no" not in app_source
    assert "behavioural_feedback_enabled" not in service_source
    assert "market_contagion_enabled" not in service_source
    assert "market_contagion_liquidity_cost_multiplier" in service_source


def test_redemption_path_theme_styles_follow_the_app_theme() -> None:
    """Keep path controls and reconciliation tables legible in both app themes."""
    app_source = Path("app/streamlit_app.py").read_text(encoding="utf-8")

    control_column_rule = app_source.split(
        '[data-testid="stColumn"]:has(.lmt-path-controls-lift) {', 1
    )[1].split("}", 1)[0]
    control_content_rule = app_source.split(
        '[data-testid="stColumn"]:has(.lmt-path-controls-lift) > [data-testid="stVerticalBlock"] {',
        1,
    )[1].split("}", 1)[0]
    card_rule = app_source.split(".st-key-path_redemption_behaviour_panel,", 1)[1].split("}", 1)[0]
    light_subgroup_rule = app_source.split(".lmt-path-subgroup-label {", 2)[2].split("}", 1)[0]

    assert "height: auto" in control_content_rule
    assert "background: $surface" in card_rule
    assert "margin-bottom: 5px" in card_rule
    assert "transform: translateY(-3px)" in control_column_rule
    assert "color: #000000" in light_subgroup_rule
    assert 'class="cash-table-container {mode_class}"' in app_source
    assert 'class="nav-table-container {mode_class}"' in app_source
    assert ".light-theme.cash-table-container" in app_source
    assert ".light-theme.nav-table-container" in app_source
    assert "_render_cash_account_diagnostics(run, dark_mode=dark_mode)" in app_source
    assert "_render_nav_reconciliation_diagnostics(run, dark_mode=dark_mode)" in app_source
    assert '[data-testid="stExpanderDetails"]' in app_source
    assert "margin: 0;" in app_source
    assert "height=360" not in app_source
    assert "height=400" not in app_source
    assert "height=cash_table_height" in app_source
    assert "height=nav_table_height" in app_source
    assert "margin-top: -20px" in app_source
    assert "margin: 12px 0 6px" in app_source
    assert "align-items: flex-end" in app_source
    assert "margin-bottom: -1px" in app_source
    assert '[data-baseweb="tab-border"]' in app_source
    assert '"Fixed redemption axis (60% NAV)"' in app_source
    assert "fixed_redemption_axis=fixed_redemption_axis" in app_source
    assert '[0.68, 0.32], vertical_alignment="bottom"' in app_source
    assert "<div class='lmt-section-h'>12-month redemption path</div>" in app_source
    assert ".st-key-path_fixed_redemption_axis" in app_source
    fixed_axis_rule = app_source.split(".st-key-path_fixed_redemption_axis {", 1)[1].split("}", 1)[
        0
    ]
    assert "transform: translateY(12px)" in fixed_axis_rule
    assert '[0.42, 0.58], gap="small", vertical_alignment="bottom"' in app_source
    assert "white-space: nowrap !important" in app_source
    assert ".st-key-path_behavioural_feedback_multiplier" in app_source
    random_seed_rule = app_source.split(".st-key-path_random_seed {", 1)[1].split("}", 1)[0]
    assert "margin-left: auto" in random_seed_rule
    assert "width: 80px" in random_seed_rule


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
            "liquidity_shortfall": Decimal("400000"),
            "realised_liquidity_cost": Decimal("25000"),
            "liquid_nav": Decimal("19000000"),
            "illiquid_nav": Decimal("81000000"),
        },
        {
            "month": 2,
            "paid_redemption": Decimal("0"),
            "deferred_redemption": Decimal("0"),
            "cumulative_backlog": Decimal("0"),
            "liquidity_shortfall": Decimal("0"),
            "realised_liquidity_cost": Decimal("75000"),
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
    assert any(patch.get_height() < 0 for patch in fig1.axes[0].patches)
    assert "Liquidity shortfall (unfunded)" in [
        text.get_text() for text in fig1.axes[0].get_legend().get_texts()
    ]

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
            "swing_signal": True,
            "swing_applied": False,
            "gate_signal": False,
            "gate_applied": False,
            "suspension_applied": False,
        },
        {
            "month": 2,
            "swing_signal": False,
            "swing_applied": False,
            "gate_signal": True,
            "gate_applied": True,
            "suspension_applied": True,
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
    assert fig3.axes[0].texts[0].get_text() == "LMT threshold breaches and activations"
    matrix_legend = fig3.axes[0].get_legend()
    assert matrix_legend is not None
    assert [text.get_text() for text in matrix_legend.get_texts()] == [
        "signal",
        "applied",
        "suspended",
    ]
    assert matrix_legend._ncols == 3
    assert matrix_legend.get_bbox_to_anchor()._bbox.x1 == 1.0
    assert {handle.get_markeredgecolor() for handle in matrix_legend.legend_handles} == {"#f5793b"}
    assert [label.get_text() for label in fig3.axes[0].get_yticklabels()] == [
        "Swing",
        "Gate",
        "Suspend",
    ]
    marker_sizes = {
        float(size) for collection in fig3.axes[0].collections for size in collection.get_sizes()
    }
    assert 24.0 in marker_sizes
    assert 20.0 in marker_sizes
    assert any(len(collection.get_facecolors()) == 0 for collection in fig3.axes[0].collections)

    fig4 = plot_redemption_and_nav_combined(
        monthly_rows=monthly_rows,
        initial_nav=initial_nav,
        fund_name="TestFund",
        as_of_date="2026-01-15",
        dark_mode=False,
    )
    assert fig4.axes[0].get_facecolor()[:3] == (1.0, 1.0, 1.0)
    assert fig4.axes[0].get_ylim()[1] == 60.0
    assert fig4.axes[0].get_ylim()[0] == 0
    assert all(patch.get_height() >= 0 for patch in fig4.axes[0].patches)
    assert list(fig4.axes[0].lines[0].get_ydata()) == [0.25, 0.0]
    legend = fig4.axes[0].get_legend()
    assert legend is not None
    assert legend._ncols == 3
    assert {text.get_text() for text in legend.get_texts()} == {
        "Paid",
        "Deferred",
        "Backlog",
    }
    assert legend.get_bbox_to_anchor()._bbox.y0 > 1.0
    assert fig4.axes[1].get_title(loc="left") == "Liquidity shortfall (unfunded)"
    assert fig4.axes[1].get_ylim()[0] < 0
    assert fig4.axes[1].get_ylim()[1] == 0
    assert any(patch.get_height() < 0 for patch in fig4.axes[1].patches)
    assert fig4.axes[2].get_title(loc="left") == "Realised liquidity cost"
    assert fig4.axes[2].lines
    assert fig4.get_figheight() == pytest.approx(5.73)
    assert fig4.axes[-1].get_position().height / fig4.axes[
        0
    ].get_position().height == pytest.approx(0.5625)

    fig4_auto_axis = plot_redemption_and_nav_combined(
        monthly_rows=monthly_rows,
        initial_nav=initial_nav,
        fund_name="TestFund",
        as_of_date="2026-01-15",
        dark_mode=False,
        fixed_redemption_axis=False,
    )
    assert 0 < fig4_auto_axis.axes[0].get_ylim()[1] < 60.0

    fig5 = plot_lmt_matrix(
        lmt_rows=lmt_rows,
        fund_name="TestFund",
        as_of_date="2026-01-15",
        dark_mode=False,
    )
    assert fig5.axes[0].get_facecolor()[:3] == (1.0, 1.0, 1.0)


def test_redemption_chart_omits_zero_liquidity_shortfall_series() -> None:
    import matplotlib

    matplotlib.use("Agg")

    sys.path.insert(0, "app")
    from chart_matplotlib import plot_redemption_and_nav_combined

    monthly_rows = [
        {
            "month": 1,
            "paid_redemption": Decimal("1200000"),
            "deferred_redemption": Decimal("0"),
            "cumulative_backlog": Decimal("0"),
            "liquidity_shortfall": Decimal("0"),
            "realised_liquidity_cost": Decimal("0"),
            "liquid_nav": Decimal("19000000"),
            "illiquid_nav": Decimal("81000000"),
        }
    ]

    figure = plot_redemption_and_nav_combined(
        monthly_rows=monthly_rows,
        initial_nav=Decimal("100000000"),
        dark_mode=False,
    )

    assert figure.axes[0].get_ylim()[0] == 0
    assert len(figure.axes) == 3
    assert figure.get_figheight() == pytest.approx(4.92)
    assert len(figure.axes[0].lines) == 0
    assert "Backlog" not in [text.get_text() for text in figure.axes[0].get_legend().get_texts()]
    assert all(
        axis.get_title(loc="left") != "Liquidity shortfall (unfunded)" for axis in figure.axes
    )
    assert "Liquidity shortfall (unfunded)" not in [
        text.get_text() for text in figure.axes[0].get_legend().get_texts()
    ]


def test_redemption_chart_omits_zero_backlog_series() -> None:
    import matplotlib

    matplotlib.use("Agg")

    sys.path.insert(0, "app")
    from chart_matplotlib import plot_redemption_and_nav_combined

    monthly_rows_no_backlog = [
        {
            "month": i,
            "paid_redemption": Decimal("1200000") if i == 1 else Decimal("100000"),
            "deferred_redemption": Decimal("0"),
            "cumulative_backlog": Decimal("0"),
            "liquidity_shortfall": Decimal("0"),
            "realised_liquidity_cost": Decimal("0"),
            "liquid_nav": Decimal("19000000"),
            "illiquid_nav": Decimal("81000000"),
        }
        for i in range(1, 13)
    ]

    figure = plot_redemption_and_nav_combined(
        monthly_rows=monthly_rows_no_backlog,
        initial_nav=Decimal("100000000"),
        dark_mode=False,
    )

    legend_texts = [text.get_text() for text in figure.axes[0].get_legend().get_texts()]
    assert "Backlog" not in legend_texts
    assert set(legend_texts) == {"Paid", "Deferred"}
    assert figure.axes[0].get_legend()._ncols == 2

    monthly_rows_with_backlog = [
        {
            "month": i,
            "paid_redemption": Decimal("1200000") if i == 1 else Decimal("100000"),
            "deferred_redemption": Decimal("0"),
            "cumulative_backlog": Decimal("250000") if i == 1 else Decimal("0"),
            "liquidity_shortfall": Decimal("0"),
            "realised_liquidity_cost": Decimal("0"),
            "liquid_nav": Decimal("19000000"),
            "illiquid_nav": Decimal("81000000"),
        }
        for i in range(1, 13)
    ]

    figure2 = plot_redemption_and_nav_combined(
        monthly_rows=monthly_rows_with_backlog,
        initial_nav=Decimal("100000000"),
        dark_mode=False,
    )

    legend_texts2 = [text.get_text() for text in figure2.axes[0].get_legend().get_texts()]
    assert "Backlog" in legend_texts2
    assert set(legend_texts2) == {"Paid", "Deferred", "Backlog"}
    assert figure2.axes[0].get_legend()._ncols == 3
