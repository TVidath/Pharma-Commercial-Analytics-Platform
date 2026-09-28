"""Territory & Sales-Force Optimization (Modules 9 & 15).

Method: workload-balancing against opportunity (alignment approach),
kept interpretable and actionable for leadership.

1. **Ideal call plan** — opportunity-based target call frequency per doctor
   (P1 > P2 > P3).
2. **Capacity-neutral reallocation** — redistribute each rep's *existing* call
   capacity across their doctors by that ideal, so effort moves from over-served
   P3 doctors to under-served P1 white space at **flat cost**.
3. **Workload index** — required load vs rep capacity per territory identifies
   structurally under/over-resourced territories and sizes **rep deployment**.
"""
from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd

from ..utils.logging import get_logger
from ..utils.paths import DATA_PROCESSED

logger = get_logger(__name__)
CRORE = 1e7

# ideal annual call frequency by priority tier (the "should-be" cadence)
IDEAL_FREQ = {"P1": 18, "P2": 9, "P3": 3}


def build_plan(t: Dict[str, pd.DataFrame], score: pd.DataFrame = None,
               data_dir=DATA_PROCESSED) -> Dict[str, Any]:
    """Compute the doctor call plan, territory workload, and deployment sizing.

    ``score`` is the opportunity-score frame (Milestone 6); if omitted it is read
    from ``data_dir/doctor_opportunity_score.csv``.
    """
    if score is None:
        score = pd.read_csv(data_dir / "doctor_opportunity_score.csv")
    doc = score.copy()
    if "territory_id" not in doc.columns:
        doc = doc.merge(t["dim_doctor"][["doctor_id", "territory_id"]], on="doctor_id")
    rep = t["dim_sales_rep"][["territory_id", "rep_id", "monthly_call_target", "employment_status"]]
    doc = doc.merge(rep, on="territory_id", how="left")

    doc["ideal_calls"] = doc["priority_tier"].map(IDEAL_FREQ)

    # rep-level totals for capacity-neutral reallocation
    rep_tot = doc.groupby("territory_id").agg(cur_total=("ttm_calls", "sum"),
                                              ideal_total=("ideal_calls", "sum"))
    doc = doc.merge(rep_tot, on="territory_id")
    # recommended calls = rep's current capacity re-split by ideal weights
    doc["rec_calls"] = np.where(
        doc["cur_total"] > 0,
        (doc["cur_total"] * doc["ideal_calls"] / doc["ideal_total"]).round(),
        doc["ideal_calls"])  # vacant/uncalled -> ideal (flags deployment need)
    doc["delta_calls"] = doc["rec_calls"] - doc["ttm_calls"]

    # --- territory rollup: capacity, coverage, workload index ---
    cap = rep.copy()
    cap["capacity"] = np.where(cap["employment_status"] == "Active",
                               cap["monthly_call_target"] * 12, 0)
    covered = (t["fact_sales_calls"][t["fact_sales_calls"]["calls_made"] > 0]
               .merge(t["dim_doctor"][["doctor_id", "territory_id"]], on="doctor_id")
               .groupby("territory_id")["doctor_id"].nunique().rename("covered"))
    terr = doc.groupby("territory_id").agg(
        region_name=("region_name", "first"),
        required=("ideal_calls", "sum"),
        current_calls=("ttm_calls", "sum"),
        n_doctors=("doctor_id", "count"),
        p1_doctors=("priority_tier", lambda s: (s == "P1").sum()),
        white_space_cr=("white_space_value", lambda s: s.sum() / CRORE)).reset_index()
    terr = terr.merge(cap[["territory_id", "capacity", "employment_status"]], on="territory_id")
    terr = terr.merge(covered, on="territory_id", how="left").fillna({"covered": 0})
    terr["coverage_pct"] = terr["covered"] / terr["n_doctors"] * 100
    terr["calls_per_doctor"] = terr["current_calls"] / terr["n_doctors"]
    terr["workload_index"] = terr["required"] / terr["capacity"].replace(0, np.nan)

    # Reach (coverage %) is saturated — reps see almost every doctor at least
    # once. The binding signal is call FREQUENCY (calls per doctor): under-served
    # territories get too few touches per doctor despite high opportunity.
    # Targets = bottom-quartile frequency ∩ top-quartile opportunity (active reps);
    # vacancies (no rep) are always a deployment need.
    ws_hi = terr["white_space_cr"].quantile(0.75)
    ws_med = terr["white_space_cr"].median()
    freq_q1 = terr.loc[terr["capacity"] > 0, "calls_per_doctor"].quantile(0.25)
    freq_q3 = terr.loc[terr["capacity"] > 0, "calls_per_doctor"].quantile(0.75)

    def _action(r):
        if r["capacity"] == 0:                                    # no active rep
            return "Deploy rep (vacant)"
        if r["calls_per_doctor"] < freq_q1 and r["white_space_cr"] >= ws_hi:
            return "Reinforce — under-served"
        if r["calls_per_doctor"] >= freq_q3 and r["white_space_cr"] < ws_med:
            return "Over-served — trim/redeploy"
        return "Balanced"
    terr["action"] = terr.apply(_action, axis=1)

    n_vacant = int((terr["action"] == "Deploy rep (vacant)").sum())
    n_reinforce = int((terr["action"] == "Reinforce — under-served").sum())
    n_over = int((terr["action"] == "Over-served — trim/redeploy").sum())
    # New HEADCOUNT is only the vacancies — reinforce territories lift frequency
    # via the (free) within-rep reallocation, not by adding reps. This keeps the
    # plan at flat cost apart from filling budgeted vacant roles.
    new_reps = n_vacant

    reallocated = doc.loc[doc["delta_calls"] > 0, "delta_calls"].sum()  # capacity-neutral shift
    total_calls = doc["ttm_calls"].sum()
    deploy_mask = terr["action"].isin(["Deploy rep (vacant)", "Reinforce — under-served"])

    summary = {
        "reallocated_calls": int(reallocated),
        "reallocated_pct": reallocated / total_calls * 100,
        "n_vacant": n_vacant,
        "n_reinforce": n_reinforce,
        "n_over": n_over,
        "new_reps": new_reps,
        "deploy_white_space_cr": terr[deploy_mask]["white_space_cr"].sum(),
        "avg_coverage": terr.loc[terr["capacity"] > 0, "coverage_pct"].mean(),
    }
    doc_plan = doc[["doctor_id", "territory_id", "region_name", "segment", "priority_tier",
                    "opportunity_score", "ttm_calls", "rec_calls", "delta_calls", "white_space_value"]]
    return {"doc_plan": doc_plan, "terr": terr, "summary": summary}
