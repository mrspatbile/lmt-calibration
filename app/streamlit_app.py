"""Alternative Streamlit dashboard for Liquidity Management Tools Calibration."""

import sys
from dataclasses import dataclass
from decimal import Decimal
from html import escape
from pathlib import Path
from string import Template

import streamlit as st

from lmt_calibration.domain import AssetPosition, LmtParameters
from lmt_calibration.services import (
    AppSampleData,
    AppScenarioRun,
    ScenarioMatrixOutcome,
    build_historical_result_rows,
    build_scenario_matrix_outcome,
    fund_positions,
    load_app_sample_data,
    run_scenario_across_market_conditions,
    run_selected_sample_scenario,
)

# Add app directory to path for content import
_APP_DIR = Path(__file__).resolve().parent
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

import content  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DATA_DIR = PROJECT_ROOT / "data" / "sample"
ZERO = Decimal("0")
ONE_HUNDRED = Decimal("100")


@dataclass(frozen=True)
class StageResult:
    """One presentation row for one scenario column."""

    label: str
    value: str
    badge_text: str
    detail_label: str = ""
    explanation: str = ""
    badge_tone: str = "neutral"


@dataclass(frozen=True)
class ScenarioResult:
    """Presentation summary for one historical scenario column."""

    name: str
    short_name: str
    stages: list[StageResult]


@dataclass(frozen=True)
class Kpi:
    """Top-line presentation KPI."""

    label: str
    value: str
    note: str = ""
    tone: str = "neutral"


@dataclass(frozen=True)
class FundCharacteristics:
    """Sidebar fund facts."""

    base_currency: str
    dealing: str
    notice: str
    settlement: str
    investor_classes: int
    positions: int


@dataclass(frozen=True)
class DashboardResult:
    """Presentation-facing dashboard data."""

    fund_name: str
    tags: list[str]
    characteristics: FundCharacteristics
    kpis: list[Kpi]
    scenarios: list[ScenarioResult]


FONT_STACK = (
    '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
)

DARK_THEME = {
    "font": FONT_STACK,
    "bg": "#0e1117",
    "surface": "#171b22",
    "tertiary": "#21262d",
    "border": "rgba(255,255,255,0.25)",
    "text": "#e8eaed",
    "muted": "#9aa0a6",
    "accent": "#5eead4",
    "neutral_bg": "rgba(255,255,255,0.05)",
    "neutral_fg": "#9aa0a6",
    "info_bg": "rgba(85,175,255,0.10)",
    "info_fg": "#66d9ff",
    "success_bg": "rgba(76,215,150,0.10)",
    "success_fg": "#66ffaa",
    "danger_bg": "rgba(255,100,100,0.10)",
    "danger_fg": "#ff8080",
    "warning_bg": "rgba(255,180,50,0.10)",
    "warning_fg": "#ffcc66",
    "guidance_bg": "rgba(255,255,255,0.04)",
    "guidance_border": "rgba(255,255,255,0.15)",
    "group_label": "#B8C3CF",
    "secondary_text": "#A5AFBA",
    "matrix_title": "#F2F4F6",
    "metric_label": "#9AA5B1",
    "scenario_header": "#7FB3D5",
}

LIGHT_THEME = {
    "font": FONT_STACK,
    "bg": "#ffffff",
    "surface": "#f6f7f9",
    "tertiary": "#eceef1",
    "border": "rgba(0,0,0,0.15)",
    "text": "#1a1d21",
    "muted": "#5f6368",
    "accent": "#0f6e56",
    "neutral_bg": "rgba(0,0,0,0.04)",
    "neutral_fg": "#5f5e5a",
    "info_bg": "rgba(0,51,255,0.08)",
    "info_fg": "#0033ff",
    "success_bg": "rgba(0,102,51,0.08)",
    "success_fg": "#006633",
    "danger_bg": "rgba(255,0,0,0.08)",
    "danger_fg": "#ff0000",
    "warning_bg": "rgba(204,82,0,0.08)",
    "warning_fg": "#cc5200",
    "guidance_bg": "#f5f5f5",
    "guidance_border": "#d1d5db",
    "group_label": "#4B5563",
    "secondary_text": "#5F6368",
    "matrix_title": "#1A1D21",
    "metric_label": "#5F6368",
    "scenario_header": "#2F6F9F",
}

