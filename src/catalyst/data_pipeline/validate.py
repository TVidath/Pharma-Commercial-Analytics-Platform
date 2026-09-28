"""Data-quality & plausibility validation.

Two tiers of checks:

* **Structural** — hard fails: FK integrity, grain uniqueness, constraint
  violations, nulls, row-count sanity. If any fail, the dataset is not fit to
  load.
* **Plausibility / planted-truth** — business sanity: revenue reconciliation,
  flat portfolio growth, and recovery of the six planted commercial truths
  (P1-P6). These prove the data tells the intended story.

``run_all`` returns a structured result consumed by the report generator and
the pytest suite.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..data_generation.reference_data import (
    MARGIN_PER_CONVERSION, PRESSURED_TAS, PRESSURED_ZONES)
from ..utils.paths import DATA_RAW

CRORE = 1e7


@dataclass
class Check:
    name: str
    category: str            # 'structural' | 'plausibility' | 'planted'
    passed: bool
    detail: str
    value: Optional[str] = None
    target: Optional[str] = None


@dataclass
class ValidationResult:
    checks: List[Check] = field(default_factory=list)

    def add(self, **kw) -> None:
        self.checks.append(Check(**kw))

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks if c.category == "structural")

    def by_category(self, cat: str) -> List[Check]:
        return [c for c in self.checks if c.category == cat]


TABLE_FILES = [
    "dim_month", "dim_zone", "dim_region", "dim_regional_manager",
    "dim_territory", "dim_sales_rep", "dim_hospital", "dim_doctor",
    "dim_therapeutic_area", "dim_product", "dim_competitor_product",
    "dim_campaign", "fact_prescriptions", "fact_competitor_rx",
    "fact_sales_calls", "fact_marketing_spend",
]


def load_tables(data_dir=DATA_RAW) -> Dict[str, pd.DataFrame]:
    """Load all table CSVs from ``data_dir`` into a dict of DataFrames."""
    return {t: pd.read_csv(data_dir / f"{t}.csv") for t in TABLE_FILES}


# ---------------------------------------------------------------------------
# Structural checks
# ---------------------------------------------------------------------------
def _fk_ok(child: pd.DataFrame, col: str, parent: pd.DataFrame, pcol: str) -> bool:
    return bool(child[col].dropna().isin(parent[pcol]).all())


def structural_checks(t: Dict[str, pd.DataFrame], res: ValidationResult) -> None:
    fks = [
        ("fact_prescriptions", "doctor_id", "dim_doctor", "doctor_id"),
        ("fact_prescriptions", "product_id", "dim_product", "product_id"),
        ("fact_prescriptions", "month_id", "dim_month", "month_id"),
        ("fact_competitor_rx", "doctor_id", "dim_doctor", "doctor_id"),
        ("fact_competitor_rx", "ta_id", "dim_therapeutic_area", "ta_id"),
        ("fact_sales_calls", "rep_id", "dim_sales_rep", "rep_id"),
        ("fact_sales_calls", "doctor_id", "dim_doctor", "doctor_id"),
        ("fact_marketing_spend", "campaign_id", "dim_campaign", "campaign_id"),
        ("fact_marketing_spend", "region_id", "dim_region", "region_id"),
        ("dim_doctor", "territory_id", "dim_territory", "territory_id"),
        ("dim_sales_rep", "territory_id", "dim_territory", "territory_id"),
    ]
    all_ok = True
    for c, col, p, pcol in fks:
        ok = _fk_ok(t[c], col, t[p], pcol)
        all_ok &= ok
        if not ok:
            res.add(name=f"FK {c}.{col} -> {p}.{pcol}", category="structural",
                    passed=False, detail="orphan foreign keys found")
    res.add(name="Referential integrity (all FKs)", category="structural",
            passed=all_ok, detail=f"{len(fks)} foreign-key relationships checked",
            value="OK" if all_ok else "FAIL")

    # grain uniqueness
    grains = {
        "fact_prescriptions": ["doctor_id", "product_id", "month_id"],
        "fact_competitor_rx": ["doctor_id", "ta_id", "month_id"],
        "fact_sales_calls": ["rep_id", "doctor_id", "month_id"],
        "fact_marketing_spend": ["campaign_id", "region_id", "month_id"],
    }
    for tbl, keys in grains.items():
        dup = int(t[tbl].duplicated(keys).sum())
        res.add(name=f"Grain uniqueness {tbl}", category="structural",
                passed=dup == 0, detail=f"duplicate rows on {keys}", value=str(dup),
                target="0")

    # constraint checks
    mkt = t["fact_marketing_spend"]
    res.add(name="conversions <= leads", category="structural",
            passed=bool((mkt["conversions"] <= mkt["leads"]).all()),
            detail="marketing funnel integrity", value="OK")
    calls = t["fact_sales_calls"]
    res.add(name="calls_made <= calls_planned + 2", category="structural",
            passed=bool((calls["calls_made"] <= calls["calls_planned"] + 2).all()),
            detail="call adherence bound", value="OK")
    rx = t["fact_prescriptions"]
    res.add(name="No negative units/revenue", category="structural",
            passed=bool((rx["units_prescribed"] >= 0).all() and (rx["revenue"] >= 0).all()),
            detail="non-negativity", value="OK")

    # entity counts
    counts_ok = (len(t["dim_doctor"]) == 1500 and len(t["dim_hospital"]) == 150
                 and len(t["dim_sales_rep"]) == 50)
    res.add(name="Entity counts match brief", category="structural", passed=counts_ok,
            detail="doctors=1500, hospitals=150, reps=50",
            value=f"{len(t['dim_doctor'])}/{len(t['dim_hospital'])}/{len(t['dim_sales_rep'])}")

    # null checks on key columns
    nulls = int(rx[["doctor_id", "product_id", "month_id", "units_prescribed"]].isna().sum().sum())
    res.add(name="No nulls in fact keys/measures", category="structural",
            passed=nulls == 0, detail="fact_prescriptions", value=str(nulls), target="0")


# ---------------------------------------------------------------------------
# Plausibility + planted-truth checks
# ---------------------------------------------------------------------------
def _doc_geo(t: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """doctor_id -> region/zone/ta helpers."""
    doc = t["dim_doctor"][["doctor_id", "territory_id", "patient_panel_size"]]
    terr = t["dim_territory"][["territory_id", "region_id"]]
    reg = t["dim_region"][["region_id", "zone_id"]]
    zone = t["dim_zone"]
    g = (doc.merge(terr, on="territory_id").merge(reg, on="region_id").merge(zone, on="zone_id"))
    return g


def plausibility_checks(t, cfg, res: ValidationResult) -> None:
    rx = t["fact_prescriptions"]
    hist_years = cfg["time"]["history_months"] / 12.0
    target = float(cfg["data_logic"]["target_annual_revenue_inr_cr"])
    annual = rx["revenue"].sum() / CRORE / hist_years
    dev = abs(annual - target) / target * 100
    res.add(name="Revenue reconciliation", category="plausibility",
            passed=dev <= 5.0, detail="annual revenue vs target",
            value=f"Rs {annual:,.0f} Cr", target=f"Rs {target:,.0f} Cr (+/-5%)")

    mkt_pct = t["fact_marketing_spend"]["spend"].sum() / rx["revenue"].sum() * 100
    res.add(name="Marketing spend as % of revenue", category="plausibility",
            passed=6.0 <= mkt_pct <= 12.0, detail="promotional intensity",
            value=f"{mkt_pct:.1f}%", target="6-12%")


def planted_truth_checks(t, cfg, res: ValidationResult) -> None:
    rx, calls, comp = t["fact_prescriptions"], t["fact_sales_calls"], t["fact_competitor_rx"]
    prod, month = t["dim_product"], t["dim_month"]

    # --- P1: effort chases current Rx more than potential(panel) -------------
    d = t["dim_doctor"][["doctor_id", "patient_panel_size"]].set_index("doctor_id")
    d["rx"] = rx.groupby("doctor_id")["units_prescribed"].sum().reindex(d.index).fillna(0)
    d["calls"] = calls.groupby("doctor_id")["calls_made"].sum().reindex(d.index).fillna(0)
    c_rx = d["calls"].corr(d["rx"])
    c_pot = d["calls"].corr(d["patient_panel_size"])
    res.add(name="P1 Effort chases volume, not potential", category="planted",
            passed=(c_rx > 0.55) and (c_rx > c_pot + 0.15),
            detail="corr(calls, current Rx) high AND > corr(calls, panel)",
            value=f"corr(calls,Rx)={c_rx:.2f}, corr(calls,panel)={c_pot:.2f}",
            target="Rx-corr>0.55 and gap>0.15")

    # --- P2: diminishing returns (low-call Rx/call > high-call Rx/call) ------
    d["dec"] = pd.qcut(d["calls"].rank(method="first"), 10, labels=False) + 1
    _g = d.groupby("dec").agg(rx=("rx", "sum"), calls=("calls", "sum"))
    rpc = _g["rx"] / _g["calls"].clip(lower=1)
    res.add(name="P2 Diminishing returns on calls", category="planted",
            passed=rpc.loc[1:3].mean() > rpc.loc[8:10].mean(),
            detail="Rx-per-call higher at low call intensity than high",
            value=f"low-decile={rpc.loc[1:3].mean():.1f} vs high-decile={rpc.loc[8:10].mean():.1f}")

    # --- P3: under-served high-potential territories -------------------------
    g = _doc_geo(t)
    tpot = g.groupby("territory_id")["patient_panel_size"].sum()
    tdoc = g.groupby("territory_id").size()
    tcalls = (calls.merge(t["dim_doctor"][["doctor_id", "territory_id"]], on="doctor_id")
              .groupby("territory_id")["calls_made"].sum())
    cov = (tcalls / tdoc)
    hi_pot = tpot > tpot.median()
    lo_cov = cov < cov.quantile(0.25)
    underserved = int((hi_pot & lo_cov).sum())
    res.add(name="P3 Under-served high-potential territories", category="planted",
            passed=underserved >= 3,
            detail="territories in top-half potential but bottom-quartile coverage",
            value=f"{underserved} territories", target=">=3")

    # --- P4: portfolio flat, decline brands down, growth brands up -----------
    rxm = rx.merge(prod[["product_id", "brand_name", "lifecycle_stage"]], on="product_id")
    f12 = month.sort_values("month_id")["month_id"].head(12).tolist()
    l12 = month.sort_values("month_id")["month_id"].tail(12).tolist()

    def yoy(df):
        a = df[df.month_id.isin(f12)]["revenue"].sum()
        b = df[df.month_id.isin(l12)]["revenue"].sum()
        return (b - a) / a * 100 if a else np.nan

    port = yoy(rxm)
    lip = yoy(rxm[rxm.brand_name == "Lipivas"])
    grow = yoy(rxm[rxm.lifecycle_stage == "Growth"])
    res.add(name="P4 Portfolio stagnation masks brand divergence", category="planted",
            passed=(-8 < port < 4) and (lip < -10) and (grow > 15),
            detail="flat total; decline hero down; growth brands up",
            value=f"portfolio={port:+.1f}%, Lipivas={lip:+.1f}%, growth={grow:+.1f}%")

    # --- P5: marketing ROI ladder (Print<1<Digital) -------------------------
    mc = t["fact_marketing_spend"].merge(t["dim_campaign"][["campaign_id", "channel"]], on="campaign_id")
    _mg = mc.groupby("channel").agg(conv=("conversions", "sum"), spend=("spend", "sum"))
    roi = _mg["conv"] * MARGIN_PER_CONVERSION / _mg["spend"]
    print_roi = roi.get("Print & Conferences", np.nan)
    digi_roi = roi.get("Digital & CME", np.nan)
    budget = mc.groupby("channel")["spend"].sum()
    print_share = budget.get("Print & Conferences", 0) / budget.sum() * 100
    res.add(name="P5 Spend skewed to low-ROI channel", category="planted",
            passed=(print_roi < 1.0) and (digi_roi > 2.0) and (print_share > 25),
            detail="over-funded Print (low ROI) vs under-funded Digital (high ROI)",
            value=f"Print ROI={print_roi:.2f}@{print_share:.0f}% budget, Digital ROI={digi_roi:.2f}")

    # --- P6: localized competitive erosion ----------------------------------
    rx_ta = (rx.merge(prod[["product_id", "ta_id"]], on="product_id")
             .groupby(["doctor_id", "ta_id", "month_id"])["units_prescribed"].sum()
             .rename("our").reset_index())
    sh = rx_ta.merge(comp, on=["doctor_id", "ta_id", "month_id"], how="left")
    sh["competitor_units"] = sh["competitor_units"].fillna(0)
    sh = (sh.merge(t["dim_doctor"][["doctor_id", "territory_id"]], on="doctor_id")
            .merge(t["dim_territory"][["territory_id", "region_id"]], on="territory_id")
            .merge(t["dim_region"][["region_id", "zone_id"]], on="region_id")
            .merge(t["dim_zone"], on="zone_id")
            .merge(t["dim_therapeutic_area"][["ta_id", "ta_name"]], on="ta_id"))
    sh["pressured"] = sh["zone_name"].isin(PRESSURED_ZONES) & sh["ta_name"].isin(PRESSURED_TAS)
    f6 = month.sort_values("month_id")["month_id"].head(6).tolist()
    l6 = month.sort_values("month_id")["month_id"].tail(6).tolist()

    def share(df, mids):
        s = df[df.month_id.isin(mids)]
        tot = s["our"].sum() + s["competitor_units"].sum()
        return s["our"].sum() / tot * 100 if tot else np.nan

    p_first, p_last = share(sh[sh.pressured], f6), share(sh[sh.pressured], l6)
    r_first, r_last = share(sh[~sh.pressured], f6), share(sh[~sh.pressured], l6)
    res.add(name="P6 Localized competitive erosion", category="planted",
            passed=(p_last < p_first - 5) and (abs(r_last - r_first) < 3),
            detail="share falls in pressured zones/TAs, stable elsewhere",
            value=f"pressured {p_first:.1f}%->{p_last:.1f}%, rest {r_first:.1f}%->{r_last:.1f}%")


def run_all(tables: Dict[str, pd.DataFrame], cfg: Dict) -> ValidationResult:
    res = ValidationResult()
    structural_checks(tables, res)
    plausibility_checks(tables, cfg, res)
    planted_truth_checks(tables, cfg, res)
    return res
