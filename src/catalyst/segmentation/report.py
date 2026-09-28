"""Segmentation report: charts, Markdown narrative, and DB persistence."""
from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
import pandas as pd

from ..data_pipeline.validate import load_tables
from ..utils.config import load_config
from ..utils.logging import get_logger
from ..utils.paths import DATA_PROCESSED, REPORTS_DIR, ensure_dir
from ..visualization import theme as T
from .doctors import segment_doctors, validate_with_kmeans
from .hospitals import segment_hospitals
from .playbooks import DOCTOR_SEGMENTS, HOSPITAL_TIERS, INCREASE, MAINTAIN, REDUCE

logger = get_logger(__name__)
CRORE = 1e7
LAKH = 1e5
ACTION_ORDER = [INCREASE, MAINTAIN, REDUCE]
ACTION_COLOR = {INCREASE: T.GREEN, MAINTAIN: T.BLUE, REDUCE: T.ORANGE}

import matplotlib.pyplot as plt  # noqa: E402


def chart_doctor_matrix(doc: pd.DataFrame) -> str:
    rows = ["High", "Medium", "Low"]          # potential top->bottom
    cols = ["Low", "Medium", "High"]          # value left->right
    counts = (doc.groupby(["potential_tier", "value_tier"]).size()
              .reindex(pd.MultiIndex.from_product([rows, cols])).fillna(0)
              .unstack().reindex(index=rows, columns=cols))
    fig, ax = plt.subplots(figsize=(7.6, 5.6))
    im = ax.imshow(counts.values, cmap="Blues", aspect="auto")
    for i, pt in enumerate(rows):
        for j, vt in enumerate(cols):
            seg = DOCTOR_SEGMENTS[(pt, vt)]
            n = int(counts.loc[pt, vt])
            dark = counts.values[i, j] > counts.values.max() * 0.55
            ax.text(j, i - 0.16, seg["name"], ha="center", va="center",
                    color="white" if dark else T.INK, fontsize=10, fontweight="bold")
            ax.text(j, i + 0.16, f"{n:,}  ·  {seg['action'].split(' ')[0]}",
                    ha="center", va="center", color="white" if dark else T.INK_SECONDARY, fontsize=8.5)
    ax.set_xticks(range(3)); ax.set_xticklabels([f"{c}\nvalue" for c in cols])
    ax.set_yticks(range(3)); ax.set_yticklabels([f"{r}\npotential" for r in rows])
    ax.set_title("Doctor segmentation — Potential × Value (9-box)")
    fig.colorbar(im, ax=ax, label="# doctors", shrink=0.8)
    ax.set_xticks(np.arange(-.5, 3, 1), minor=True)
    ax.set_yticks(np.arange(-.5, 3, 1), minor=True)
    ax.grid(which="minor", color=T.SURFACE, linewidth=3)
    ax.tick_params(which="minor", length=0)
    return T.save_fig(fig, "11_doctor_matrix")


def chart_segment_economics(doc: pd.DataFrame) -> str:
    g = (doc.groupby(["segment", "action"])["ttm_revenue"].sum() / CRORE).reset_index()
    g = g.sort_values("ttm_revenue")
    colors = g["action"].map(ACTION_COLOR)
    fig, ax = plt.subplots(figsize=(8.4, 5))
    bars = ax.barh(g["segment"], g["ttm_revenue"], color=colors, height=0.68)
    T.label_bars(ax, bars, fmt="₹{:.0f}Cr", horizontal=True)
    ax.set_title("Revenue by segment (colour = investment action)")
    ax.set_xlabel("TTM revenue (₹ Cr)")
    ax.grid(axis="x"); ax.grid(axis="y", visible=False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=ACTION_COLOR[a]) for a in ACTION_ORDER]
    ax.legend(handles, ACTION_ORDER, title="Action", loc="lower right")
    return T.save_fig(fig, "12_segment_economics")


def chart_reallocation(doc: pd.DataFrame) -> Tuple[str, Dict]:
    g = doc.groupby("action").agg(calls=("ttm_calls", "sum"),
                                  ws=("white_space_value", "sum")).reindex(ACTION_ORDER)
    calls_share = g["calls"] / g["calls"].sum() * 100
    ws_share = g["ws"] / g["ws"].sum() * 100
    x = np.arange(len(ACTION_ORDER)); w = 0.38
    fig, ax = plt.subplots(figsize=(8, 4.8))
    b1 = ax.bar(x - w / 2, calls_share, w, color=T.MUTED, label="% of current sales calls")
    b2 = ax.bar(x + w / 2, ws_share, w, color=T.BLUE, label="% of white-space opportunity")
    T.label_bars(ax, b1, fmt="{:.0f}%"); T.label_bars(ax, b2, fmt="{:.0f}%")
    ax.set_xticks(x); ax.set_xticklabels([a.split(" ")[0] for a in ACTION_ORDER])
    ax.set_title("The mis-allocation: effort vs opportunity")
    ax.set_ylabel("Share (%)")
    ax.legend(loc="upper right")
    ax.grid(axis="y")
    return T.save_fig(fig, "13_reallocation"), {
        "inc_calls": calls_share[INCREASE], "inc_ws": ws_share[INCREASE],
        "red_calls": calls_share[REDUCE], "red_ws": ws_share[REDUCE]}


