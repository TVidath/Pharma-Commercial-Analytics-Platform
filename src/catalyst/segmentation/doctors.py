"""Doctor segmentation: Potential x Value 9-box framework.

Method (interpretable first, ML only to validate):
1. Build a transparent **potential score** from observable drivers (panel size,
   specialty economics, hospital tier, urbanicity, KOL status).
2. Place each doctor on two axes — Potential (High/Med/Low) and current Value
   (High/Med/Low) — giving nine action-mapped segments (see playbooks).
3. Size the **white space** (₹) for under-realised doctors.
4. Validate the rule-based cut against K-means (adjusted Rand index + silhouette)
   — clustering confirms the segments; it does not define them.
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from ..data_generation.reference_data import HOSPITAL_TYPE_POTENTIAL, URBANICITY_POTENTIAL
from ..data_generation.rng import minmax, zscore
from ..utils.logging import get_logger
from .playbooks import DOCTOR_SEGMENTS

logger = get_logger(__name__)

# potential-score driver weights (sum to 1.0)
W_PANEL, W_SPEC, W_HOSP, W_URBAN, W_KOL = 0.40, 0.20, 0.20, 0.10, 0.10
WHITE_SPACE_CAPTURE = 0.40  # conservative fraction of the gap deemed addressable


def _tier(pct: pd.Series) -> pd.Series:
    """Even tertiles: High (top third), Medium, Low (bottom third)."""
    return pd.cut(pct, bins=[-0.01, 1 / 3, 2 / 3, 1.01], labels=["Low", "Medium", "High"])


def build_features(t: Dict[str, pd.DataFrame], ttm_months) -> pd.DataFrame:
    """Per-doctor feature frame with the transparent potential score."""
    doc = t["dim_doctor"].copy()

    # TTM value & activity
    rx = t["fact_prescriptions"]
    rx_ttm = rx[rx["month_id"].isin(ttm_months)]
    val = rx_ttm.groupby("doctor_id").agg(ttm_revenue=("revenue", "sum"),
                                          ttm_units=("units_prescribed", "sum"))
    calls = t["fact_sales_calls"]
    calls_ttm = (calls[calls["month_id"].isin(ttm_months)]
                 .groupby("doctor_id")["calls_made"].sum().rename("ttm_calls"))
    doc = doc.merge(val, on="doctor_id", how="left").merge(calls_ttm, on="doctor_id", how="left")
    doc[["ttm_revenue", "ttm_units", "ttm_calls"]] = doc[["ttm_revenue", "ttm_units", "ttm_calls"]].fillna(0)

    # driver: specialty economics (data-driven avg value per specialty)
    spec_val = doc.groupby("specialty")["ttm_revenue"].mean()
    doc["spec_value"] = doc["specialty"].map(spec_val)

    # driver: hospital potential (beds + volume + type)
    h = t["dim_hospital"].copy()
    h["hosp_pot"] = (0.4 * minmax(h["bed_count"].to_numpy())
                     + 0.4 * minmax(h["annual_patient_volume"].to_numpy())
                     + 0.2 * h["hospital_type"].map(HOSPITAL_TYPE_POTENTIAL)
                     / max(HOSPITAL_TYPE_POTENTIAL.values()))
    doc = doc.merge(h[["hospital_id", "hosp_pot"]], on="hospital_id", how="left")
    doc["hosp_pot"] = doc["hosp_pot"].fillna(doc["hosp_pot"].median())  # standalone doctors

    # driver: urbanicity
    urb = t["dim_territory"][["territory_id", "urbanicity_tier"]]
    doc = doc.merge(urb, on="territory_id", how="left")
    doc["urban_w"] = doc["urbanicity_tier"].map(URBANICITY_POTENTIAL)

    # transparent potential score (0-100)
    raw = (W_PANEL * zscore(doc["patient_panel_size"].to_numpy())
           + W_SPEC * zscore(doc["spec_value"].to_numpy())
           + W_HOSP * zscore(doc["hosp_pot"].to_numpy())
           + W_URBAN * zscore(doc["urban_w"].to_numpy())
           + W_KOL * zscore(doc["kol_flag"].astype(float).to_numpy()))
    doc["potential_score"] = np.round(minmax(raw) * 100, 1)

    # percentile positions and opportunity
    doc["value_pct"] = doc["ttm_revenue"].rank(pct=True)
    doc["potential_pct"] = doc["potential_score"].rank(pct=True)
    doc["opportunity_gap"] = doc["potential_pct"] - doc["value_pct"]

    # white-space value (₹): expected value at this potential minus actual
    expected = np.quantile(doc["ttm_revenue"].to_numpy(), doc["potential_pct"].to_numpy())
    doc["white_space_value"] = np.clip(expected - doc["ttm_revenue"].to_numpy(), 0, None) * WHITE_SPACE_CAPTURE
    return doc


def segment_doctors(t: Dict[str, pd.DataFrame], ttm_months) -> pd.DataFrame:
    """Assign the 9-box segment, action, and playbook fields to each doctor."""
    doc = build_features(t, ttm_months)
    doc["potential_tier"] = _tier(doc["potential_pct"]).astype(str)
    doc["value_tier"] = _tier(doc["value_pct"]).astype(str)

    def _lookup(row, field):
        return DOCTOR_SEGMENTS[(row["potential_tier"], row["value_tier"])][field]

    doc["segment"] = doc.apply(lambda r: _lookup(r, "name"), axis=1)
    doc["action"] = doc.apply(lambda r: _lookup(r, "action"), axis=1)
    # decile 1 = highest value: qcut gives 0 (lowest)..9 (highest); map to 10..1
    doc["decile"] = pd.qcut(doc["ttm_revenue"].rank(method="first"), 10,
                            labels=False).rsub(10)
    return doc


def validate_with_kmeans(doc: pd.DataFrame) -> Dict[str, float]:
    """Confirm the interpretable segments are supported by unsupervised clustering."""
    from sklearn.cluster import KMeans
    from sklearn.metrics import adjusted_rand_score, silhouette_score

    X = np.column_stack([zscore(doc["potential_score"].to_numpy()),
                         zscore(doc["value_pct"].to_numpy() * 100)])
    km = KMeans(n_clusters=4, n_init=10, random_state=42).fit(X)

    # rule-based 4-quadrant (median split) for concordance
    p_hi = doc["potential_pct"] >= 0.5
    v_hi = doc["value_pct"] >= 0.5
    rule4 = (p_hi.astype(int) * 2 + v_hi.astype(int)).to_numpy()

    sample = np.random.default_rng(42).choice(len(X), size=min(5000, len(X)), replace=False)
    return {
        "ari": float(adjusted_rand_score(rule4, km.labels_)),
        "silhouette": float(silhouette_score(X[sample], km.labels_[sample])),
    }
