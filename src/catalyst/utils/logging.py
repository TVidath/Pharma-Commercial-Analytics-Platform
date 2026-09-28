"""Single configured logger for the whole package.

Use ``get_logger(__name__)`` everywhere; never ``print``.
"""
from __future__ import annotations

import logging
import sys

_CONFIGURED = False
_FMT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATEFMT = "%H:%M:%S"


def get_logger(name: str = "catalyst", level: str = "INFO") -> logging.Logger:
    """Return a package logger, configuring the root handler once."""
    global _CONFIGURED
    if not _CONFIGURED:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_FMT, datefmt=_DATEFMT))
        root = logging.getLogger("catalyst")
        root.addHandler(handler)
        root.setLevel(level)
        root.propagate = False
        _CONFIGURED = True
    logger = logging.getLogger(name if name.startswith("catalyst") else f"catalyst.{name}")
    return logger
