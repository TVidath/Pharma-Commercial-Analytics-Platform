"""Generate the four fact tables from dimensions + latent drivers.

This module is where the planted business truths become data:

* **P1/P2** — call effort is allocated on a 0.72/0.28 blend of *current volume*
  vs *potential*, and prescriptions respond to calls through a saturating
  (diminishing-returns) curve, so over-called loyalists gain little.
* **P3** — under-invested territories get their call capacity cut.
* **P4** — product lifecycle trends make one declining brand drag the total.
* **P5** — marketing budget is skewed to a low-ROI channel.
* **P6** — competitor share rises over time in two pressured zones/TAs.
"""
from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
import pandas as pd

from . import reference_data as ref
from .rng import make_rng, minmax


# ---------------------------------------------------------------------------
# Shape functions (vectorised)
# ---------------------------------------------------------------------------
def _lifecycle_factor(stage: np.ndarray, t_frac: np.ndarray,
                      months_since_launch: np.ndarray) -> np.ndarray:
    """Multiplicative trend by lifecycle stage over the horizon."""
    f = np.ones_like(t_frac, dtype=float)
    decline = stage == "Decline"
    mature = stage == "Mature"
    growth = stage == "Growth"
    launch = stage == "Launch"
    f = np.where(decline, 1.25 - 0.45 * t_frac, f)
    f = np.where(mature, 1.02 - 0.04 * t_frac, f)
    f = np.where(growth, 0.70 + 0.65 * t_frac, f)
    # launch: logistic ramp on months since launch; 0 before launch
    logistic = 1.5 / (1.0 + np.exp(-0.18 * (months_since_launch - 10.0)))
    f = np.where(launch, np.where(months_since_launch < 0, 0.0, logistic), f)
    return f


def _seasonality(profile: np.ndarray, month_num: np.ndarray) -> np.ndarray:
    """Seasonal multiplier by TA profile and calendar month."""
    ang = (month_num - 1) / 12.0 * 2 * np.pi
    winter = 1.0 + 0.30 * np.cos(ang)                    # peaks in Jan
    summer = 1.0 + 0.25 * np.cos((month_num - 7) / 12.0 * 2 * np.pi)  # peaks in Jul
    out = np.ones_like(month_num, dtype=float)
    out = np.where(profile == "Winter-peak", winter, out)
    out = np.where(profile == "Summer-peak", summer, out)
    return out


def _comp_share(zone_name: np.ndarray, ta_name: np.ndarray, t_frac: np.ndarray) -> np.ndarray:
    """Competitor share of market; escalates in pressured zones/TAs (P6)."""
    pressured = np.isin(zone_name, ref.PRESSURED_ZONES) & np.isin(ta_name, ref.PRESSURED_TAS)
    return np.where(pressured, 0.55 + 0.13 * t_frac, 0.45)


