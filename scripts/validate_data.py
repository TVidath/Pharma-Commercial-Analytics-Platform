#!/usr/bin/env python
"""Clean data/raw -> data/processed, validate it, and write the DQ report.

Usage:
    python scripts/validate_data.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from catalyst.data_pipeline.clean import clean_all  # noqa: E402
from catalyst.data_pipeline.validate import load_tables, run_all  # noqa: E402
from catalyst.utils.config import load_config  # noqa: E402
from catalyst.utils.logging import get_logger  # noqa: E402
from catalyst.utils.paths import DATA_PROCESSED, REPORTS_DIR, ensure_dir  # noqa: E402

logger = get_logger("catalyst.validate")
CRORE = 1e7


def _status(ok: bool) -> str:
    return "✅ PASS" if ok else "❌ FAIL"


def _table(checks) -> str:
    rows = ["| Check | Result | Value | Target |", "|-------|--------|-------|--------|"]
    for c in checks:
        rows.append(f"| {c.name} | {_status(c.passed)} | {c.value or c.detail} | {c.target or '—'} |")
    return "\n".join(rows)


def write_report(res, tables, cfg) -> Path:
    rx = tables["fact_prescriptions"]
    annual = rx["revenue"].sum() / CRORE / (cfg["time"]["history_months"] / 12.0)
    n_struct = res.by_category("structural")
    n_plaus = res.by_category("plausibility")
    n_plant = res.by_category("planted")
    all_pass = all(c.passed for c in res.checks)

    overview = "\n".join(
        f"| {t} | {len(tables[t]):,} |" for t in [
            "dim_doctor", "dim_hospital", "dim_sales_rep", "dim_product",
            "fact_prescriptions", "fact_competitor_rx", "fact_sales_calls",
            "fact_marketing_spend"])

    md = f"""# Pharma Commercial Analytics Platform — Data Quality & Plausibility Report

**Generated:** {date.today().isoformat()}  ·  **Dataset:** synthetic, seed={cfg['random_seed']}  ·  **Horizon:** {cfg['time']['period_start']} → {cfg['time']['period_end']} ({cfg['time']['history_months']} months)

**Overall status: {_status(all_pass)}**  ·  Structural {sum(c.passed for c in n_struct)}/{len(n_struct)} · Plausibility {sum(c.passed for c in n_plaus)}/{len(n_plaus)} · Planted-truth {sum(c.passed for c in n_plant)}/{len(n_plant)}

This report certifies the generated dataset is (a) **structurally sound** — safe to load into PostgreSQL — and (b) **commercially plausible** — it reproduces the client's presenting symptom (flat revenue) and encodes the six diagnostic truths the engagement must recover. No truth is stated in any table; each is *emergent* and recovered here from raw facts.

---

## 1. Dataset overview

| Table | Rows |
|-------|-----:|
{overview}

Reconciled annual revenue: **₹ {annual:,.0f} Cr** (target ₹ {cfg['data_logic']['target_annual_revenue_inr_cr']:,} Cr).

---

## 2. Structural integrity (hard gates)

Referential integrity, grain uniqueness, constraint and null checks. Any failure blocks database load.

{_table(n_struct)}

---

## 3. Business plausibility

Does the data behave like a real commercial P&L?

{_table(n_plaus)}

---

## 4. Planted-truth recovery (the diagnostic contract)

Each row is a commercial truth deliberately engineered into the generative model and independently **recovered** here from the raw fact tables. This validates that the synthetic data is analytically sound.

{_table(n_plant)}

---

## 5. What this proves

- **P1** is the engagement's smoking gun: sales effort tracks *current* prescribing far more than *potential*, so high-potential/low-volume doctors are under-served — a quantifiable white space.
- **P4** explains the paradox in the boardroom: the portfolio looks flat only because a declining mature brand masks strong growth brands.
- **P5** explains "rising spend, flat sales": the largest marketing budget sits in the lowest-ROI channel.
- **P3 / P6** localise the problem — specific under-served territories and specific zones losing share — so the fix is targeted, not blanket.

The diagnostic modules (Milestones 3–6) will now *rediscover* these from the database and quantify the prize in rupees.
"""
    ensure_dir(REPORTS_DIR)
    out = REPORTS_DIR / "data_quality_report.md"
    out.write_text(md, encoding="utf-8")
    return out


def main() -> None:
    cfg = load_config()
    logger.info("Cleaning raw -> processed ...")
    clean_all()
    logger.info("Validating ...")
    tables = load_tables(DATA_PROCESSED)
    res = run_all(tables, cfg)
    out = write_report(res, tables, cfg)

    for c in res.checks:
        logger.info("  [%-11s] %s %s", c.category, "PASS" if c.passed else "FAIL", c.name)
    logger.info("Report written to %s", out)
    if not all(c.passed for c in res.checks):
        logger.warning("Some checks FAILED — review the report.")
        sys.exit(1)
    logger.info("All checks passed.")


if __name__ == "__main__":
    main()
