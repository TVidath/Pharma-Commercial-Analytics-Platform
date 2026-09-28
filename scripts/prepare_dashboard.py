#!/usr/bin/env python
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from catalyst.data_pipeline.validate import load_tables
from catalyst.utils.paths import DATA_PROCESSED, ensure_dir

OUT = DATA_PROCESSED / "dashboard"
CRORE = 1e7

def main() -> None:
    ensure_dir(OUT)
    t = load_tables()
    
    # 1. monthly portfolio
    rx = t["fact_prescriptions"]
    mrev = rx.groupby("month_id")["revenue"].sum().reset_index()
    mrev["revenue_cr"] = mrev["revenue"] / CRORE
    mrev[["month_id", "revenue_cr"]].to_csv(OUT / "monthly_portfolio.csv", index=False)

    # 2. product summary
    prod = t["dim_product"].merge(t["dim_therapeutic_area"], on="ta_id", how="left")
    prev = rx.groupby("product_id")["revenue"].sum().reset_index()
    prev["revenue_cr"] = prev["revenue"] / CRORE
    p_summ = prod.merge(prev, on="product_id", how="left")
    p_summ.to_csv(OUT / "product_summary.csv", index=False)

    # 3. region summary
    rx_geo = rx.merge(t["dim_doctor"][["doctor_id", "territory_id"]], on="doctor_id") \
               .merge(t["dim_territory"][["territory_id", "region_id"]], on="territory_id") \
               .merge(t["dim_region"][["region_id", "region_name", "zone_id"]], on="region_id") \
               .merge(t["dim_zone"][["zone_id", "zone_name"]], on="zone_id")
    rrev = rx_geo.groupby(["region_id", "region_name", "zone_name"])["revenue"].sum().reset_index()
    rrev["revenue_cr"] = rrev["revenue"] / CRORE
    rrev.to_csv(OUT / "region_summary.csv", index=False)

    # 4. KPIs
    annual = mrev["revenue_cr"].tail(12).sum() if len(mrev) >= 12 else mrev["revenue_cr"].sum()
    kpis = pd.DataFrame([
        {"metric": "Annual revenue (₹ Cr)", "value": f"{annual:,.0f}"},
        {"metric": "Total Products", "value": f"{len(prod)}"},
        {"metric": "Total Regions", "value": f"{len(rrev)}"},
    ])
    kpis.to_csv(OUT / "kpis.csv", index=False)
    
    print(f"Wrote dashboard CSVs to {OUT}")

if __name__ == "__main__":
    main()