# ---------------------------------------------------------------------------
# Calls
# ---------------------------------------------------------------------------
def _generate_calls(cfg, dims, latents, month_ids) -> Tuple[pd.DataFrame, np.ndarray]:
    """Return (fact_sales_calls, calls_made matrix [n_doc x n_months])."""
    rng = make_rng(int(cfg["random_seed"]) + 11)
    dl = cfg["data_logic"]
    w_cur = float(dl["effort_to_current_rx_corr"])   # 0.72
    w_pot = float(dl["effort_to_potential_corr"])    # 0.28
    n_months = len(month_ids)

    L = latents.copy()
    # what reps observe/chase: realised baseline volume (potential x adoption x
    # product-mix scale), NOT raw capacity -> effort tracks current Rx (P1)
    L["current_vol"] = (0.20 + L["potential"]) * L["adoption"] * L["_elig_base_sum"]

    # z-score priority drivers within each rep's panel
    def _z(s):
        sd = s.std()
        return (s - s.mean()) / sd if sd > 1e-9 else s * 0.0
    grp = L.groupby("rep_id")
    z_cur = grp["current_vol"].transform(_z)
    z_pot = grp["potential"].transform(_z)
    priority = w_cur * z_cur + w_pot * z_pot
    weight = np.exp(priority.to_numpy())
    L["_w"] = weight
    L["_wshare"] = grp_share = L.groupby("rep_id")["_w"].transform(lambda x: x / x.sum())

    rep = dims["dim_sales_rep"].set_index("rep_id")
    target = rep.loc[L["rep_id"], "monthly_call_target"].to_numpy(dtype=float)
    status = rep.loc[L["rep_id"], "employment_status"].to_numpy()
    exp_years = rep.loc[L["rep_id"], "experience_years"].to_numpy(dtype=float)

    planned = target * L["_wshare"].to_numpy()
    planned = np.where(L["_underinvested"].to_numpy(), planned * 0.5, planned)  # P3
    planned = np.where(status == "Vacant", 0.0, planned)
    planned = np.where(status == "On-Leave", planned * 0.5, planned)
    planned = np.clip(planned, 0.0, 6.0)

    # monthly adherence: rep-tenure mean + doctor-month noise
    mean_adh = np.clip(0.72 + 0.012 * exp_years, 0.5, 0.96)
    adh = np.clip(mean_adh[:, None] + rng.normal(0, 0.12, (len(L), n_months)), 0.0, 1.2)
    calls_made = np.rint(planned[:, None] * adh).astype(int)
    calls_planned_row = np.rint(planned).astype(int)

    # build long fact only for doctors with a real plan (>=1 planned call)
    active = calls_planned_row >= 1
    doc_ids = L["doctor_id"].to_numpy()
    rep_ids = L["rep_id"].to_numpy()
    rows = []
    act_idx = np.where(active)[0]
    for j, mid in enumerate(month_ids):
        cm = calls_made[act_idx, j]
        rows.append(pd.DataFrame({
            "rep_id": rep_ids[act_idx],
            "doctor_id": doc_ids[act_idx],
            "month_id": mid,
            "calls_planned": calls_planned_row[act_idx],
            "calls_made": cm,
            "samples_dropped": rng.poisson(np.maximum(cm, 0) * 0.6),
        }))
    calls_df = pd.concat(rows, ignore_index=True)
    calls_df = calls_df[calls_df["calls_planned"] > 0].reset_index(drop=True)
    return calls_df, calls_made


# ---------------------------------------------------------------------------
# Marketing
# ---------------------------------------------------------------------------
def _generate_marketing(cfg, dims, latents, month_ids, mpos) -> Tuple[pd.DataFrame, np.ndarray]:
    """Return (fact_marketing_spend, intensity array [n_prod+1, n_region+1, n_months])."""
    rng = make_rng(int(cfg["random_seed"]) + 13)
    hist_years = cfg["time"]["history_months"] / 12.0
    total_budget = 0.09 * float(cfg["data_logic"]["target_annual_revenue_inr_cr"]) * 1e7 * hist_years

    camp = dims["dim_campaign"]
    n_regions = len(dims["dim_region"])
    n_prod = len(dims["dim_product"])
    n_months = len(month_ids)

    # region spend weight ~ number of doctors per region
    reg_w = latents.groupby("region_id").size().reindex(
        range(1, n_regions + 1), fill_value=1).to_numpy(dtype=float)
    reg_w = reg_w / reg_w.sum()

    # split channel budget equally across that channel's campaigns
    ch_counts = camp["channel"].value_counts().to_dict()

    rows = []
    for _, c in camp.iterrows():
        ch = c["channel"]
        econ = ref.MARKETING_CHANNELS[ch]
        camp_budget = total_budget * econ["budget_share"] / ch_counts[ch]
        s, e = mpos[c["start_month_id"]], mpos[c["end_month_id"]]
        flight = np.arange(s, e + 1)
        # monthly weights (mild ramp/noise), region weights
        mw = np.clip(rng.normal(1.0, 0.2, len(flight)), 0.3, None)
        mw = mw / mw.sum()
        for mi, mwt in zip(flight, mw):
            spend_vec = camp_budget * mwt * reg_w * np.clip(rng.normal(1.0, 0.15, n_regions), 0.4, None)
            leads = spend_vec / 1000.0 * econ["lead_rate"] * np.clip(rng.normal(1.0, 0.15, n_regions), 0.3, None)
            leads_i = np.rint(leads).astype(int)
            conv_i = np.minimum(leads_i, np.rint(leads * econ["conv_rate"]).astype(int))
            rows.append(pd.DataFrame({
                "campaign_id": int(c["campaign_id"]),
                "product_id": int(c["product_id"]),
                "region_id": np.arange(1, n_regions + 1),
                "month_id": int(month_ids[mi]),
                "spend": np.round(spend_vec, 2),
                "leads": leads_i,
                "conversions": conv_i,
            }))
    mkt = pd.concat(rows, ignore_index=True)
    # collapse to grain (campaign, region, month) — a channel/product may repeat
    mkt = (mkt.groupby(["campaign_id", "product_id", "region_id", "month_id"], as_index=False)
              .agg(spend=("spend", "sum"), leads=("leads", "sum"), conversions=("conversions", "sum")))

    # intensity array by (product, region, month) for prescription lift
    intensity = np.zeros((n_prod + 1, n_regions + 1, n_months))
    agg = mkt.groupby(["product_id", "region_id", "month_id"])["spend"].sum().reset_index()
    for _, r in agg.iterrows():
        intensity[int(r["product_id"]), int(r["region_id"]), mpos[int(r["month_id"])]] += r["spend"]
    flat = intensity.reshape(-1)
    intensity = minmax(flat).reshape(intensity.shape)
    return mkt, intensity


