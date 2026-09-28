"""Revenue forecasting: seasonal baseline + transparent driver overlay.

A board trusts a forecast it can see. We fit a Holt-Winters / ETS model to the
monthly revenue history (a seasonal, trend-aware **baseline**), then add an
explicit **driver overlay** — the phased capture of the opportunity register
(Milestone 5) — to produce the "with-intervention" scenario. No black box: the
uplift is a visible, tunable ramp tied to named levers.
"""
from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd

from ..utils.config import load_config
from ..utils.logging import get_logger
from ..utils.paths import DATA_PROCESSED
from ..visualization import theme as T

logger = get_logger(__name__)
CRORE = 1e7

import matplotlib.pyplot as plt  # noqa: E402


def monthly_revenue(t: Dict[str, pd.DataFrame]) -> pd.Series:
    """Monthly portfolio revenue (₹ Cr) indexed by month_id, calendar-ordered."""
    months = t["dim_month"].sort_values("month_id")["month_id"]
    rev = (t["fact_prescriptions"].groupby("month_id")["revenue"].sum()
           .reindex(months).fillna(0) / CRORE)
    return rev


def baseline_forecast(series: pd.Series, horizon: int = 12, alpha: float = 0.2) -> pd.DataFrame:
    """ETS (additive trend + seasonal) baseline with prediction interval."""
    from statsmodels.tsa.exponential_smoothing.ets import ETSModel
    # ETSModel needs an indexed Series (a RangeIndex is fine) to label predictions
    y = pd.Series(series.to_numpy(dtype=float))
    model = ETSModel(y, error="add", trend="add", seasonal="add", seasonal_periods=12)
    fit = model.fit(disp=False)
    pred = fit.get_prediction(start=len(y), end=len(y) + horizon - 1)
    sf = pred.summary_frame(alpha=alpha)
    return pd.DataFrame({
        "mean": sf["mean"].to_numpy(),
        "lower": sf["pi_lower"].to_numpy(),
        "upper": sf["pi_upper"].to_numpy(),
    })


def intervention_overlay(baseline_mean: np.ndarray, opportunity_annual_cr: float,
                         capture_fraction: float = 0.5, ramp_months: int = 12) -> np.ndarray:
    """Add a phased capture of the opportunity register to the baseline.

    Monthly uplift ramps linearly to a run-rate of
    ``opportunity_annual * capture_fraction`` by ``ramp_months``.
    """
    monthly_target = opportunity_annual_cr * capture_fraction / 12.0
    ramp = np.minimum(np.arange(1, len(baseline_mean) + 1) / ramp_months, 1.0)
    return baseline_mean + monthly_target * ramp


def build_forecast(t: Dict[str, pd.DataFrame], horizon: int = 12,
                   capture_fraction: float = 0.5) -> Dict[str, Any]:
    """Produce baseline + intervention forecast and scenario summary."""
    hist = monthly_revenue(t)
    fc = baseline_forecast(hist, horizon)

    reg = pd.read_csv(DATA_PROCESSED / "opportunity_register.csv")
    opp_annual = reg.loc[reg["type"] == "Revenue", "value_cr"].sum()
    fc["intervention"] = intervention_overlay(fc["mean"].to_numpy(), opp_annual, capture_fraction, horizon)

    ttm_actual = hist.iloc[-12:].sum()
    y1_base = fc["mean"].sum()
    y1_interv = fc["intervention"].sum()
    exit_runrate = fc["intervention"].iloc[-1] * 12  # annualised exit month
    return {
        "hist": hist, "fc": fc, "opp_annual": opp_annual, "capture_fraction": capture_fraction,
        "ttm_actual": ttm_actual, "y1_base": y1_base, "y1_interv": y1_interv,
        "y1_uplift_cr": y1_interv - y1_base, "y1_uplift_pct": (y1_interv - y1_base) / y1_base * 100,
        "exit_runrate": exit_runrate,
    }


def chart_forecast(res: Dict[str, Any]) -> str:
    hist, fc = res["hist"], res["fc"]
    nh, nf = len(hist), len(fc)
    xh = np.arange(nh)
    xf = np.arange(nh, nh + nf)
    fig, ax = plt.subplots(figsize=(9.4, 5))
    ax.plot(xh, hist.to_numpy(), color=T.INK_SECONDARY, lw=1.8, label="History")
    ax.plot(xf, fc["mean"], color=T.BLUE, lw=2.2, ls="--", label="Baseline forecast")
    ax.fill_between(xf, fc["lower"], fc["upper"], color=T.SEQ_BLUE[1], alpha=0.5,
                    label="80% interval")
    ax.plot(xf, fc["intervention"], color=T.GREEN, lw=2.6, label="With reallocation")
    ax.axvline(nh - 0.5, color=T.BASELINE, lw=1, ls=":")
    ax.text(nh - 0.5, max(hist.max(), fc["intervention"].max()) * 0.06, " forecast >>",
            color=T.MUTED, fontsize=9)
    labels = [str(m)[:4] for m in list(hist.index)[::6]]
    ax.set_xticks(list(xh)[::6]); ax.set_xticklabels(labels)
    ax.set_title("Revenue forecast — baseline vs reallocation scenario")
    ax.set_ylabel("Monthly revenue (₹ Cr)")
    ax.legend(loc="upper left", ncol=2)
    ax.set_ylim(0, max(hist.max(), fc["intervention"].max()) * 1.2)
    return T.save_fig(fig, "21_revenue_forecast")
