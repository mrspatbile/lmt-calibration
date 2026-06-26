"""Alternative Streamlit dashboard for Liquidity Management Tools Calibration."""

from dataclasses import dataclass
from decimal import Decimal
from html import escape
from pathlib import Path
from string import Template

import streamlit as st

from lmt_calibration.domain import AssetPosition
from lmt_calibration.services import (
    AppSampleData,
    AppScenarioRun,
    build_historical_result_rows,
    fund_positions,
    load_app_sample_data,
    run_selected_sample_scenario,
)

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
  margin: 0 0 14px;
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
  display: none;
}
h1.lmt-title {
  color: $text !important;
  font-size: 40px;
  font-weight: 760;
  line-height: 1.15;
  margin: 0 0 24px;
}
.lmt-subtitle {
  display: none;
}
.lmt-tags {
  display: none;
}
.lmt-tag {
  display: none;
}
.lmt-section-h {
  color: $text;
  font-size: 18px;
  font-weight: 700;
  margin: 8px 0 4px;
}
.lmt-section-d {
  color: $muted;
  font-size: 14px;
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
  color: $muted;
  font-size: 12px;
  margin-bottom: 4px;
}
.lmt-kpi .k-value {
  color: $text;
  font-size: 21px;
  font-weight: 700;
}
.lmt-kpi .k-note {
  font-size: 12px;
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
  color: $muted;
  font-weight: 700;
  padding: 12px 14px;
  text-align: right;
}
table.lmt-matrix thead th:first-child {
  text-align: right;
}
table.lmt-matrix tbody td {
  background: $surface;
  padding: 12px 14px;
  vertical-align: top;
}
table.lmt-matrix tbody tr {
  border-bottom: 3px solid $border;
}
table.lmt-matrix tbody tr:last-child {
  border-bottom: 2px solid $border;
}
table.lmt-matrix thead th {
  font-weight: 760;
}
table.lmt-matrix .stage-col {
  text-align: right;
  width: 25%;
  padding-right: 20px;
}
table.lmt-matrix .stage-title {
  color: $text;
  font-weight: 760;
  font-size: 15px;
  display: block;
  margin-bottom: 4px;
}
table.lmt-matrix .stage-explanation {
  color: $muted;
  font-size: 12px;
  font-weight: 400;
  line-height: 1.35;
  display: block;
}
table.lmt-matrix .cell-label {
  color: $muted;
  font-size: 11px;
  display: block;
  margin-top: 6px;
  text-align: right;
}
table.lmt-matrix .val {
  color: $text;
  font-weight: 760;
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
  margin-top: 5px;
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
  color: $muted;
  font-size: 12px;
  line-height: 1.45;
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
  color: $muted;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .04em;
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
</style>
"""
)


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
        st.markdown("<div class='lmt-sidebar-title'>LMT Calibration</div>", unsafe_allow_html=True)

    # Initialize session state for theme
    if "dark_mode" not in st.session_state:
        st.session_state.dark_mode = True

    with st.sidebar:
        selected_fund_id = _fund_selector(inputs)
        selected_strategy_id = _strategy_selector(inputs)

    run = run_selected_sample_scenario(
        inputs,
        fund_id=selected_fund_id,
        strategy_id=selected_strategy_id,
    )
    positions = fund_positions(inputs, run.fund)
    dashboard = _build_dashboard_result(inputs, run, positions)

    with st.sidebar:
        _render_fund_card(dashboard.characteristics, dashboard.fund_name)
        _render_lmt_reference_thresholds(run)

    col_header, col_theme_top = st.columns([0.82, 0.18])
    with col_header:
        _render_header(dashboard)
    with col_theme_top:
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
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

    st.markdown(
        """
        <div class='lmt-section-h'>Worst case scenario</div>
        """,
        unsafe_allow_html=True,
    )
    _render_kpis(dashboard.kpis)
    st.markdown(
        "<hr style='border: none; border-top: 1px solid rgba(255,255,255,0.10); margin: 28px 0;'>",
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class='lmt-section-h'>Historical scenarios</div>
        """,
        unsafe_allow_html=True,
    )
    _render_matrix(dashboard.scenarios)


@st.cache_data(show_spinner=False)
def _load_inputs() -> AppSampleData:
    return load_app_sample_data(SAMPLE_DATA_DIR)


def _fund_selector(inputs: AppSampleData) -> str:
    fund_options = {fund.fund_name: fund.fund_id for fund in inputs.funds}
    selected_name = st.selectbox("Fund", list(fund_options))
    return fund_options[selected_name]


