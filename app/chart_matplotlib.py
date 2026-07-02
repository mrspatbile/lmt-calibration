"""Matplotlib plots for LMT redemption path analysis.

Adapted from fund-risk-workflow liquidity_calibration_display.py
"""

from datetime import timedelta
from decimal import Decimal

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter

# Color palette (from brief + fund-risk-workflow)
COLORS = {
    "bg": "#0d1424",
    "text": "#c9d4e3",
    "muted": "#9ca3af",
    "cyan": "#39c2d6",
    "orange": "#f5793b",
    "blue_paid": "#2d6fe8",  # Paid redemption
    "shortfall": "#ef4444",  # Unfunded liquidity shortfall
    "blue_bright": "#2563eb",  # Backlog line in NAV context
    "nav_liquid": "#2f5aa8",  # Liquid NAV (medium blue from brief)
    "nav_illiquid": "#1c5a5e",  # Illiquid NAV (teal from brief)
}

LIGHT_COLORS = {
    "bg": "#ffffff",
    "text": "#111827",
    "muted": "#4b5563",
    "cyan": "#0f6e56",
    "orange": "#d97706",
    "blue_paid": "#2563eb",
    "shortfall": "#b91c1c",
    "blue_bright": "#1d4ed8",
    "nav_liquid": "#2f5aa8",
    "nav_illiquid": "#1f4b5f",
    "grid": "#d1d5db",
    "marker_edge": "#ffffff",
    "row_band": "#111827",
}

BACKLOG_DISPLAY_EPSILON_M = 1e-6


def _palette(*, dark_mode: bool) -> dict[str, str]:
    if dark_mode:
        dark_colors = COLORS.copy()
        dark_colors["grid"] = COLORS["muted"]
        dark_colors["marker_edge"] = "#ffffff"
        dark_colors["row_band"] = "#ffffff"
        return dark_colors
    return LIGHT_COLORS


