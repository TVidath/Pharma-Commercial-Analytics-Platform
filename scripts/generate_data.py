#!/usr/bin/env python
"""Generate the full synthetic dataset and write schema-clean CSVs to data/raw.

Usage:
    python scripts/generate_data.py [--config PATH]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from catalyst.data_generation import build_all, write_raw  # noqa: E402
from catalyst.utils.config import load_config  # noqa: E402
from catalyst.utils.logging import get_logger  # noqa: E402

logger = get_logger("catalyst.generate")


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate Pharma Commercial Analytics Platform synthetic data")
    ap.add_argument("--config", default=None, help="path to engagement_config.yaml")
    args = ap.parse_args()

    t0 = time.time()
    cfg = load_config(args.config)
    logger.info("Seed=%s | doctors=%s | history_months=%s",
                cfg["random_seed"], cfg["entities"]["doctors"], cfg["time"]["history_months"])
    tables = build_all(cfg)
    write_raw(tables)
    logger.info("Done in %.1fs. CSVs in data/raw/", time.time() - t0)


if __name__ == "__main__":
    main()
