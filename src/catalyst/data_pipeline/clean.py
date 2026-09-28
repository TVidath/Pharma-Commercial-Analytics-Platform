"""Cleaning & type-enforcement stage: data/raw -> data/processed.

The synthetic generator emits well-formed data, so cleaning here is light but
real: it enforces dtypes, coerces booleans/dates, removes any impossible rows,
and de-duplicates on declared grain. In a production engagement this is where
messy source extracts would be standardised — the stage exists so the pipeline
shape matches reality.
"""
from __future__ import annotations

from typing import Dict

import pandas as pd

from ..data_generation.engine import LOAD_ORDER
from ..utils.logging import get_logger
from ..utils.paths import DATA_PROCESSED, DATA_RAW, ensure_dir

logger = get_logger(__name__)

_GRAINS = {
    "fact_prescriptions": ["doctor_id", "product_id", "month_id"],
    "fact_competitor_rx": ["doctor_id", "ta_id", "month_id"],
    "fact_sales_calls": ["rep_id", "doctor_id", "month_id"],
    "fact_marketing_spend": ["campaign_id", "region_id", "month_id"],
}
_NONNEG = {
    "fact_prescriptions": ["units_prescribed", "revenue", "new_patient_count"],
    "fact_competitor_rx": ["competitor_units"],
    "fact_sales_calls": ["calls_planned", "calls_made", "samples_dropped"],
    "fact_marketing_spend": ["spend", "leads", "conversions"],
}
# Nullable FK columns: keep as integers (pandas float would emit "1403.0",
# which a Postgres INTEGER column rejects). Int64 writes "1403"/"" (-> NULL).
_NULLABLE_INT = {
    "dim_doctor": ["hospital_id"],
}


def clean_table(name: str, df: pd.DataFrame) -> pd.DataFrame:
    """Apply cleaning rules for a single table."""
    before = len(df)
    # booleans
    for col in ("is_forecast", "kol_flag"):
        if col in df.columns:
            df[col] = df[col].astype(bool)
    # dates
    for col in ("month_date", "joining_date", "launch_date"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col]).dt.date
    # nullable integer FKs -> Int64 (avoids "1403.0" float rendering)
    for col in _NULLABLE_INT.get(name, []):
        if col in df.columns:
            df[col] = df[col].astype("Int64")
    # drop impossible negatives
    for col in _NONNEG.get(name, []):
        df = df[df[col] >= 0]
    # de-duplicate on grain
    if name in _GRAINS:
        df = df.drop_duplicates(_GRAINS[name])
    dropped = before - len(df)
    if dropped:
        logger.info("  %s: dropped %d invalid/duplicate rows", name, dropped)
    return df.reset_index(drop=True)


def clean_all(raw_dir=DATA_RAW, out_dir=DATA_PROCESSED) -> Dict[str, int]:
    """Clean every raw CSV and write to processed. Returns row counts."""
    ensure_dir(out_dir)
    counts: Dict[str, int] = {}
    for name in LOAD_ORDER:
        df = pd.read_csv(raw_dir / f"{name}.csv")
        df = clean_table(name, df)
        df.to_csv(out_dir / f"{name}.csv", index=False)
        counts[name] = len(df)
        logger.info("  cleaned %-24s -> %8d rows", name, len(df))
    return counts