# ---------------------------------------------------------------------------
# Prescriptions + competitor
# ---------------------------------------------------------------------------
def _generate_prescriptions(cfg, dims, latents, calls_made, mkt_intensity,
                            month_ids, mpos) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = make_rng(int(cfg["random_seed"]) + 17)
    k = float(cfg["data_logic"]["call_response_saturation_k"])
    n_months = len(month_ids)

    prod = dims["dim_product"].set_index("brand_name")
    prod_by_id = dims["dim_product"].set_index("product_id")
    ta_name_by_id = dims["dim_therapeutic_area"].set_index("ta_id")["ta_name"].to_dict()

    # month feature arrays indexed by position
    m_num = dims["dim_month"].set_index("month_id").loc[month_ids, "month_num"].to_numpy()
    m_year = dims["dim_month"].set_index("month_id").loc[month_ids, "year"].to_numpy()
    t_frac_pos = np.arange(n_months) / (n_months - 1)

    # doctor-indexed arrays (position = doctor_id - 1)
    L = latents.set_index("doctor_id").sort_index()
    pot = L["potential"].to_numpy()
    adop = L["adoption"].to_numpy()
    region_of = L["region_id"].to_numpy()
    zone_name_of = L["zone_name"].to_numpy()

    blocks = []
    for spec, brands in ref.SPECIALTY_PRODUCTS.items():
        doc_ids = latents.loc[latents["specialty"] == spec, "doctor_id"].to_numpy()
        if len(doc_ids) == 0:
            continue
        D = len(doc_ids)
        prod_ids = prod.loc[brands, "product_id"].to_numpy()
        K = len(prod_ids)
        di = doc_ids - 1  # 0-based

        # flattened (doctor, product, month) with ordering d -> k -> m
        doc_col = np.repeat(doc_ids, K * n_months)
        di_col = np.repeat(di, K * n_months)
        prod_col = np.tile(np.repeat(prod_ids, n_months), D)
        mpos_col = np.tile(np.arange(n_months), D * K)

        # per (doctor, product) brand preference, repeated over months
        brand_pref = rng.uniform(0.55, 1.45, D * K)
        brand_pref_col = np.repeat(brand_pref, n_months)

        # gather product attributes
        p_base = prod_by_id.loc[prod_col, "_base_size"].to_numpy()
        p_price = prod_by_id.loc[prod_col, "unit_price"].to_numpy(dtype=float)
        p_stage = prod_by_id.loc[prod_col, "lifecycle_stage"].to_numpy()
        p_taid = prod_by_id.loc[prod_col, "ta_id"].to_numpy()
        p_launch = prod_by_id.loc[prod_col, "launch_date"].to_numpy()
        ta_names = np.array([ta_name_by_id[t] for t in p_taid], dtype=object)
        seas_prof = np.array([ref.THERAPEUTIC_AREAS[t] for t in ta_names], dtype=object)

        # months since launch
        launch_ym = np.array([d.year * 12 + (d.month - 1) for d in pd.to_datetime(p_launch)])
        cur_ym = m_year[mpos_col] * 12 + (m_num[mpos_col] - 1)
        msl = cur_ym - launch_ym

        t_frac = t_frac_pos[mpos_col]
        life = _lifecycle_factor(p_stage, t_frac, msl)
        seas = _seasonality(seas_prof, m_num[mpos_col])

        # ceiling capacity (pre global calibration)
        cap = (0.20 + pot[di_col]) * p_base * brand_pref_col
        ceiling = cap * life * seas

        # realised fraction = adoption closed toward 1 by call response (saturating)
        cm = calls_made[di_col, mpos_col]
        promo = 1.0 - np.exp(-k * cm)
        realized = np.minimum(1.0, adop[di_col] + (1.0 - adop[di_col]) * promo)

        # competitor drag on our units in pressured zones (P6)
        zname = zone_name_of[di_col]
        cs = _comp_share(zname, ta_names, t_frac)
        our_drag = np.clip(1.0 - (cs - 0.45), 0.55, 1.0)

        # marketing lift
        reg = region_of[di_col]
        mlift = 1.0 + 0.08 * mkt_intensity[prod_col, reg, mpos_col]

        units_cont = ceiling * realized * our_drag * mlift
        blocks.append({
            "doctor_id": doc_col, "product_id": prod_col,
            "month_pos": mpos_col, "ta_id": p_taid, "region_id": reg,
            "zone_name": zname, "t_frac": t_frac,
            "units_cont": units_cont, "price": p_price,
        })

    # global calibration to hit revenue target
    total_rev_cont = sum((b["units_cont"] * b["price"]).sum() for b in blocks)
    hist_years = cfg["time"]["history_months"] / 12.0
    target_total = float(cfg["data_logic"]["target_annual_revenue_inr_cr"]) * 1e7 * hist_years
    scale = target_total / total_rev_cont

    # assemble prescriptions
    parts = []
    for b in blocks:
        noise = rng.lognormal(mean=-0.045, sigma=0.30, size=len(b["units_cont"]))
        units = np.rint(b["units_cont"] * scale * noise).astype(int)
        mask = units > 0
        parts.append(pd.DataFrame({
            "doctor_id": b["doctor_id"][mask],
            "product_id": b["product_id"][mask],
            "month_id": np.asarray(month_ids)[b["month_pos"][mask]],
            "ta_id": b["ta_id"][mask],
            "region_id": b["region_id"][mask],
            "zone_name": b["zone_name"][mask],
            "t_frac": b["t_frac"][mask],
            "units": units[mask],
            "revenue": np.round(units[mask] * b["price"][mask], 2),
        }))
    rx = pd.concat(parts, ignore_index=True)
    rx["new_patient_count"] = rng.poisson(np.maximum(rx["units"].to_numpy(), 0) * 0.08)

    fact_rx = rx[["doctor_id", "product_id", "month_id", "units", "revenue", "new_patient_count"]].rename(
        columns={"units": "units_prescribed"})

    # --- competitor fact from our TA-level volume + planted share ------------
    ta_agg = rx.groupby(["doctor_id", "ta_id", "month_id"], as_index=False).agg(
        our_units=("units", "sum"),
        zone_name=("zone_name", "first"),
        t_frac=("t_frac", "first"))
    ta_agg["ta_name"] = ta_agg["ta_id"].map(ta_name_by_id)
    cs = _comp_share(ta_agg["zone_name"].to_numpy(), ta_agg["ta_name"].to_numpy(),
                     ta_agg["t_frac"].to_numpy())
    ratio = cs / (1.0 - cs)
    comp_noise = rng.lognormal(mean=-0.06, sigma=0.30, size=len(ta_agg))
    comp_units = np.rint(ta_agg["our_units"].to_numpy() * ratio * comp_noise).astype(int)
    fact_comp = pd.DataFrame({
        "doctor_id": ta_agg["doctor_id"].to_numpy(),
        "ta_id": ta_agg["ta_id"].to_numpy(),
        "month_id": ta_agg["month_id"].to_numpy(),
        "competitor_units": np.maximum(comp_units, 0),
    })
    return fact_rx, fact_comp


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def build_facts(cfg, dims, latents) -> Dict[str, pd.DataFrame]:
    """Build all fact tables; returns dict keyed by table name."""
    month_ids = dims["dim_month"]["month_id"].to_numpy()
    mpos = {int(m): i for i, m in enumerate(month_ids)}

    calls_df, calls_made = _generate_calls(cfg, dims, latents, month_ids)
    mkt_df, mkt_intensity = _generate_marketing(cfg, dims, latents, month_ids, mpos)
    rx_df, comp_df = _generate_prescriptions(cfg, dims, latents, calls_made,
                                             mkt_intensity, month_ids, mpos)
    return {
        "fact_prescriptions": rx_df,
        "fact_competitor_rx": comp_df,
        "fact_sales_calls": calls_df,
        "fact_marketing_spend": mkt_df,
    }
