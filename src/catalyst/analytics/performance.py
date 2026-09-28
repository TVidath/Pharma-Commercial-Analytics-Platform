"""Opportunity & Performance Diagnostics (Modules 8, 10, 11, 12).

Turns the diagnosis into quantified, rupee-denominated opportunity across four
lenses — Rx/market opportunity, regional performance, product performance, and
marketing effectiveness — and writes an **opportunity register** that the
financial model (M8) monetises. Reads data/processed (facts + segment outputs).
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd

from ..data_generation.reference_data import (MARGIN_PER_CONVERSION,
                                              PRESSURED_TAS, PRESSURED_ZONES)
from ..utils.config import load_config
from ..utils.logging import get_logger
from ..utils.paths import DATA_PROCESSED, REPORTS_DIR, ensure_dir
from ..visualization import theme as T
from ..data_pipeline.validate import load_tables

logger = get_logger(__name__)
CRORE = 1e7

import matplotlib.pyplot as plt  # noqa: E402


# ---------------------------------------------------------------------------
# Shared context & metric frames
# ---------------------------------------------------------------------------
def _context(t: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    months = t["dim_month"].sort_values("month_id")["month_id"].tolist()
    geo = (t["dim_doctor"][["doctor_id", "territory_id"]]
           .merge(t["dim_territory"][["territory_id", "region_id"]], on="territory_id")
           .merge(t["dim_region"][["region_id", "region_name", "zone_id"]], on="region_id")
           .merge(t["dim_zone"], on="zone_id"))
    return {"months": months, "ttm": months[-12:], "py": months[-24:-12],
            "first6": months[:6], "last6": months[-6:], "geo": geo,
            "prod": t["dim_product"], "ta": t["dim_therapeutic_area"]}


def market_by_ta(t, ctx) -> pd.DataFrame:
    """Our units, competitor units, share and market size (₹) by TA (TTM)."""
    ttm = ctx["ttm"]
    ours = (t["fact_prescriptions"][t["fact_prescriptions"].month_id.isin(ttm)]
            .merge(ctx["prod"][["product_id", "ta_id", "unit_price"]], on="product_id"))
    our_ta = ours.groupby("ta_id").agg(our_units=("units_prescribed", "sum"),
                                       our_rev=("revenue", "sum")).reset_index()
    comp = (t["fact_competitor_rx"][t["fact_competitor_rx"].month_id.isin(ttm)]
            .groupby("ta_id")["competitor_units"].sum().rename("comp_units").reset_index())
    m = our_ta.merge(comp, on="ta_id").merge(ctx["ta"][["ta_id", "ta_name"]], on="ta_id")
    m["share_pct"] = m["our_units"] / (m["our_units"] + m["comp_units"]) * 100
    m["avg_price"] = m["our_rev"] / m["our_units"]
    m["market_size_cr"] = (m["our_units"] + m["comp_units"]) * m["avg_price"] / CRORE
    return m


# ---------------------------------------------------------------------------
# Module 8 — Rx / market opportunity
# ---------------------------------------------------------------------------
def opportunity_components(t, ctx, seg: pd.DataFrame) -> Dict[str, float]:
    """Quantify the three revenue/margin opportunity pools (₹ Cr)."""
    # (a) white space from under-served doctors (segmentation)
    white_space_cr = seg["white_space_value"].sum() / CRORE

    # (b) share recapture in pressured zones/TAs (recover half the gap to rest-of-market)
    rx = (t["fact_prescriptions"][t["fact_prescriptions"].month_id.isin(ctx["ttm"])]
          .merge(ctx["prod"][["product_id", "ta_id", "unit_price"]], on="product_id")
          .merge(ctx["geo"][["doctor_id", "zone_name"]], on="doctor_id")
          .merge(ctx["ta"][["ta_id", "ta_name"]], on="ta_id"))
    rx["pressured"] = rx.zone_name.isin(PRESSURED_ZONES) & rx.ta_name.isin(PRESSURED_TAS)
    comp = (t["fact_competitor_rx"][t["fact_competitor_rx"].month_id.isin(ctx["ttm"])]
            .merge(ctx["geo"][["doctor_id", "zone_name"]], on="doctor_id")
            .merge(ctx["ta"][["ta_id", "ta_name"]], on="ta_id"))
    comp["pressured"] = comp.zone_name.isin(PRESSURED_ZONES) & comp.ta_name.isin(PRESSURED_TAS)

    our_p = rx[rx.pressured]["units_prescribed"].sum()
    our_rev_p = rx[rx.pressured]["revenue"].sum()
    comp_p = comp[comp.pressured]["competitor_units"].sum()
    our_r = rx[~rx.pressured]["units_prescribed"].sum()
    comp_r = comp[~comp.pressured]["competitor_units"].sum()
    cur_share_p = our_p / (our_p + comp_p)
    rest_share = our_r / (our_r + comp_r)
    target_share = cur_share_p + 0.5 * (rest_share - cur_share_p)
    incr_units = (our_p + comp_p) * (target_share - cur_share_p)
    avg_price_p = our_rev_p / our_p
    share_recapture_cr = incr_units * avg_price_p / CRORE

    # (c) marketing reallocation: move 50% of Print budget to Digital (margin lever)
    mc = (t["fact_marketing_spend"][t["fact_marketing_spend"].month_id.isin(ctx["ttm"])]
          .merge(t["dim_campaign"][["campaign_id", "channel"]], on="campaign_id"))
    ch = mc.groupby("channel").agg(spend=("spend", "sum"), conv=("conversions", "sum"))
    ch["roi"] = ch["conv"] * MARGIN_PER_CONVERSION / ch["spend"]
    print_spend = ch.loc["Print & Conferences", "spend"]
    realloc = 0.5 * print_spend
    mkt_uplift_cr = realloc * (ch.loc["Digital & CME", "roi"] - ch.loc["Print & Conferences", "roi"]) / CRORE

    return {"white_space_cr": white_space_cr, "share_recapture_cr": share_recapture_cr,
            "mkt_uplift_cr": mkt_uplift_cr, "cur_share_p": cur_share_p * 100,
            "target_share_p": target_share * 100, "rest_share": rest_share * 100}


def chart_market_share_ta(m: pd.DataFrame) -> str:
    m = m.sort_values("share_pct")
    fig, ax = plt.subplots(figsize=(8, 4.6))
    b1 = ax.barh(m["ta_name"], m["share_pct"], color=T.BLUE, label="Our share")
    ax.barh(m["ta_name"], 100 - m["share_pct"], left=m["share_pct"], color=T.GRID, label="Headroom")
    for y, (s, sz) in enumerate(zip(m["share_pct"], m["market_size_cr"])):
        ax.text(2, y, f"{s:.0f}%  ·  ₹{sz:,.0f}Cr market", va="center", color=T.INK, fontsize=9)
    ax.set_title("Market share by therapeutic area (headroom = the gap)")
    ax.set_xlabel("Share of market (%)"); ax.set_xlim(0, 100)
    ax.grid(axis="x", visible=False); ax.legend(loc="lower right")
    return T.save_fig(fig, "15_market_share_ta")


def chart_opportunity_bridge(cur_cr: float, comp: Dict[str, float]) -> str:
    labels = ["Current\nrevenue", "White space\n(under-served)", "Share\nrecapture", "Addressable\nrevenue"]
    ws, sr = comp["white_space_cr"], comp["share_recapture_cr"]
    total = cur_cr + ws + sr
    fig, ax = plt.subplots(figsize=(8.4, 5))
    ax.bar(0, cur_cr, color=T.MUTED, width=0.6)
    ax.bar(1, ws, bottom=cur_cr, color=T.GREEN, width=0.6)
    ax.bar(2, sr, bottom=cur_cr + ws, color=T.AQUA, width=0.6)
    ax.bar(3, total, color=T.BLUE, width=0.6)
    for x, (base, val) in enumerate([(0, cur_cr), (cur_cr, ws), (cur_cr + ws, sr), (0, total)]):
        ax.annotate((f"+₹{val:,.0f}" if 0 < x < 3 else f"₹{val:,.0f}") + "Cr",
                    (x, base + val), xytext=(0, 4), textcoords="offset points",
                    ha="center", color=T.INK, fontsize=9.5, fontweight="bold")
    ax.set_xticks(range(4)); ax.set_xticklabels(labels)
    ax.set_title("Opportunity bridge — identified revenue pools")
    ax.set_ylabel("Revenue (₹ Cr)"); ax.grid(axis="y")
    ax.set_ylim(0, total * 1.15)
    ax.text(0.03, 0.92, f"+{(ws + sr) / cur_cr * 100:.1f}% upside identified",
            transform=ax.transAxes, color=T.GREEN, fontsize=10, fontweight="bold")
    return T.save_fig(fig, "16_opportunity_bridge")


# ---------------------------------------------------------------------------
# Module 10 — Regional performance
# ---------------------------------------------------------------------------
def region_metrics(t, ctx, seg) -> pd.DataFrame:
    rx = t["fact_prescriptions"].merge(ctx["geo"][["doctor_id", "region_id", "region_name", "zone_name"]],
                                       on="doctor_id")
    ttm = rx[rx.month_id.isin(ctx["ttm"])].groupby(["region_id", "region_name", "zone_name"])["revenue"].sum()
    py = rx[rx.month_id.isin(ctx["py"])].groupby("region_id")["revenue"].sum()
    reg = ttm.reset_index().rename(columns={"revenue": "ttm_rev"})
    reg = reg.merge(py.rename("py_rev"), on="region_id")
    reg["growth_pct"] = (reg["ttm_rev"] - reg["py_rev"]) / reg["py_rev"] * 100
    # share by region (our vs competitor units, TTM)
    our = rx[rx.month_id.isin(ctx["ttm"])].groupby("region_id")["units_prescribed"].sum()
    comp = (t["fact_competitor_rx"][t["fact_competitor_rx"].month_id.isin(ctx["ttm"])]
            .merge(ctx["geo"][["doctor_id", "region_id"]], on="doctor_id")
            .groupby("region_id")["competitor_units"].sum())
    reg = reg.merge((our / (our + comp) * 100).rename("share_pct"), on="region_id")
    # white space by region
    ws = (seg.merge(ctx["geo"][["doctor_id", "region_id"]], on="doctor_id")
          .groupby("region_id")["white_space_value"].sum() / CRORE)
    reg = reg.merge(ws.rename("white_space_cr"), on="region_id")
    reg["ttm_rev_cr"] = reg["ttm_rev"] / CRORE
    return reg


def chart_region_quadrant(reg: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    sizes = reg["ttm_rev_cr"] / reg["ttm_rev_cr"].max() * 600 + 60
    ax.scatter(reg["share_pct"], reg["growth_pct"], s=sizes, color=T.BLUE, alpha=0.55, edgecolors="white")
    xm, ym = reg["share_pct"].median(), reg["growth_pct"].median()
    ax.axvline(xm, color=T.BASELINE, lw=1); ax.axhline(ym, color=T.BASELINE, lw=1)
    # label the laggards (low share & low growth) in red
    lag = reg[(reg["share_pct"] < xm) & (reg["growth_pct"] < ym)]
    for _, r in reg.iterrows():
        col = T.CRITICAL if r["region_id"] in set(lag["region_id"]) else T.INK_SECONDARY
        ax.annotate(r["region_name"], (r["share_pct"], r["growth_pct"]),
                    xytext=(5, 4), textcoords="offset points", fontsize=8, color=col)
    ax.set_title("Regional performance — share vs growth (bubble = revenue)")
    ax.set_xlabel("Market share (%)"); ax.set_ylabel("YoY growth (%)")
    ax.text(0.02, 0.04, "Laggards (low share, low growth) in red", transform=ax.transAxes,
            color=T.CRITICAL, fontsize=9)
    return T.save_fig(fig, "17_region_quadrant")


def chart_region_opportunity(reg: pd.DataFrame) -> str:
    r = reg.sort_values("white_space_cr", ascending=False).head(12)
    fig, ax = plt.subplots(figsize=(8.2, 5))
    bars = ax.barh(r["region_name"][::-1], r["white_space_cr"][::-1], color=T.GREEN, height=0.68)
    T.label_bars(ax, bars, fmt="₹{:.1f}Cr", horizontal=True)
    ax.set_title("White-space opportunity by region (top 12)")
    ax.set_xlabel("Addressable white space (₹ Cr)")
    ax.grid(axis="x"); ax.grid(axis="y", visible=False)
    return T.save_fig(fig, "18_region_opportunity")


# ---------------------------------------------------------------------------
# Module 11 — Product performance
# ---------------------------------------------------------------------------
def product_metrics(t, ctx) -> pd.DataFrame:
    p = ctx["prod"]
    rx = t["fact_prescriptions"]
    ttm = rx[rx.month_id.isin(ctx["ttm"])].groupby("product_id").agg(
        ttm_rev=("revenue", "sum"), ttm_units=("units_prescribed", "sum"))
    py = rx[rx.month_id.isin(ctx["py"])].groupby("product_id")["revenue"].sum().rename("py_rev")
    m = p.merge(ttm, on="product_id").merge(py, on="product_id")
    m = m.merge(ctx["ta"][["ta_id", "ta_name"]], on="ta_id", how="left")
    m["growth_pct"] = (m["ttm_rev"] - m["py_rev"]) / m["py_rev"] * 100
    m["margin_pct"] = (m["unit_price"] - m["cost_per_unit"]) / m["unit_price"] * 100
    m["ttm_rev_cr"] = m["ttm_rev"] / CRORE
    # marketing spend per product (TTM)
    spend = (t["fact_marketing_spend"][t["fact_marketing_spend"].month_id.isin(ctx["ttm"])]
             .groupby("product_id")["spend"].sum() / CRORE).rename("spend_cr")
    m = m.merge(spend, on="product_id", how="left").fillna({"spend_cr": 0})
    return m


def chart_product_matrix(m: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    for stage, col in T.LIFECYCLE_COLORS.items():
        s = m[m["lifecycle_stage"] == stage]
        ax.scatter(s["growth_pct"], s["margin_pct"], s=s["ttm_rev_cr"] / m["ttm_rev_cr"].max() * 700 + 60,
                   color=col, alpha=0.7, edgecolors="white", label=stage)
    for _, r in m.iterrows():
        ax.annotate(r["brand_name"], (r["growth_pct"], r["margin_pct"]),
                    xytext=(5, 3), textcoords="offset points", fontsize=8, color=T.INK_SECONDARY)
    ax.axvline(0, color=T.BASELINE, lw=1)
    ax.set_title("Product portfolio — growth vs margin (bubble = revenue)")
    ax.set_xlabel("YoY revenue growth (%)"); ax.set_ylabel("Gross margin (%)")
    ax.legend(title="Lifecycle", loc="lower right", ncol=2)
    return T.save_fig(fig, "19_product_matrix")


# ---------------------------------------------------------------------------
# Module 12 — Marketing effectiveness
# ---------------------------------------------------------------------------
def chart_marketing_realloc(t, ctx, comp: Dict[str, float]) -> str:
    mc = (t["fact_marketing_spend"][t["fact_marketing_spend"].month_id.isin(ctx["ttm"])]
          .merge(t["dim_campaign"][["campaign_id", "channel"]], on="campaign_id"))
    ch = mc.groupby("channel").agg(spend=("spend", "sum"), conv=("conversions", "sum"))
    ch["roi"] = ch["conv"] * MARGIN_PER_CONVERSION / ch["spend"]
    ch["cur_share"] = ch["spend"] / ch["spend"].sum() * 100
    # recommended: move half of Print budget, split to Digital & KOL (highest ROI)
    ch["rec_share"] = ch["cur_share"].copy()
    move = ch.loc["Print & Conferences", "cur_share"] * 0.5
    ch.loc["Print & Conferences", "rec_share"] -= move
    ch.loc["Digital & CME", "rec_share"] += move * 0.6
    ch.loc["KOL Engagement", "rec_share"] += move * 0.4
    order = ch.sort_values("roi").index
    x = np.arange(len(order)); w = 0.38
    fig, ax = plt.subplots(figsize=(9, 5))
    b1 = ax.bar(x - w / 2, ch.loc[order, "cur_share"], w, color=T.MUTED, label="Current mix")
    b2 = ax.bar(x + w / 2, ch.loc[order, "rec_share"], w, color=T.BLUE, label="Recommended mix")
    ax.set_xticks(x); ax.set_xticklabels([o.replace(" & ", "\n& ") for o in order], fontsize=8.5)
    ax2_labels = [f"{ch.loc[o, 'roi']:.1f}×" for o in order]
    for xi, lab in zip(x, ax2_labels):
        ax.text(xi, -4, lab, ha="center", color=T.INK_SECONDARY, fontsize=8)
    ax.text(-0.7, -4, "ROI:", ha="right", color=T.INK_SECONDARY, fontsize=8)
    ax.set_title("Marketing mix — shift budget toward high-ROI channels")
    ax.set_ylabel("Share of budget (%)"); ax.legend(loc="upper left"); ax.grid(axis="y")
    return T.save_fig(fig, "20_marketing_realloc")


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------
def build_report(data_dir=DATA_PROCESSED) -> pd.DataFrame:
    T.apply_theme()
    cfg = load_config()
    t = load_tables(data_dir)
    ctx = _context(t)
    seg = pd.read_csv(data_dir / "doctor_segments.csv")

    logger.info("Computing opportunity components ...")
    m_ta = market_by_ta(t, ctx)
    comp = opportunity_components(t, ctx, seg)
    cur_cr = t["fact_prescriptions"][t["fact_prescriptions"].month_id.isin(ctx["ttm"])]["revenue"].sum() / CRORE
    reg = region_metrics(t, ctx, seg)
    prod = product_metrics(t, ctx)

    logger.info("Rendering charts ...")
    f_share = chart_market_share_ta(m_ta)
    f_bridge = chart_opportunity_bridge(cur_cr, comp)
    f_regq = chart_region_quadrant(reg)
    f_rego = chart_region_opportunity(reg)
    f_prod = chart_product_matrix(prod)
    f_mkt = chart_marketing_realloc(t, ctx, comp)

    # opportunity register (feeds financial model, M8)
    register = pd.DataFrame([
        {"lever": "White space (under-served doctors)", "type": "Revenue",
         "value_cr": round(comp["white_space_cr"], 1)},
        {"lever": "Share recapture (pressured zones/TAs)", "type": "Revenue",
         "value_cr": round(comp["share_recapture_cr"], 1)},
        {"lever": "Marketing reallocation (Print→Digital)", "type": "Margin",
         "value_cr": round(comp["mkt_uplift_cr"], 1)},
    ])
    ensure_dir(REPORTS_DIR)
    register.to_csv(DATA_PROCESSED / "opportunity_register.csv", index=False)

    laggards = reg[(reg["share_pct"] < reg["share_pct"].median()) &
                   (reg["growth_pct"] < reg["growth_pct"].median())].sort_values("white_space_cr", ascending=False)
    worst_prod = prod.sort_values("growth_pct").iloc[0]
    best_prod = prod.sort_values("growth_pct").iloc[-1]

    total_rev_opp = comp["white_space_cr"] + comp["share_recapture_cr"]
    reg_tbl = "\n".join(
        f"| {r['region_name']} | {r['zone_name']} | ₹{r['ttm_rev_cr']:.0f}Cr | {r['growth_pct']:+.1f}% | "
        f"{r['share_pct']:.0f}% | ₹{r['white_space_cr']:.1f}Cr |"
        for _, r in reg.sort_values("white_space_cr", ascending=False).head(8).iterrows())

    md = f"""# Project Catalyst — Opportunity & Performance Diagnostics

