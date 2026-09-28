#!/usr/bin/env bash
# Project Catalyst — one-command, reproducible build of the data foundation.
#   1. generate synthetic data          -> data/raw/
#   2. clean + validate + DQ report      -> data/processed/, reports/
#   3. (optional) load into PostgreSQL   -> requires a running DB
#
# Usage:
#   ./scripts/build_all.sh          # generate + validate
#   ./scripts/build_all.sh --db     # also load into PostgreSQL
set -euo pipefail

cd "$(dirname "$0")/.."
PY="${PYTHON:-./.venv/bin/python}"

echo "==> [1/3] Generating synthetic data ..."
"$PY" scripts/generate_data.py

echo "==> [2/3] Cleaning, validating, and writing DQ report ..."
"$PY" scripts/validate_data.py

if [[ "${1:-}" == "--db" ]]; then
  echo "==> [3/3] Loading into PostgreSQL ..."
  "$PY" scripts/load_to_postgres.py
else
  echo "==> [3/3] Skipping DB load (pass --db to enable; needs 'docker compose up -d')."
fi

echo "==> Done."