def _strategy_selector(inputs: AppSampleData) -> str:
    strategy_options = {
        _strategy_label(strategy.liquidation_strategy_id): strategy.liquidation_strategy_id
        for strategy in inputs.liquidation_strategies
    }
    selected_name = st.selectbox("Liquidation strategy", list(strategy_options))
    return strategy_options[selected_name]


def _build_dashboard_result(
    inputs: AppSampleData,
    run: AppScenarioRun,
    positions: list[AssetPosition],
) -> DashboardResult:
    historical_rows = build_historical_result_rows(inputs, run)
    initial_nav = run.fund.nav
    redemption_amount = run.result.total_redemption_amount
    liquidity_cost = run.result.dilution_amount
    final_nav = max(initial_nav - redemption_amount - liquidity_cost, ZERO)
    final_nav_change = _safe_rate(final_nav - initial_nav, initial_nav)
    redemption_rate = _safe_rate(redemption_amount, initial_nav)
    initial_buffer = _safe_rate(_cash_total(positions), initial_nav)
    buffer_change = run.result.remaining_liquid_buffer_rate - initial_buffer
    redemption_met = run.result.shortfall == ZERO
    investor_classes = {
        investor.client_class.value
        for investor in inputs.investor_classes
        if investor.fund_id == run.fund.fund_id
    }
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
        for row in historical_rows
    ]

    return DashboardResult(
        fund_name=run.fund.fund_name,
        tags=[
            "UCITS",
            run.fund.dealing_frequency.title(),
            run.fund.base_currency,
            run.scenario.market_stress_id,
        ],
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
                f"{_rate(redemption_rate)} NAV",
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
        <div class="lmt-eyebrow">Version 1 calibration review</div>
        <h1 class="lmt-title">Liquidity Management Tools Calibration</h1>
        <p class="lmt-subtitle">{escape(result.fund_name)}</p>
        <div class="lmt-tags">{tags}</div>
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
    head += "".join(f"<th>{escape(scenario.short_name)}</th>" for scenario in scenarios)
    body = ""
    for index, stage in enumerate(scenarios[0].stages):
        cells = ""
        for scenario in scenarios:
            scenario_stage = scenario.stages[index]
            cells += (
                "<td class='cell-wrapper'>"
                f"<span class='cell-label'>{escape(scenario_stage.detail_label)}</span>"
                f"<div class='val'>{escape(scenario_stage.value)}</div>"
                f"{_badge(scenario_stage.badge_text, scenario_stage.badge_tone)}"
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


def _render_lmt_reference_thresholds(run: AppScenarioRun) -> None:
    """Render LMT reference threshold controls in sidebar."""
    params = run.parameters

    st.markdown(
        "<div class='lmt-thresholds-section'>"
        "<div style='color: var(--text-color, #e8eaed); font-size: 14px; font-weight: 700; margin-bottom: 12px;'>"
        "LMT reference thresholds"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div class='lmt-threshold-subsection' style='margin-bottom: 12px; padding-left: 12px;'>"
        "<div class='lmt-threshold-subsection-title'>Anti-dilution tools</div>",
        unsafe_allow_html=True,
    )

    st.slider(
        "Swing pricing threshold (0% - 10%)",
        min_value=0.0,
        max_value=10.0,
        value=float(params.swing_threshold_rate * ONE_HUNDRED),
        step=0.25,
        key="swing_threshold_placeholder",
    )

    st.slider(
        "Swing factor / adjustment (0% - 5%)",
        min_value=0.0,
        max_value=5.0,
        value=float(params.max_swing_factor_rate * ONE_HUNDRED),
        step=0.25,
        key="swing_factor_placeholder",
    )

    st.slider(
        "Anti-dilution levy (0% - 5%)",
        min_value=0.0,
        max_value=5.0,
        value=0.25,
        step=0.25,
        key="anti_dilution_levy_placeholder",
    )

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        "<div class='lmt-threshold-subsection' style='padding-left: 12px;'>"
        "<div class='lmt-threshold-subsection-title'>Quantitative LMTs</div>",
        unsafe_allow_html=True,
    )

    st.slider(
        "Redemption gate threshold (0% - 50%)",
        min_value=0.0,
        max_value=50.0,
        value=float(params.gate_threshold_rate * ONE_HUNDRED),
        step=1.0,
        key="gate_threshold_placeholder",
    )

    st.markdown("</div>", unsafe_allow_html=True)


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