**Reproducible** · seed={cfg['random_seed']} · TTM window · `scripts/run_performance.py`.

This milestone converts the diagnosis into **quantified opportunity** across four lenses —
market/Rx, region, product, and marketing — and produces the **opportunity register** the
financial model (M8) monetises.

## Headline — the opportunity register

| Lever | Type | Value (₹ Cr / yr) |
|-------|------|------------------:|
| White space (under-served doctors) | Revenue | {comp['white_space_cr']:.0f} |
| Share recapture (pressured zones/TAs) | Revenue | {comp['share_recapture_cr']:.0f} |
| Marketing reallocation (Print→Digital) | Margin | {comp['mkt_uplift_cr']:.0f} |
| **Identified revenue opportunity** | | **{total_rev_opp:.0f}** (+{total_rev_opp/cur_cr*100:.1f}% of current) |

*(Pools are identified independently and may partially overlap; M8 reconciles them into conservative/base/aggressive scenarios.)*

---

## 1. Market & Rx opportunity (Module 8)

![market share by TA]({f_share})

![opportunity bridge]({f_bridge})

We hold meaningful headroom in every therapeutic area. In the **pressured zones/TAs** our
share is **{comp['cur_share_p']:.0f}%** vs **{comp['rest_share']:.0f}%** in the rest of the market;
recovering half that gap is worth **₹{comp['share_recapture_cr']:.0f} Cr**. Combined with the
under-served-doctor white space, the identified revenue pool is **₹{total_rev_opp:.0f} Cr (+{total_rev_opp/cur_cr*100:.1f}%)**.

