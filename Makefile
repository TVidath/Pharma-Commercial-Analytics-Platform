# Project Catalyst — developer entry points
# Usage: make <target>
PY ?= ./.venv/bin/python
PIP ?= ./.venv/bin/pip

.PHONY: help setup generate validate build eda segment performance score optimize dashboard db-up db-down db-load test clean

help:            ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	 awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup:           ## Create venv and install dependencies
	python3 -m venv .venv && $(PIP) install -q --upgrade pip && $(PIP) install -q -r requirements.txt

generate:        ## Generate synthetic data -> data/raw/
	$(PY) scripts/generate_data.py

validate:        ## Clean + validate + write data-quality report
	$(PY) scripts/validate_data.py

eda:             ## Generate the diagnostic EDA report + figures
	$(PY) scripts/run_eda.py

segment:         ## Run doctor & hospital segmentation (add ARGS=--db to load tables)
	$(PY) scripts/run_segmentation.py $(ARGS)

performance:     ## Run opportunity & performance diagnostics (report + register)
	$(PY) scripts/run_performance.py

score:           ## Run revenue forecast + Commercial Opportunity Score (ARGS=--db to load)
	$(PY) scripts/run_forecast_scoring.py $(ARGS)

optimize:        ## Run territory & sales-force optimization (ARGS=--db to load)
	$(PY) scripts/run_optimization.py $(ARGS)

dashboard:       ## Prepare aggregates and launch the Streamlit dashboard
	$(PY) scripts/prepare_dashboard.py && ./.venv/bin/streamlit run dashboard/streamlit/app.py

build:           ## Generate + validate (no DB)
	./scripts/build_all.sh

db-up:           ## Start PostgreSQL (Docker)
	docker compose up -d

db-down:         ## Stop PostgreSQL (add ARGS=-v to wipe data)
	docker compose down $(ARGS)

db-load:         ## Create schema, load data, build views & procedures
	$(PY) scripts/load_to_postgres.py

test:            ## Run the test suite
	$(PY) -m pytest tests/ -q

clean:           ## Remove generated data artifacts
	rm -f data/raw/*.csv data/processed/*.csv
