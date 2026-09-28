#!/usr/bin/env python
"""Run revenue forecasting + Commercial Opportunity Score (Modules 13, 14).

Usage:
    python scripts/run_forecast_scoring.py [--db]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from catalyst.scoring.report import build_report, persist_to_db  # noqa: E402
from catalyst.utils.config import load_config  # noqa: E402
from catalyst.utils.logging import get_logger  # noqa: E402

logger = get_logger("catalyst.forecast_scoring")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", action="store_true", help="load score tables into PostgreSQL")
    args = ap.parse_args()
    doc, terr = build_report()
    if args.db:
        persist_to_db(doc, terr, load_config())
    logger.info("Done → reports/forecast_and_scoring_report.md")


if __name__ == "__main__":
    main()
