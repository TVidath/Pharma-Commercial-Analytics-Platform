"""Milestone 7 report: territory & sales-force optimization."""
from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd

from ..data_pipeline.validate import load_tables
from ..utils.config import load_config
from ..utils.logging import get_logger
from ..utils.paths import DATA_PROCESSED, REPORTS_DIR, ensure_dir
from ..visualization import theme as T
from .optimize import IDEAL_FREQ, build_plan

logger = get_logger(__name__)
CRORE = 1e7

ACTION_COLOR = {
    "Deploy rep (vacant)": T.CRITICAL,
    "Reinforce — under-served": T.ORANGE,
    "Over-served — trim/redeploy": T.BLUE,
    "Balanced": T.MUTED,
}

import matplotlib.pyplot as plt  # noqa: E402


def chart_call_reallocation(doc: pd.DataFrame) -> str:
    g = doc.groupby("priority_tier").agg(current=("ttm_calls", "sum"),
                                         recommended=("rec_calls", "sum")).reindex(["P1", "P2", "P3"])
    x = np.arange(3); w = 0.38
    fig, ax = plt.subplots(figsize=(7.6, 4.8))
    b1 = ax.bar(x - w / 2, g["current"] / 1000, w, color=T.MUTED, label="Current")
    b2 = ax.bar(x + w / 2, g["recommended"] / 1000, w, color=T.BLUE, label="Recommended")
    for bars in (b1, b2):
        T.label_bars(ax, bars, fmt="{:.0f}k")
    ax.set_xticks(x); ax.set_xticklabels(["P1 (act)", "P2", "P3 (over-served)"])
    ax.set_title("Capacity-neutral call reallocation by priority tier")
    ax.set_ylabel("Annual calls ('000)"); ax.legend(loc="upper right"); ax.grid(axis="y")
    return T.save_fig(fig, "25_call_reallocation")


def chart_workload_distribution(terr: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(8, 4.6))
    wi = terr["workload_index"].clip(upper=2.5).dropna()
    ax.hist(wi, bins=30, color=T.SEQ_BLUE[3], alpha=0.9)
    ax.axvline(1.0, color=T.INK_SECONDARY, lw=1.4, ls="--", label="Balanced (index = 1.0)")
    ax.axvspan(1.15, 2.5, color=T.ORANGE, alpha=0.08)
    ax.axvspan(0, 0.85, color=T.BLUE, alpha=0.06)
    ax.set_title("Territory workload index — required load vs rep capacity")
    ax.set_xlabel("Workload index (>1 under-resourced, <1 slack)")
    ax.set_ylabel("# territories"); ax.legend(loc="upper right")
    return T.save_fig(fig, "26_workload_distribution")


def chart_deployment(terr: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(8.4, 5.2))
    wi = terr["workload_index"].clip(upper=2.5).fillna(2.5)
    for action, col in ACTION_COLOR.items():
        s = terr[terr["action"] == action]
        w = s["workload_index"].clip(upper=2.5).fillna(2.5)
        ax.scatter(w, s["white_space_cr"], s=34, color=col, alpha=0.7, edgecolors="white", label=action)
    ax.axvline(1.0, color=T.BASELINE, lw=1)
    ax.set_title("Rep deployment map — opportunity vs workload")
    ax.set_xlabel("Workload index (capped at 2.5; vacant plotted at 2.5)")
    ax.set_ylabel("Territory white space (₹ Cr)")
    ax.legend(loc="upper left", fontsize=8)
    return T.save_fig(fig, "27_deployment_map")


def chart_deploy_targets(terr: pd.DataFrame) -> str:
    d = terr[terr["action"].isin(["Deploy rep (vacant)", "Reinforce — under-served"])]
    d = d.sort_values("white_space_cr", ascending=False).head(12)
    fig, ax = plt.subplots(figsize=(8.2, 5))
    colors = d["action"].map(ACTION_COLOR)
    bars = ax.barh([f"T-{int(i)}" for i in d["territory_id"]][::-1],
                   d["white_space_cr"][::-1], color=list(colors)[::-1], height=0.66)
    T.label_bars(ax, bars, fmt="₹{:.2f}Cr", horizontal=True)
    ax.set_title("Priority territories for capacity / new-rep deployment")
    ax.set_xlabel("White-space opportunity (₹ Cr)")
    ax.grid(axis="x"); ax.grid(axis="y", visible=False)
    return T.save_fig(fig, "28_deploy_targets")


