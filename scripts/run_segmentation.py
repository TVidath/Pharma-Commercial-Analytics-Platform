#!/usr/bin/env python
"""Run doctor & hospital segmentation: report, figures, CSVs, (optional) DB load.

Usage:
    python scripts/run_segmentation.py [--db]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from catalyst.segmentation.report import build_report, persist_to_db  # noqa: E402
from catalyst.utils.config import load_config  # noqa: E402
from catalyst.utils.logging import get_logger  # noqa: E402

logger = get_logger("catalyst.segmentation")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", action="store_true", help="also load segment tables into PostgreSQL")
    args = ap.parse_args()

    doc, hosp = build_report()
    if args.db:
        logger.info("Loading segment tables into PostgreSQL ...")
        persist_to_db(doc, hosp, load_config())
    logger.info("Segmentation complete → reports/segmentation_report.md")


if __name__ == "__main__":
    main()
