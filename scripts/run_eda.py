#!/usr/bin/env python
"""Generate the diagnostic EDA report and figures.

Usage:
    python scripts/run_eda.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from catalyst.analytics.eda import build_report  # noqa: E402
from catalyst.utils.logging import get_logger  # noqa: E402

logger = get_logger("catalyst.eda")

if __name__ == "__main__":
    build_report()
    logger.info("EDA complete → reports/eda_report.md")