def chart_hospital_tiers(hosp: pd.DataFrame) -> str:
    order = ["Platinum", "Gold", "Silver", "Bronze"]
    g = hosp.groupby("tier").agg(n=("hospital_id", "count"),
                                 value=("affiliated_ttm_revenue", "sum")).reindex(order)
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    colors = [T.SEQ_BLUE[6], T.SEQ_BLUE[4], T.SEQ_BLUE[2], T.SEQ_BLUE[1]]
    bars = ax.bar(order, g["value"] / CRORE, color=colors, width=0.6)
    for b, n in zip(bars, g["n"]):
        ax.annotate(f"{int(n)} hosp.", (b.get_x() + b.get_width() / 2, b.get_height()),
                    xytext=(0, 3), textcoords="offset points", ha="center",
                    color=T.INK_SECONDARY, fontsize=9)
    ax.set_title("Hospital tiers by affiliated commercial value")
    ax.set_ylabel("Affiliated TTM revenue (₹ Cr)")
    ax.grid(axis="y")
    return T.save_fig(fig, "14_hospital_tiers")


def _segment_table(doc: pd.DataFrame) -> str:
    tot_rev = doc["ttm_revenue"].sum()
    g = doc.groupby(["segment", "action"]).agg(
        n=("doctor_id", "count"), revenue=("ttm_revenue", "sum"),
        calls=("ttm_calls", "sum"), ws=("white_space_value", "sum")).reset_index()
    g["pct_doctors"] = g["n"] / g["n"].sum() * 100
    g["pct_revenue"] = g["revenue"] / tot_rev * 100
    order = {INCREASE: 0, MAINTAIN: 1, REDUCE: 2}
    g = g.sort_values(by=["action", "revenue"], key=lambda s: s.map(order) if s.name == "action" else -s)
    rows = ["| Segment | Action | Doctors | % Docs | % Revenue | White space (₹Cr) |",
            "|---------|--------|--------:|-------:|----------:|------------------:|"]
    for _, r in g.iterrows():
        rows.append(f"| {r['segment']} | {r['action']} | {int(r['n']):,} | "
                    f"{r['pct_doctors']:.1f}% | {r['pct_revenue']:.1f}% | {r['ws']/CRORE:.1f} |")
    return "\n".join(rows)


def build_report(data_dir=DATA_PROCESSED) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Compute segments, render charts, write report + CSVs. Returns (doc, hosp)."""
    T.apply_theme()
    cfg = load_config()
    t = load_tables(data_dir)
    ttm = t["dim_month"].sort_values("month_id")["month_id"].tolist()[-12:]

    logger.info("Segmenting doctors ...")
    doc = segment_doctors(t, ttm)
    logger.info("Validating segments with K-means ...")
    val = validate_with_kmeans(doc)
    logger.info("Segmenting hospitals ...")
    hosp = segment_hospitals(t, doc)

    m_doc = chart_doctor_matrix(doc)
    m_eco = chart_segment_economics(doc)
    m_re, re = chart_reallocation(doc)
    m_hosp = chart_hospital_tiers(hosp)

    # headline numbers
    gems = doc[doc["segment"] == "Hidden Gems"]
    total_ws = doc["white_space_value"].sum() / CRORE
    inc_ws = doc[doc["action"] == INCREASE]["white_space_value"].sum() / CRORE

    md = f"""# Pharma Commercial Analytics Platform — Customer Segmentation

**Reproducible** · seed={cfg['random_seed']} · TTM window · regenerated by `scripts/run_segmentation.py`.

Segmentation converts the diagnostic into a **targeting decision**. Doctors are placed
on a **Potential × Value 9-box** framework; hospitals are tiered by potential. Each
segment carries an explicit field play (see below). Interpretable rules define the
segments; K-means only *validates* them.

## Headline

