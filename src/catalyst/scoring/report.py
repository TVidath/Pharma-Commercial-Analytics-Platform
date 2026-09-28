"""Milestone 6 report: revenue forecast + Commercial Opportunity Score."""
from __future__ import annotations

from typing import Tuple

import pandas as pd

from ..data_pipeline.validate import load_tables
from ..forecasting.forecast import build_forecast, chart_forecast
from ..utils.config import load_config
from ..utils.logging import get_logger
from ..utils.paths import DATA_PROCESSED, REPORTS_DIR, ensure_dir
from ..visualization import theme as T
from .opportunity_score import (WEIGHTS, chart_component_by_tier,
                                chart_score_distribution, chart_score_vs_calls,
                                compute_scores, territory_scores)

logger = get_logger(__name__)
CRORE, LAKH = 1e7, 1e5


def build_report(data_dir=DATA_PROCESSED) -> Tuple[pd.DataFrame, pd.DataFrame]:
    T.apply_theme()
    cfg = load_config()
    t = load_tables(data_dir)

    logger.info("Fitting revenue forecast (ETS baseline + driver overlay) ...")
    res = build_forecast(t, horizon=cfg["time"]["forecast_horizon_months"])
    f_fc = chart_forecast(res)

    logger.info("Computing Commercial Opportunity Score ...")
    doc = compute_scores(t, data_dir=data_dir)
    terr = territory_scores(doc, t)
    f_dist = chart_score_distribution(doc)
    f_calls, act = chart_score_vs_calls(doc)
    f_comp = chart_component_by_tier(doc)

    # persist for optimisation (M7) & dashboard
    out_cols = ["doctor_id", "region_name", "segment", "priority_tier", "opportunity_score",
                "c_potential", "c_headroom", "c_momentum", "c_accessibility", "c_competitive",
                "ttm_revenue", "ttm_calls", "white_space_value"]
    doc[out_cols].to_csv(data_dir / "doctor_opportunity_score.csv", index=False)
    terr.to_csv(data_dir / "territory_opportunity.csv", index=False)

    # top-15 priority list
    top = doc.sort_values("opportunity_score", ascending=False).head(15)
    top_tbl = "\n".join(
        f"| {int(r.opportunity_score)} | {r.doctor_id} | {r.region_name} | {r.segment} | "
        f"₹{r.ttm_revenue/LAKH:.1f}L | {int(r.ttm_calls)} | ₹{r.white_space_value/LAKH:.1f}L |"
        for r in top.itertuples())

    n_p1 = (doc.priority_tier == "P1").sum()
    weights_tbl = " · ".join(f"{k.title()} {int(v*100)}%" for k, v in WEIGHTS.items())

    md = f"""# Pharma Commercial Analytics Platform — Forecasting & Commercial Opportunity Scoring

**Reproducible** · seed={cfg['random_seed']} · `scripts/run_forecast_scoring.py`.

Two deliverables: a **board-grade revenue forecast** (what happens if we act vs not)
and the **Commercial Opportunity Score** — the single ranked call list for the field.

---

## 1. Revenue forecast (Module 13)

![forecast]({f_fc})

An ETS model (additive trend + seasonality) gives the **baseline**; the **driver overlay**
phases in a conservative {int(res['capture_fraction']*100)}% capture of the ₹{res['opp_annual']:.0f} Cr
revenue opportunity register (M5) over 12 months.

| Scenario | Year-1 revenue | vs baseline |
|----------|---------------:|------------:|
| Baseline (do nothing) | ₹{res['y1_base']:,.0f} Cr | — |
| With reallocation | ₹{res['y1_interv']:,.0f} Cr | **+₹{res['y1_uplift_cr']:,.0f} Cr (+{res['y1_uplift_pct']:.1f}%)** |
| Exit run-rate (annualised) | ₹{res['exit_runrate']:,.0f} Cr | — |

The baseline confirms the client's problem — flat. The gap between the two lines is the
value of acting, and it compounds into the exit run-rate the financial model (M8) carries forward.

---

## 2. Commercial Opportunity Score (Module 14)

The master field-prioritisation index — a transparent 0–100 composite, published weights,
fully explainable to a sales VP:

> **Weights:** {weights_tbl}

![score distribution]({f_dist})

![score vs calls]({f_calls})

![component by tier]({f_comp})

**{n_p1:,} doctors are Priority-1.** The decisive picture is the call-list scatter: **{act['act_now']:,}
high-score doctors currently receive below-median call effort** — the field's immediate
"act now" list. The component chart shows P1 doctors are driven by high potential + headroom +
accessibility — exactly the reallocation thesis, now operationalised per doctor.

### Top-15 priority doctors

| Score | Doctor | Region | Segment | TTM Rev | TTM Calls | White space |
|------:|--------|--------|---------|--------:|----------:|------------:|
{top_tbl}

---

## So what → optimisation & financials

The score turns strategy into a **ranked list a rep can work Monday morning**. Milestone 7
uses the territory-level scores to re-balance workload and deploy new reps; Milestone 8
converts the forecast gap and capture ramp into ROI, NPV, payback, and scenario ranges.
"""
    ensure_dir(REPORTS_DIR)
    (REPORTS_DIR / "forecast_and_scoring_report.md").write_text(md, encoding="utf-8")
    logger.info("Wrote forecast_and_scoring_report.md, doctor_opportunity_score.csv, territory_opportunity.csv")
    return doc[out_cols], terr


def persist_to_db(doc: pd.DataFrame, terr: pd.DataFrame, cfg) -> None:
    from sqlalchemy import text
    from ..utils.db import get_engine
    engine = get_engine(cfg)
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS catalyst"))
    doc.to_sql("doctor_opportunity_score", engine, schema="catalyst", if_exists="replace", index=False)
    terr.to_sql("territory_opportunity", engine, schema="catalyst", if_exists="replace", index=False)
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_oppscore_doctor ON catalyst.doctor_opportunity_score(doctor_id)")
    logger.info("Loaded catalyst.doctor_opportunity_score (%d) and catalyst.territory_opportunity (%d)",
                len(doc), len(terr))
