"""Tests for doctor & hospital segmentation."""
from __future__ import annotations

from catalyst.segmentation.doctors import segment_doctors
from catalyst.segmentation.hospitals import segment_hospitals
from catalyst.segmentation.playbooks import INCREASE, MAINTAIN, REDUCE


def _ttm(tables):
    return tables["dim_month"].sort_values("month_id")["month_id"].tolist()[-12:]


def test_every_doctor_segmented(small_tables):
    doc = segment_doctors(small_tables, _ttm(small_tables))
    assert len(doc) == len(small_tables["dim_doctor"])
    assert doc["segment"].notna().all()
    assert set(doc["action"].unique()).issubset({INCREASE, MAINTAIN, REDUCE})


def test_potential_score_bounds_and_whitespace(small_tables):
    doc = segment_doctors(small_tables, _ttm(small_tables))
    assert doc["potential_score"].between(0, 100).all()
    assert (doc["white_space_value"] >= 0).all()
    # white space should be concentrated in high-potential / low-value doctors
    gems = doc[doc["segment"] == "Hidden Gems"]
    others = doc[doc["segment"] == "Champions"]
    if len(gems) and len(others):
        assert gems["white_space_value"].mean() > others["white_space_value"].mean()


def test_deciles_cover_1_to_10(small_tables):
    doc = segment_doctors(small_tables, _ttm(small_tables))
    assert set(doc["decile"].unique()) == set(range(1, 11))


def test_hospitals_tiered(small_tables):
    doc = segment_doctors(small_tables, _ttm(small_tables))
    hosp = segment_hospitals(small_tables, doc)
    assert len(hosp) == len(small_tables["dim_hospital"])
    assert set(hosp["tier"].unique()).issubset({"Platinum", "Gold", "Silver", "Bronze"})
    assert hosp["potential_score"].between(0, 100).all()
