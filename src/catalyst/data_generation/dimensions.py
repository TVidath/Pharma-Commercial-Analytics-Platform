"""Build all dimension tables as pandas DataFrames.

Referential integrity is guaranteed by construction: parents are built before
children and foreign keys are drawn from existing parent keys. Some DataFrames
carry internal helper columns prefixed with ``_`` (e.g. ``_is_underinvested``)
that drive fact generation but are dropped before loading to the database.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict

import numpy as np
import pandas as pd

from ..utils.config import build_calendar
from . import reference_data as ref
from .rng import clipped_normal, make_rng


def _names(rng, first, last, n, prefix=""):
    fn = first[rng.integers(0, len(first), n)]
    ln = last[rng.integers(0, len(last), n)]
    return np.array([f"{prefix}{a} {b}" for a, b in zip(fn, ln)], dtype=object)


def build_dimensions(cfg: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
    """Return a dict of dimension DataFrames keyed by table name."""
    rng = make_rng(int(cfg["random_seed"]))
    ent = cfg["entities"]
    first = np.array(ref.FIRST_NAMES, dtype=object)
    last = np.array(ref.LAST_NAMES, dtype=object)
    dims: Dict[str, pd.DataFrame] = {}

    # --- dim_month -----------------------------------------------------------
    cal = build_calendar(cfg, include_forecast=False)
    dims["dim_month"] = pd.DataFrame(cal)
    month_ids = dims["dim_month"]["month_id"].to_numpy()
    n_months = len(month_ids)

    # --- dim_zone ------------------------------------------------------------
    dims["dim_zone"] = pd.DataFrame({
        "zone_id": np.arange(1, len(ref.ZONES) + 1),
        "zone_name": ref.ZONES,
    })
    zone_id_by_name = dict(zip(ref.ZONES, range(1, len(ref.ZONES) + 1)))

    # --- dim_region (rm_id filled after RMs) ---------------------------------
    n_regions = len(ref.REGIONS)
    region = pd.DataFrame({
        "region_id": np.arange(1, n_regions + 1),
        "zone_id": [zone_id_by_name[z] for _, _, z in ref.REGIONS],
        "region_name": [r for r, _, _ in ref.REGIONS],
        "state": [s for _, s, _ in ref.REGIONS],
        "rm_id": np.arange(1, n_regions + 1),  # 1:1 mapping
    })
    dims["dim_region"] = region

    # --- dim_regional_manager ------------------------------------------------
    dims["dim_regional_manager"] = pd.DataFrame({
        "rm_id": np.arange(1, n_regions + 1),
        "region_id": np.arange(1, n_regions + 1),
        "rm_name": _names(rng, first, last, n_regions),
        "experience_years": clipped_normal(rng, 11, 4, 3, 25, n_regions).astype(int),
    })

    # --- dim_territory (rep_id filled after reps) ----------------------------
    n_terr = int(ent["territories"])
    # distribute territories across regions as evenly as possible
    terr_region = np.repeat(np.arange(1, n_regions + 1),
                            n_terr // n_regions)
    remainder = n_terr - len(terr_region)
    if remainder:
        terr_region = np.concatenate([terr_region, np.arange(1, remainder + 1)])
    rng.shuffle(terr_region)
    urb = ref.URBANICITY_TIERS
    terr_urban = np.array(urb)[rng.choice(len(urb), n_terr, p=ref.URBANICITY_WEIGHTS)]
    region_name_by_id = dict(zip(region["region_id"], region["region_name"]))
    terr_city = np.array([region_name_by_id[r] for r in terr_region], dtype=object)

    territory = pd.DataFrame({
        "territory_id": np.arange(1, n_terr + 1),
        "region_id": terr_region,
        "rep_id": np.arange(1, n_terr + 1),  # 1:1 with rep
        "territory_name": [f"TER-{i:04d}" for i in range(1, n_terr + 1)],
        "city": terr_city,
        "urbanicity_tier": terr_urban,
    })
    # planted truth P3: pick under-invested territories in high-potential regions
    ui_region_ids = region.loc[region["region_name"].isin(ref.UNDERINVESTED_REGIONS),
                               "region_id"].to_numpy()
    ui_pool = territory.loc[territory["region_id"].isin(ui_region_ids), "territory_id"].to_numpy()
    n_ui = int(cfg["data_logic"]["underinvested_territory_count"])
    ui_terr = rng.choice(ui_pool, size=min(n_ui, len(ui_pool)), replace=False)
    territory["_is_underinvested"] = territory["territory_id"].isin(ui_terr)
    dims["dim_territory"] = territory

    # --- dim_sales_rep -------------------------------------------------------
    n_reps = int(ent["sales_reps"])
    rm_by_region = dict(zip(region["region_id"], region["rm_id"]))
    rep_region = territory["region_id"].to_numpy()[:n_reps]
    exp = clipped_normal(rng, 6.5, 4.0, 1, 20, n_reps).astype(int)
    join = np.array([date(2026, 6, 1)] * n_reps, dtype=object)
    join = np.array([date(2026 - int(e), rng.integers(1, 13), 1) for e in exp], dtype=object)
    status = np.where(rng.random(n_reps) < 0.03, "Vacant",
                      np.where(rng.random(n_reps) < 0.02, "On-Leave", "Active"))
    dims["dim_sales_rep"] = pd.DataFrame({
        "rep_id": np.arange(1, n_reps + 1),
        "region_id": rep_region,
        "rm_id": [rm_by_region[r] for r in rep_region],
        "territory_id": np.arange(1, n_reps + 1),
        "rep_name": _names(rng, first, last, n_reps),
        "experience_years": exp,
        "joining_date": join,
        "monthly_call_target": clipped_normal(rng, 240, 25, 180, 300, n_reps).astype(int),
        "employment_status": status,
    })

    # --- dim_hospital --------------------------------------------------------
    n_hosp = int(ent["hospitals"])
    # weight hospital location by territory urbanicity potential; guarantee >=1 each
    terr_pot = territory["urbanicity_tier"].map(ref.URBANICITY_POTENTIAL).to_numpy()
    base_terr = np.arange(1, n_terr + 1)  # one hospital per territory
    extra = n_hosp - n_terr
    w = terr_pot / terr_pot.sum()
    extra_terr = rng.choice(np.arange(1, n_terr + 1), size=extra, p=w)
    hosp_terr = np.concatenate([base_terr, extra_terr])
    rng.shuffle(hosp_terr)
    htype = np.array(ref.HOSPITAL_TYPES)[rng.choice(len(ref.HOSPITAL_TYPES), n_hosp,
                                                    p=ref.HOSPITAL_TYPE_WEIGHTS)]
    beds = np.array([rng.integers(*ref.HOSPITAL_TYPE_BEDS[t]) + 1 for t in htype])
    pv = (beds * clipped_normal(rng, 55, 15, 20, 120, n_hosp)).astype(int)  # annual patient volume
    hosp_terr_region = territory.set_index("territory_id").loc[hosp_terr, "region_id"].to_numpy()
    dims["dim_hospital"] = pd.DataFrame({
        "hospital_id": np.arange(1, n_hosp + 1),
        "territory_id": hosp_terr,
        "hospital_name": [f"{c} {t} Hospital #{i}"
                          for i, (c, t) in enumerate(zip(
                              territory.set_index("territory_id").loc[hosp_terr, "city"].to_numpy(),
                              htype), 1)],
        "hospital_type": htype,
        "bed_count": beds,
        "annual_patient_volume": pv,
        "established_year": clipped_normal(rng, 2002, 12, 1960, 2022, n_hosp).astype(int),
        "_region_id": hosp_terr_region,
    })

    # --- dim_doctor ----------------------------------------------------------
    n_doc = int(ent["doctors"])
    specs = list(ref.SPECIALTY_MIX.keys())
    spec_w = np.array(list(ref.SPECIALTY_MIX.values()))
    doc_spec = np.array(specs)[rng.choice(len(specs), n_doc, p=spec_w / spec_w.sum())]
    # assign doctors to territories weighted by urbanicity potential
    doc_terr = rng.choice(np.arange(1, n_terr + 1), size=n_doc, p=w)
    doc_terr_urban = territory.set_index("territory_id").loc[doc_terr, "urbanicity_tier"].to_numpy()
    yrs = clipped_normal(rng, 14, 8, 1, 40, n_doc).astype(int)
    # panel size = latent capacity driver
    spec_pot = np.array([ref.SPECIALTY_POTENTIAL[s] for s in doc_spec])
    urb_pot = np.array([ref.URBANICITY_POTENTIAL[u] for u in doc_terr_urban])
    panel = (clipped_normal(rng, 900, 350, 120, 3000, n_doc)
             * spec_pot * urb_pot * (0.6 + 0.03 * yrs)).astype(int)
    kol = (rng.random(n_doc) < 0.04) & (panel > np.quantile(panel, 0.75))
    # assign each doctor a hospital in its territory (or None ~ 15% standalone)
    hosp_by_terr: Dict[int, np.ndarray] = {
        t: g["hospital_id"].to_numpy()
        for t, g in dims["dim_hospital"].groupby("territory_id")
    }
    doc_hosp = np.empty(n_doc, dtype=object)
    standalone = rng.random(n_doc) < 0.15
    for i in range(n_doc):
        if standalone[i]:
            doc_hosp[i] = None
            continue
        pool = hosp_by_terr.get(int(doc_terr[i]))
        doc_hosp[i] = int(rng.choice(pool)) if pool is not None and len(pool) else None
    dims["dim_doctor"] = pd.DataFrame({
        "doctor_id": np.arange(1, n_doc + 1),
        "hospital_id": doc_hosp,
        "territory_id": doc_terr,
        "doctor_name": _names(rng, first, last, n_doc, prefix="Dr. "),
        "specialty": doc_spec,
        "years_in_practice": yrs,
        "patient_panel_size": panel,
        "kol_flag": kol,
    })

    # --- dim_therapeutic_area ------------------------------------------------
    ta_names = list(ref.THERAPEUTIC_AREAS.keys())
    dims["dim_therapeutic_area"] = pd.DataFrame({
        "ta_id": np.arange(1, len(ta_names) + 1),
        "ta_name": ta_names,
        "seasonality_profile": [ref.THERAPEUTIC_AREAS[t] for t in ta_names],
    })
    ta_id_by_name = dict(zip(ta_names, range(1, len(ta_names) + 1)))

    # --- dim_product ---------------------------------------------------------
    prod = pd.DataFrame(ref.PRODUCTS, columns=[
        "brand_name", "molecule", "ta_name", "dosage_form",
        "unit_price", "cost_per_unit", "launch_date", "lifecycle_stage", "_base_size"])
    prod.insert(0, "product_id", np.arange(1, len(prod) + 1))
    prod["ta_id"] = prod["ta_name"].map(ta_id_by_name)
    prod["launch_date"] = pd.to_datetime(prod["launch_date"]).dt.date
    dims["dim_product"] = prod

    # --- dim_competitor_product ---------------------------------------------
    comp = pd.DataFrame(ref.COMPETITORS, columns=[
        "competitor_brand", "company", "ta_name", "unit_price"])
    comp.insert(0, "competitor_product_id", np.arange(1, len(comp) + 1))
    comp["ta_id"] = comp["ta_name"].map(ta_id_by_name)
    dims["dim_competitor_product"] = comp

    # --- dim_campaign --------------------------------------------------------
    channels = list(ref.MARKETING_CHANNELS.keys())
    rows = []
    cid = 1
    for _, p in prod.iterrows():
        # each product promoted through 3 channels chosen by promo weight
        pw = np.array([ref.MARKETING_CHANNELS[c]["promo_weight"] for c in channels])
        chosen = rng.choice(channels, size=3, replace=False, p=pw / pw.sum())
        for ch in chosen:
            # flight window: some campaigns run the full horizon, some partial
            if rng.random() < 0.6:
                s_idx, e_idx = 0, n_months - 1
            else:
                s_idx = int(rng.integers(0, n_months // 2))
                e_idx = int(rng.integers(s_idx + 6, n_months))
            rows.append({
                "campaign_id": cid,
                "product_id": int(p["product_id"]),
                "campaign_name": f"{p['brand_name']} - {ch}",
                "channel": ch,
                "objective": rng.choice(["Awareness", "Adoption", "Retention"]),
                "start_month_id": int(month_ids[s_idx]),
                "end_month_id": int(month_ids[e_idx]),
            })
            cid += 1
    dims["dim_campaign"] = pd.DataFrame(rows)

    return dims
