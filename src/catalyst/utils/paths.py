"""Canonical filesystem paths for the engagement.

All modules resolve locations through this module so no path is ever
hard-coded elsewhere.
"""
from __future__ import annotations

from pathlib import Path

# src/catalyst/utils/paths.py -> parents[3] == project root
PROJECT_ROOT: Path = Path(__file__).resolve().parents[3]

CONFIG_DIR: Path = PROJECT_ROOT / "config"
DATA_DIR: Path = PROJECT_ROOT / "data"
DATA_RAW: Path = DATA_DIR / "raw"
DATA_PROCESSED: Path = DATA_DIR / "processed"
DATA_EXTERNAL: Path = DATA_DIR / "external"
SQL_DIR: Path = PROJECT_ROOT / "sql"
SQL_SCHEMA: Path = SQL_DIR / "schema"
SQL_VIEWS: Path = SQL_DIR / "views"
SQL_PROCEDURES: Path = SQL_DIR / "procedures"
REPORTS_DIR: Path = PROJECT_ROOT / "reports"

DEFAULT_CONFIG_PATH: Path = CONFIG_DIR / "engagement_config.yaml"


def ensure_dir(path: Path) -> Path:
    """Create ``path`` (and parents) if missing; return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path
