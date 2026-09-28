"""Pytest configuration: make the src package importable and share fixtures."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from catalyst.data_generation.engine import build_all  # noqa: E402
from catalyst.utils.config import load_config  # noqa: E402


@pytest.fixture(scope="session")
def small_cfg():
    """A scaled-down config for fast, deterministic engine tests."""
    cfg = load_config()
    cfg["entities"].update(dict(doctors=1200, hospitals=120, sales_reps=50,
                                territories=50, regional_managers=25))
    cfg["time"]["history_months"] = 24  # full TTM + prior-year windows for tests
    return cfg


@pytest.fixture(scope="session")
def small_tables(small_cfg):
    """Full table set built once from the scaled-down config."""
    return build_all(small_cfg)


@pytest.fixture(scope="session")
def processed_dir():
    """Path to full processed data if it has been generated, else None."""
    p = ROOT / "data" / "processed"
    return p if (p / "fact_prescriptions.csv").exists() else None
