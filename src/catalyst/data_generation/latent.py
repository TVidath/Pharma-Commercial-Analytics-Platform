"""Latent-variable model for doctors.

Two hidden drivers govern the whole simulation:

* **potential** (0-1): a doctor's structural prescribing capacity, driven by
  panel size and KOL status. This is what the diagnostic must *infer* — it is
  never observed directly.
* **adoption** (0-1): how much of that potential is currently realised as
  baseline prescribing of our brands, before any promotional push. Adoption is
  correlated with potential but deliberately *decoupled* for two groups —
  competitor-loyal doctors and doctors in under-invested territories — which is
  what creates recoverable white space (planted truths P1-P3).
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from . import reference_data as ref
from .rng import make_rng, minmax


def compute_doctor_latents(cfg: Dict, dims: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Return a per-doctor frame with latent potential/adoption and org keys."""
    rng = make_rng(int(cfg["random_seed"]) + 7)
    doc = dims["dim_doctor"]
    terr = dims["dim_territory"].set_index("territory_id")
    region = dims["dim_region"].set_index("region_id")

    # --- potential: panel-driven capacity, with KOL uplift -------------------
    potential_raw = doc["patient_panel_size"].to_numpy(dtype=float) * (
        1.0 + 0.15 * doc["kol_flag"].to_numpy(dtype=float))
    potential = minmax(potential_raw)

    # --- org keys per doctor -------------------------------------------------
    region_id = terr.loc[doc["territory_id"], "region_id"].to_numpy()
    zone_id = region.loc[region_id, "zone_id"].to_numpy()
    zone_name = dims["dim_zone"].set_index("zone_id").loc[zone_id, "zone_name"].to_numpy()
    underinvested = terr.loc[doc["territory_id"], "_is_underinvested"].to_numpy()
    rep_id = terr.loc[doc["territory_id"], "rep_id"].to_numpy()

    # --- adoption: correlated with potential + independent noise -------------
    noise = rng.beta(2.0, 2.0, len(doc))          # centred, bounded (0,1)
    adoption = 0.45 * potential + 0.55 * noise

    # decouple for competitor-loyal doctors (~18%) -> low baseline adoption
    comp_loyal = rng.random(len(doc)) < 0.18
    adoption = np.where(comp_loyal, adoption * 0.45, adoption)

    # under-invested territories: historically under-exposed -> lower adoption
    adoption = np.where(underinvested, adoption * 0.60, adoption)

    adoption = np.clip(adoption, 0.02, 0.95)

    # eligible-product base weight per specialty (captures product-mix scale),
    # so the "current volume" proxy that drives call allocation tracks realised
    # prescribing rather than raw panel size.
    brand_base = {p[0]: p[8] for p in ref.PRODUCTS}
    spec_base_sum = {s: float(sum(brand_base[b] for b in brands))
                     for s, brands in ref.SPECIALTY_PRODUCTS.items()}
    elig_base_sum = doc["specialty"].map(spec_base_sum).to_numpy(dtype=float)

    return pd.DataFrame({
        "doctor_id": doc["doctor_id"].to_numpy(),
        "territory_id": doc["territory_id"].to_numpy(),
        "rep_id": rep_id,
        "region_id": region_id,
        "zone_id": zone_id,
        "zone_name": zone_name,
        "specialty": doc["specialty"].to_numpy(),
        "potential": potential,
        "adoption": adoption,
        "_elig_base_sum": elig_base_sum,
        "_underinvested": underinvested,
        "_comp_loyal": comp_loyal,
    })