CSS = Template(
    """
<style>
.stApp { background: $bg; }
html, body, [class*="css"] { font-family: $font; }
.block-container { padding-top: 2rem; padding-bottom: 3rem; }

section[data-testid="stSidebar"] {
  background: $surface;
  border-right: 1px solid $border;
}
section[data-testid="stSidebar"] *,
section[data-testid="stSidebar"] label,
[data-testid="stToggle"] label,
[data-testid="stSelectbox"] label {
  color: $text !important;
}
[data-testid="stToggle"] div[role="switch"] {
  background: $tertiary;
  border: 1px solid $border;
}
[data-testid="stToggle"] div[role="switch"][aria-checked="true"] {
  background: $accent;
  border-color: $accent;
}
[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
  background: $tertiary;
  border-color: $border;
  color: $text;
}
[data-testid="stSelectbox"] div[data-baseweb="select"] span,
[data-testid="stSelectbox"] div[data-baseweb="select"] svg {
  color: $text;
  fill: $text;
}
[role="radiogroup"] {
  background: $tertiary;
  border: 1px solid $border;
  border-radius: 20px;
  display: flex;
  gap: 2px;
  padding: 2px;
  margin-bottom: 14px;
}
div[data-testid="stRadio"] {
  margin-top: 45px;
}
[role="radio"] {
  flex: 1;
  border-radius: 18px;
  padding: 6px 12px !important;
  font-size: 0.85rem;
  font-weight: 700;
  text-align: center;
  color: $muted !important;
  transition: all 0.2s ease;
}
[role="radio"][aria-checked="true"] {
  background: $accent !important;
  color: $bg !important;
}
div[data-baseweb="popover"],
ul[data-baseweb="menu"],
[role="listbox"] {
  background: $surface;
  border-color: $border;
  color: $text;
}
ul[data-baseweb="menu"] li,
[role="option"] {
  background: $surface;
  color: $text;
}
ul[data-baseweb="menu"] li:hover,
[role="option"]:hover {
  background: $tertiary;
  color: $text;
}

.lmt-sidebar-title {
  color: $text;
  font-size: 1.08rem;
  font-weight: 800;
  margin: 0;
}
.lmt-sidebar-header {
  align-items: baseline;
  display: flex;
  gap: 7px;
  margin: 0 0 14px;
}
.lmt-sidebar-separator {
  color: $muted !important;
  font-size: 0.72rem;
  font-weight: 400;
}
.lmt-sidebar-header .lmt-about-link {
  background: none;
  border: 0;
  box-shadow: none;
  color: $muted !important;
  cursor: pointer;
  font-size: 0.72rem;
  font-weight: 400;
  padding: 0;
  text-decoration: none;
}
.lmt-sidebar-header .lmt-about-link:hover,
.lmt-sidebar-header .lmt-about-link:focus-visible {
  color: $accent !important;
  text-decoration: underline;
}
.lmt-theme-toggle {
  background: $tertiary;
  border: 1px solid $border;
  border-radius: 20px;
  display: flex;
  gap: 2px;
  margin-bottom: 14px;
  padding: 2px;
}
.lmt-theme-option {
  color: $muted;
  flex: 1;
  font-size: 0.85rem;
  font-weight: 700;
  padding: 6px 12px;
  text-align: center;
  white-space: nowrap;
  border-radius: 18px;
  transition: all 0.2s ease;
  cursor: pointer;
}
.lmt-theme-option.active {
  background: $accent;
  color: $bg;
}
.lmt-eyebrow {
  color: $text-secondary;
  font-size: 13px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin: 0 0 4px;
}
.lmt-header-copy {
  display: flex;
  flex-direction: column;
}
h1.lmt-title {
  color: $text !important;
  font-size: 40px;
  font-weight: 760;
  line-height: 1.15;
  margin: 0 !important;
}
.lmt-subtitle {
  color: $secondary_text;
  font-size: 16px;
  font-weight: 400;
  line-height: 1.3;
  margin: -8px 0 6px !important;
}
.lmt-tags {
  display: flex;
  gap: 6px;
  margin: 8px 0 0;
}
.lmt-tag {
  display: inline-block;
  background: $bg-secondary;
  color: $text-secondary;
  font-size: 11px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 3px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.lmt-section-h {
  color: $text;
  font-size: 18px;
  font-weight: 700;
  margin: 8px 0 4px;
}
.lmt-section-d {
  color: $secondary_text;
  font-size: 14px;
  font-weight: 400;
  line-height: 1.3;
  margin: 0 0 16px;
}
.lmt-kpis {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  margin-bottom: 22px;
}
.lmt-kpi {
  background: $surface;
  border: 1px solid $border;
  border-radius: 10px;
  padding: 12px 14px;
}
.lmt-kpi .k-label {
  color: $metric_label;
  font-size: 12px;
  font-weight: 500;
  margin-bottom: 4px;
}
.lmt-kpi .k-value {
  color: $text;
  font-size: 21px;
  font-weight: 700;
}
.lmt-kpi .k-note {
  color: $secondary_text;
  font-size: 12px;
  font-weight: 400;
  line-height: 1.3;
  margin-top: 2px;
}
.lmt-matrix-wrap {
  border: 1px solid $border;
  border-radius: 12px;
  overflow: hidden;
}
table.lmt-matrix {
  border-collapse: collapse;
  font-size: 13px;
  width: 100%;
}
table.lmt-matrix thead th {
  background: $surface;
  color: $scenario_header;
  font-weight: 700;
  padding: 4px 14px 8px 14px;
  text-align: right;
  border-bottom: 1px solid rgba(111, 168, 220, 0.3);
}
table.lmt-matrix thead th:first-child {
  text-align: right;
}
table.lmt-matrix tbody td {
  background: $surface;
  padding: 9px 14px;
  vertical-align: top;
}
table.lmt-matrix tbody tr {
  border-bottom: 2px solid $border;
}
table.lmt-matrix tbody tr:last-child {
  border-bottom: 2px solid $border;
}
table.lmt-matrix thead th {
  font-weight: 700;
}
table.lmt-matrix thead th > div > div:last-child {
  color: $scenario_header !important;
  font-weight: 700;
}
table.lmt-matrix .stage-col {
  text-align: right;
  width: 25%;
  padding-right: 20px;
}
table.lmt-matrix .stage-title {
  color: $matrix_title;
  font-weight: 600;
  font-size: 15px;
  display: block;
  margin-bottom: 4px;
}
table.lmt-matrix .stage-explanation {
  color: $secondary_text;
  font-size: 12px;
  font-weight: 400;
  line-height: 1.3;
  display: block;
}
table.lmt-matrix .cell-label {
  color: $metric_label;
  font-size: 11px;
  font-weight: 500;
  display: block;
  margin-top: 6px;
  text-align: right;
}
table.lmt-matrix .val {
  color: $text;
  font-weight: 700;
  white-space: nowrap;
  text-align: right;
  display: block;
  margin-bottom: 4px;
}
table.lmt-matrix .cell-wrapper {
  text-align: right;
}
.lmt-badge {
  border: 1px solid;
  border-radius: 8px;
  display: inline-block;
  font-size: 11px;
  line-height: 1.5;
  margin-top: 3px;
  padding: 2px 8px;
}
.tone-neutral { background: $neutral_bg; color: $neutral_fg; }
.tone-info { background: $info_bg; color: $info_fg; }
.tone-success { background: $success_bg; color: $success_fg; }
.tone-danger { background: $danger_bg; color: $danger_fg; }
.tone-warning { background: $warning_bg; color: $warning_fg; }
.lmt-badge.tone-neutral { border-color: rgba(154,160,166,0.5); }
.lmt-badge.tone-info { border-color: rgba(102,217,255,0.5); }
.lmt-badge.tone-success { border-color: rgba(102,255,170,0.5); }
.lmt-badge.tone-danger { border-color: rgba(255,128,128,0.5); }
.lmt-badge.tone-warning { border-color: rgba(255,204,102,0.5); }
.lmt-fund-card {
  background: $surface;
  border: 1px solid $border;
  border-radius: 10px;
  margin: 16px 0 14px;
  padding: 14px 16px;
}
.lmt-fund-card .fc-eyebrow {
  color: $muted;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .04em;
  margin-bottom: 4px;
  text-transform: uppercase;
}
.lmt-fund-card .fc-name {
  color: $text;
  font-size: 15px;
  font-weight: 700;
  line-height: 1.25;
  margin-bottom: 10px;
}
.lmt-fund-card .fc-row {
  display: flex;
  font-size: 13px;
  justify-content: space-between;
  padding: 5px 0;
}
.lmt-fund-card .fc-k { color: $muted; }
.lmt-fund-card .fc-v {
  color: $text;
  font-weight: 700;
  padding-left: 10px;
  text-align: right;
}
.lmt-note {
  color: $secondary_text;
  font-size: 12px;
  font-weight: 400;
  line-height: 1.3;
  margin-top: 12px;
}
.lmt-thresholds-section {
  margin-top: 16px;
  padding-top: 0;
}
.lmt-threshold-subsection {
  margin-bottom: 18px;
}
.lmt-threshold-subsection-title {
  color: $group_label;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: .06em;
  margin-bottom: 3px;
  padding-bottom: 6px;
  border-bottom: 2px solid $text;
  text-transform: uppercase;
  text-align: left;
  display: block;
}
.lmt-threshold-item {
  margin-bottom: 16px;
}
[data-testid="stSlider"] {
  margin: 0 !important;
}
[data-testid="stSlider"] > div > div > div:nth-child(1),
[data-testid="stSlider"] > div > div > div:nth-child(2) {
  font-size: 10px !important;
}
.lmt-config-ribbon {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  margin: 6px 0;
  border-top: 1px solid $border;
  border-bottom: 1px solid $border;
}
.lmt-config-label-text {
  color: $muted;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  white-space: nowrap;
  padding-right: 8px;
  border-right: 1px solid $border;
}
.lmt-config-chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.lmt-chip {
  background: rgba($accent, 0.08);
  border: 1px solid rgba($accent, 0.3);
  border-radius: 6px;
  padding: 4px 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 80px;
  text-align: center;
}
.lmt-chip-label {
  color: $muted;
  font-size: 10px;
  font-weight: 600;
  margin-bottom: 1px;
  white-space: nowrap;
}
.lmt-chip-value {
  color: $accent;
  font-size: 13px;
  font-weight: 700;
}
.lmt-banner-heading {
  align-items: center;
  color: $group_label;
  display: flex;
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 600;
  gap: 5px;
  letter-spacing: .06em;
  line-height: 1.3;
  text-transform: uppercase;
  width: 120px;
}
.lmt-help-icon {
  align-items: center;
  border: 1px solid #9ca3af;
  border-radius: 50%;
  color: #9ca3af;
  cursor: help;
  display: inline-flex;
  flex: 0 0 15px;
  font-size: 10px;
  height: 15px;
  justify-content: center;
  line-height: 1;
  position: relative;
  text-transform: none;
  width: 15px;
}
.lmt-help-icon::after {
  background: $surface;
  border: 1px solid $border;
  border-radius: 4px;
  color: $text;
  content: attr(data-tooltip);
  font-size: 11px;
  font-weight: 500;
  left: 0;
  line-height: 1.4;
  opacity: 0;
  padding: 7px 9px;
  pointer-events: none;
  position: absolute;
  text-align: left;
  text-transform: none;
  top: calc(100% + 7px);
  transition: opacity 0.15s ease;
  visibility: hidden;
  white-space: normal;
  width: 230px;
  z-index: 20;
}
.lmt-help-icon:hover::after,
.lmt-help-icon:focus::after {
  opacity: 1;
  visibility: visible;
}

.lmt-guidance-container {
  background: $guidance_bg;
  border: 1px solid $guidance_border;
}
.lmt-guidance-container div[style*="text-transform:uppercase"] {
  color: $group_label !important;
  font-weight: 600 !important;
  letter-spacing: .06em !important;
}
.lmt-guidance-container div[style*="font-size:8px"] {
  color: $secondary_text !important;
  font-weight: 400 !important;
  line-height: 1.3 !important;
}
.lmt-guidance-container > div > div:first-child > div:nth-child(2) {
  color: $secondary_text !important;
  font-weight: 400 !important;
  line-height: 1.3 !important;
}
.lmt-config-panel div[style*="text-transform:uppercase"] {
  color: $metric_label !important;
  font-weight: 500 !important;
}
.lmt-sidebar-group-label {
  color: $group_label;
  font-size: 9px;
  font-weight: 600;
  letter-spacing: .06em;
  margin-bottom: 3px;
  text-transform: uppercase;
}
</style>
"""
)

