"""Matplotlib plots for LMT redemption path analysis.

Adapted from fund-risk-workflow liquidity_calibration_display.py
"""

from datetime import timedelta
from decimal import Decimal

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FuncFormatter

# Color palette (from brief + fund-risk-workflow)
COLORS = {
    "bg": "#0d1424",
    "text": "#c9d4e3",
    "muted": "#9ca3af",
    "cyan": "#39c2d6",
    "orange": "#f5793b",
    "blue_paid": "#2d6fe8",  # Paid redemption
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
    "blue_bright": "#1d4ed8",
    "nav_liquid": "#2f5aa8",
    "nav_illiquid": "#1f4b5f",
    "grid": "#d1d5db",
    "marker_edge": "#ffffff",
    "row_band": "#111827",
}


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
    """Plot redemptions: paid, deferred, and backlog over time.

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

    # Backlog: orange (outstanding balance)
    ax.plot(
        months,
        backlog_m,
        color=COLORS["orange"],
        marker="o",
        linewidth=2.5,
        label="Backlog",
        markersize=6,
    )

    # Formatting - smaller tick labels for quiet reference
    ax.set_xticks(months)
    ax.set_xticklabels(month_labels, fontsize=7, color=COLORS["muted"])
    ax.set_ylabel("")
    ax.tick_params(axis="y", labelcolor=COLORS["muted"], labelsize=8)

    # Y-axis: fixed to 60% of initial NAV, 5 gridlines, M-suffixed format with EUR symbol
    y_max = float(initial_nav) / 1e6 * 0.6
    ax.set_ylim(0, y_max)
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

    fig, ax = plt.subplots(figsize=(7, 2.4), dpi=120)
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
    """Combined plot: redemptions and NAV evolution with shared x-axis.

    Three compact subplots with synchronized month labels.
    """
    df = pd.DataFrame(monthly_rows)
    colors = _palette(dark_mode=dark_mode)

    # Data preparation
    paid_m = df["paid_redemption"].astype(float) / 1e6
    deferred_m = df["deferred_redemption"].astype(float) / 1e6
    backlog_m = df["cumulative_backlog"].astype(float) / 1e6
    realised_liquidity_cost_m = (
        df.get("realised_liquidity_cost", pd.Series(0.0, index=df.index)).astype(float) / 1e6
    )
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

    # Keep liquidity cost separate from redemption bars while sharing the monthly timeline.
    fig, (ax1, ax_cost, ax2) = plt.subplots(
        3,
        1,
        figsize=(7, 6.0),
        sharex=True,
        dpi=120,
        gridspec_kw={"height_ratios": [2.2, 0.8, 2.2]},
    )
    fig.patch.set_facecolor(colors["bg"])
    fig.patch.set_alpha(0 if dark_mode else 1)
    fig.subplots_adjust(hspace=0.58, top=0.93, right=0.98, bottom=0.11, left=0.09)

    # ===== TOP SUBPLOT: REDEMPTIONS =====
    ax1.set_facecolor(colors["bg"])

    # Subtitle for redemptions plot
    ax1.set_title(
        "Paid / deferred / backlog",
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

    # Backlog line
    ax1.plot(
        months,
        backlog_m,
        color=colors["orange"],
        marker="o",
        linewidth=2.5,
        label="Backlog",
        markersize=6,
    )

    ax1.set_ylabel("")
    redemption_axis_max_m = float(initial_nav * Decimal("0.80")) / 1e6
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
        ncol=3,
        frameon=False,
        fontsize=8,
        handlelength=1.2,
        handletextpad=0.4,
        columnspacing=0.8,
        borderaxespad=0,
    )
    for text in legend1.get_texts():
        text.set_color(colors["text"])

    # ===== MIDDLE SUBPLOT: REALISED LIQUIDITY COST =====
    ax_cost.set_facecolor(colors["bg"])
    ax_cost.set_title(
        "Realised liquidity cost",
        loc="left",
        fontsize=8,
        color=colors["text"],
        fontweight="normal",
        pad=6,
    )
    ax_cost.plot(
        months,
        realised_liquidity_cost_m,
        color=colors["cyan"],
        marker="o",
        linewidth=1.8,
        markersize=4,
    )
    ax_cost.fill_between(
        months,
        0,
        realised_liquidity_cost_m,
        color=colors["cyan"],
        alpha=0.14,
    )
    cost_max = float(realised_liquidity_cost_m.max())
    ax_cost.set_ylim(0, cost_max * 1.25 if cost_max > 0 else 1)
    ax_cost.set_ylabel("")
    ax_cost.yaxis.set_major_locator(plt.MaxNLocator(3))
    ax_cost.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"€{value:.2f}M"))
    ax_cost.tick_params(axis="y", labelcolor=colors["muted"], labelsize=7)
    ax_cost.tick_params(axis="x", labelbottom=False, length=0)
    ax_cost.grid(True, axis="y", alpha=0.3, linestyle="-", linewidth=0.5, color=colors["grid"])
    ax_cost.set_axisbelow(True)
    for spine in ax_cost.spines.values():
        spine.set_color(colors["muted"])
        spine.set_linewidth(0.5)
    ax_cost.spines["top"].set_visible(False)
    ax_cost.spines["right"].set_visible(False)

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
    """Plot LMT trigger status matrix: Gate, Swing, Suspension by month.

    Binary status grid showing which months each LMT tool is triggered.
    Filled circles = triggered, X markers = not triggered.

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
    inactive_color = colors["muted"]

    # Tool order and positions
    tool_order = ["Swing", "Gate", "Suspension"]
    tool_columns = ["swing_pricing", "redemption_gate", "suspension"]
    y_positions = {
        "Swing": 2.0,
        "Gate": 1.0,
        "Suspension": 0.0,
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

    ax.scatter(
        -0.05,
        1.18,
        transform=ax.transAxes,
        marker="o",
        s=24,
        color=trigger_color,
        edgecolor=colors["marker_edge"],
        linewidth=0.3,
        clip_on=False,
        zorder=4,
    )
    ax.text(
        -0.037,
        1.18,
        "Activated LMTs",
        transform=ax.transAxes,
        fontsize=8,
        color=colors["text"],
        fontweight="normal",
        va="center",
    )

    # Faint row bands with reduced height
    for tool in tool_order:
        y = y_positions[tool]
        ax.axhspan(y - 0.2, y + 0.2, color=colors["row_band"], alpha=0.03, zorder=0)

    # Plot markers for each tool
    for tool, col_name in zip(tool_order, tool_columns):
        y = y_positions[tool]
        trigger_status = df[col_name].astype(bool).values

        for month, is_active in zip(months, trigger_status):
            if is_active:
                # Filled circle for triggered
                ax.scatter(
                    month,
                    y,
                    marker="o",
                    s=24,
                    color=trigger_color,
                    edgecolor=colors["marker_edge"],
                    linewidth=0.3,
                    zorder=3,
                )
            else:
                # X marker for not triggered
                ax.scatter(
                    month,
                    y,
                    marker="x",
                    s=18,
                    color=inactive_color,
                    alpha=0.6,
                    linewidth=1.0,
                    zorder=2,
                )

    # Axes setup - compact spacing
    ax.set_yticks([y_positions[tool] for tool in tool_order])
    ax.set_yticklabels(tool_order, fontsize=8, color=colors["text"])
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
