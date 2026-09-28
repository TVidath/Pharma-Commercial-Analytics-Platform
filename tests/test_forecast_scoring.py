"""Tests for revenue forecasting and the Commercial Opportunity Score."""
from __future__ import annotations

import numpy as np
import pandas as pd

from catalyst.forecasting.forecast import (baseline_forecast, intervention_overlay,
                                           monthly_revenue)
from catalyst.scoring.opportunity_score import WEIGHTS, compute_scores
from catalyst.segmentation.doctors import segment_doctors


def test_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_monthly_revenue_length(small_tables, small_cfg):
    rev = monthly_revenue(small_tables)
    assert len(rev) == small_cfg["time"]["history_months"]
    assert (rev >= 0).all()


def test_intervention_overlay_ramps_up():
    base = np.full(12, 100.0)
    out = intervention_overlay(base, opportunity_annual_cr=120.0, capture_fraction=0.5, ramp_months=12)
    assert (out >= base).all()                 # never below baseline
    assert out[-1] > out[0]                     # ramps up
    # month-12 run-rate ~ target: +120*0.5/12 = +5
    assert abs((out[-1] - base[-1]) - 5.0) < 1e-6


def test_baseline_forecast_shape_and_interval():
    # synthetic 36-month seasonal + trend series
    t = np.arange(36)
    y = pd.Series(100 + 0.3 * t + 8 * np.sin(2 * np.pi * t / 12) + np.random.default_rng(0).normal(0, 2, 36))
    fc = baseline_forecast(y, horizon=12)
    assert list(fc.columns) == ["mean", "lower", "upper"]
    assert len(fc) == 12
    assert (fc["lower"] <= fc["mean"]).all() and (fc["mean"] <= fc["upper"]).all()


def test_opportunity_score_bounds(small_tables):
    ttm = small_tables["dim_month"].sort_values("month_id")["month_id"].tolist()[-12:]
    seg = segment_doctors(small_tables, ttm)
    doc = compute_scores(small_tables, seg=seg)
    assert len(doc) == len(small_tables["dim_doctor"])
    assert doc["opportunity_score"].between(0, 100).all()
    assert set(doc["priority_tier"].unique()).issubset({"P1", "P2", "P3"})
    for c in ("c_potential", "c_headroom", "c_momentum", "c_accessibility", "c_competitive"):
        assert doc[c].between(0, 100).all()