LIGHT_MODE_CSS = """
<style>
.lmt-subtitle {
  color: #374151 !important;
}
[role="radiogroup"] [role="radio"],
[role="radiogroup"] [role="radio"] * {
  color: #000000 !important;
}
[data-testid="stRadio"] [role="radio"] *,
[data-testid="stRadio"] [role="radio"] p {
  color: #000000 !important;
  -webkit-text-fill-color: #000000 !important;
  opacity: 1 !important;
}
[data-testid="stRadio"] label[data-baseweb="radio"],
[data-testid="stRadio"] label[data-baseweb="radio"] *,
[data-testid="stRadio"] [data-testid="stMarkdownContainer"],
[data-testid="stRadio"] [data-testid="stMarkdownContainer"] * {
  color: #000000 !important;
  -webkit-text-fill-color: #000000 !important;
  opacity: 1 !important;
}
.lmt-config-panel {
  background: #f6f7f9 !important;
  border-color: #9ca3af !important;
  padding-left: 10px !important;
  padding-right: 10px !important;
}
.lmt-config-panel div {
  color: #4b5563 !important;
}
.lmt-config-panel .lmt-config-value {
  color: #0f6e56 !important;
}
.lmt-config-panel .lmt-help-icon {
  border-color: #4b5563 !important;
  color: #111827 !important;
}
.lmt-guidance-container div,
.lmt-guidance-container span {
  color: #4b5563 !important;
}
.lmt-guidance-container span:first-child {
  color: #0f6e56 !important;
}
.lmt-guidance-container span + span {
  color: #ffffff !important;
}
.lmt-guidance-container {
  background-color: #f5f5f5 !important;
  border-color: #d1d5db !important;
}
</style>
"""


@st.dialog("About this app")
def show_about_dialog() -> None:
    """Display the About this app modal dialog."""
    st.markdown(content.ABOUT_TEXT)