## 2. Regional performance (Module 10)

![region quadrant]({f_regq})

![region opportunity]({f_rego})

Performance is uneven: **{len(laggards)} regions** sit in the low-share / low-growth quadrant —
led by **{laggards.iloc[0]['region_name'] if len(laggards) else 'n/a'}** — yet several of these carry
the largest white space, confirming they are *under-served, not saturated*. These are the
priority regions for field re-alignment and marketing investment.

## 3. Product performance (Module 11)

![product matrix]({f_prod})

The portfolio splits cleanly: growth brands (**{best_prod['brand_name']}, +{best_prod['growth_pct']:.0f}%**)
sit in the attractive high-growth/high-margin space, while the declining hero
(**{worst_prod['brand_name']}, {worst_prod['growth_pct']:.0f}%**) drags the total. Promotional
support should follow margin-weighted growth, not legacy volume.

## 4. Marketing effectiveness (Module 12)

![marketing reallocation]({f_mkt})

Re-weighting **50% of the Print & Conferences budget** toward Digital/CME and KOL lifts blended
efficiency materially — an estimated **₹{comp['mkt_uplift_cr']:.0f} Cr of incremental margin** at
flat total spend.

## Regional opportunity table (top 8 by white space)

| Region | Zone | TTM Rev | YoY | Share | White space |
|--------|------|--------:|----:|------:|------------:|
{reg_tbl}

---

## So what → the financial model

The three levers above are the inputs to Milestone 8: the **Commercial Opportunity Score**
(M6) prioritises *which* doctors/territories, the **optimization** (M7) sets *how much* effort
moves, and the **financial model** (M8) turns this register into ROI, NPV, payback, and
sensitivity/scenario ranges.
"""
    (REPORTS_DIR / "performance_report.md").write_text(md, encoding="utf-8")
    logger.info("Wrote performance_report.md + opportunity_register.csv (6 figures)")
    return register
