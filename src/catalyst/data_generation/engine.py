"""Data-generation orchestrator.

``build_all`` produces every table as a DataFrame; ``write_raw`` persists only
the database-schema columns (internal helper columns are dropped) to
``data/raw`` as CSV. ``LOAD_ORDER`` gives an FK-safe insertion sequence.
"""
from __future__ import annotations

from typing import Dict

import pandas as pd

from ..utils.logging import get_logger
from ..utils.paths import DATA_RAW, ensure_dir
from .dimensions import build_dimensions
from .facts import build_facts
from .latent import compute_doctor_latents

logger = get_logger(__name__)

# FK-safe order: parents before children
LOAD_ORDER = [
    "dim_month", "dim_zone", "dim_region", "dim_regional_manager",
    "dim_territory", "dim_sales_rep", "dim_hospital", "dim_doctor",
    "dim_therapeutic_area", "dim_product", "dim_competitor_product",
    "dim_campaign",
    "fact_prescriptions", "fact_competitor_rx", "fact_sales_calls",
    "fact_marketing_spend",
]

# Exact columns (and order) that map to the database schema.
SCHEMA_COLUMNS: Dict[str, list] = {
    "dim_month": ["month_id", "month_date", "year", "quarter", "month_num",
                  "month_name", "fiscal_year", "is_forecast"],
    "dim_zone": ["zone_id", "zone_name"],
    "dim_region": ["region_id", "zone_id", "region_name", "state", "rm_id"],
    "dim_regional_manager": ["rm_id", "region_id", "rm_name", "experience_years"],
    "dim_territory": ["territory_id", "region_id", "rep_id", "territory_name",
                      "city", "urbanicity_tier"],
    "dim_sales_rep": ["rep_id", "region_id", "rm_id", "territory_id", "rep_name",
                      "experience_years", "joining_date", "monthly_call_target",
                      "employment_status"],
    "dim_hospital": ["hospital_id", "territory_id", "hospital_name", "hospital_type",
                     "bed_count", "annual_patient_volume", "established_year"],
    "dim_doctor": ["doctor_id", "hospital_id", "territory_id", "doctor_name",
                   "specialty", "years_in_practice", "patient_panel_size", "kol_flag"],
    "dim_therapeutic_area": ["ta_id", "ta_name", "seasonality_profile"],
    "dim_product": ["product_id", "ta_id", "brand_name", "molecule", "dosage_form",
                    "unit_price", "cost_per_unit", "launch_date", "lifecycle_stage"],
    "dim_competitor_product": ["competitor_product_id", "ta_id", "competitor_brand",
                               "company", "unit_price"],
    "dim_campaign": ["campaign_id", "product_id", "campaign_name", "channel",
                     "objective", "start_month_id", "end_month_id"],
    "fact_prescriptions": ["doctor_id", "product_id", "month_id",
                           "units_prescribed", "revenue", "new_patient_count"],
    "fact_competitor_rx": ["doctor_id", "ta_id", "month_id", "competitor_units"],
    "fact_sales_calls": ["rep_id", "doctor_id", "month_id", "calls_planned",
                         "calls_made", "samples_dropped"],
    "fact_marketing_spend": ["campaign_id", "product_id", "region_id", "month_id",
                             "spend", "leads", "conversions"],
}


def build_all(cfg: Dict) -> Dict[str, pd.DataFrame]:
    """Generate every table. Returns dict keyed by table name (full columns)."""
    logger.info("Building dimensions ...")
    dims = build_dimensions(cfg)
    logger.info("Computing doctor latent drivers ...")
    latents = compute_doctor_latents(cfg, dims)
    logger.info("Building facts (this is the heavy step) ...")
    facts = build_facts(cfg, dims, latents)
    tables = {**dims, **facts}
    for name in LOAD_ORDER:
        logger.info("  %-24s %10d rows", name, len(tables[name]))
    return tables


def write_raw(tables: Dict[str, pd.DataFrame], out_dir=DATA_RAW) -> None:
    """Write schema-clean CSVs to ``out_dir`` in load order."""
    ensure_dir(out_dir)
    for name in LOAD_ORDER:
        cols = SCHEMA_COLUMNS[name]
        df = tables[name][cols]
        path = out_dir / f"{name}.csv"
        df.to_csv(path, index=False)
        logger.info("  wrote %s", path.name)
