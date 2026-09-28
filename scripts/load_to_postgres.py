#!/usr/bin/env python
"""Create the schema and load data/processed into PostgreSQL.

Prerequisite: a running Postgres (e.g. `docker compose up -d`).
Credentials come from env (see .env.example); defaults match docker-compose.

Usage:
    python scripts/load_to_postgres.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import text  # noqa: E402

from catalyst.data_pipeline.load import load_all  # noqa: E402
from catalyst.utils.config import load_config  # noqa: E402
from catalyst.utils.db import get_engine  # noqa: E402
from catalyst.utils.logging import get_logger  # noqa: E402

logger = get_logger("catalyst.load")


def main() -> None:
    cfg = load_config()
    # fail fast with a clear message if the DB is unreachable
    try:
        with get_engine(cfg).connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        logger.error("Cannot reach PostgreSQL. Is it running? (`docker compose up -d`)")
        logger.error("Details: %s", exc)
        sys.exit(2)

    load_all(cfg)
    logger.info("Verifying with a KPI query ...")
    with get_engine(cfg).connect() as conn:
        rows = conn.execute(text(
            "SELECT channel, roi, budget_share_pct FROM catalyst.vw_marketing_roi "
            "ORDER BY roi")).fetchall()
        for r in rows:
            logger.info("  %-22s ROI=%.2f  budget=%.1f%%", r[0], r[1], r[2])


if __name__ == "__main__":
    main()
