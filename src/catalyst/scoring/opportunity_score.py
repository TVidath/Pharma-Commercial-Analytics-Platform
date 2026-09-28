"""Commercial Opportunity Score — the master field-prioritisation index.

A transparent 0-100 composite that ranks every doctor for the sales force. Five
interpretable components, fixed published weights, no black box — a sales VP can
explain any doctor's score and a rep gets a ranked call list. This is the single
number the field acts on; it feeds territory optimisation (M7) and sizing (M8).

    Score = 0.30·Potential + 0.30·Headroom + 0.15·Momentum
          + 0.15·Accessibility + 0.10·CompetitiveSwitch
"""
from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
import pandas as pd

from ..utils.logging import get_logger
from ..utils.paths import DATA_PROCESSED
from ..visualization import theme as T

logger = get_logger(__name__)
CRORE = 1e7

WEIGHTS = {"potential": 0.30, "headroom": 0.30, "momentum": 0.15,
           "accessibility": 0.15, "competitive": 0.10}

import matplotlib.pyplot as plt  # noqa: E402


def _pct(s: pd.Series) -> pd.Series:
    """Percentile rank scaled to 0-100."""
    return s.rank(pct=True) * 100


def compute_scores(t: Dict[str, pd.DataFrame], seg: pd.DataFrame = None,
                   data_dir=DATA_PROCESSED) -> pd.DataFrame:
    """Return per-doctor opportunity score with its five components + priority tier.

    ``seg`` is the doctor-segment frame (Milestone 4); if omitted it is read from
    ``data_dir/doctor_segments.csv``.
    """
    if seg is None:
        seg = pd.read_csv(data_dir / "doctor_segments.csv")
    months = t["dim_month"].sort_values("month_id")["month_id"].tolist()
    last3, prior3 = months[-3:], months[-6:-3]
    rx = t["fact_prescriptions"]

    # momentum: recent 3m vs prior 3m revenue growth
    r_last = rx[rx.month_id.isin(last3)].groupby("doctor_id")["revenue"].sum()
    r_prior = rx[rx.month_id.isin(prior3)].groupby("doctor_id")["revenue"].sum()
    mom = ((r_last - r_prior) / r_prior.replace(0, np.nan)).rename("mom_growth")

    # competitive switch: TTM competitor share across the doctor's TAs
    ttm = months[-12:]
    our_u = rx[rx.month_id.isin(ttm)].groupby("doctor_id")["units_prescribed"].sum()
    comp_u = (t["fact_competitor_rx"][t["fact_competitor_rx"].month_id.isin(ttm)]
              .groupby("doctor_id")["competitor_units"].sum())
    comp_share = (comp_u / (comp_u + our_u.reindex(comp_u.index).fillna(0))).rename("comp_share")

    geo = (t["dim_doctor"][["doctor_id", "territory_id"]]
           .merge(t["dim_territory"][["territory_id", "region_id"]], on="territory_id")
           .merge(t["dim_region"][["region_id", "region_name"]], on="region_id"))

    d = seg.merge(mom, on="doctor_id", how="left").merge(comp_share, on="doctor_id", how="left")
    d = d.merge(geo[["doctor_id", "region_name"]], on="doctor_id", how="left")
    d[["mom_growth", "comp_share"]] = d[["mom_growth", "comp_share"]].fillna(0)

    # --- components (0-100) ---
    d["c_potential"] = d["potential_score"]                       # already 0-100
    d["c_headroom"] = _pct(d["opportunity_gap"])                  # untapped opportunity
    d["c_momentum"] = _pct(d["mom_growth"])                       # recent trajectory
    d["c_accessibility"] = 100 - _pct(d["ttm_calls"])            # under-serviced headroom
    d["c_competitive"] = _pct(d["comp_share"])                    # switch pool

    d["opportunity_score"] = np.round(
        WEIGHTS["potential"] * d["c_potential"]
        + WEIGHTS["headroom"] * d["c_headroom"]
        + WEIGHTS["momentum"] * d["c_momentum"]
        + WEIGHTS["accessibility"] * d["c_accessibility"]
        + WEIGHTS["competitive"] * d["c_competitive"], 1)

    # priority tiers by score percentile
    p = d["opportunity_score"].rank(pct=True)
    d["priority_tier"] = np.select([p >= 0.80, p >= 0.50], ["P1", "P2"], default="P3")
    return d


