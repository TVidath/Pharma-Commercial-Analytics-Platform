"""Tests for territory & sales-force optimization."""
from __future__ import annotations

from catalyst.optimization.optimize import IDEAL_FREQ, build_plan
from catalyst.scoring.opportunity_score import compute_scores
from catalyst.segmentation.doctors import segment_doctors


def _score(tables):
    ttm = tables["dim_month"].sort_values("month_id")["month_id"].tolist()[-12:]
    return compute_scores(tables, seg=segment_doctors(tables, ttm))


def test_ideal_frequency_ordering():
    assert IDEAL_FREQ["P1"] > IDEAL_FREQ["P2"] > IDEAL_FREQ["P3"]


def test_reallocation_is_capacity_neutral(small_tables):
    plan = build_plan(small_tables, score=_score(small_tables))
    doc = plan["doc_plan"]
    # total recommended calls ~ total current (within rounding); no new capacity
    cur, rec = doc["ttm_calls"].sum(), doc["rec_calls"].sum()
    assert abs(rec - cur) / cur < 0.05


def test_effort_moves_from_p3_to_p1(small_tables):
    plan = build_plan(small_tables, score=_score(small_tables))
    doc = plan["doc_plan"]
    by_tier = doc.groupby("priority_tier")["delta_calls"].mean()
    assert by_tier.get("P1", 0) > 0        # P1 gains calls
    assert by_tier.get("P3", 0) < 0        # P3 loses calls


def test_new_reps_equal_vacancies(small_tables):
    plan = build_plan(small_tables, score=_score(small_tables))
    s = plan["summary"]
    assert s["new_reps"] == s["n_vacant"]
    assert s["reallocated_calls"] > 0