def plot_redemption_profile(
    monthly_rows: list[dict],
    initial_nav: Decimal,
    fund_name: str = "Fund",
    as_of_date: str = None,
) -> plt.Figure:
    """Plot paid, deferred, backlog, and unfunded liquidity shortfall over time.

    Parameters
    ----------
    monthly_rows : list[dict]
        Monthly results from AppRedemptionPathRun.monthly_rows
    initial_nav : Decimal
        Initial fund NAV (for scaling y-axis)
    fund_name : str
        Fund identifier
    as_of_date : str
        Valuation date for month labels

    Returns
    -------
    plt.Figure
        Matplotlib figure object
    """
    df = pd.DataFrame(monthly_rows)

    # Convert Decimal to float and EUR to millions
    paid_m = df["paid_redemption"].astype(float) / 1e6
    deferred_m = df["deferred_redemption"].astype(float) / 1e6
    backlog_m = df["cumulative_backlog"].astype(float) / 1e6
    has_backlog = backlog_m.abs().max() > BACKLOG_DISPLAY_EPSILON_M
    liquidity_shortfall_m = (
        df.get("liquidity_shortfall", pd.Series(0.0, index=df.index)).astype(float) / 1e6
    )
    has_liquidity_shortfall = bool((liquidity_shortfall_m > 0).any())
    months = df["month"].values

    # Generate month labels
    if as_of_date:
        computation_date = pd.Timestamp(as_of_date)
    else:
        computation_date = pd.Timestamp.now()

    month_labels = [
        (computation_date + timedelta(days=30 * i)).strftime("%b/%y") for i in range(len(months))
    ]

    fig, ax = plt.subplots(figsize=(7, 3), dpi=120)
    fig.patch.set_facecolor(COLORS["bg"])
    fig.patch.set_alpha(0)
    ax.set_facecolor(COLORS["bg"])

    # Paid redemptions: blue (on bottom)
    ax.bar(months, paid_m, color=COLORS["blue_paid"], label="Paid", width=0.6)

    # Deferred redemptions: lighter blue with stronger hatch (on top)
    ax.bar(
        months,
        deferred_m,
        color=COLORS["blue_paid"],
        alpha=0.3,
        hatch="///",
        label="Deferred",
        bottom=paid_m,
        width=0.6,
        edgecolor=COLORS["blue_paid"],
        linewidth=0.8,
    )

    if has_backlog:
        backlog_m_clean = backlog_m.where(backlog_m.abs() > BACKLOG_DISPLAY_EPSILON_M, 0)
        ax.plot(
            months,
            backlog_m_clean,
            color=COLORS["orange"],
            marker="o",
            linewidth=2.5,
            label="Backlog",
            markersize=6,
        )

    if has_liquidity_shortfall:
        ax.bar(
            months,
            -liquidity_shortfall_m,
            color=COLORS["shortfall"],
            alpha=0.75,
            label="Liquidity shortfall (unfunded)",
            width=0.6,
        )

    # Formatting - smaller tick labels for quiet reference
    ax.set_xticks(months)
    ax.set_xticklabels(month_labels, fontsize=7, color=COLORS["muted"])
    ax.set_ylabel("")
    ax.tick_params(axis="y", labelcolor=COLORS["muted"], labelsize=8)

    # Y-axis: fixed to 60% of initial NAV, 5 gridlines, M-suffixed format with EUR symbol
    y_max = float(initial_nav) / 1e6 * 0.6
    y_min = -float(liquidity_shortfall_m.max()) * 1.25 if has_liquidity_shortfall else 0
    ax.set_ylim(y_min, y_max)
    ax.yaxis.set_major_locator(plt.MaxNLocator(5))
    top = y_max
    ax.yaxis.set_major_formatter(
        FuncFormatter(lambda v, _: f"€{v:.0f}M" if abs(v - top) < 1e-6 else f"€{v:.0f}M")
    )

    # Gridlines
    ax.grid(True, axis="y", alpha=0.2, linestyle="-", linewidth=0.5, color=COLORS["muted"])
    ax.set_axisbelow(True)

    # Spines
    for spine in ax.spines.values():
        spine.set_color(COLORS["muted"])
        spine.set_linewidth(0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Legend: stacked in top right, borderless, bright text
    legend = ax.legend(
        loc="upper right",
        bbox_to_anchor=(1.0, 1.0),
        frameon=False,
        fontsize=8,
        handlelength=1.5,
        borderaxespad=0,
    )
    # Brighten legend text from muted to near-white
    for text in legend.get_texts():
        text.set_color(COLORS["text"])

    fig.tight_layout()
    return fig


def plot_nav_evolution(
    monthly_rows: list[dict],
    initial_nav: Decimal,
    fund_name: str = "Fund",
    as_of_date: str = None,
) -> plt.Figure:
    """Plot NAV evolution: liquid vs illiquid assets as stacked area.

    Parameters
    ----------
    monthly_rows : list[dict]
        Monthly results from AppRedemptionPathRun.monthly_rows
    initial_nav : Decimal
        Initial fund NAV (for scaling y-axis)
    fund_name : str
        Fund identifier
    as_of_date : str
        Valuation date for month labels

    Returns
    -------
    plt.Figure
        Matplotlib figure object
    """
    df = pd.DataFrame(monthly_rows)

    # Convert Decimal to float and EUR to millions
    illiquid_m = df["illiquid_nav"].astype(float) / 1e6
    liquid_m = df["liquid_nav"].astype(float) / 1e6
    months = df["month"].values

    # Generate month labels
    if as_of_date:
        computation_date = pd.Timestamp(as_of_date)
    else:
        computation_date = pd.Timestamp.now()

    month_labels = [
        (computation_date + timedelta(days=30 * i)).strftime("%b/%y") for i in range(len(months))
    ]

    fig, ax = plt.subplots(figsize=(7, 2.0), dpi=120)
    fig.patch.set_facecolor(COLORS["bg"])
    fig.patch.set_alpha(0)
    ax.set_facecolor(COLORS["bg"])

    # Stacked area: only include illiquid if it has meaningful values
    has_illiquid = (illiquid_m > 0).any()

    if has_illiquid:
        ax.stackplot(
            months,
            illiquid_m,
            liquid_m,
            labels=["Illiquid NAV", "Liquid NAV"],
            colors=[COLORS["nav_illiquid"], COLORS["nav_liquid"]],
            alpha=0.85,
        )
    else:
        # Only plot liquid NAV if illiquid is zero
        ax.fill_between(
            months,
            0,
            liquid_m,
            label="Liquid NAV",
            color=COLORS["nav_liquid"],
            alpha=0.85,
        )

    # Formatting - smaller tick labels for quiet reference
    ax.set_xticks(months)
    ax.set_xticklabels(month_labels, fontsize=7, color=COLORS["muted"])
    ax.set_ylabel("")
    ax.tick_params(axis="y", labelcolor=COLORS["muted"], labelsize=8)

    # Y-axis: tighten to data range, 5 gridlines, EUR symbol
    data_max = max(liquid_m.max(), illiquid_m.max() if has_illiquid else 0)
    ax.set_ylim(0, data_max * 1.1)  # 10% margin above data
    ax.yaxis.set_major_locator(plt.MaxNLocator(5))
    top = ax.get_ylim()[1]
    ax.yaxis.set_major_formatter(
        FuncFormatter(lambda v, _: f"€{v:.0f}M" if abs(v - top) < 1e-6 else f"€{v:.0f}M")
    )

    # Gridlines
    ax.grid(True, axis="y", alpha=0.2, linestyle="-", linewidth=0.5, color=COLORS["muted"])
    ax.set_axisbelow(True)

    # Spines
    for spine in ax.spines.values():
        spine.set_color(COLORS["muted"])
        spine.set_linewidth(0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Legend: stacked on right side, borderless, bright text
    handles, labels = ax.get_legend_handles_labels()
    legend = ax.legend(
        handles[::-1],
        labels[::-1],
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        frameon=False,
        fontsize=8,
        handlelength=1.5,
        borderaxespad=0,
    )
    # Brighten legend text from muted to near-white
    for text in legend.get_texts():
        text.set_color(COLORS["text"])

    fig.tight_layout()
    return fig


def plot_redemption_and_nav_combined(
    monthly_rows: list[dict],
    initial_nav: Decimal,
    fund_name: str = "Fund",
    as_of_date: str = None,
    dark_mode: bool = True,
) -> plt.Figure:
    """Combined plot: redemptions, shortfall, liquidity cost, and NAV evolution."""
    df = pd.DataFrame(monthly_rows)
    colors = _palette(dark_mode=dark_mode)

    # Data preparation
    paid_m = df["paid_redemption"].astype(float) / 1e6
    deferred_m = df["deferred_redemption"].astype(float) / 1e6
    backlog_m = df["cumulative_backlog"].astype(float) / 1e6
    has_backlog = backlog_m.abs().max() > BACKLOG_DISPLAY_EPSILON_M
    liquidity_shortfall_m = (
        df.get("liquidity_shortfall", pd.Series(0.0, index=df.index)).astype(float) / 1e6
    )
    has_liquidity_shortfall = bool((liquidity_shortfall_m > 0).any())
    realised_liquidity_cost_m = (
        df.get("realised_liquidity_cost", pd.Series(0.0, index=df.index)).astype(float) / 1e6
    )
    swing_adjustment_received_m = (
        df.get("swing_pricing_adjustment_received", pd.Series(0.0, index=df.index)).astype(float)
        / 1e6
    )
    swing_receivable_opening_m = (
        df.get("swing_pricing_receivable_opening", pd.Series(0.0, index=df.index)).astype(float)
        / 1e6
    )
    swing_receivable_closing_m = (
        df.get("swing_pricing_receivable_closing", pd.Series(0.0, index=df.index)).astype(float)
        / 1e6
    )
    # Liquidity cost allocated to redeeming investors = swing received + increase in receivable
    swing_receivable_increase_m = swing_receivable_closing_m - swing_receivable_opening_m
    allocated_liquidity_cost_m = swing_adjustment_received_m + swing_receivable_increase_m
    # Net fund-borne cost = economic cost - allocated cost
    net_fund_borne_m = realised_liquidity_cost_m - allocated_liquidity_cost_m
    illiquid_m = df["illiquid_nav"].astype(float) / 1e6
    liquid_m = df["liquid_nav"].astype(float) / 1e6
    months = df["month"].values

    # Generate month labels
    if as_of_date:
        computation_date = pd.Timestamp(as_of_date)
    else:
        computation_date = pd.Timestamp.now()

    month_labels = [
        (computation_date + timedelta(days=30 * i)).strftime("%b/%y") for i in range(len(months))
    ]

    # Give small liquidity shortfalls their own scale immediately below redemptions.
    if has_liquidity_shortfall:
        fig, axes = plt.subplots(
            4,
            1,
            figsize=(7, 6.8),
            sharex=True,
            dpi=120,
            gridspec_kw={"height_ratios": [2.2, 0.8, 0.8, 2.2]},
        )
        ax1, ax_shortfall, ax_cost, ax2 = axes
    else:
        fig, axes = plt.subplots(
            3,
            1,
            figsize=(7, 6.0),
            sharex=True,
            dpi=120,
            gridspec_kw={"height_ratios": [2.2, 0.8, 2.2]},
        )
        ax1, ax_cost, ax2 = axes
        ax_shortfall = None
    fig.patch.set_facecolor(colors["bg"])
    fig.patch.set_alpha(0 if dark_mode else 1)
    fig.subplots_adjust(hspace=0.48, top=0.93, right=0.98, bottom=0.11, left=0.09)

    # ===== TOP SUBPLOT: REDEMPTIONS =====
    ax1.set_facecolor(colors["bg"])

    # Subtitle for redemptions plot
    ax1.set_title(
        (
            "Paid redemptions, deferred redemptions, and backlog"
            if has_backlog
            else "Paid and deferred redemptions"
        ),
        loc="left",
        fontsize=9,
        color=colors["text"],
        fontweight="normal",
        pad=8,
    )

    # Paid redemptions
    ax1.bar(months, paid_m, color=colors["blue_paid"], label="Paid", width=0.6)

    # Deferred redemptions
    ax1.bar(
        months,
        deferred_m,
        color=colors["blue_paid"],
        alpha=0.3,
        hatch="///",
        label="Deferred",
        bottom=paid_m,
        width=0.6,
        edgecolor=colors["blue_paid"],
        linewidth=0.8,
    )

    if has_backlog:
        backlog_m_clean = backlog_m.where(backlog_m.abs() > BACKLOG_DISPLAY_EPSILON_M, 0)
        ax1.plot(
            months,
            backlog_m_clean,
            color=colors["orange"],
            marker="o",
            linewidth=2.5,
            label="Backlog",
            markersize=6,
        )

    ax1.set_ylabel("")
    redemption_axis_max_m = float(initial_nav * Decimal("0.60")) / 1e6
    ax1.set_ylim(0, redemption_axis_max_m)
    ax1.tick_params(axis="y", labelcolor=colors["muted"], labelsize=8)
    ax1.yaxis.set_major_locator(plt.MaxNLocator(5))
    top1 = ax1.get_ylim()[1]
    ax1.yaxis.set_major_formatter(
        FuncFormatter(lambda v, _: f"€{v:.0f}M" if abs(v - top1) < 1e-6 else f"€{v:.0f}M")
    )
    # Share x-axis with the NAV plot; show month labels only at the bottom.
    ax1.xaxis.set_visible(True)
    ax1.set_xticks(months)
    ax1.set_xlim(0.5, len(months) + 0.5)
    ax1.tick_params(axis="x", labelbottom=False, labeltop=False, length=0)
    ax1.grid(True, axis="y", alpha=0.35, linestyle="-", linewidth=0.5, color=colors["grid"])
    ax1.set_axisbelow(True)

    for spine in ax1.spines.values():
        spine.set_color(colors["muted"])
        spine.set_linewidth(0.5)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # Legend for redemptions
    legend1 = ax1.legend(
        loc="lower right",
        bbox_to_anchor=(1.0, 1.02),
        ncol=3 if has_backlog else 2,
        frameon=False,
        fontsize=8,
        handlelength=1.2,
        handletextpad=0.4,
        columnspacing=0.8,
        borderaxespad=0,
    )
    for text in legend1.get_texts():
        text.set_color(colors["text"])

    # ===== OPTIONAL SUBPLOT: LIQUIDITY SHORTFALL =====
    if ax_shortfall is not None:
        shortfall_max_m = float(liquidity_shortfall_m.max())
        ax_shortfall.set_facecolor(colors["bg"])
        ax_shortfall.set_title(
            "Liquidity shortfall (unfunded)",
            loc="left",
            fontsize=9,
            color=colors["text"],
            fontweight="normal",
            pad=6,
        )
        ax_shortfall.bar(
            months,
            -liquidity_shortfall_m,
            color=colors["shortfall"],
            alpha=0.75,
            width=0.6,
        )
        ax_shortfall.axhline(0, color=colors["muted"], linewidth=0.6)
        ax_shortfall.set_ylim(-shortfall_max_m * 1.25, 0)
        ax_shortfall.set_ylabel("")
        ax_shortfall.yaxis.set_major_locator(plt.MaxNLocator(3))

        def shortfall_formatter(value: float, _: float) -> str:
            if shortfall_max_m < 0.01:
                return f"€{value * 1000:.1f}k"
            return f"€{value:.2f}M"

        ax_shortfall.yaxis.set_major_formatter(FuncFormatter(shortfall_formatter))
        ax_shortfall.tick_params(axis="y", labelcolor=colors["muted"], labelsize=8)
        ax_shortfall.tick_params(axis="x", labelbottom=False, length=0)
        ax_shortfall.grid(
            True,
            axis="y",
            alpha=0.3,
            linestyle="-",
            linewidth=0.5,
            color=colors["grid"],
        )
        ax_shortfall.set_axisbelow(True)
        for spine in ax_shortfall.spines.values():
            spine.set_color(colors["muted"])
            spine.set_linewidth(0.5)
        ax_shortfall.spines["top"].set_visible(False)
        ax_shortfall.spines["right"].set_visible(False)

    # ===== LIQUIDITY COST OWNERSHIP SUBPLOT =====
    ax_cost.set_facecolor(colors["bg"])
    ax_cost.set_title(
        "Realised liquidity cost",
        loc="left",
        fontsize=9,
        color=colors["text"],
        fontweight="normal",
        pad=6,
    )

    # Two-line chart: Economic cost (always constant) and Fund-borne cost (drops when swing active)
    ax_cost.plot(
        months,
        realised_liquidity_cost_m,
        color=colors["nav_liquid"],
        marker="o",
        linewidth=2.0,
        markersize=5,
        label="Economic cost",
        zorder=3,
    )
    ax_cost.plot(
        months,
        net_fund_borne_m,
        color=colors["orange"],
        marker="s",
        linewidth=1.8,
        markersize=4,
        linestyle="-",
        label="Fund-borne cost",
        zorder=2,
    )
    ax_cost.fill_between(
        months,
        0,
        realised_liquidity_cost_m,
        color=colors["nav_liquid"],
        alpha=0.10,
        zorder=1,
    )

    cost_max = float(realised_liquidity_cost_m.max()) if realised_liquidity_cost_m.max() > 0 else 1
    ax_cost.set_ylim(0, cost_max * 1.25 if cost_max > 0 else 1)
    ax_cost.set_ylabel("")
    ax_cost.yaxis.set_major_locator(plt.MaxNLocator(3))
    ax_cost.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"€{value:.2f}M"))
    ax_cost.tick_params(axis="y", labelcolor=colors["muted"], labelsize=8)
    ax_cost.tick_params(axis="x", labelbottom=False, length=0)
    ax_cost.grid(True, axis="y", alpha=0.3, linestyle="-", linewidth=0.5, color=colors["grid"])
    ax_cost.set_axisbelow(True)
    for spine in ax_cost.spines.values():
        spine.set_color(colors["muted"])
        spine.set_linewidth(0.5)
    ax_cost.spines["top"].set_visible(False)
    ax_cost.spines["right"].set_visible(False)
    legend_cost = ax_cost.legend(
        loc="lower right",
        bbox_to_anchor=(1.0, 1.02),
        ncol=2,
        frameon=False,
        fontsize=8,
        handlelength=1.2,
        handletextpad=0.4,
        columnspacing=0.8,
        borderaxespad=0,
    )
    for text in legend_cost.get_texts():
        text.set_color(colors["text"])

    # ===== BOTTOM SUBPLOT: NAV EVOLUTION =====
    ax2.set_facecolor(colors["bg"])

    # Check if illiquid has meaningful values
    has_illiquid = (illiquid_m > 0).any()

    if has_illiquid:
        ax2.stackplot(
            months,
            illiquid_m,
            liquid_m,
            labels=["Illiquid NAV", "Liquid NAV"],
            colors=[colors["nav_illiquid"], colors["nav_liquid"]],
            alpha=0.85,
        )
    else:
        ax2.fill_between(
            months,
            0,
            liquid_m,
            label="Liquid NAV",
            color=colors["nav_liquid"],
            alpha=0.85,
        )

    ax2.set_title(
        "Liquid / illiquid NAV",
        loc="left",
        fontsize=9,
        color=colors["text"],
        fontweight="normal",
        pad=8,
    )
    ax2.set_ylabel("")
    ax2.tick_params(axis="y", labelcolor=colors["muted"], labelsize=8)
    ax2.yaxis.set_major_locator(plt.MaxNLocator(5))
    data_max = max(liquid_m.max(), illiquid_m.max() if has_illiquid else 0)
    ax2.set_ylim(0, data_max * 1.1)
    top2 = ax2.get_ylim()[1]
    ax2.yaxis.set_major_formatter(
        FuncFormatter(lambda v, _: f"€{v:.0f}M" if abs(v - top2) < 1e-6 else f"€{v:.0f}M")
    )
    ax2.grid(True, axis="y", alpha=0.35, linestyle="-", linewidth=0.5, color=colors["grid"])
    ax2.set_axisbelow(True)

    for spine in ax2.spines.values():
        spine.set_color(colors["muted"])
        spine.set_linewidth(0.5)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    # Shared x-axis formatting (only on bottom)
    ax2.set_xticks(months)
    ax2.set_xlim(0.5, len(months) + 0.5)
    ax2.set_xticklabels(month_labels, fontsize=7, color=colors["muted"])

    # Legend for NAV - top right
    handles, labels = ax2.get_legend_handles_labels()
    legend2 = ax2.legend(
        handles[::-1],
        labels[::-1],
        loc="upper right",
        bbox_to_anchor=(1.0, 1.0),
        frameon=False,
        fontsize=8,
        handlelength=1.5,
        borderaxespad=0,
    )
    for text in legend2.get_texts():
        text.set_color(colors["text"])

    return fig