def territory_scores(doc: pd.DataFrame, t: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Aggregate the opportunity score to territory level (feeds M7)."""
    geo = (t["dim_doctor"][["doctor_id", "territory_id"]])
    d = doc.merge(geo, on="doctor_id")
    agg = d.groupby("territory_id").agg(
        avg_opportunity_score=("opportunity_score", "mean"),
        p1_doctors=("priority_tier", lambda s: (s == "P1").sum()),
        white_space_cr=("white_space_value", lambda s: s.sum() / CRORE),
        n_doctors=("doctor_id", "count")).reset_index()
    return agg


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
TIER_COLOR = {"P1": T.CRITICAL, "P2": T.YELLOW, "P3": T.MUTED}


def chart_score_distribution(doc: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(8, 4.6))
    bins = np.linspace(0, 100, 41)
    for tier in ["P3", "P2", "P1"]:
        ax.hist(doc[doc.priority_tier == tier]["opportunity_score"], bins=bins,
                color=TIER_COLOR[tier], alpha=0.85, label=tier)
    ax.set_title("Commercial Opportunity Score — distribution by priority tier")
    ax.set_xlabel("Opportunity score (0–100)"); ax.set_ylabel("# doctors")
    ax.legend(title="Priority", loc="upper right")
    return T.save_fig(fig, "22_score_distribution")


def chart_score_vs_calls(doc: pd.DataFrame) -> Tuple[str, Dict]:
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(doc["ttm_calls"], doc["opportunity_score"], s=6, color=T.BLUE, alpha=0.35, edgecolors="none")
    call_med = doc["ttm_calls"].median()
    score_hi = doc["opportunity_score"].quantile(0.80)
    ax.axvline(call_med, color=T.BASELINE, lw=1); ax.axhline(score_hi, color=T.BASELINE, lw=1)
    act = doc[(doc["opportunity_score"] >= score_hi) & (doc["ttm_calls"] < call_med)]
    ax.axhspan(score_hi, 100, xmin=0, xmax=call_med / ax.get_xlim()[1], color=T.CRITICAL, alpha=0.06)
    ax.annotate(f"ACT NOW\n{len(act):,} high-score,\nunder-called doctors",
                (call_med * 0.15, score_hi + (100 - score_hi) * 0.35), color=T.CRITICAL,
                fontsize=9.5, fontweight="bold")
    ax.set_title("The call list: opportunity score vs current effort")
    ax.set_xlabel("TTM calls received"); ax.set_ylabel("Opportunity score")
    return T.save_fig(fig, "23_score_vs_calls"), {"act_now": len(act)}


def chart_component_by_tier(doc: pd.DataFrame) -> str:
    comps = ["c_potential", "c_headroom", "c_momentum", "c_accessibility", "c_competitive"]
    names = ["Potential", "Headroom", "Momentum", "Accessibility", "Competitive"]
    g = doc.groupby("priority_tier")[comps].mean().reindex(["P1", "P2", "P3"])
    x = np.arange(len(comps)); w = 0.26
    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    for i, tier in enumerate(["P1", "P2", "P3"]):
        ax.bar(x + (i - 1) * w, g.loc[tier], w, color=TIER_COLOR[tier], label=tier)
    ax.set_xticks(x); ax.set_xticklabels(names)
    ax.set_title("What drives priority — average component score by tier")
    ax.set_ylabel("Component score (0–100)")
    ax.legend(title="Priority", loc="upper right"); ax.grid(axis="y")
    return T.save_fig(fig, "24_component_by_tier")
