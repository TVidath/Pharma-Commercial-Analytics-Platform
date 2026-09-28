"""Load and interpret ``config/engagement_config.yaml``.

The YAML file is the single source of truth. This module loads it and
derives convenience structures (e.g. the month calendar) so callers never
re-implement date logic.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

import yaml

from .paths import DEFAULT_CONFIG_PATH

_MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def load_config(path: Optional[str] = None) -> Dict[str, Any]:
    """Load the engagement config YAML into a dict."""
    cfg_path = path or DEFAULT_CONFIG_PATH
    with open(cfg_path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    return cfg


def _add_months(y: int, m: int, delta: int) -> tuple:
    """Return (year, month) offset by ``delta`` months from (y, m)."""
    idx = (y * 12 + (m - 1)) + delta
    return idx // 12, idx % 12 + 1


def _fiscal_year(y: int, m: int, fy_start: int) -> str:
    """Indian-style fiscal-year label, e.g. FY2024-25 (Apr-Mar)."""
    start_y = y if m >= fy_start else y - 1
    return f"FY{start_y}-{str((start_y + 1) % 100).zfill(2)}"


def build_calendar(cfg: Dict[str, Any], include_forecast: bool = False) -> List[Dict[str, Any]]:
    """Build the monthly calendar rows implied by the config time settings.

    Returns one dict per month with keys matching ``dim_month``.
    """
    t = cfg["time"]
    fy_start = int(cfg["engagement"]["fiscal_year_start_month"])
    end_y, end_m = (int(p) for p in t["period_end"].split("-"))
    n_hist = int(t["history_months"])
    n_fc = int(t["forecast_horizon_months"]) if include_forecast else 0

    # start = period_end minus (history_months - 1)
    start_y, start_m = _add_months(end_y, end_m, -(n_hist - 1))

    rows: List[Dict[str, Any]] = []
    for i in range(n_hist + n_fc):
        y, m = _add_months(start_y, start_m, i)
        rows.append({
            "month_id": y * 100 + m,
            "month_date": date(y, m, 1),
            "year": y,
            "quarter": (m - 1) // 3 + 1,
            "month_num": m,
            "month_name": _MONTH_NAMES[m - 1],
            "fiscal_year": _fiscal_year(y, m, fy_start),
            "is_forecast": i >= n_hist,
        })
    return rows