def main() -> None:
    """Render the alternative Streamlit dashboard."""

    st.set_page_config(
        page_title="Liquidity Management Tools Calibration",
        page_icon=None,
        layout="wide",
        initial_sidebar_state="expanded",
    )

    inputs = _load_inputs()

    with st.sidebar:
        st.markdown(
            "<div class='lmt-sidebar-header'>"
            "<span class='lmt-sidebar-title'>LMT Calibration</span>"
            "<span class='lmt-sidebar-separator'>|</span>"
            "<a class='lmt-about-link' href='?about=1' target='_self' "
            "aria-label='About this app'>About</a>"
            "</div>",
            unsafe_allow_html=True,
        )

    if st.query_params.get("about") == "1":
        del st.query_params["about"]
        show_about_dialog()

    # Initialize session state for theme
    if "dark_mode" not in st.session_state:
        st.session_state.dark_mode = True

    with st.sidebar:
        selected_fund_id = _fund_selector(inputs)

        # Get fund and build characteristics for early display
        scenario_template_early = next(
            scenario
            for scenario in inputs.scenario_definitions
            if scenario.fund_id == selected_fund_id
        )
        fund_early = inputs.fund_by_key[(selected_fund_id, scenario_template_early.as_of_date)]
        investor_classes_early = {
            investor.client_class.value
            for investor in inputs.investor_classes
            if investor.fund_id == selected_fund_id
        }
        positions_early = fund_positions(inputs, fund_early)

        # Render fund characteristics card early
        fund_chars = FundCharacteristics(
            base_currency=fund_early.base_currency,
            dealing=fund_early.dealing_frequency.title(),
            notice=f"{fund_early.redemption_notice_days} days",
            settlement=f"{fund_early.redemption_settlement_days} days",
            investor_classes=len(investor_classes_early),
            positions=len(positions_early),
        )
        _render_fund_card(fund_chars, fund_early.fund_name)

        selected_redemption_id = _redemption_selector(inputs)
        selected_strategy_id = _strategy_selector(inputs)

    # Get scenario template to access default LMT parameters
    scenario_template = next(
        scenario for scenario in inputs.scenario_definitions if scenario.fund_id == selected_fund_id
    )
    default_params = inputs.parameters_by_key[
        (
            scenario_template.fund_id,
            scenario_template.as_of_date,
            scenario_template.lmt_parameter_set_id,
        )
    ]

    # Render sliders and capture updated LMT parameters BEFORE building scenarios
    with st.sidebar:
        updated_params = _capture_lmt_thresholds_from_sliders(default_params)

    # NOW build scenario runs with updated LMT parameters and selected redemption scenario
    run = run_selected_sample_scenario(
        inputs,
        fund_id=selected_fund_id,
        strategy_id=selected_strategy_id,
        lmt_parameters_override=updated_params,
        redemption_scenario_id_override=selected_redemption_id,
    )
    positions = fund_positions(inputs, run.fund)

    # Build scenario runs for matrix comparison across market conditions with updated parameters and redemption scenario
    market_condition_runs = run_scenario_across_market_conditions(
        inputs,
        fund_id=selected_fund_id,
        strategy_id=selected_strategy_id,
        lmt_parameters_override=updated_params,
        redemption_scenario_id_override=selected_redemption_id,
    )

    dashboard = _build_dashboard_result(inputs, run, positions, market_condition_runs)

    col_header, col_theme_top = st.columns([0.82, 0.18])
    with col_header:
        _render_header(dashboard)
    with col_theme_top:
        selected_theme = st.radio(
            "Theme",
            options=["Light", "Dark"],
            index=1 if st.session_state.dark_mode else 0,
            label_visibility="collapsed",
            horizontal=True,
            key="theme_toggle",
        )
        st.session_state.dark_mode = selected_theme == "Dark"

    dark_mode = st.session_state.dark_mode
    theme = DARK_THEME if dark_mode else LIGHT_THEME
    st.markdown(CSS.substitute(theme), unsafe_allow_html=True)
    if not dark_mode:
        st.markdown(LIGHT_MODE_CSS, unsafe_allow_html=True)

    _render_lmt_configuration(run)

    st.markdown(
        """
        <div class='lmt-section-h'>Calibration Across Market Conditions</div>
        """,
        unsafe_allow_html=True,
    )
    _render_matrix(dashboard.scenarios)

    # Calibration guidance panel
    _render_calibration_guidance(run)


@st.cache_data(show_spinner=False)
def _load_inputs() -> AppSampleData:
    return load_app_sample_data(SAMPLE_DATA_DIR)


def _capture_lmt_thresholds_from_sliders(default_params: LmtParameters) -> LmtParameters:
    """Render LMT threshold sliders and return updated parameters based on slider values."""
    st.markdown(
        "<div class='lmt-threshold-subsection' style='padding-left: 12px;'>"
        "<div class='lmt-threshold-subsection-title'>Anti-dilution tools</div>",
        unsafe_allow_html=True,
    )

    default_swing = float(default_params.swing_threshold_rate * ONE_HUNDRED)
    swing_pct = st.slider(
        "Swing activation threshold",
        min_value=0.5,
        max_value=5.0,
        value=default_swing,
        step=0.25,
        key="swing_threshold",
        help="Redemption rate at which the simulated swing activation condition is met.",
    )

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        "<div class='lmt-threshold-subsection' style='padding-left: 12px;'>"
        "<div class='lmt-threshold-subsection-title'>Quantitative LMTs</div>",
        unsafe_allow_html=True,
    )

    gate_pct = st.slider(
        "Gate activation threshold",
        min_value=5.0,
        max_value=15.0,
        value=6.0,
        step=1.0,
        key="gate_threshold",
        help="Redemption rate at which the simulated gate activation condition is met.",
    )

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        "<div class='lmt-threshold-subsection' style='padding-left: 12px;'>"
        "<div class='lmt-threshold-subsection-title'>Internal Monitoring</div>",
        unsafe_allow_html=True,
    )

    default_buffer = float(default_params.minimum_buffer_rate * ONE_HUNDRED)
    buffer_pct = st.slider(
        "Internal liquidity buffer target",
        min_value=2.0,
        max_value=15.0,
        value=default_buffer,
        step=0.5,
        key="internal_buffer_target",
        help="Internal monitoring threshold, not regulatory minimum.",
    )

    st.markdown("</div>", unsafe_allow_html=True)

    # Return updated parameters with slider values
    return default_params.model_copy(
        update={
            "swing_threshold_rate": Decimal(str(swing_pct / 100.0)),
            "gate_threshold_rate": Decimal(str(gate_pct / 100.0)),
            "minimum_buffer_rate": Decimal(str(buffer_pct / 100.0)),
        }
    )


