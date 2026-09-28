"""Exploratory Data Analysis — the diagnostic narrative.

Recovers each planted commercial truth (P1-P6) as a chart and assembles a
reproducible Markdown report (reports/eda_report.md) with saved figures. The
same functions back the narrative notebook, so report and notebook never drift.

Reads the cleaned CSVs in data/processed (no live DB required).
"""
from __future__ import annotations

from typing import Any, Dict

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
LAKH = 1e5


# ---------------------------------------------------------------------------
# Data preparation
# ---------------------------------------------------------------------------
def build_context(t: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    """Shared lookups: period windows and doctor->geo / product maps."""
    months = t["dim_month"].sort_values("month_id")["month_id"].tolist()
    doc = t["dim_doctor"].merge(t["dim_territory"][["territory_id", "region_id"]], on="territory_id")
    doc = doc.merge(t["dim_region"][["region_id", "zone_id"]], on="region_id")
    doc = doc.merge(t["dim_zone"], on="zone_id")
    return {
        "months": months,
        "ttm": months[-12:],
        "py": months[-24:-12],
        "first6": months[:6],
        "last6": months[-6:],
        "doc_geo": doc[["doctor_id", "region_id", "zone_name"]],
        "prod": t["dim_product"][["product_id", "brand_name", "ta_id", "lifecycle_stage",
                                  "unit_price", "cost_per_unit"]],
        "ta": t["dim_therapeutic_area"][["ta_id", "ta_name"]],
    }


def doctor_summary(t: Dict[str, pd.DataFrame], ctx: Dict[str, Any]) -> pd.DataFrame:
    """One row per doctor: panel (potential proxy), TTM units/revenue/calls."""
    rx = t["fact_prescriptions"]
    rx_ttm = rx[rx["month_id"].isin(ctx["ttm"])]
    calls = t["fact_sales_calls"]
    calls_ttm = calls[calls["month_id"].isin(ctx["ttm"])]

    s = t["dim_doctor"][["doctor_id", "specialty", "patient_panel_size", "territory_id"]].copy()
    s = s.merge(rx_ttm.groupby("doctor_id").agg(
        ttm_units=("units_prescribed", "sum"), ttm_revenue=("revenue", "sum")),
        on="doctor_id", how="left")
    s = s.merge(calls_ttm.groupby("doctor_id")["calls_made"].sum().rename("ttm_calls"),
                on="doctor_id", how="left")
    s = s.merge(ctx["doc_geo"], on="doctor_id", how="left")
    return s.fillna({"ttm_units": 0, "ttm_revenue": 0, "ttm_calls": 0})


# ---------------------------------------------------------------------------
# Charts — each returns a dict with the figure path and recovered numbers
# ---------------------------------------------------------------------------
import matplotlib.pyplot as plt  # noqa: E402  (after theme import)


def chart_revenue_trend(t, ctx) -> Dict[str, Any]:
    m = (t["fact_prescriptions"].groupby("month_id")["revenue"].sum().reindex(ctx["months"])
         / CRORE).reset_index()
    m.columns = ["month_id", "revenue_cr"]
    m["ma3"] = m["revenue_cr"].rolling(3).mean()
    x = range(len(m))
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(x, m["revenue_cr"], color=T.MUTED, lw=1.2, alpha=0.7, label="Monthly")
    ax.plot(x, m["ma3"], color=T.BLUE, lw=2.4, label="3-month moving avg")
    ax.set_title("Monthly revenue is flat — the presenting symptom")
    ax.set_ylabel("Revenue (₹ Cr)")
    ax.set_xticks(list(x)[::6])
    ax.set_xticklabels([str(mm)[:4] + "-" + str(mm)[4:] for mm in m["month_id"][::6]], rotation=0)
    ax.legend(loc="lower right")
    ax.set_ylim(0, m["revenue_cr"].max() * 1.25)
    yoy = (m[m.month_id.isin(ctx["ttm"])]["revenue_cr"].sum()
           - m[m.month_id.isin(ctx["py"])]["revenue_cr"].sum()) \
        / m[m.month_id.isin(ctx["py"])]["revenue_cr"].sum() * 100
    return {"path": T.save_fig(fig, "01_revenue_trend"), "yoy": yoy,
            "annual": m[m.month_id.isin(ctx["ttm"])]["revenue_cr"].sum()}


def chart_brand_growth(t, ctx) -> Dict[str, Any]:
    rx = t["fact_prescriptions"].merge(ctx["prod"], on="product_id")
    ttm = rx[rx.month_id.isin(ctx["ttm"])].groupby(["brand_name", "lifecycle_stage"])["revenue"].sum()
    py = rx[rx.month_id.isin(ctx["py"])].groupby(["brand_name", "lifecycle_stage"])["revenue"].sum()
    g = ((ttm - py) / py * 100).reset_index().rename(columns={"revenue": "yoy"})
    g = g.sort_values("yoy")
    colors = g["lifecycle_stage"].map(T.LIFECYCLE_COLORS)
    fig, ax = plt.subplots(figsize=(8.5, 5))
    bars = ax.barh(g["brand_name"], g["yoy"], color=colors, height=0.68)
    ax.axvline(0, color=T.BASELINE, lw=1)
    T.label_bars(ax, bars, fmt="{:+.0f}%", horizontal=True)
    ax.set_title("Portfolio 'stagnation' hides sharp brand divergence")
    ax.set_xlabel("YoY revenue growth (%)")
    ax.grid(axis="x"); ax.grid(axis="y", visible=False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in T.LIFECYCLE_COLORS.values()]
    ax.legend(handles, T.LIFECYCLE_COLORS.keys(), title="Lifecycle", loc="lower right", ncol=2)
    return {"path": T.save_fig(fig, "02_brand_growth"),
            "worst": g.iloc[0]["brand_name"], "worst_val": g.iloc[0]["yoy"],
            "best": g.iloc[-1]["brand_name"], "best_val": g.iloc[-1]["yoy"]}


def chart_lifecycle_area(t, ctx) -> Dict[str, Any]:
    rx = t["fact_prescriptions"].merge(ctx["prod"][["product_id", "lifecycle_stage"]], on="product_id")
    piv = (rx.groupby(["month_id", "lifecycle_stage"])["revenue"].sum().unstack(fill_value=0)
           .reindex(ctx["months"]) / CRORE)
    order = ["Decline", "Mature", "Growth", "Launch"]
    piv = piv[[c for c in order if c in piv.columns]]
    x = range(len(piv))
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.stackplot(x, [piv[c] for c in piv.columns],
                 labels=piv.columns, colors=[T.LIFECYCLE_COLORS[c] for c in piv.columns], alpha=0.9)
    ax.set_title("Decline brands mask the rise of the growth portfolio")
    ax.set_ylabel("Revenue (₹ Cr)")
    ax.set_xticks(list(x)[::6])
    ax.set_xticklabels([str(mm)[:4] for mm in piv.index[::6]])
    ax.legend(loc="upper left", ncol=4)
    ax.grid(axis="y", visible=False)
    return {"path": T.save_fig(fig, "03_lifecycle_area")}


def chart_decile_concentration(summary) -> Dict[str, Any]:
    s = summary.sort_values("ttm_revenue", ascending=False).reset_index(drop=True)
    cum_rev = s["ttm_revenue"].cumsum() / s["ttm_revenue"].sum() * 100
    cum_doc = (np.arange(len(s)) + 1) / len(s) * 100
    top20 = cum_rev.iloc[int(len(s) * 0.2)]
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    ax.plot(cum_doc, cum_rev, color=T.BLUE, lw=2.4)
    ax.plot([0, 100], [0, 100], color=T.MUTED, lw=1, ls="--", label="Perfect equality")
    ax.axvline(20, color=T.BASELINE, lw=1, ls=":")
    ax.annotate(f"Top 20% of doctors\n= {top20:.0f}% of revenue",
                (20, top20), xytext=(30, top20 - 22),
                color=T.INK, fontsize=10,
                arrowprops=dict(arrowstyle="->", color=T.MUTED))
    ax.set_title("Revenue is highly concentrated in a minority of prescribers")
    ax.set_xlabel("Cumulative % of doctors (highest value first)")
    ax.set_ylabel("Cumulative % of revenue")
    ax.legend(loc="lower right")
    return {"path": T.save_fig(fig, "04_decile_concentration"), "top20": top20}


def chart_effort_gap(summary) -> Dict[str, Any]:
    s = summary.copy()
    pan_med = s["patient_panel_size"].median()
    call_q1 = s["ttm_calls"].quantile(0.25)
    fig, ax = plt.subplots(figsize=(8, 5))
    sc = ax.scatter(s["patient_panel_size"], s["ttm_calls"], c=s["ttm_units"],
                    cmap="Blues", s=7, alpha=0.5, edgecolors="none",
                    vmin=0, vmax=s["ttm_units"].quantile(0.97))
    ax.axvline(pan_med, color=T.BASELINE, lw=1)
    ax.axhline(call_q1, color=T.BASELINE, lw=1)
    # highlight white-space quadrant (high potential, low effort)
    ax.axvspan(pan_med, s["patient_panel_size"].max(), ymin=0, ymax=call_q1 / ax.get_ylim()[1],
               color=T.RED, alpha=0.06)
    ws = s[(s["patient_panel_size"] > pan_med) & (s["ttm_calls"] < call_q1)]
    ax.annotate(f"WHITE SPACE\n{len(ws):,} high-potential doctors\nwith bottom-quartile calls",
                (pan_med * 1.05, call_q1 * 0.3), color=T.CRITICAL, fontsize=9, fontweight="bold")
    ax.set_title("Effort chases current volume, not potential (P1)")
    ax.set_xlabel("Patient panel size (potential proxy)")
    ax.set_ylabel("TTM sales calls received")
    fig.colorbar(sc, ax=ax, label="TTM units prescribed", shrink=0.8)
    return {"path": T.save_fig(fig, "05_effort_gap"), "whitespace_docs": len(ws),
            "ws_share": len(ws) / len(s[s["patient_panel_size"] > pan_med]) * 100}


def chart_effort_corr(summary) -> Dict[str, Any]:
    c_rx = summary["ttm_calls"].corr(summary["ttm_units"])
    c_pan = summary["ttm_calls"].corr(summary["patient_panel_size"])
    fig, ax = plt.subplots(figsize=(5.5, 4.2))
    bars = ax.bar(["Calls vs\ncurrent Rx", "Calls vs\npotential (panel)"],
                  [c_rx, c_pan], color=[T.BLUE, T.MUTED], width=0.55)
    T.label_bars(ax, bars, fmt="{:.2f}")
    ax.set_title("Sales effort tracks volume, not opportunity")
    ax.set_ylabel("Correlation with call effort")
    ax.set_ylim(0, max(c_rx, c_pan) * 1.25)
    ax.grid(axis="y")
    return {"path": T.save_fig(fig, "06_effort_corr"), "c_rx": c_rx, "c_pan": c_pan}


def chart_diminishing_returns(summary) -> Dict[str, Any]:
    s = summary.copy()
    s["dec"] = pd.qcut(s["ttm_calls"].rank(method="first"), 10, labels=False) + 1
    g = s.groupby("dec").agg(units=("ttm_units", "sum"), calls=("ttm_calls", "sum"),
                             avg_calls=("ttm_calls", "mean"))
    g["rx_per_call"] = g["units"] / g["calls"].clip(lower=1)
    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    ax.plot(g.index, g["rx_per_call"], color=T.BLUE, lw=2.4, marker="o", ms=6)
    ax.set_title("Diminishing returns: each extra call yields less (P2)")
    ax.set_xlabel("Call-intensity decile (1 = fewest calls, 10 = most)")
    ax.set_ylabel("Rx units per call")
    ax.set_xticks(range(1, 11))
    return {"path": T.save_fig(fig, "07_diminishing_returns"),
            "low": g.loc[1:3, "rx_per_call"].mean(), "high": g.loc[8:10, "rx_per_call"].mean()}


def chart_territory_coverage(t, ctx, summary) -> Dict[str, Any]:
    terr = summary.groupby("territory_id").agg(
        panel=("patient_panel_size", "sum"), n_doc=("doctor_id", "count"),
        calls=("ttm_calls", "sum")).reset_index()
    covered = (t["fact_sales_calls"][t["fact_sales_calls"].calls_made > 0]
               .merge(t["dim_doctor"][["doctor_id", "territory_id"]], on="doctor_id")
               .groupby("territory_id")["doctor_id"].nunique().rename("covered"))
    terr = terr.merge(covered, on="territory_id", how="left").fillna({"covered": 0})
    terr["coverage_pct"] = terr["covered"] / terr["n_doc"] * 100
    pan_med = terr["panel"].median()
    cov_q1 = terr["coverage_pct"].quantile(0.25)
    under = terr[(terr["panel"] > pan_med) & (terr["coverage_pct"] < cov_q1)]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.scatter(terr["panel"] / 1000, terr["coverage_pct"], s=22, color=T.BLUE, alpha=0.55,
               edgecolors="none", label="Territory")
    ax.scatter(under["panel"] / 1000, under["coverage_pct"], s=40, color=T.CRITICAL,
               edgecolors="none", label="Under-served (high potential, low coverage)")
    ax.axhline(cov_q1, color=T.BASELINE, lw=1)
    ax.axvline(pan_med / 1000, color=T.BASELINE, lw=1)
    ax.set_title("Under-served high-potential territories (P3)")
    ax.set_xlabel("Territory potential — total panel ('000)")
    ax.set_ylabel("Doctor coverage (%)")
    ax.legend(loc="upper right")
    return {"path": T.save_fig(fig, "08_territory_coverage"),
            "n_under": len(under), "avg_cov": under["coverage_pct"].mean()}


def chart_marketing_roi(t) -> Dict[str, Any]:
    mc = t["fact_marketing_spend"].merge(t["dim_campaign"][["campaign_id", "channel"]], on="campaign_id")
    g = mc.groupby("channel").agg(spend=("spend", "sum"), conv=("conversions", "sum"))
    g["roi"] = g["conv"] * MARGIN_PER_CONVERSION / g["spend"]
    g["budget_share"] = g["spend"] / g["spend"].sum() * 100
    fig, ax = plt.subplots(figsize=(8, 5))
    sizes = g["spend"] / g["spend"].max() * 900 + 120
    colors = [T.CRITICAL if r < 1 else T.GOOD if r > 2 else T.WARNING for r in g["roi"]]
    ax.scatter(g["budget_share"], g["roi"], s=sizes, color=colors, alpha=0.65, edgecolors="white")
    for ch, row in g.iterrows():
        ax.annotate(ch, (row["budget_share"], row["roi"]),
                    xytext=(6, 6), textcoords="offset points", fontsize=9, color=T.INK)
    ax.axhline(1.0, color=T.BASELINE, lw=1, ls="--")
    ax.text(g["budget_share"].max() * 0.98, 1.03, "break-even ROI = 1.0×", ha="right",
            color=T.MUTED, fontsize=8)
    ax.set_title("Marketing money sits in the lowest-ROI channel (P5)")
    ax.set_xlabel("Share of marketing budget (%)")
    ax.set_ylabel("ROI (₹ margin per ₹ spent)")
    ax.grid(True)
    return {"path": T.save_fig(fig, "09_marketing_roi"),
            "print_roi": g.loc["Print & Conferences", "roi"],
            "print_share": g.loc["Print & Conferences", "budget_share"],
            "digi_roi": g.loc["Digital & CME", "roi"],
            "digi_share": g.loc["Digital & CME", "budget_share"]}


def chart_share_trend(t, ctx) -> Dict[str, Any]:
    prod_ta = ctx["prod"][["product_id", "ta_id"]]
    our = (t["fact_prescriptions"].merge(prod_ta, on="product_id")
           .merge(ctx["doc_geo"], on="doctor_id").merge(ctx["ta"], on="ta_id"))
    our["pressured"] = our["zone_name"].isin(PRESSURED_ZONES) & our["ta_name"].isin(PRESSURED_TAS)
    comp = (t["fact_competitor_rx"].merge(ctx["ta"], on="ta_id")
            .merge(ctx["doc_geo"], on="doctor_id"))
    comp["pressured"] = comp["zone_name"].isin(PRESSURED_ZONES) & comp["ta_name"].isin(PRESSURED_TAS)
    og = our.groupby(["month_id", "pressured"])["units_prescribed"].sum().unstack()
    cg = comp.groupby(["month_id", "pressured"])["competitor_units"].sum().unstack()
    share = (og / (og + cg) * 100).reindex(ctx["months"])
    x = range(len(share))
    fig, ax = plt.subplots(figsize=(9, 4.4))
    ax.plot(x, share[True], color=T.CRITICAL, lw=2.4, label="Pressured zones/TAs")
    ax.plot(x, share[False], color=T.BLUE, lw=2.4, label="Rest of market")
    ax.set_title("Competitive erosion is localised, not everywhere (P6)")
    ax.set_ylabel("Our market share (%)")
    ax.set_xticks(list(x)[::6])
    ax.set_xticklabels([str(mm)[:4] for mm in share.index[::6]])
    ax.legend(loc="center left")
    ax.set_ylim(0, 70)
    return {"path": T.save_fig(fig, "10_share_trend"),
            "p_first": share[True].iloc[:6].mean(), "p_last": share[True].iloc[-6:].mean(),
            "r_first": share[False].iloc[:6].mean(), "r_last": share[False].iloc[-6:].mean()}


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------
def build_report(data_dir=DATA_PROCESSED) -> str:
    """Run all EDA charts and write reports/eda_report.md. Returns report text."""
    T.apply_theme()
    cfg = load_config()
    t = load_tables(data_dir)
    ctx = build_context(t)
    summary = doctor_summary(t, ctx)

    logger.info("Rendering charts ...")
    rev = chart_revenue_trend(t, ctx)
    brand = chart_brand_growth(t, ctx)
    life = chart_lifecycle_area(t, ctx)
    conc = chart_decile_concentration(summary)
    gap = chart_effort_gap(summary)
    corr = chart_effort_corr(summary)
    dim = chart_diminishing_returns(summary)
    cov = chart_territory_coverage(t, ctx, summary)
    mkt = chart_marketing_roi(t)
    share = chart_share_trend(t, ctx)

    blended_roi = (t["fact_marketing_spend"]["conversions"].sum() * MARGIN_PER_CONVERSION
                   / t["fact_marketing_spend"]["spend"].sum())

    md = f"""# Pharma Commercial Analytics Platform — Diagnostic EDA

**Reproducible report** · seed={cfg['random_seed']} · horizon {cfg['time']['period_start']}→{cfg['time']['period_end']} · all figures regenerated by `scripts/run_eda.py`.

> **The question:** the client spends more to grow less. This EDA locates *where* the growth is hiding and *why* effort and money are not converting — recovering, from raw data, the six commercial truths that frame the engagement.

## Headline

| KPI | Value |
|-----|------:|
| Annual revenue (TTM) | ₹ {rev['annual']:,.0f} Cr |
| Revenue growth (YoY) | {rev['yoy']:+.1f}% |
| Top-20% doctor revenue concentration | {conc['top20']:.0f}% |
| Blended marketing ROI | {blended_roi:.2f}× |
| Under-served high-potential territories | {cov['n_under']} |

---

## 1. The symptom: flat revenue

![revenue trend]({rev['path']})

Revenue is essentially flat at **{rev['yoy']:+.1f}% YoY**. This is not a demand story — the market is growing — so the problem is where effort and money land. The rest of this report decomposes that.

## 2. The paradox: stagnation hides divergence (P4)

![brand growth]({brand['path']})

![lifecycle area]({life['path']})

The flat total is an *average of opposites*: **{brand['worst']}** is down **{brand['worst_val']:+.0f}%** while **{brand['best']}** is up **{brand['best_val']:+.0f}%**. Declining mature brands are masking a healthy growth portfolio. **Implication:** promotional support is likely mis-weighted toward the wrong end of the lifecycle.

## 3. Customers are concentrated

![decile concentration]({conc['path']})

The top **20%** of doctors account for **{conc['top20']:.0f}%** of revenue. Targeting must be differentiated — but concentration alone doesn't tell us *who is under-served*. That is the next, decisive chart.

## 4. The smoking gun: effort chases volume, not potential (P1)

![effort gap]({gap['path']})  ![effort corr]({corr['path']})

Call effort correlates **{corr['c_rx']:.2f}** with a doctor's *current* prescribing but only **{corr['c_pan']:.2f}** with their *potential* (panel size). The consequence is the shaded quadrant: **{gap['whitespace_docs']:,} high-potential doctors** ({gap['ws_share']:.0f}% of all high-potential prescribers) receive bottom-quartile call effort. **This is the white space** — the reallocation prize the engagement will size in rupees.

## 5. And the doctors we over-call are saturating (P2)

![diminishing returns]({dim['path']})

Rx-per-call falls from **{dim['low']:.0f}** at low call-intensity to **{dim['high']:.0f}** at high intensity — classic diminishing returns. Effort poured onto already-loyal, high-decile doctors earns a low marginal return, while the white-space doctors above go under-served.

## 6. Some territories are structurally under-resourced (P3)

![territory coverage]({cov['path']})

**{cov['n_under']} territories** combine top-half potential with bottom-quartile coverage (avg coverage {cov['avg_cov']:.0f}%). These are candidates for re-alignment and new-rep deployment (Milestone 7).

## 7. Marketing money is in the wrong channel (P5)

![marketing roi]({mkt['path']})

Blended ROI is just **{blended_roi:.2f}×**. **Print & Conferences** absorbs **{mkt['print_share']:.0f}%** of budget at **{mkt['print_roi']:.2f}×** ROI, while **Digital & CME** — at **{mkt['digi_roi']:.2f}×** — receives only **{mkt['digi_share']:.0f}%**. Re-weighting spend toward high-ROI channels is a near-free lever.

## 8. Competitive loss is localised, not universal (P6)

![share trend]({share['path']})

Share in the pressured zones/TAs fell from **{share['p_first']:.0f}% → {share['p_last']:.0f}%**, while the rest of the market held steady (**{share['r_first']:.0f}% → {share['r_last']:.0f}%**). The competitive fix should be *targeted*, not a blanket national response.

---

## So what — the diagnostic thesis

1. **Reallocate field effort** from saturated high-deciles toward the {gap['whitespace_docs']:,}-doctor white space and the {cov['n_under']} under-served territories.
2. **Re-weight marketing** from Print toward Digital/CME to lift blended ROI above {blended_roi:.2f}×.
3. **Rebalance promotional mix** toward growth brands; manage the declining hero for cash.
4. **Defend selectively** in the pressured zones rather than spreading thin.

Milestones 4–8 quantify each of these in rupees (segmentation → opportunity scoring → optimization → financial model).
"""
    ensure_dir(REPORTS_DIR)
    (REPORTS_DIR / "eda_report.md").write_text(md, encoding="utf-8")
    logger.info("Wrote reports/eda_report.md with 10 figures")
    return md
