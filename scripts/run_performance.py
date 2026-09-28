#!/usr/bin/env python
"""Run the opportunity & performance diagnostics (Modules 8, 10, 11, 12).

Usage:
    python scripts/run_performance.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from catalyst.analytics.performance import build_report  # noqa: E402
from catalyst.utils.logging import get_logger  # noqa: E402

logger = get_logger("catalyst.performance")

if __name__ == "__main__":
    reg = build_report()
    logger.info("Performance diagnostics complete → reports/performance_report.md")
    logger.info("Opportunity register:\n%s", reg.to_string(index=False))
