"""Shared chart theme and palette for Project Catalyst.

Colours come from a validated, colourblind-safe categorical palette (fixed
slot order — never cycled). One consistent look across the EDA report, the
notebook, and the Streamlit companion so the deliverable reads as one system.
Static charts render on a light surface (report/GitHub friendly).
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict

import matplotlib as mpl
import matplotlib.pyplot as plt

from ..utils.paths import REPORTS_DIR, ensure_dir

# --- Categorical palette (fixed order) --------------------------------------
SERIES = ["#2a78d6", "#008300", "#e87ba4", "#eda100",
          "#1baf7a", "#eb6834", "#4a3aa7", "#e34948"]
BLUE, GREEN, MAGENTA, YELLOW, AQUA, ORANGE, VIOLET, RED = SERIES

# --- Ink / chrome ------------------------------------------------------------
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"

# --- Status (reserved; icon+label in copy, never series) --------------------
GOOD = "#0ca30c"
WARNING = "#fab219"
CRITICAL = "#d03b3b"

# --- Sequential blue ramp (magnitude) ---------------------------------------
SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

# --- Semantic mappings reused across charts ---------------------------------
LIFECYCLE_COLORS: Dict[str, str] = {
    "Launch": BLUE, "Growth": GREEN, "Mature": MUTED, "Decline": RED,
}

FIGURES_DIR = REPORTS_DIR / "figures"


def apply_theme() -> None:
    """Set global matplotlib rcParams for the Catalyst look."""
    mpl.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"],
        "font.size": 11,
        "axes.edgecolor": BASELINE,
        "axes.linewidth": 0.8,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlecolor": INK,
        "axes.labelcolor": INK_SECONDARY,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "text.color": INK,
        "legend.frameon": False,
        "figure.dpi": 120,
    })


def save_fig(fig, name: str) -> str:
    """Save a figure to reports/figures and return the report-relative path."""
    ensure_dir(FIGURES_DIR)
    out = FIGURES_DIR / f"{name}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return f"figures/{name}.png"


def label_bars(ax, bars, fmt="{:.0f}", offset=3, color=INK_SECONDARY, horizontal=False):
    """Attach direct value labels to bars (selective labelling, not gridlines)."""
    for b in bars:
        if horizontal:
            w = b.get_width()
            ax.annotate(fmt.format(w), (w, b.get_y() + b.get_height() / 2),
                        xytext=(offset if w >= 0 else -offset, 0), textcoords="offset points",
                        va="center", ha="left" if w >= 0 else "right", color=color, fontsize=9)
        else:
            h = b.get_height()
            ax.annotate(fmt.format(h), (b.get_x() + b.get_width() / 2, h),
                        xytext=(0, offset), textcoords="offset points",
                        ha="center", va="bottom", color=color, fontsize=9)