def _fund_selector(inputs: AppSampleData) -> str:
    fund_options = {fund.fund_name: fund.fund_id for fund in inputs.funds}
    selected_name = st.selectbox("Fund", list(fund_options))
    return fund_options[selected_name]


def _redemption_selector(inputs: AppSampleData) -> str:
    redemption_options = {
        scenario.name: scenario.redemption_scenario_id for scenario in inputs.redemption_scenarios
    }
    st.markdown(
        "<div class='lmt-sidebar-group-label'>Selected redemption scenario</div>",
        unsafe_allow_html=True,
    )
    selected_name = st.selectbox(
        "Redemption scenario", list(redemption_options), label_visibility="collapsed"
    )
    return redemption_options[selected_name]


def _strategy_selector(inputs: AppSampleData) -> str:
    strategy_options = {
        _strategy_label(strategy.liquidation_strategy_id): strategy.liquidation_strategy_id
        for strategy in inputs.liquidation_strategies
    }
    st.markdown(
        "<div class='lmt-sidebar-group-label'>Selected liquidation strategy</div>",
        unsafe_allow_html=True,
    )
    selected_name = st.selectbox(
        "Liquidation strategy", list(strategy_options), label_visibility="collapsed"
    )
    return strategy_options[selected_name]


def _build_dashboard_result(
    inputs: AppSampleData,
    run: AppScenarioRun,
    positions: list[AssetPosition],
    market_condition_runs: list[AppScenarioRun] | None = None,
) -> DashboardResult:
    initial_nav = run.fund.nav
    redemption_amount = run.result.total_redemption_amount
    liquidity_cost = run.result.dilution_amount
    final_nav = max(initial_nav - redemption_amount - liquidity_cost, ZERO)
    final_nav_change = _safe_rate(final_nav - initial_nav, initial_nav)
    redemption_rate = run.redemption_rate
    initial_buffer = _safe_rate(_cash_total(positions), initial_nav)
    buffer_change = run.result.remaining_liquid_buffer_rate - initial_buffer
    redemption_met = run.result.shortfall == ZERO
    investor_classes = {
        investor.client_class.value
        for investor in inputs.investor_classes
        if investor.fund_id == run.fund.fund_id
    }

    # Build scenario comparison matrix from market condition runs
    if market_condition_runs:
        scenarios = [
            _scenario_result_from_market_condition_run(
                market_run,
                initial_nav=initial_nav,
            )
            for market_run in market_condition_runs
        ]
    else:
        # Fallback to historical scenarios if no market condition runs provided
        normal_row = {
            "scenario_id": "normal_market_conditions",
            "scenario": "Normal Market Conditions",
            "period": "Baseline",
            "holding_period_days": 0,
            "cash_used": run.result.cash_used,
            "post_haircut_cash_raised": run.result.total_post_haircut_cash_raised,
            "shortfall": run.result.shortfall,
            "dilution": run.result.dilution_amount,
            "remaining_buffer": run.result.remaining_liquid_buffer_rate,
        }
        historical_rows = build_historical_result_rows(inputs, run)
        all_rows = [normal_row] + historical_rows

        scenarios = [
            _scenario_result_from_row(
                row,
                run=run,
                initial_nav=initial_nav,
                final_nav=final_nav,
                final_nav_change=final_nav_change,
                redemption_rate=redemption_rate,
                buffer_change=buffer_change,
            )
            for row in all_rows
        ]

    return DashboardResult(
        fund_name=run.fund.fund_name,
        tags=[],
        characteristics=FundCharacteristics(
            base_currency=run.fund.base_currency,
            dealing=run.fund.dealing_frequency.title(),
            notice=f"{run.fund.redemption_notice_days} days",
            settlement=f"{run.fund.redemption_settlement_days} days",
            investor_classes=len(investor_classes),
            positions=len(positions),
        ),
        kpis=[
            Kpi("Final NAV", _money(final_nav), _signed_rate(final_nav_change), "danger"),
            Kpi(
                "Liquidity buffer",
                _rate(run.result.remaining_liquid_buffer_rate),
                f"{_signed_rate(buffer_change)} vs initial",
                _positive_or_warning(buffer_change),
            ),
            Kpi(
                "Redemption",
                "Met" if redemption_met else "Not met",
                f"{_rate(redemption_rate)} of NAV",
                "success" if redemption_met else "danger",
            ),
            Kpi(
                "Liquidity impact",
                _money(run.result.total_haircut_cost if redemption_met else run.result.shortfall),
                "haircut cost" if redemption_met else "shortfall",
                "neutral" if redemption_met else "danger",
            ),
        ],
        scenarios=scenarios,
    )


def _scenario_result_from_market_condition_run(
    market_run: AppScenarioRun,
    *,
    initial_nav: Decimal,
) -> ScenarioResult:
    """Create a ScenarioResult from a market condition run."""
    shocked_nav = market_run.current_nav_before_lmt_effects
    outcome = build_scenario_matrix_outcome(market_run)

    gross_redemption_amount = market_run.result.total_redemption_amount

    # For comparison with initial NAV
    final_nav_change = _safe_rate(outcome.nav_after_lmt - initial_nav, initial_nav)
    shocked_nav_change = _safe_rate(shocked_nav - initial_nav, initial_nav)

    # Determine market condition label based on shock magnitude
    market_shock = market_run.market_stress.market_shock_rate
    if market_shock == ZERO:
        scenario_name = "Normal Market Conditions"
    elif market_shock >= Decimal("-0.06"):  # Between 0 and -6% (~COVID magnitude)
        scenario_name = "2020 COVID-19 Crash"
    elif market_shock >= Decimal("-0.22"):  # Between -6% and -22% (~2022 inflation magnitude)
        scenario_name = "2022 Rate & Inflation Shock"
    else:  # More severe than -22% (~2008 GFC magnitude)
        scenario_name = "2008 Financial Crisis"

    return ScenarioResult(
        name=scenario_name,
        short_name=scenario_name,
        stages=[
            StageResult(
                "Asset-side market shock",
                _money(shocked_nav),
                f"{_signed_rate(shocked_nav_change)}%",
                "NAV after market shock",
                "Portfolio revaluation from selected market scenario.",
                "neutral" if market_shock == ZERO else "danger",
            ),
            StageResult(
                "Liability-side redemption shock",
                _money(gross_redemption_amount),
                "",
                "Redemption cash need",
                "Cash amount the fund must pay to redeeming investors.",
                "info",
            ),
            StageResult(
                "Asset-side liquidity shock",
                _money(outcome.realised_liquidity_cost),
                "",
                "Realised liquidation cost",
                "Haircut cost produced by the selected liquidation strategy.",
                "info"
                if outcome.realised_liquidity_cost < gross_redemption_amount * Decimal("0.1")
                else "warning",
            ),
            StageResult(
                "Fund state before LMT",
                _money(outcome.nav_before_lmt),
                "",
                "NAV before LMT effects",
                "NAV after market shock, redemption demand, and liquidity costs before LMT effects.",
                "warning",
            ),
            StageResult(
                "Fund state after LMT",
                _money(outcome.nav_after_lmt),
                _format_lmt_pills_compact(market_run, outcome),
                "NAV after LMT effects",
                "NAV after simulated LMT effects and resulting cash-flow adjustments.",
                "danger" if final_nav_change < ZERO else "success",
            ),
            StageResult(
                "Liquidity position",
                _rate(market_run.result.remaining_liquid_buffer_rate),
                "",
                "Remaining liquid assets",
                "Remaining liquid assets as % of post-redemption NAV.",
                _positive_or_warning(
                    market_run.result.remaining_liquid_buffer_rate - Decimal("0.05")
                ),
            ),
        ],
    )


