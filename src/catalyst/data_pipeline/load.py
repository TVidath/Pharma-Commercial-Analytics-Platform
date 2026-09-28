"""Load processed CSVs into PostgreSQL.

Strategy: create tables -> bulk-COPY facts (fast) -> build indexes -> create
views & stored procedures -> ANALYZE. Serial primary keys are auto-generated,
so COPY targets the explicit schema column list.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from sqlalchemy import text
from sqlalchemy.engine import Engine

from ..data_generation.engine import LOAD_ORDER, SCHEMA_COLUMNS
from ..utils.db import get_engine
from ..utils.logging import get_logger
from ..utils.paths import (DATA_PROCESSED, SQL_PROCEDURES, SQL_SCHEMA, SQL_VIEWS)

logger = get_logger(__name__)
SCHEMA = "catalyst"


def run_sql_file(engine: Engine, path: Path) -> None:
    """Execute a .sql file as a single script.

    Uses the raw DBAPI cursor (not SQLAlchemy text execution) so that literal
    ``%`` characters in PL/pgSQL bodies (e.g. RAISE NOTICE '... %') are not
    misread as bind-parameter placeholders.
    """
    sql = path.read_text(encoding="utf-8")
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute(sql)
        raw.commit()
        cur.close()
    finally:
        raw.close()
    logger.info("  ran %s", path.name)


def _copy_on_cursor(cur, name: str, csv_path: Path) -> None:
    """COPY one CSV into its table using an existing cursor."""
    cols = ", ".join(SCHEMA_COLUMNS[name])
    with open(csv_path, "r", encoding="utf-8") as fh:
        cur.copy_expert(
            f"COPY {SCHEMA}.{name} ({cols}) FROM STDIN WITH (FORMAT csv, HEADER true)",
            fh,
        )


def _bulk_load(engine: Engine, data_dir: Path) -> None:
    """Load every table in a single transaction (deferred cyclic FKs)."""
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute(f"SET search_path TO {SCHEMA}")
        cur.execute("SET CONSTRAINTS ALL DEFERRED")
        for name in LOAD_ORDER:
            _copy_on_cursor(cur, name, data_dir / f"{name}.csv")
        raw.commit()
        for name in LOAD_ORDER:
            cur.execute(f"SELECT count(*) FROM {SCHEMA}.{name}")
            logger.info("  loaded %-24s %10d rows", name, cur.fetchone()[0])
        cur.close()
    finally:
        raw.close()


def load_all(cfg: Dict, data_dir=DATA_PROCESSED) -> None:
    """End-to-end database build: schema -> data -> indexes -> views -> procs."""
    engine = get_engine(cfg)
    logger.info("Creating schema & tables ...")
    run_sql_file(engine, SQL_SCHEMA / "01_create_tables.sql")

    logger.info("Bulk-loading tables (COPY, single transaction) ...")
    _bulk_load(engine, data_dir)

    logger.info("Building indexes ...")
    run_sql_file(engine, SQL_SCHEMA / "02_indexes_constraints.sql")

    for folder, label in ((SQL_VIEWS, "views"), (SQL_PROCEDURES, "procedures")):
        for f in sorted(folder.glob("*.sql")):
            run_sql_file(engine, f)
        logger.info("Created %s", label)

    logger.info("Running ANALYZE ...")
    with engine.begin() as conn:
        for tbl in ("fact_prescriptions", "fact_competitor_rx",
                    "fact_sales_calls", "fact_marketing_spend"):
            conn.exec_driver_sql(f"ANALYZE {SCHEMA}.{tbl}")
    logger.info("Database build complete.")
