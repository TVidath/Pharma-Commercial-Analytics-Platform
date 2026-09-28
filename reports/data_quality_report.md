# Project Catalyst — Data Quality & Plausibility Report

**Generated:** 2026-09-29  ·  **Dataset:** synthetic, seed=42  ·  **Horizon:** 2023-07 → 2026-06 (36 months)

**Overall status: ✅ PASS**  ·  Structural 10/10 · Plausibility 2/2 · Planted-truth 6/6

This report certifies the generated dataset is (a) **structurally sound** — safe to load into PostgreSQL — and (b) **commercially plausible** — it reproduces the client's presenting symptom (flat revenue) and encodes the six diagnostic truths the engagement must recover. No truth is stated in any table; each is *emergent* and recovered here from raw facts.

---

## 1. Dataset overview

| Table | Rows |
|-------|-----:|
| dim_doctor | 1,500 |
| dim_hospital | 150 |
| dim_sales_rep | 50 |
| dim_product | 5 |
| fact_prescriptions | 170,352 |
| fact_competitor_rx | 91,764 |
| fact_sales_calls | 53,388 |
| fact_marketing_spend | 2,045 |

Reconciled annual revenue: **₹ 1,449 Cr** (target ₹ 1,450 Cr).

---

## 2. Structural integrity (hard gates)

Referential integrity, grain uniqueness, constraint and null checks. Any failure blocks database load.

| Check | Result | Value | Target |
|-------|--------|-------|--------|
| Referential integrity (all FKs) | ✅ PASS | OK | — |
| Grain uniqueness fact_prescriptions | ✅ PASS | 0 | 0 |
| Grain uniqueness fact_competitor_rx | ✅ PASS | 0 | 0 |
| Grain uniqueness fact_sales_calls | ✅ PASS | 0 | 0 |
| Grain uniqueness fact_marketing_spend | ✅ PASS | 0 | 0 |
| conversions <= leads | ✅ PASS | OK | — |
| calls_made <= calls_planned + 2 | ✅ PASS | OK | — |
| No negative units/revenue | ✅ PASS | OK | — |
| Entity counts match brief | ✅ PASS | 1500/150/50 | — |
| No nulls in fact keys/measures | ✅ PASS | 0 | 0 |

---

## 3. Business plausibility

Does the data behave like a real commercial P&L?

| Check | Result | Value | Target |
|-------|--------|-------|--------|
| Revenue reconciliation | ✅ PASS | Rs 1,449 Cr | Rs 1,450 Cr (+/-5%) |
| Marketing spend as % of revenue | ✅ PASS | 9.0% | 6-12% |

---

## 4. Planted-truth recovery (the diagnostic contract)

Each row is a commercial truth deliberately engineered into the generative model and independently **recovered** here from the raw fact tables. This validates that the synthetic data is analytically sound.

| Check | Result | Value | Target |
|-------|--------|-------|--------|
| P1 Effort chases volume, not potential | ✅ PASS | corr(calls,Rx)=0.75, corr(calls,panel)=0.59 | Rx-corr>0.55 and gap>0.15 |
| P2 Diminishing returns on calls | ✅ PASS | low-decile=3076.0 vs high-decile=2407.8 | — |
| P3 Under-served high-potential territories | ✅ PASS | 10 territories | >=3 |
| P4 Portfolio stagnation masks brand divergence | ✅ PASS | portfolio=-4.8%, Lipivas=-30.7%, growth=+47.5% | — |
| P5 Spend skewed to low-ROI channel | ✅ PASS | Print ROI=0.59@34% budget, Digital ROI=3.02 | — |
| P6 Localized competitive erosion | ✅ PASS | pressured 44.5%->33.1%, rest 55.4%->55.4% | — |

---

## 5. What this proves

- **P1** is the engagement's smoking gun: sales effort tracks *current* prescribing far more than *potential*, so high-potential/low-volume doctors are under-served — a quantifiable white space.
- **P4** explains the paradox in the boardroom: the portfolio looks flat only because a declining mature brand masks strong growth brands.
- **P5** explains "rising spend, flat sales": the largest marketing budget sits in the lowest-ROI channel.
- **P3 / P6** localise the problem — specific under-served territories and specific zones losing share — so the fix is targeted, not blanket.

The diagnostic modules (Milestones 3–6) will now *rediscover* these from the database and quantify the prize in rupees.
