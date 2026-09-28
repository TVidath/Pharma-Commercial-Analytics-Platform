"""Tests for the opportunity & performance diagnostics."""
from __future__ import annotations

from catalyst.analytics import performance as perf
from catalyst.segmentation.doctors import segment_doctors


def test_market_share_bounds(small_tables):
    ctx = perf._context(small_tables)
    m = perf.market_by_ta(small_tables, ctx)
    assert len(m) == len(small_tables["dim_therapeutic_area"])
    assert m["share_pct"].between(0, 100).all()
    assert (m["market_size_cr"] > 0).all()


def test_opportunity_components_nonnegative(small_tables):
    ctx = perf._context(small_tables)
    seg = segment_doctors(small_tables, ctx["ttm"])
    comp = perf.opportunity_components(small_tables, ctx, seg)
    for key in ("white_space_cr", "share_recapture_cr", "mkt_uplift_cr"):
        assert comp[key] >= 0, f"{key} should be non-negative"
    # pressured-zone share should be below the rest-of-market share (P6)
    assert comp["cur_share_p"] < comp["rest_share"]


def test_region_metrics_complete(small_tables):
    ctx = perf._context(small_tables)
    seg = segment_doctors(small_tables, ctx["ttm"])
    reg = perf.region_metrics(small_tables, ctx, seg)
    assert reg["share_pct"].between(0, 100).all()
    assert (reg["white_space_cr"] >= 0).all()
