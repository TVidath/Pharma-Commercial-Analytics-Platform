# Pharma Sales & Incentive Analytics — Project Flow

> **A student data engineering project building a Python ETL pipeline to generate and load synthetic pharmaceutical data into a PostgreSQL database, visualized using Power BI and Streamlit.**

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture Layers](#2-architecture-layers)
3. [Technology Stack](#3-technology-stack)
4. [Configuration](#4-configuration)
5. [Execution Pipeline — End-to-End Flow](#5-execution-pipeline--end-to-end-flow)
6. [Data Model — Dimensional Schema](#6-data-model--dimensional-schema)
7. [SQL Semantic Layer](#7-sql-semantic-layer)
8. [Testing](#8-testing)
9. [Repository Structure](#9-repository-structure)
10. [Quickstart Commands](#10-quickstart-commands)
11. [Output Artifacts](#11-output-artifacts)

---

## 1. Project Overview

This project builds a robust data engineering and analytics pipeline for a simulated pharmaceutical company operating across India — 50 sales reps, 5 regions, 1,500 doctors, 150 hospitals, and 5 product brands.

**What this project covers:**
- Python-based ETL pipeline generating ~500,000 rows of relational data
- Automated data cleaning, validation, and quality reporting
- PostgreSQL dimensional data model (star schema) 
- Custom SQL stored procedures for business logic (e.g., sales incentives calculations)
- Interactive Streamlit dashboard for business insights and exploratory data analysis
- End-to-end automation via Makefile and pytest testing

---

## 2. Architecture Layers

```text
┌─────────────────────────────────────────────────────────────────┐
│  PRESENTATION LAYER                                             │
│  Streamlit dashboard (3 pages) · Power BI                       │
├─────────────────────────────────────────────────────────────────┤
│  ANALYTICS LAYER                                                │
│  Exploratory Data Analysis (EDA) · KPIs                         │
├─────────────────────────────────────────────────────────────────┤
│  STORAGE LAYER                                                  │
│  PostgreSQL (catalyst schema) · Dimensional model               │
│  Views · Stored procedures (Incentive Calculation)              │
├─────────────────────────────────────────────────────────────────┤
│  FOUNDATION LAYER                                               │
│  Python ETL pipeline (~500,000 rows)                            │
│  Data cleaning · Validation · Data Quality Report               │
└─────────────────────────────────────────────────────────────────┘
                            ▲
            config/engagement_config.yaml drives the pipeline
```

---

## 3. Technology Stack

| Layer | Technology |
|-------|-----------|
| Core | Python 3.9+, Pandas, NumPy, PyYAML |
| Database | PostgreSQL 15+ (Docker), SQLAlchemy, psycopg2 |
| Visualization | Matplotlib, Seaborn, Plotly |
| Dashboard | Streamlit 1.30+, Power BI |
| Testing | pytest 7.4+ |
| Infrastructure | Docker Compose, Makefile |

---

## 4. Configuration

**File:** `config/engagement_config.yaml`

All parameters flow from this single YAML file, defining the scale of the generated synthetic data.
- 50 sales reps
- 1,500 doctors
- 150 hospitals

---

## 5. Execution Pipeline — End-to-End Flow

### Phase 1: Data Generation
**Command:** `make generate` → `python scripts/generate_data.py`
- Builds all dimensions (zones, regions, reps, doctors, hospitals, products).
- Generates 4 fact tables (`fact_prescriptions`, `fact_competitor_rx`, `fact_sales_calls`, `fact_marketing_spend`) totaling ~500,000 rows.
- **Output:** `data/raw/*.csv` (16 files)

### Phase 2: Data Pipeline — Cleaning & Validation
**Command:** `make validate` → `python scripts/validate_data.py`
- Cleans data types and enforces schema standards.
- Runs structural validation (grain uniqueness, referential integrity).
- **Output:** `data/processed/*.csv` (16 cleaned files) + `reports/data_quality_report.md`

### Phase 3: Database Build — PostgreSQL Load
**Command:** `make db-up` then `make db-load` → `python scripts/load_to_postgres.py`
- Creates PostgreSQL schema (`catalyst`).
- Bulk loads all processed CSV files.
- Builds views and custom stored procedures (including `sp_calculate_rep_incentives`).

### Phase 4: Diagnostic Analytics — EDA
**Command:** `make eda` → `python scripts/run_eda.py`
- Generates charts covering revenue trends, product portfolio, and marketing spend.
- **Output:** `reports/eda_report.md` + charts in `reports/figures/`

### Phase 5: Executive Dashboard
**Command:** `make dashboard`
- `prepare_dashboard.py` precomputes aggregate CSVs.
- `streamlit run dashboard/streamlit/app.py` launches a 3-page interactive dashboard (Overview, Regional, Product).

---

## 6. Data Model — Dimensional Schema

**Dimension Tables (12)**
- `dim_month`, `dim_zone`, `dim_region`, `dim_regional_manager`, `dim_territory`, `dim_sales_rep`, `dim_hospital`, `dim_doctor`, `dim_therapeutic_area`, `dim_product`, `dim_competitor_product`, `dim_campaign`

**Fact Tables (4)**
- `fact_prescriptions`: doctor × product × month 
- `fact_competitor_rx`: doctor × TA × month 
- `fact_sales_calls`: rep × doctor × month 
- `fact_marketing_spend`: campaign × region × month

---

## 7. SQL Semantic Layer

### Views (`sql/views/01_kpi_views.sql`)
- Pre-aggregated views for dashboard consumption and Power BI.

### Stored Procedures (`sql/procedures/`)
- `sp_calculate_rep_incentives.sql` — Calculates tiered percentage bonuses based on a representative's total prescription revenue.
- Other targeting and territory summary procedures.

---

## 8. Testing

**Command:** `make test` → `pytest tests/ -q`
- `test_data_pipeline.py`: Tests data generation, row counts, and data validation rules.
- `test_analytics.py`: Tests EDA report generation.

---

## 9. Repository Structure

```text
pharma-commercial-analytics-main/
│
├── config/             # Pipeline configuration (engagement_config.yaml)
├── src/catalyst/       # Core python module (data_generation, pipeline, utils)
├── scripts/            # CLI entry points (generate, validate, load, dashboard prep)
├── sql/                # Schema, views, and custom stored procedures
├── dashboard/          # Streamlit app and Power BI notes
├── data/               # raw → processed → dashboard (auto-generated)
├── notebooks/          # EDA diagnostic notebook
├── reports/            # Data-quality report, EDA report, figures
├── tests/              # pytest suite
├── docs/               # Architecture, ERD, data dictionary
├── docker-compose.yml  # PostgreSQL container config
├── Makefile            # Build automation
└── requirements.txt    # Python dependencies
```

---

## 10. Quickstart Commands

```bash
make setup              # Create venv + install dependencies
make build              # Generate ~500k rows + validate + DQ report
make db-up              # Start PostgreSQL (Docker)
make db-load            # Schema, bulk-load, views & procedures
make eda                # Diagnostic EDA report + figures
make dashboard          # Launch Streamlit dashboard
make test               # Run pytest tests
make clean              # Remove generated data artifacts
```

---

## 11. Output Artifacts

| Artifact | Created By | Content |
|----------|-----------|---------|
| `data/raw/*.csv` | `make generate` | Raw unvalidated CSVs |
| `data/processed/*.csv` | `make validate` | Cleaned and validated data for DB load |
| `reports/data_quality_report.md` | `make validate` | Validation results, foreign key integrity |
| `reports/eda_report.md` | `make eda` | Exploratory data analysis with charts |
| `data/processed/dashboard/*.csv` | `prepare_dashboard.py` | Light-weight pre-aggregated tables for Streamlit |

---
*All data is synthetic and privacy-safe.*