def _scenario_result_from_row(
    row: dict[str, object],
    *,
    run: AppScenarioRun,
    initial_nav: Decimal,
    final_nav: Decimal,
    final_nav_change: Decimal,
    redemption_rate: Decimal,
    buffer_change: Decimal,
) -> ScenarioResult:
    redemption_met = run.result.shortfall == ZERO
    liquidity_value = run.result.total_haircut_cost if redemption_met else run.result.shortfall
    liquidity_badge = "Redemption met" if redemption_met else "Redemption not met"

    return ScenarioResult(
        name=str(row["scenario"]),
        short_name=_short_scenario_name(str(row["scenario"])),
        stages=[
            StageResult(
                "Asset-side market shock",
                _money(initial_nav),
                "Market shock not applied",
                "NAV after market shock",
                "Portfolio impact from equity, interest-rate, credit spread, and FX shocks.",
                "neutral",
            ),
            StageResult(
                "Liability-side redemption shock",
                _money(run.result.total_redemption_amount),
                "",
                "Redemption cash need",
                "Cash amount the fund must pay to redeeming investors.",
                "info",
            ),
            StageResult(
                "Asset-side liquidity shock",
                _money(liquidity_value),
                liquidity_badge,
                "Liquidity impact",
                "Effect of stressed liquidation capacity and haircuts on asset sales.",
                "success" if redemption_met else "danger",
            ),
            StageResult(
                "Final fund state",
                _money(final_nav),
                f"{_signed_rate(final_nav_change)} total",
                "Final NAV",
                "Fund NAV after market shock, redemption payment, and haircut cost.",
                "danger" if final_nav_change < ZERO else "success",
            ),
            StageResult(
                "Liquidity position",
                _rate(run.result.remaining_liquid_buffer_rate),
                f"{_signed_rate(buffer_change)} vs initial",
                "Remaining liquidity buffer",
                "Remaining liquidity buffer after the stressed liquidation.",
                _positive_or_warning(buffer_change),
            ),
        ],
    )


