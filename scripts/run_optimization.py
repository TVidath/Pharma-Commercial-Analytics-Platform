#!/usr/bin/env python
"""Run territory & sales-force optimization (Modules 9, 15).

Usage:
    python scripts/run_optimization.py [--db]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from catalyst.optimization.report import build_report, persist_to_db  # noqa: E402
from catalyst.utils.config import load_config  # noqa: E402
from catalyst.utils.logging import get_logger  # noqa: E402

logger = get_logger("catalyst.optimization")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", action="store_true", help="load plan tables into PostgreSQL")
    args = ap.parse_args()
    plan = build_report()
    if args.db:
        persist_to_db(plan, load_config())
    s = plan["summary"]
    logger.info("Reallocated %s calls (%.0f%%); new reps recommended: %d",
                f"{s['reallocated_calls']:,}", s["reallocated_pct"], s["new_reps"])
    logger.info("Done → reports/optimization_report.md")


if __name__ == "__main__":
    main()
