#!/usr/bin/env python
"""Precompute lightweight aggregate CSVs for the executive dashboard.

The fact tables are millions of rows; the dashboard needs small summaries. This
step writes them to data/processed/dashboard/ so the Streamlit app (and a Power
BI import) load instantly. Reuses the analytics/financial modules as the single
source of truth.

Usage:  python scripts/prepare_dashboard.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from catalyst.analytics import performance as perf  # noqa: E402
from catalyst.data_generation.reference_data import MARGIN_PER_CONVERSION  # noqa: E402
from catalyst.data_pipeline.validate import load_tables  # noqa: E402
from catalyst.forecasting.forecast import monthly_revenue  # noqa: E402
from catalyst.utils.config import load_config  # noqa: E402
from catalyst.utils.logging import get_logger  # noqa: E402
from catalyst.utils.paths import DATA_PROCESSED, ensure_dir  # noqa: E402

logger = get_logger("catalyst.dashboard_prep")
CRORE = 1e7
OUT = DATA_PROCESSED / "dashboard"


def main() -> None:
    ensure_dir(OUT)
    cfg = load_config()
    t = load_tables()
    ctx = perf._context(t)
    seg = pd.read_csv(DATA_PROCESSED / "doctor_segments.csv")

    # monthly portfolio
    mrev = monthly_revenue(t).rename("revenue_cr").reset_index()
    mrev.columns = ["month_id", "revenue_cr"]
    mrev.to_csv(OUT / "monthly_portfolio.csv", index=False)

    # region summary
    reg = perf.region_metrics(t, ctx, seg)[
        ["region_name", "zone_name", "ttm_rev_cr", "growth_pct", "share_pct", "white_space_cr"]]
    reg.to_csv(OUT / "region_summary.csv", index=False)

    # product summary
    prod = perf.product_metrics(t, ctx)[
        ["brand_name", "ta_name", "lifecycle_stage", "ttm_rev_cr", "growth_pct", "margin_pct", "spend_cr"]]
    prod.to_csv(OUT / "product_summary.csv", index=False)

    # market by TA
    perf.market_by_ta(t, ctx)[["ta_name", "share_pct", "market_size_cr"]].to_csv(
        OUT / "market_ta.csv", index=False)

    # marketing channel ROI
    mc = (t["fact_marketing_spend"].merge(t["dim_campaign"][["campaign_id", "channel"]], on="campaign_id"))
    ch = mc.groupby("channel").agg(spend=("spend", "sum"), conv=("conversions", "sum")).reset_index()
    ch["spend_cr"] = ch["spend"] / CRORE
    ch["roi"] = ch["conv"] * MARGIN_PER_CONVERSION / ch["spend"]
    ch["budget_share_pct"] = ch["spend"] / ch["spend"].sum() * 100
    ch[["channel", "spend_cr", "roi", "budget_share_pct"]].to_csv(OUT / "channel_roi.csv", index=False)

    # segment summary
    tot_rev = seg["ttm_revenue"].sum()
    sg = seg.groupby(["segment", "action"]).agg(
        doctors=("doctor_id", "count"), revenue=("ttm_revenue", "sum"),
        white_space=("white_space_value", "sum")).reset_index()
    sg["pct_revenue"] = sg["revenue"] / tot_rev * 100
    sg["white_space_cr"] = sg["white_space"] / CRORE
    sg[["segment", "action", "doctors", "pct_revenue", "white_space_cr"]].to_csv(
        OUT / "segment_summary.csv", index=False)

    # opportunity-score tier summary
    if (DATA_PROCESSED / "doctor_opportunity_score.csv").exists():
        sc = pd.read_csv(DATA_PROCESSED / "doctor_opportunity_score.csv")
        ts = sc.groupby("priority_tier").agg(
            doctors=("doctor_id", "count"), avg_score=("opportunity_score", "mean"),
            avg_calls=("ttm_calls", "mean"),
            white_space_cr=("white_space_value", lambda s: s.sum() / CRORE)).reset_index()
        ts.to_csv(OUT / "score_tier_summary.csv", index=False)

    # headline KPIs
    annual = mrev["revenue_cr"].tail(12).sum()
    yoy = (mrev["revenue_cr"].tail(12).sum() - mrev["revenue_cr"].iloc[-24:-12].sum()) \
        / mrev["revenue_cr"].iloc[-24:-12].sum() * 100
    blended_roi = ch["conv"].sum() * MARGIN_PER_CONVERSION / ch["spend"].sum()
    ws_total = seg["white_space_value"].sum() / CRORE
    kpis = pd.DataFrame([
        {"metric": "Annual revenue (₹ Cr)", "value": f"{annual:,.0f}"},
        {"metric": "Revenue growth YoY", "value": f"{yoy:+.1f}%"},
        {"metric": "Blended marketing ROI", "value": f"{blended_roi:.2f}×"},
        {"metric": "Total white space (₹ Cr)", "value": f"{ws_total:,.0f}"},
    ])
    kpis.to_csv(OUT / "kpis.csv", index=False)

    logger.info("Wrote %d dashboard CSVs to %s", len(list(OUT.glob('*.csv'))), OUT)


if __name__ == "__main__":
    main()
