# Project Catalyst — Complete Project Flow

> **Pharma Commercial Analytics & Sales-Force Effectiveness Platform**
> End-to-end data analytics pipeline for a simulated pharmaceutical company

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Business Problem & Hypothesis](#2-business-problem--hypothesis)
3. [Architecture Layers](#3-architecture-layers)
4. [Technology Stack](#4-technology-stack)
5. [Configuration — Single Source of Truth](#5-configuration--single-source-of-truth)
6. [Execution Pipeline — End-to-End Flow](#6-execution-pipeline--end-to-end-flow)
   - [Phase 1: Data Generation](#phase-1-data-generation)
   - [Phase 2: Data Pipeline (Cleaning & Validation)](#phase-2-data-pipeline--cleaning--validation)
   - [Phase 3: Database Build (PostgreSQL Load)](#phase-3-database-build--postgresql-load)
   - [Phase 4: Diagnostic Analytics (EDA)](#phase-4-diagnostic-analytics--eda)
   - [Phase 5: Customer Segmentation](#phase-5-customer-segmentation)
   - [Phase 6: Performance & Opportunity Diagnostics](#phase-6-performance--opportunity-diagnostics)
   - [Phase 7: Forecasting & Opportunity Scoring](#phase-7-forecasting--opportunity-scoring)
   - [Phase 8: Territory & Sales-Force Optimization](#phase-8-territory--sales-force-optimization)
   - [Phase 9: Executive Dashboard](#phase-9-executive-dashboard)
7. [Data Model — Dimensional Schema](#7-data-model--dimensional-schema)
8. [SQL Semantic Layer](#8-sql-semantic-layer)
9. [Module Dependency Graph](#9-module-dependency-graph)
10. [Testing](#10-testing)
11. [Repository Structure](#11-repository-structure)
12. [Quickstart Commands](#12-quickstart-commands)
13. [Output Artifacts](#13-output-artifacts)

---

## 1. Project Overview

**Project Catalyst** is a complete commercial analytics platform built for a simulated pharmaceutical company operating across India — 50 sales reps, 5 regions, 1,500 doctors, 150 hospitals, and 5 product brands across 2 therapeutic areas (Cardiology & Diabetology).

The platform diagnoses why the company has **stagnant revenue despite rising promotional spend**, and produces a data-driven reallocation strategy to capture growth at flat cost.

**What this project covers:**
- Synthetic data engine generating ~500,000 rows with embedded business patterns
- Full ETL pipeline: generation → cleaning → validation → PostgreSQL load
- Dimensional data model (star schema) with SQL KPI library
- Doctor segmentation (Potential × Value 9-box) and hospital tiering
- Prescription, regional, product, and marketing performance diagnostics
- Revenue forecasting (ETS model + intervention overlay)
- Commercial Opportunity Score — a transparent 0-100 doctor prioritisation index
- Territory optimization and capacity-neutral call reallocation
- 7-page interactive Streamlit executive dashboard
- Automated end-to-end via Makefile with pytest tests

---

## 2. Business Problem & Hypothesis

### The Problem
- 50 sales reps across 5 regions covering 1,500 doctors and 150 hospitals
- Revenue is stagnant despite rising promotional spend
- This is **not** a demand problem — it is an **allocation and effectiveness problem**

### Hypothesis
> A large share of effort is concentrated on saturated high-volume prescribers and mature products, while a quantifiable pool of growth-elastic doctors, hospitals and territories is under-served. Reallocating **15–25% of selling capacity** and re-weighting marketing can lift revenue **~8–12%** in 12–18 months at **flat cost**.

### Six Business Patterns in the Simulation

| # | Pattern | Config Parameter |
|---|---------|------------------|
| 1 | Sales effort tracks *current* Rx, not *potential* (effort is mis-allocated) | `effort_to_current_rx_corr: 0.72` vs `effort_to_potential_corr: 0.28` |
| 2 | Diminishing returns on call frequency (saturation curve) | `call_response_saturation_k: 0.35` |
| 3 | 1 under-invested territory has disproportionate white space | `underinvested_territory_count: 1` |
| 4 | A declining hero brand masks portfolio growth | `declining_hero_brand: "Lipivas"` |
| 5 | Marketing spend is skewed toward a low-ROI channel | `overfunded_low_roi_channel: "Print & Conferences"` |
| 6 | Specific zones are losing competitive share | Emergent from latent-variable model |

---

## 3. Architecture Layers

```
┌─────────────────────────────────────────────────────────────────┐
│  PRESENTATION LAYER                                             │
│  Streamlit dashboard (7 pages) · Power BI spec · Reports        │
├─────────────────────────────────────────────────────────────────┤
│  DECISION LAYER                                                 │
│  Opportunity scoring · Territory/salesforce optimization        │
├─────────────────────────────────────────────────────────────────┤
│  ANALYTICS LAYER                                                │
│  EDA · Segmentation (doctor 9-box + hospital tiers)             │
│  Rx opportunity · Performance diagnostics · Marketing mix       │
│  Forecasting (ETS + driver overlay)                             │
├─────────────────────────────────────────────────────────────────┤
│  STORAGE LAYER                                                  │
│  PostgreSQL (catalyst schema) · Dimensional model               │
│  Views · Stored procedures · KPI library                        │
├─────────────────────────────────────────────────────────────────┤
│  FOUNDATION LAYER                                               │
│  Synthetic data engine (~500,000 rows)                          │
│  ETL pipeline · Cleaning · Validation · Data Quality Report     │
└─────────────────────────────────────────────────────────────────┘
                            ▲
            config/engagement_config.yaml drives every layer
```

---

## 4. Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Language | Python 3.9+ | All analytics, generation, pipeline |
| Database | PostgreSQL 15+ (Docker) | Dimensional data warehouse |
| Core Data | NumPy, Pandas, PyYAML | Data manipulation & config |
| Database ORM | SQLAlchemy 2.0, psycopg2 | DB connectivity & bulk load |
| Analytics/ML | scikit-learn, statsmodels, scipy | Clustering validation, ETS forecasting |
| Visualization | Matplotlib, Seaborn, Plotly | Charts & figures |
| Dashboard | Streamlit 1.30+ | Interactive executive dashboard |
| Testing | pytest 7.4+ | Test suite |
| Containerization | Docker Compose | PostgreSQL provisioning |
| Build System | Makefile, Bash | Orchestration & developer UX |

---

## 5. Configuration — Single Source of Truth

**File:** `config/engagement_config.yaml`

All parameters flow from this single YAML file. No magic numbers exist in source code.

```
engagement_config.yaml
├── engagement:          # scope, currency (INR), FY start (April)
├── time:                # 36 months history (2023-07 → 2026-06), 12-month forecast
├── entities:            # scale: 2 zones, 5 regions, 50 reps, 1500 doctors, 150 hospitals, 5 products
├── random_seed: 42      # full reproducibility
├── database:            # PostgreSQL connection (catalyst schema, port 5432)
└── data_logic:          # business dynamics controlling the simulation
```

**How config flows through the system:**
1. `src/catalyst/utils/config.py` → `load_config()` reads the YAML
2. `src/catalyst/utils/paths.py` → canonical filesystem paths (never hard-coded)
3. Every module receives `cfg` dict as input — no module reads config independently
4. `build_calendar(cfg)` derives the 36-month calendar with fiscal year labels

---

## 6. Execution Pipeline — End-to-End Flow

### Phase 1: Data Generation
**Command:** `make generate` → `python scripts/generate_data.py`

```
Flow:
  load_config()
    │
    ├─► build_dimensions(cfg)                  [src/catalyst/data_generation/dimensions.py]
    │     Creates: dim_month, dim_zone, dim_region, dim_regional_manager,
    │              dim_territory, dim_sales_rep, dim_hospital, dim_doctor,
    │              dim_therapeutic_area, dim_product, dim_competitor_product, dim_campaign
    │     Scale: 2 zones, 5 regions, 50 territories/reps, 1.5K doctors, 150 hospitals
    │
    ├─► compute_doctor_latents(cfg, dims)      [src/catalyst/data_generation/latent.py]
    │     Two hidden drivers per doctor:
    │       • potential (0-1): structural prescribing capacity (panel × KOL uplift)
    │       • adoption (0-1): how much potential is currently realized
    │     Decouples adoption for:
    │       • Competitor-loyal doctors (~18%) → adoption × 0.45
    │       • Under-invested territories → adoption × 0.60
    │
    └─► build_facts(cfg, dims, latents)        [src/catalyst/data_generation/facts.py]
          Creates 4 fact tables (~500,000 rows total):
            • fact_prescriptions: doctor × product × month (revenue, units, new patients)
            • fact_competitor_rx: doctor × TA × month (competitor units)
            • fact_sales_calls: rep × doctor × month (calls planned/made, samples)
            • fact_marketing_spend: campaign × region × month (spend, leads, conversions)

  write_raw(tables) → 16 schema-clean CSVs to data/raw/
```

**Output:** `data/raw/*.csv` (16 CSV files, ~500k rows total)

---

### Phase 2: Data Pipeline — Cleaning & Validation
**Command:** `make validate` → `python scripts/validate_data.py`

```
Flow:
  clean_all()                                  [src/catalyst/data_pipeline/clean.py]
    │ For each of 16 tables (in FK-safe LOAD_ORDER):
    │   • Enforce boolean dtypes (is_forecast, kol_flag)
    │   • Coerce date columns (month_date, joining_date, launch_date)
    │   • Fix nullable integer FKs (Int64 for hospital_id)
    │   • Remove impossible negatives (revenue, units, spend ≥ 0)
    │   • De-duplicate on declared grain keys
    │   • Write cleaned CSV to data/processed/
    │
  load_tables() + run_all()                    [src/catalyst/data_pipeline/validate.py]
    │ Three categories of validation:
    │   a) Structural (hard gates): FK integrity, grain uniqueness, NOT NULL, range checks
    │   b) Plausibility: revenue reconciles, seasonality present
    │   c) Business-pattern recovery: validates the embedded patterns are recoverable
    │
  write_report() → reports/data_quality_report.md
```

**Output:** `data/processed/*.csv` (16 cleaned files) + `reports/data_quality_report.md`

---

### Phase 3: Database Build — PostgreSQL Load
**Command:** `make db-up` then `make db-load` → `python scripts/load_to_postgres.py`

```
Flow:
  docker compose up -d → PostgreSQL 15 container (catalyst_pg, port 5432)

  load_all(cfg)                                [src/catalyst/data_pipeline/load.py]
    ├─► Execute sql/schema/01_create_tables.sql (16 tables, PK/FK/CHECK constraints)
    ├─► Bulk COPY all 16 CSVs (single transaction, deferred FK constraints)
    ├─► Execute sql/schema/02_indexes_constraints.sql (composite indexes)
    ├─► Build KPI views (sql/views/01_kpi_views.sql)
    ├─► Build stored procedures (sql/procedures/01_procedures.sql)
    └─► ANALYZE on all fact tables
```

**Output:** Fully loaded PostgreSQL database with schema, data, views, procedures

---

### Phase 4: Diagnostic Analytics — EDA
**Command:** `make eda` → `python scripts/run_eda.py`

```
Flow:
  build_report()                               [src/catalyst/analytics/eda.py]
    └─► Generates 10 diagnostic charts + reports/eda_report.md:
          01. Revenue trend (monthly, YoY)
          02. Revenue by zone
          03. Revenue by therapeutic area
          04. Product portfolio (growth vs size bubble)
          05. Top 20 doctors by revenue
          06. Call activity heatmap (rep utilization)
          07. Prescription concentration (Pareto/Lorenz)
          08. Marketing spend by channel
          09. Seasonality decomposition
          10. Competitive share trend
```

**Output:** `reports/eda_report.md` + `reports/figures/01_*` through `10_*`

---

### Phase 5: Customer Segmentation
**Command:** `make segment` → `python scripts/run_segmentation.py`

```
Flow:
  segment_doctors(tables, ttm_months)          [src/catalyst/segmentation/doctors.py]
    │
    ├─► Transparent potential score (0-100):
    │     0.40 × panel_size + 0.20 × specialty_economics
    │   + 0.20 × hospital_potential + 0.10 × urbanicity + 0.10 × KOL_status
    │
    ├─► Potential × Value 9-Box segments
    ├─► White space value (₹) per doctor
    │
    └─► K-Means validation (k=4): ARI + Silhouette Score

  segment_hospitals(tables, doc_seg)           [src/catalyst/segmentation/hospitals.py]
    └─► Tiers: Platinum (top 10%) → Gold → Silver → Bronze (bottom 30%)
```

**Output:** `reports/segmentation_report.md` + `data/processed/doctor_segments.csv` + `data/processed/hospital_segments.csv`

---

### Phase 6: Performance & Opportunity Diagnostics
**Command:** `make performance` → `python scripts/run_performance.py`

```
Flow:
  build_report()                               [src/catalyst/analytics/performance.py]
    │
    ├─► Prescription opportunity analysis (doctor-level Rx gaps, white space ₹)
    ├─► Regional & market performance (TTM revenue, growth, share per region)
    ├─► Product portfolio diagnostics (growth vs margin, lifecycle stages)
    ├─► Marketing effectiveness (channel ROI, budget share)
    │
    └─► Builds the Opportunity Register (₹ Cr)
```

**Output:** `reports/performance_report.md` + `data/processed/opportunity_register.csv`

---

### Phase 7: Forecasting & Opportunity Scoring
**Command:** `make score` → `python scripts/run_forecast_scoring.py`

```
Flow:
  build_forecast()                             [src/catalyst/forecasting/forecast.py]
    ├─► ETS model (additive trend + seasonal, 12-period): mean + 80% prediction interval
    └─► Intervention overlay: phased capture ramp of opportunity register

  compute_scores()                             [src/catalyst/scoring/opportunity_score.py]
    │  Commercial Opportunity Score (0-100):
    │    Score = 0.30 × Potential + 0.30 × Headroom + 0.15 × Momentum
    │          + 0.15 × Accessibility + 0.10 × Competitive
    │
    └─► Priority tiers: P1 (top 20%) | P2 (50-80%) | P3 (bottom 50%)

  territory_scores() → aggregate to territory level
```

**Output:** `reports/forecast_and_scoring_report.md` + `data/processed/doctor_opportunity_score.csv` + `data/processed/territory_opportunity_score.csv`

---

### Phase 8: Territory & Sales-Force Optimization
**Command:** `make optimize` → `python scripts/run_optimization.py`

```
Flow:
  build_plan()                                 [src/catalyst/optimization/optimize.py]
    │
    ├─► Ideal call plan: P1=18/yr, P2=9/yr, P3=3/yr
    │
    ├─► Capacity-neutral reallocation:
    │     rec_calls = current_capacity × (ideal / total_ideal)
    │     ~34% of calls shift from P3 → P1 at FLAT COST
    │
    ├─► Territory workload analysis (capacity, coverage, frequency)
    │
    └─► Territory actions:
          "Deploy rep (vacant)" | "Reinforce — under-served"
          "Over-served — trim/redeploy" | "Balanced"
```

**Output:** `reports/optimization_report.md` + `data/processed/doctor_call_plan.csv` + `data/processed/territory_plan.csv`

---

### Phase 9: Executive Dashboard
**Command:** `make dashboard`

```
Flow:
  prepare_dashboard.py → precompute aggregate CSVs:
    monthly_portfolio, region_summary, product_summary, market_ta,
    channel_roi, segment_summary, score_tier_summary, kpis

  streamlit run dashboard/streamlit/app.py → 7 interactive pages:
    1. Executive Overview (headline KPIs, revenue trend)
    2. Sales Performance (rep productivity, call patterns)
    3. Regional Performance (zone/region heatmap, growth)
    4. Doctor Segmentation (9-box grid, white space)
    5. Hospital Analysis (tier pyramid)
    6. Marketing ROI (channel comparison, budget allocation)
    7. Product Analysis (portfolio growth, lifecycle)
```

**Output:** Running Streamlit dashboard (no database required)

---

## 7. Data Model — Dimensional Schema

### Dimension Tables (12)

| Table | Primary Key | Rows | Description |
|-------|-------------|------|-------------|
| `dim_month` | `month_id` | 36 | Calendar months (2023-07 to 2026-06) |
| `dim_zone` | `zone_id` | 2 | North, South |
| `dim_region` | `region_id` | 5 | Reporting regions (1 RM each) |
| `dim_regional_manager` | `rm_id` | 5 | Regional managers |
| `dim_territory` | `territory_id` | 50 | Sales territories (1 rep each) |
| `dim_sales_rep` | `rep_id` | 50 | Field sales representatives |
| `dim_hospital` | `hospital_id` | 150 | Hospitals |
| `dim_doctor` | `doctor_id` | 1,500 | Prescribing doctors |
| `dim_therapeutic_area` | `ta_id` | 2 | 2 therapeutic areas |
| `dim_product` | `product_id` | 5 | Company brands |
| `dim_competitor_product` | `competitor_product_id` | 6 | Competitor brands |
| `dim_campaign` | `campaign_id` | varies | Marketing campaigns |

### Fact Tables (4)

| Table | Grain | Rows | Description |
|-------|-------|------|-------------|
| `fact_prescriptions` | doctor × product × month | ~200K | Revenue, units prescribed, new patients |
| `fact_competitor_rx` | doctor × TA × month | ~100K | Competitor prescription units |
| `fact_sales_calls` | rep × doctor × month | ~180K | Calls planned/made, samples dropped |
| `fact_marketing_spend` | campaign × region × month | varies | Spend, leads, conversions |

---

## 8. SQL Semantic Layer

### Views (`sql/views/01_kpi_views.sql`)
- `vw_marketing_roi` — Channel ROI, budget share %
- `vw_doctor_value` — TTM revenue, calls, conversion per doctor
- `vw_regional_performance` — Zone/region revenue, growth, share
- `vw_product_performance` — Brand P&L, lifecycle, margin

### Stored Procedures (`sql/procedures/01_procedures.sql`)
- `fn_top_doctors(region, limit)` — Ranked doctor list by value
- `fn_territory_summary()` — Territory-level KPIs

### Analysis Library (`sql/analysis/`)
- `01_ranking_and_targeting.sql` — Doctor ranking, NTILE deciles, targeting queries
- `02_regional_and_growth.sql` — Regional growth rates, YoY, zone ROLLUP
- `03_product_and_marketing.sql` — Product portfolio, marketing channel analysis
- `04_salesforce_effectiveness.sql` — Rep productivity, call-to-Rx correlation

---

## 9. Module Dependency Graph

```
engagement_config.yaml
        │
        ▼
  data_generation ──► data_pipeline ──► analytics/eda ──► segmentation
                                                               │
                                              analytics/performance
                                                     │
                                           forecasting + scoring
                                                     │
                                              optimization
                                                     │
                                           dashboard (Streamlit)
```

---

## 10. Testing

**Command:** `make test` → `pytest tests/ -q`

| Test File | What it Tests |
|-----------|--------------|
| `conftest.py` | Shared fixtures (config, mini-dataset, tables) |
| `test_data_pipeline.py` | Generation, cleaning, validation, row counts, FK integrity |
| `test_analytics.py` | EDA report generation, chart output |
| `test_segmentation.py` | 9-box assignment, hospital tiers, K-means validation |
| `test_performance.py` | Opportunity register, regional/product metrics |
| `test_forecast_scoring.py` | ETS forecast, opportunity score computation |
| `test_optimization.py` | Call plan, territory workload, reallocation math |

---

## 11. Repository Structure

```
pharma-commercial-analytics-main/
│
├── config/
│   └── engagement_config.yaml          # Single source of truth
│
├── src/catalyst/                       # Main Python package
│   ├── data_generation/                # Synthetic data engine
│   ├── data_pipeline/                  # ETL pipeline
│   ├── analytics/                      # Diagnostic analytics
│   ├── segmentation/                   # Customer segmentation
│   ├── forecasting/                    # Revenue forecasting
│   ├── scoring/                        # Opportunity scoring
│   ├── optimization/                   # Territory optimization
│   ├── visualization/theme.py          # Chart theming
│   └── utils/                          # Shared utilities
│
├── scripts/                            # CLI entry points
│   ├── generate_data.py, validate_data.py, load_to_postgres.py
│   ├── run_eda.py, run_segmentation.py, run_performance.py
│   ├── run_forecast_scoring.py, run_optimization.py
│   └── prepare_dashboard.py
│
├── sql/                                # SQL semantic layer
│
├── dashboard/
│   ├── streamlit/app.py                # 7-page dashboard
│   └── powerbi/README.md               # Power BI spec + DAX
│
├── data/                               # raw → processed → dashboard/
├── notebooks/01_eda_diagnostic.ipynb   # Narrative EDA
├── reports/                            # Analytics reports + figures
├── tests/                              # pytest suite
├── docs/                               # Architecture, data model, data dictionary
├── docker-compose.yml                  # PostgreSQL 15 container
├── Makefile                            # Build automation
└── requirements.txt                    # Python dependencies
```

---

## 12. Quickstart Commands

```bash
make setup              # Create venv + install dependencies
make build              # Generate ~500k rows + validate + DQ report
make db-up              # Start PostgreSQL (Docker)
make db-load            # Schema, bulk-load, views & procedures
make eda                # Diagnostic EDA report + 10 figures
make segment            # Doctor 9-box + hospital tiers
make performance        # Opportunity diagnostics + register
make score              # Revenue forecast + Opportunity Score
make optimize           # Territory optimization + call reallocation
make dashboard          # Launch Streamlit dashboard
make test               # Run pytest tests
make clean              # Remove generated data artifacts
```

---

## 13. Output Artifacts

### Data Artifacts
| File | Created By | Used By |
|------|-----------|---------|
| `data/raw/*.csv` (16 files) | generate_data.py | validate_data.py |
| `data/processed/*.csv` (16 files) | validate_data.py | All analytics modules |
| `data/processed/doctor_segments.csv` | segmentation | scoring, optimization, dashboard |
| `data/processed/hospital_segments.csv` | segmentation | dashboard |
| `data/processed/opportunity_register.csv` | performance | forecasting |
| `data/processed/doctor_opportunity_score.csv` | scoring | optimization |
| `data/processed/territory_plan.csv` | optimization | dashboard |
| `data/processed/dashboard/*.csv` (8 files) | prepare_dashboard | Streamlit app |

### Reports
| Report | Content |
|--------|---------|
| `data_quality_report.md` | Structural + plausibility + pattern validation |
| `eda_report.md` | 10-chart diagnostic EDA |
| `segmentation_report.md` | 9-box segments, hospital tiers, K-means validation |
| `performance_report.md` | Opportunity register, regional/product/marketing |
| `forecast_and_scoring_report.md` | ETS forecast, opportunity score distribution |
| `optimization_report.md` | Reallocation plan, territory actions |

---

*All data is synthetic and privacy-safe.*
