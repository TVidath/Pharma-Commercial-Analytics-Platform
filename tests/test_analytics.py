"""Tests for the EDA analytics layer (non-plotting logic)."""
from __future__ import annotations

from catalyst.analytics import eda


def test_context_windows(small_tables):
    ctx = eda.build_context(small_tables)
    for key in ("months", "ttm", "py", "first6", "last6", "doc_geo", "prod", "ta"):
        assert key in ctx
    assert len(ctx["ttm"]) == 12
    assert len(ctx["py"]) == 12
    # TTM and PY windows are disjoint and contiguous
    assert set(ctx["ttm"]).isdisjoint(ctx["py"])
    assert max(ctx["py"]) < min(ctx["ttm"])


def test_doctor_summary_shape(small_tables):
    ctx = eda.build_context(small_tables)
    s = eda.doctor_summary(small_tables, ctx)
    assert len(s) == len(small_tables["dim_doctor"])
    for col in ("doctor_id", "patient_panel_size", "ttm_units",
                "ttm_revenue", "ttm_calls", "zone_name"):
        assert col in s.columns
    # no NaNs in the aggregated measures (filled)
    assert s[["ttm_units", "ttm_revenue", "ttm_calls"]].isna().sum().sum() == 0


def test_effort_gap_recovers_p1_direction(small_tables):
    """Calls should correlate with current Rx more than with panel (P1)."""
    ctx = eda.build_context(small_tables)
    s = eda.doctor_summary(small_tables, ctx)
    c_rx = s["ttm_calls"].corr(s["ttm_units"])
    c_pan = s["ttm_calls"].corr(s["patient_panel_size"])
    assert c_rx > c_pan
