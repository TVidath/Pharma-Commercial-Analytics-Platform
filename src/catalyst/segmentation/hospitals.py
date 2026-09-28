"""Hospital segmentation: potential-based tiering (Platinum/Gold/Silver/Bronze).

Hospital potential blends physical scale (beds, patient volume, type) with the
commercial value of its affiliated doctors — a hospital is only as valuable as
the prescribers it houses. Tiers drive key-account vs low-touch coverage.
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from ..data_generation.reference_data import HOSPITAL_TYPE_POTENTIAL
from ..data_generation.rng import minmax

# score weights (sum to 1.0)
W_BEDS, W_VOL, W_TYPE, W_NDOC, W_VALUE = 0.20, 0.20, 0.15, 0.15, 0.30


def segment_hospitals(t: Dict[str, pd.DataFrame], doc_seg: pd.DataFrame) -> pd.DataFrame:
    """Return hospital-level potential score, tier, and affiliated economics."""
    h = t["dim_hospital"].copy()

    aff = doc_seg.groupby("hospital_id").agg(
        affiliated_doctors=("doctor_id", "count"),
        affiliated_ttm_revenue=("ttm_revenue", "sum"),
        affiliated_white_space=("white_space_value", "sum"),
    )
    h = h.merge(aff, on="hospital_id", how="left")
    for c in ("affiliated_doctors", "affiliated_ttm_revenue", "affiliated_white_space"):
        h[c] = h[c].fillna(0)

    type_w = h["hospital_type"].map(HOSPITAL_TYPE_POTENTIAL) / max(HOSPITAL_TYPE_POTENTIAL.values())
    score = (W_BEDS * minmax(h["bed_count"].to_numpy())
             + W_VOL * minmax(h["annual_patient_volume"].to_numpy())
             + W_TYPE * type_w.to_numpy()
             + W_NDOC * minmax(h["affiliated_doctors"].to_numpy())
             + W_VALUE * minmax(h["affiliated_ttm_revenue"].to_numpy()))
    h["potential_score"] = np.round(minmax(score) * 100, 1)

    pct = h["potential_score"].rank(pct=True)
    h["tier"] = np.select(
        [pct >= 0.90, pct >= 0.70, pct >= 0.30],
        ["Platinum", "Gold", "Silver"], default="Bronze")

    # attach region for reporting
    geo = (t["dim_territory"][["territory_id", "region_id"]]
           .merge(t["dim_region"][["region_id", "region_name", "zone_id"]], on="region_id")
           .merge(t["dim_zone"], on="zone_id"))
    h = h.merge(geo[["territory_id", "region_name", "zone_name"]], on="territory_id", how="left")
    return h