| Metric | Value |
|--------|------:|
| Total quantified white space | ₹ {total_ws:,.0f} Cr |
| White space in "Increase" segments | ₹ {inc_ws:,.0f} Cr ({inc_ws/total_ws*100:.0f}% of total) |
| "Hidden Gems" (high potential, low value) | {len(gems):,} doctors |
| Segment validation (K-means vs rules, ARI) | {val['ari']:.2f} |

---

## 1. The 9-box: who our doctors are

![doctor matrix]({m_doc})

The grid crosses **potential** (the ceiling) with **current value** (realised).
The decisive cell is **High potential / Low value — "Hidden Gems" ({len(gems):,} doctors)**:
genuine capacity we are not converting. Top-left of the value axis holds the
over-serviced, near-ceiling doctors.

## 2. Where the money is today

![segment economics]({m_eco})

Revenue concentrates in the "Maintain" segments (already-loyal doctors). That is
fine to protect — but it is not where *growth* comes from.

## 3. The mis-allocation, in one chart

![reallocation]({m_re})

**"Increase" segments hold {re['inc_ws']:.0f}% of the white-space opportunity but receive only {re['inc_calls']:.0f}% of current calls.** Conversely, "Reduce/Efficient"
doctors — near their ceiling — absorb {re['red_calls']:.0f}% of calls for just {re['red_ws']:.0f}% of the
opportunity. This is the reallocation prize, made concrete.

## 4. Hospital tiers

![hospital tiers]({m_hosp})

Hospitals are tiered Platinum→Bronze by potential (scale + affiliated-doctor value).
Platinum/Gold accounts warrant key-account coverage; Bronze shifts to digital/low-touch.

---

## Segment summary & size

{_segment_table(doc)}

## Field playbooks (the "so what")

| Segment | Action | Objective | Cadence | Channels | KPI |
|---------|--------|-----------|---------|----------|-----|
""" + "\n".join(
        f"| {v['name']} | {v['action']} | {v['objective']} | {v['cadence']} | {v['channels']} | {v['kpi']} |"
        for v in DOCTOR_SEGMENTS.values()
    ) + f"""

### Hospital tier plays
| Tier | Action | Objective |
|------|--------|-----------|
""" + "\n".join(f"| {k} | {v['action']} | {v['objective']} |" for k, v in HOSPITAL_TIERS.items()) + f"""

---

## Validation (ML confirms, does not define)

A K-means (k=4) on [potential, value] reproduces the rule-based quadrants with
**Adjusted Rand Index {val['ari']:.2f}** and silhouette **{val['silhouette']:.2f}** — the
interpretable segmentation is supported by the data's natural structure, while
remaining fully explainable to a sales VP.

**Next (M5–M6):** size each segment's opportunity per product and territory, and
fold potential + realisation + accessibility into a single **Commercial Opportunity
Score** to rank every doctor for the field.
"""
    ensure_dir(REPORTS_DIR)
    (REPORTS_DIR / "segmentation_report.md").write_text(md, encoding="utf-8")

    # persist segment assignments as CSVs (feed dashboard & later milestones)
    doc_out = doc[["doctor_id", "specialty", "potential_score", "potential_tier",
                   "value_pct", "value_tier", "decile", "ttm_revenue", "ttm_units",
                   "ttm_calls", "opportunity_gap", "white_space_value", "segment", "action"]]
    hosp_out = hosp[["hospital_id", "hospital_name", "hospital_type", "region_name",
                     "zone_name", "bed_count", "affiliated_doctors", "affiliated_ttm_revenue",
                     "affiliated_white_space", "potential_score", "tier"]]
    doc_out.to_csv(DATA_PROCESSED / "doctor_segments.csv", index=False)
    hosp_out.to_csv(DATA_PROCESSED / "hospital_segments.csv", index=False)
    logger.info("Wrote segmentation_report.md, doctor_segments.csv, hospital_segments.csv")
    return doc_out, hosp_out


def persist_to_db(doc_out: pd.DataFrame, hosp_out: pd.DataFrame, cfg) -> None:
    """Load segment tables into PostgreSQL for the dashboard & SQL analysis."""
    from sqlalchemy import text
    from ..utils.db import get_engine
    engine = get_engine(cfg)
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS catalyst"))
    doc_out.to_sql("doctor_segments", engine, schema="catalyst", if_exists="replace", index=False)
    hosp_out.to_sql("hospital_segments", engine, schema="catalyst", if_exists="replace", index=False)
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_docseg_doctor ON catalyst.doctor_segments(doctor_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_hospseg_hospital ON catalyst.hospital_segments(hospital_id)")
    logger.info("Loaded catalyst.doctor_segments (%d) and catalyst.hospital_segments (%d)",
                len(doc_out), len(hosp_out))
