"""Database engine factory.

Credentials come from environment variables (never committed); connection
coordinates come from ``config/engagement_config.yaml``. Defaults match the
bundled docker-compose Postgres so a fresh clone works out of the box.
"""
from __future__ import annotations

import os
from typing import Any, Dict

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def db_url(cfg: Dict[str, Any]) -> str:
    d = cfg["database"]
    user = os.environ.get("CATALYST_DB_USER", "catalyst")
    pwd = os.environ.get("CATALYST_DB_PASSWORD", "catalyst")
    host = os.environ.get("CATALYST_DB_HOST", d.get("host", "localhost"))
    port = os.environ.get("CATALYST_DB_PORT", str(d.get("port", 5432)))
    name = d.get("dbname", "catalyst")
    return f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{name}"


def get_engine(cfg: Dict[str, Any]) -> Engine:
    """Return a SQLAlchemy engine for the configured Postgres database."""
    return create_engine(db_url(cfg), future=True)