def plot_lmt_matrix(
    lmt_rows: list[dict],
    fund_name: str = "Fund",
    as_of_date: str = None,
    dark_mode: bool = True,
) -> plt.Figure:
    """Plot compact monthly LMT signal and application states.

    Hollow circles show threshold signals, filled circles show applied swing
    pricing or gates, and diamonds show assumed suspension months.

    Parameters
    ----------
    lmt_rows : list[dict]
        LMT timeline rows from AppRedemptionPathRun.lmt_timeline_rows
    fund_name : str
        Fund identifier
    as_of_date : str
        Valuation date for month labels

    Returns
    -------
    plt.Figure
        Matplotlib figure object
    """
    df = pd.DataFrame(lmt_rows)
    colors = _palette(dark_mode=dark_mode)

    months = df["month"].values
    trigger_color = colors["orange"]

    tool_order = ["Swing", "Gate", "Suspend"]
    y_positions = {
        "Swing": 2.0,
        "Gate": 1.0,
        "Suspend": 0.0,
    }

    # Generate month labels
    if as_of_date:
        computation_date = pd.Timestamp(as_of_date)
    else:
        computation_date = pd.Timestamp.now()

    month_labels = [
        (computation_date + timedelta(days=30 * i)).strftime("%b/%y") for i in range(len(months))
    ]

    fig, ax = plt.subplots(figsize=(7, 1.25), dpi=120)
    fig.patch.set_facecolor(colors["bg"])
    fig.patch.set_alpha(0 if dark_mode else 1)
    ax.set_facecolor(colors["bg"])
    ax.patch.set_alpha(0 if dark_mode else 1)
    fig.subplots_adjust(top=0.72, left=0.09, right=0.98, bottom=0.3)

    ax.text(
        -0.05,
        1.18,
        "LMT threshold breaches and activations",
        transform=ax.transAxes,
        fontsize=9,
        color=colors["text"],
        fontweight="normal",
        va="center",
    )
    legend = ax.legend(
        handles=[
            Line2D(
                [],
                [],
                marker="o",
                linestyle="none",
                markerfacecolor="none",
                markeredgecolor=trigger_color,
                markersize=4.5,
                label="signal",
            ),
            Line2D(
                [],
                [],
                marker="o",
                linestyle="none",
                markerfacecolor=trigger_color,
                markeredgecolor=trigger_color,
                markersize=4.5,
                label="applied",
            ),
            Line2D(
                [],
                [],
                marker="D",
                linestyle="none",
                markerfacecolor=trigger_color,
                markeredgecolor=trigger_color,
                markersize=4,
                label="suspended",
            ),
        ],
        loc="lower right",
        bbox_to_anchor=(1.0, 1.02),
        ncol=3,
        frameon=False,
        fontsize=7,
        handlelength=0.8,
        handletextpad=0.3,
        columnspacing=0.8,
        borderaxespad=0,
    )
    for text in legend.get_texts():
        text.set_color(colors["muted"])

    # Faint row bands with reduced height
    for tool in tool_order:
        y = y_positions[tool]
        ax.axhspan(y - 0.2, y + 0.2, color=colors["row_band"], alpha=0.03, zorder=0)

    for month, signal, applied in zip(
        months,
        df["swing_signal"].astype(bool),
        df["swing_applied"].astype(bool),
    ):
        _plot_lmt_status_marker(
            ax=ax,
            month=month,
            y=y_positions["Swing"],
            signal=signal,
            applied=applied,
            color=trigger_color,
            marker_edge=colors["marker_edge"],
        )

    for month, signal, applied in zip(
        months,
        df["gate_signal"].astype(bool),
        df["gate_applied"].astype(bool),
    ):
        _plot_lmt_status_marker(
            ax=ax,
            month=month,
            y=y_positions["Gate"],
            signal=signal,
            applied=applied,
            color=trigger_color,
            marker_edge=colors["marker_edge"],
        )

    for month, suspension_applied in zip(
        months,
        df["suspension_applied"].astype(bool),
    ):
        if suspension_applied:
            ax.scatter(
                month,
                y_positions["Suspend"],
                marker="D",
                s=20,
                color=trigger_color,
                edgecolor=colors["marker_edge"],
                linewidth=0.3,
                zorder=3,
            )

    # Axes setup - compact spacing
    ax.set_yticks([y_positions[tool] for tool in tool_order])
    # Use darker color for y-axis labels in light mode for better visibility
    y_label_color = colors["text"] if dark_mode else "#000000"
    ax.set_yticklabels(tool_order, fontsize=8, color=y_label_color, fontweight="600")
    ax.set_xticks(months)
    ax.set_xticklabels(month_labels, fontsize=7, color=colors["text"])
    ax.set_xlim(0.5, len(months) + 0.5)
    ax.set_ylim(-0.4, 3.0)

    # Clean design
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.patch.set_alpha(0 if dark_mode else 1)

    return fig


def _plot_lmt_status_marker(
    *,
    ax: plt.Axes,
    month: int,
    y: float,
    signal: bool,
    applied: bool,
    color: str,
    marker_edge: str,
) -> None:
    if applied:
        ax.scatter(
            month,
            y,
            marker="o",
            s=24,
            color=color,
            edgecolor=marker_edge,
            linewidth=0.3,
            zorder=3,
        )
    elif signal:
        ax.scatter(
            month,
            y,
            marker="o",
            s=24,
            facecolors="none",
            edgecolors=color,
            linewidth=1.0,
            zorder=2,
        )
