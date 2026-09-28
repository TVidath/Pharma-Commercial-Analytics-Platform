"""Tests for the data engine, schema contract, and validation checks.

Fast tests run on a scaled-down dataset; the planted-truth integration test
runs on the full processed data when present (skipped otherwise).
"""
from __future__ import annotations

import pytest

from catalyst.data_generation.engine import LOAD_ORDER, SCHEMA_COLUMNS
from catalyst.data_pipeline.validate import (load_tables, run_all,
                                             structural_checks, ValidationResult)
from catalyst.utils.config import build_calendar, load_config


# --- config / calendar -------------------------------------------------------
def test_calendar_length_and_ids():
    cfg = load_config()
    cal = build_calendar(cfg)
    assert len(cal) == cfg["time"]["history_months"]
    # month_id is a sortable YYYYMM integer, strictly increasing
    ids = [r["month_id"] for r in cal]
    assert ids == sorted(ids)
    assert cal[-1]["month_id"] == 202606


# --- engine output contract --------------------------------------------------
def test_all_tables_present_with_schema_columns(small_tables):
    for name in LOAD_ORDER:
        assert name in small_tables, f"missing table {name}"
        cols = small_tables[name].columns
        missing = [c for c in SCHEMA_COLUMNS[name] if c not in cols]
        assert not missing, f"{name} missing schema columns {missing}"


def test_entity_scale_matches_config(small_tables, small_cfg):
    assert len(small_tables["dim_doctor"]) == small_cfg["entities"]["doctors"]
    assert len(small_tables["dim_sales_rep"]) == small_cfg["entities"]["sales_reps"]
    # one rep per territory (1:1)
    assert small_tables["dim_sales_rep"]["territory_id"].is_unique


# --- structural integrity on scaled data ------------------------------------
def test_structural_checks_pass_on_scaled(small_tables):
    res = ValidationResult()
    structural_checks(small_tables, res)
    # entity-count check is brief-specific (18000); ignore it at small scale
    failures = [c for c in res.checks
                if not c.passed and c.name != "Entity counts match brief"]
    assert not failures, f"structural failures: {[c.name for c in failures]}"


def test_grain_uniqueness(small_tables):
    grains = {
        "fact_prescriptions": ["doctor_id", "product_id", "month_id"],
        "fact_sales_calls": ["rep_id", "doctor_id", "month_id"],
        "fact_marketing_spend": ["campaign_id", "region_id", "month_id"],
    }
    for tbl, keys in grains.items():
        assert small_tables[tbl].duplicated(keys).sum() == 0


def test_marketing_funnel_integrity(small_tables):
    m = small_tables["fact_marketing_spend"]
    assert (m["conversions"] <= m["leads"]).all()


# --- planted-truth integration (full data) ----------------------------------
def test_planted_truths_recovered(processed_dir):
    if processed_dir is None:
        pytest.skip("full processed data not generated; run scripts/build_all.sh")
    cfg = load_config()
    tables = load_tables(processed_dir)
    res = run_all(tables, cfg)
    planted = res.by_category("planted")
    failed = [c.name for c in planted if not c.passed]
    assert not failed, f"planted truths not recovered: {failed}"
    assert res.passed, "structural checks failed on full data"