def build_report(data_dir=DATA_PROCESSED) -> Dict[str, Any]:
    T.apply_theme()
    cfg = load_config()
    t = load_tables(data_dir)
    logger.info("Building optimization plan ...")
    plan = build_plan(t, data_dir=data_dir)
    doc, terr, s = plan["doc_plan"], plan["terr"], plan["summary"]

    f_re = chart_call_reallocation(doc)
    f_wl = chart_workload_distribution(terr)
    f_dep = chart_deployment(terr)
    f_tgt = chart_deploy_targets(terr)

    # persist plans
    doc.to_csv(data_dir / "doctor_call_plan.csv", index=False)
    terr.to_csv(data_dir / "territory_plan.csv", index=False)

    freq_tbl = " · ".join(f"{k} = {v}/yr" for k, v in IDEAL_FREQ.items())
    top_deploy = (terr[terr["action"].isin(["Deploy rep (vacant)", "Reinforce — under-covered"])]
                  .sort_values("white_space_cr", ascending=False).head(8))
    deploy_tbl = "\n".join(
        f"| T-{int(r.territory_id)} | {r.region_name} | {r.action.split(' —')[0]} | "
        f"{r.calls_per_doctor:.1f} | {r.p1_doctors} | ₹{r.white_space_cr:.2f}Cr |"
        for r in top_deploy.itertuples())

    over = terr[terr["action"] == "Over-served — trim/redeploy"].sort_values("calls_per_doctor", ascending=False).head(6)
    over_tbl = "\n".join(
        f"| T-{int(r.territory_id)} | {r.region_name} | {r.calls_per_doctor:.1f} | {r.p1_doctors} | ₹{r.white_space_cr:.2f}Cr |"
        for r in over.itertuples())

    md = f"""# Project Catalyst — Territory & Sales-Force Optimization

**Reproducible** · seed={cfg['random_seed']} · `scripts/run_optimization.py`.

Turns the Commercial Opportunity Score into a **field plan**: who gets more calls, who
gets fewer, which territories need capacity, and where new reps deploy — using
workload-balancing against opportunity (interpretable, not a solver black box).

## Headline

| Metric | Value |
|--------|------:|
| Calls reallocated (capacity-neutral) | {s['reallocated_calls']:,} ({s['reallocated_pct']:.0f}% of effort) |
| Vacant territories to fill | {s['n_vacant']} |
| Under-served territories to reinforce (via reallocation, no new cost) | {s['n_reinforce']} |
| Over-served territories to trim/redeploy | {s['n_over']} |
| **New reps needed (fill budgeted vacancies)** | **{s['new_reps']}** |
| White space behind deployment + reinforcement | ₹{s['deploy_white_space_cr']:.0f} Cr |

---

## 1. Reallocate effort within each rep — at flat cost (Module 9)

![call reallocation]({f_re})

Holding every rep's total calls constant, we re-split their capacity by opportunity
(ideal cadence: {freq_tbl}). **{s['reallocated_calls']:,} calls ({s['reallocated_pct']:.0f}% of all effort)** move
from over-served P3 doctors to under-served P1 white space — **no added cost**. This is the
single largest, lowest-risk lever in the engagement.

## 2. Capacity is ample — the constraint is allocation, not headcount (Module 9)

![workload distribution]({f_wl})

The workload index (required opportunity load ÷ rep capacity) sits **below 1.0 for almost every
territory** — reps have the capacity to hit the ideal cadence; they are simply pointed at the wrong
doctors. **The headline is therefore "reallocate, don't hire"** — the {s['reallocated_pct']:.0f}% call shift
above is nearly free. Reach is already saturated (avg coverage **{s['avg_coverage']:.0f}%**), so deployment
is driven by *call-frequency gaps and vacancies*, not by adding raw capacity everywhere.

## 3. Where to deploy reps (Module 15)

![deployment map]({f_dep})

![deploy targets]({f_tgt})

The deployment answer is deliberately lean: only **{s['new_reps']} new reps** — to fill the
**{s['n_vacant']} budgeted vacant territories** that today have *zero* coverage. The other
**{s['n_reinforce']} under-served high-opportunity territories** (low call frequency) are fixed by their
*existing* rep re-prioritising via the reallocation above — **no added headcount**. Together, the
deployment + reinforcement addresses **₹{s['deploy_white_space_cr']:.0f} Cr** of white space; the financial
model (M8) prices the {s['new_reps']} vacancy fills against that capture.

### Priority territories to deploy / reinforce
| Territory | Region | Action | Calls/doc | P1 docs | White space |
|-----------|--------|--------|----------:|--------:|------------:|
{deploy_tbl}

### Over-served territories (trim & redeploy effort)
| Territory | Region | Calls/doc | P1 docs | White space |
|-----------|--------|----------:|--------:|------------:|
{over_tbl}

---

## So what → the financial model

Two funding-distinct moves: a **cost-neutral reallocation** ({s['reallocated_pct']:.0f}% of effort, immediate,
~zero cost, addressing the reinforcement gaps) and a **minimal deployment** ({s['new_reps']} reps to fill
budgeted vacancies). Milestone 8 prices both: rep cost, phased revenue capture, ROI, NPV, payback,
and sensitivity — against the ₹{s['deploy_white_space_cr']:.0f} Cr the deployment + reinforcement unlocks.
"""
    ensure_dir(REPORTS_DIR)
    (REPORTS_DIR / "optimization_report.md").write_text(md, encoding="utf-8")
    logger.info("Wrote optimization_report.md, doctor_call_plan.csv, territory_plan.csv")
    return plan


def persist_to_db(plan: Dict[str, Any], cfg) -> None:
    from sqlalchemy import text
    from ..utils.db import get_engine
    engine = get_engine(cfg)
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS catalyst"))
    plan["doc_plan"].to_sql("doctor_call_plan", engine, schema="catalyst", if_exists="replace", index=False)
    plan["terr"].to_sql("territory_plan", engine, schema="catalyst", if_exists="replace", index=False)
    logger.info("Loaded catalyst.doctor_call_plan (%d) and catalyst.territory_plan (%d)",
                len(plan["doc_plan"]), len(plan["terr"]))