def _render_header(result: DashboardResult) -> None:
    tags = "".join(f"<span class='lmt-tag'>{escape(tag)}</span>" for tag in result.tags)
    st.markdown(
        f"""
        <div class="lmt-header-copy">
          <div class="lmt-eyebrow">LMT Calibration Tool</div>
          <h1 class="lmt-title">Liquidity Management Tools Calibration</h1>
          <p class="lmt-subtitle">Calibrating LMT settings across normal market conditions, market stress, redemption pressure, and liquidity stress.</p>
          <div class="lmt-tags">{tags}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_kpis(kpis: list[Kpi]) -> None:
    cards = ""
    for kpi in kpis:
        note = ""
        if kpi.note:
            note = f"<div class='k-note tone-{kpi.tone}'>{escape(kpi.note)}</div>"
        cards += (
            "<div class='lmt-kpi'>"
            f"<div class='k-label'>{escape(kpi.label)}</div>"
            f"<div class='k-value'>{escape(kpi.value)}</div>"
            f"{note}</div>"
        )
    st.markdown(f"<div class='lmt-kpis'>{cards}</div>", unsafe_allow_html=True)


def _render_matrix(scenarios: list[ScenarioResult]) -> None:
    if not scenarios:
        st.info("No scenario results to display.")
        return

    head = "<th class='stage-col'></th>"
    head += "".join(
        f"<th><div style='display:flex;align-items:center;gap:6px;justify-content:flex-end;'><div style='width:22px;height:2px;background:rgba(111,168,220,0.65);flex-shrink:0;'></div><div style='color:#bbb;'>{escape(scenario.short_name)}</div></div></th>"
        for scenario in scenarios
    )
    body = ""
    for index, stage in enumerate(scenarios[0].stages):
        cells = ""
        is_lmt_row = stage.label == "Fund state after LMT"
        for scenario in scenarios:
            scenario_stage = scenario.stages[index]
            # For LMT row, render badge_text as raw HTML (pills); for others, use _badge
            if is_lmt_row and scenario_stage.badge_text:
                badge_html = scenario_stage.badge_text
            else:
                badge_html = (
                    _badge(scenario_stage.badge_text, scenario_stage.badge_tone)
                    if scenario_stage.badge_text
                    else ""
                )
            cells += (
                "<td class='cell-wrapper'>"
                f"<span class='cell-label'>{escape(scenario_stage.detail_label)}</span>"
                f"<div class='val'>{escape(scenario_stage.value)}</div>"
                f"{badge_html}"
                "</td>"
            )
        body += f"<tr><td class='stage-col'><div class='stage-title'>{escape(stage.label)}</div><div class='stage-explanation'>{escape(stage.explanation)}</div></td>{cells}</tr>"

    st.markdown(
        "<div class='lmt-matrix-wrap'>"
        "<table class='lmt-matrix'>"
        f"<thead><tr>{head}</tr></thead>"
        f"<tbody>{body}</tbody>"
        "</table></div>",
        unsafe_allow_html=True,
    )


def _render_fund_card(characteristics: FundCharacteristics, fund_name: str) -> None:
    rows = [
        ("Base currency", characteristics.base_currency),
        ("Dealing", characteristics.dealing),
        ("Notice", characteristics.notice),
        ("Settlement", characteristics.settlement),
    ]
    body = "".join(
        "<div class='fc-row'>"
        f"<span class='fc-k'>{escape(key)}</span>"
        f"<span class='fc-v'>{escape(value)}</span>"
        "</div>"
        for key, value in rows
    )
    st.markdown(
        "<div class='lmt-fund-card'>"
        "<div class='fc-eyebrow'>Fund characteristics</div>"
        f"<div class='fc-name'>{escape(fund_name)}</div>"
        f"{body}</div>",
        unsafe_allow_html=True,
    )


def _render_lmt_configuration(run: AppScenarioRun) -> None:
    """Render thresholds under review and selected inputs as ribbon-style banners."""
    # Read slider values from session state, fallback to run parameters
    default_swing = float(run.parameters.swing_threshold_rate * ONE_HUNDRED)
    default_gate = float(run.parameters.gate_threshold_rate * ONE_HUNDRED)
    default_buffer = float(run.parameters.minimum_buffer_rate * ONE_HUNDRED)

    swing_threshold = st.session_state.get("swing_threshold", default_swing)
    gate_threshold = st.session_state.get("gate_threshold", default_gate)
    internal_buffer_target = st.session_state.get("internal_buffer_target", default_buffer)

    # Get scenario names from run
    redemption_name = run.redemption.name if run.redemption else "Unknown"
    strategy_name = (
        _strategy_label(run.strategy.liquidation_strategy_id) if run.strategy else "Unknown"
    )

    config_html = f"""
    <div style='display:grid;grid-template-columns:1fr 1fr;gap:60px;margin-top:8px;margin-bottom:16px;'>
      <div class='lmt-config-panel' style='border-top:1px solid rgba(139,151,163,0.5);border-bottom:1px solid rgba(139,151,163,0.5);padding:10px 0;display:flex;align-items:center;gap:10px;'>
        <div class='lmt-banner-heading'>
          <span>Thresholds<br/>under review</span>
          <span class='lmt-help-icon' role='button' tabindex='0' aria-label='How to change threshold values' data-tooltip='Change these values using the threshold sliders in the sidebar.'>?</span>
        </div>
        <div style='width:1px;background:rgba(139,151,163,0.5);height:24px;flex-shrink:0;'></div>
        <div style='display:flex;gap:0;flex:1;justify-content:space-around;'>
          <div style='text-align:center;'>
            <div style='color:#999;font-size:12px;font-weight:600;margin-bottom:2px;text-transform:uppercase;'>Swing</div>
            <div class='lmt-config-value' style='color:#5eead4;font-size:13px;font-weight:700;'>{swing_threshold:.2f}%</div>
          </div>
          <div style='text-align:center;'>
            <div style='color:#999;font-size:12px;font-weight:600;margin-bottom:2px;text-transform:uppercase;'>Gate</div>
            <div class='lmt-config-value' style='color:#5eead4;font-size:13px;font-weight:700;'>{gate_threshold:.1f}%</div>
          </div>
          <div style='text-align:center;'>
            <div style='color:#999;font-size:12px;font-weight:600;margin-bottom:2px;text-transform:uppercase;'>Buffer</div>
            <div class='lmt-config-value' style='color:#5eead4;font-size:13px;font-weight:700;'>{internal_buffer_target:.1f}%</div>
          </div>
        </div>
      </div>
      <div class='lmt-config-panel' style='border-top:1px solid rgba(139,151,163,0.5);border-bottom:1px solid rgba(139,151,163,0.5);padding:10px 0;display:flex;align-items:center;gap:10px;'>
        <div class='lmt-banner-heading'>
          <span>Selected<br/>inputs</span>
          <span class='lmt-help-icon' role='button' tabindex='0' aria-label='How to change selected inputs' data-tooltip='Change these values using the redemption scenario and liquidation strategy selectors in the sidebar.'>?</span>
        </div>
        <div style='width:1px;background:rgba(139,151,163,0.5);height:24px;flex-shrink:0;'></div>
        <div style='display:flex;gap:0;flex:1;justify-content:space-around;'>
          <div style='text-align:center;'>
            <div style='color:#999;font-size:12px;font-weight:600;margin-bottom:2px;text-transform:uppercase;'>Redemption scenario</div>
            <div class='lmt-config-value' style='color:#5eead4;font-size:13px;font-weight:700;'>{escape(redemption_name)}</div>
          </div>
          <div style='text-align:center;'>
            <div style='color:#999;font-size:12px;font-weight:600;margin-bottom:2px;text-transform:uppercase;'>Liquidation strategy</div>
            <div class='lmt-config-value' style='color:#5eead4;font-size:13px;font-weight:700;'>{escape(strategy_name)}</div>
          </div>
        </div>
      </div>
    </div>
    """
    st.markdown(config_html, unsafe_allow_html=True)


def _format_lmt_pills_compact(
    run: AppScenarioRun,
    outcome: ScenarioMatrixOutcome,
) -> str:
    """Format simulated LMT activation-assessment pills for matrix display.

    Returns HTML that shows in the matrix cell below the NAV value for each scenario.
    Each LMT action is a separate pill using lmt-badge styling.
    """
    pills_html = []

    if run.lmt_activation.swing_activated:
        swing_factor_pct = float(run.lmt_activation.estimated_liquidity_cost_rate * ONE_HUNDRED)
        recovered_text = (
            "Swing "
            f"{swing_factor_pct:.2f}% | "
            f"Cost recovered €{float(outcome.cost_recovered / 1000):.0f}k"
        )
        pills_html.append(f"<span class='lmt-badge tone-info'>{recovered_text}</span>")

    if run.lmt_activation.gate_activated:
        deferred = run.lmt_activation.redemption_deferred_amount
        if deferred > ZERO:
            deferred_text = f"Gate | Deferred €{float(deferred / 1000000):.1f}m"
            pills_html.append(f"<span class='lmt-badge tone-warning'>{deferred_text}</span>")

    if run.lmt_activation.buffer_breached:
        pills_html.append("<span class='lmt-badge tone-danger'>Buffer warning</span>")

    if not pills_html:
        return "No simulated activation conditions met"

    return "<div style='line-height:1.6;'>" + " ".join(pills_html) + "</div>"


def _render_calibration_guidance(run: AppScenarioRun) -> None:
    """Render LMT Calibration Guidance using exact 6-column grid layout."""
    st.markdown(
        "<div class='lmt-guidance-container' style='margin-top:13px;border-radius:12px;padding:6px 10px;'><div style='display:grid;grid-template-columns:0.8fr 1.1fr 1.1fr 1.1fr 1.1fr 1.1fr;gap:8px;'><div style='grid-column:1;'><div style='color:#9ca3af;font-size:13px;font-weight:600;margin-bottom:3px;line-height:1.3;'>LMT Calibration Guidance</div><div style='color:#6b7280;font-size:10px;line-height:1.4;'>Indicative suitability based on selected fund characteristics and scenario.</div></div><div style='grid-column:2/4;margin-left:14px;'><div style='display:flex;align-items:center;gap:6px;margin-bottom:4px;'><div style='width:22px;height:2px;background:rgba(111,168,220,0.65);'></div><div style='color:#aaa;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;'>Anti-dilution tools</div></div><div style='display:grid;grid-template-columns:1fr 1fr;gap:6px 6px;row-gap:5px;'><div style='border:1px solid rgba(0,102,204,0.4);border-radius:2px;padding:5px 8px;background:transparent;'><span style='color:#4da6ff;font-size:11px;font-weight:600;'>Swing pricing</span> <span style='background:#0066cc;color:#fff;padding:1px 4px;border-radius:1px;font-size:9px;margin-left:8px;'>Selected</span><div style='color:#999;font-size:8px;margin-top:2px;'>Price adjustment | activation threshold | passes liquidity cost</div></div><div style='border:1px solid rgba(85,85,85,0.4);border-radius:2px;padding:5px 8px;background:transparent;'><span style='color:#ccc;font-size:11px;font-weight:600;'>Anti-dilution levy</span><div style='color:#999;font-size:8px;margin-top:2px;'>Separate levy | cost recovery | alternative to swing</div></div><div style='border:1px solid rgba(85,85,85,0.4);border-radius:2px;padding:5px 8px;background:transparent;'><span style='color:#ccc;font-size:11px;font-weight:600;'>Dual pricing</span><div style='color:#999;font-size:8px;margin-top:2px;'>Bid/offer NAV | spread-based | operationally heavier</div></div><div style='border:1px solid rgba(85,85,85,0.4);border-radius:2px;padding:5px 8px;background:transparent;'><span style='color:#ccc;font-size:11px;font-weight:600;'>Redemption fee</span><div style='color:#999;font-size:8px;margin-top:2px;'>Fixed fee | predictable costs | less stress-responsive</div></div></div></div><div style='grid-column:4/7;margin-left:10px;'><div style='display:flex;align-items:center;gap:6px;margin-bottom:4px;'><div style='width:22px;height:2px;background:rgba(111,168,220,0.65);'></div><div style='color:#aaa;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;'>Quantitative-based LMT<span style='font-size:0.75em;'>S</span></div></div><div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px 6px;row-gap:5px;'><div style='border:1px solid rgba(0,102,204,0.4);border-radius:2px;padding:5px 8px;background:transparent;'><span style='color:#4da6ff;font-size:11px;font-weight:600;'>Redemption gate</span> <span style='background:#0066cc;color:#fff;padding:1px 4px;border-radius:1px;font-size:9px;margin-left:8px;'>Selected</span><div style='color:#999;font-size:8px;margin-top:2px;'>Partial deferral | protects liquidity</div></div><div style='border:1px solid rgba(85,85,85,0.4);border-radius:2px;padding:5px 8px;background:transparent;'><span style='color:#ccc;font-size:11px;font-weight:600;'>Notice extension</span><div style='color:#999;font-size:8px;margin-top:2px;'>More time to sell | ex-ante tool | less liquid assets</div></div><div style='border:1px solid rgba(85,85,85,0.4);border-radius:2px;padding:5px 8px;background:transparent;'><span style='color:#ccc;font-size:11px;font-weight:600;'>Side pockets</span><span style='background:rgba(136,136,136,0.5);color:#fff;padding:1px 4px;border-radius:1px;font-size:9px;margin-left:8px;'>Exceptional</span><div style='color:#999;font-size:8px;margin-top:2px;'>Segregate assets | hard-to-value/illiquid</div></div><div style='border:1px solid rgba(85,85,85,0.4);border-radius:2px;padding:5px 8px;background:transparent;'><span style='color:#ccc;font-size:11px;font-weight:600;'>Redemption in kind</span><div style='color:#999;font-size:8px;margin-top:2px;'>Institutional use | avoids forced sales</div></div><div style='border:1px solid rgba(85,85,85,0.4);border-radius:2px;padding:5px 8px;background:transparent;'><span style='color:#ccc;font-size:11px;font-weight:600;'>Suspension</span><span style='background:rgba(136,136,136,0.5);color:#fff;padding:1px 4px;border-radius:1px;font-size:9px;margin-left:8px;'>Exceptional</span><div style='color:#999;font-size:8px;margin-top:2px;'>Temporary stop | last resort</div></div><div style='background:transparent;'></div></div></div></div></div>",
        unsafe_allow_html=True,
    )


def _badge(text: str, tone: str) -> str:
    return f"<span class='lmt-badge tone-{tone}'>{escape(text)}</span>"


def _cash_total(positions: list[AssetPosition]) -> Decimal:
    return sum(
        (position.market_value for position in positions if position.asset_group.value == "cash"),
        ZERO,
    )


def _safe_rate(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == ZERO:
        return ZERO
    return numerator / denominator


def _money(value: Decimal) -> str:
    return f"{value:,.0f}"


def _rate(value: Decimal) -> str:
    return f"{value * ONE_HUNDRED:.2f}%"


def _signed_rate(value: Decimal) -> str:
    sign = "+" if value >= ZERO else ""
    return f"{sign}{_rate(value)}"


def _positive_or_warning(value: Decimal) -> str:
    if value >= ZERO:
        return "success"
    return "warning"


def _strategy_label(strategy_id: str) -> str:
    return strategy_id.replace("_", " ").title()


def _short_scenario_name(name: str) -> str:
    replacements = {
        "2008 Financial Crisis": "2008 crisis",
        "2020 COVID-19 Crash": "2020 COVID",
        "2022 Rate and Inflation Shock": "2022 rates",
    }
    return replacements.get(name, name)


if __name__ == "__main__":
    main()
