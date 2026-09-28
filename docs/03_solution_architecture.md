# Project Catalyst — Solution Architecture

**Status:** Milestone 1 baseline · **Audience:** technical reviewer / architect

---

## 1. Architectural principles

| Principle | Implication |
|-----------|-------------|
| **Layered & modular** | Data → Storage → Analytics → Decision → Presentation. Each layer swappable. |
| **Config-driven** | No magic numbers in code; everything from `config/engagement_config.yaml`. |
| **Reproducible** | Fixed random seed; deterministic pipeline; `make`/scripts rebuild from scratch. |
| **SQL for set logic, Python for math** | KPIs, joins, ranking, windows → SQL. Segmentation, forecasting, optimization, scoring → Python. |
| **Interpretability first** | Transparent indices and rules over black-box models. |
| **Testable** | Data-quality checks + unit tests on every transform and score. |

---

## 2. Layered architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  L5  PRESENTATION      Power BI dashboard · Streamlit companion ·      │
│                        Analytics reports · Financial model              │
├──────────────────────────────────────────────────────────────────────┤
│  L4  DECISION          Opportunity scoring · Territory & salesforce    │
│                        optimization · Financial model · Recommendation │
│                        engine                                          │
├──────────────────────────────────────────────────────────────────────┤
│  L3  ANALYTICS         EDA · Segmentation · Rx opportunity ·           │
│                        Performance analytics · Marketing mix ·         │
│                        Forecasting                                     │
├──────────────────────────────────────────────────────────────────────┤
│  L2  STORAGE & SEMANTICS   PostgreSQL (catalyst schema) ·              │
│                        Dimensional model · Views · Stored procedures · │
│                        KPI/business-query library                      │
├──────────────────────────────────────────────────────────────────────┤
│  L1  DATA FOUNDATION   Synthetic data engine · Cleaning & validation · │
│                        Data-quality reporting                          │
└──────────────────────────────────────────────────────────────────────┘
        ▲ config/engagement_config.yaml drives every layer ▲
```

### Data flow
```
config.yaml
   │
   ▼
[data_generation] ──► data/raw/*.csv ──► [data_pipeline: clean+validate] ──► data/processed/
   │                                                    │
   │                                                    ▼
   └──────────────────────────────► PostgreSQL (catalyst schema)  ◄── sql/schema, views, procedures
                                                        │
                          ┌─────────────────────────────┼─────────────────────────────┐
                          ▼                             ▼                             ▼
                    [SQL analysis]              [Python analytics]            [Power BI / Streamlit]
                    KPIs, rankings              segmentation, forecast,       dashboards
                                                optimization, scoring
                                                        │
                                                        ▼
                                          [financial model] ─► [recommendation engine]
                                                        │
                                                        ▼
                                          reports/ + presentation/ (deliverables)
```

---

## 3. Technology stack & rationale

| Concern | Choice | Why (vs. alternatives) |
|---------|--------|------------------------|
| Database | **PostgreSQL 15+** | Full stored-procedure/function support, window functions, free, enterprise-credible, native Power BI connector. Chosen over SQLite (no stored procs) and SQL Server (heavier setup) — see decision log. |
| Language | **Python 3.11** | Ecosystem for analytics; readable for reviewers. |
| Data | pandas, numpy | Standard, transparent. |
| Stats/ML | scikit-learn, statsmodels | KMeans (segment *validation* only), regression, time-series. Deliberately lightweight — no deep learning. |
| Optimization | scipy / PuLP | Territory & salesforce balancing (LP/greedy). |
| DB access | SQLAlchemy + psycopg2 | Parameterised, safe, testable. |
| Config | PyYAML | Single source of truth. |
| Dashboard | **Power BI** (primary spec + DAX) + **Streamlit** (runnable companion) | Power BI for résumé/enterprise credibility; Streamlit so the work is demoable live without a Power BI licence. |
| Report/Deck | Markdown → PDF, python-pptx | Reproducible, versionable deliverables. |
| Testing | pytest | Data-quality + unit tests. |
| Viz | matplotlib, seaborn, plotly | EDA + report charts. |

---

## 4. Repository structure

```
Pharma/
├── config/                 # engagement_config.yaml — single source of truth
├── data/
│   ├── raw/                # generator output (git-ignored)
│   ├── processed/          # cleaned/validated (git-ignored)
│   └── external/           # reference lookups (cities, specialties)
├── docs/                   # charter, KPI, architecture, data model, data spec
│   └── diagrams/           # ERD, flow diagrams
├── sql/
│   ├── schema/             # DDL: tables, keys, indexes  (Milestone 1–2)
│   ├── views/              # KPI & semantic views        (Milestone 2–3)
│   ├── procedures/         # stored procedures           (Milestone 2)
│   └── analysis/           # business query library      (Milestone 3)
├── src/catalyst/           # installable package
│   ├── data_generation/    # synthetic data engine       (M2)
│   ├── data_pipeline/      # clean, validate, load        (M2)
│   ├── analytics/          # EDA, performance, market     (M3, M5)
│   ├── segmentation/       # doctor & hospital segments   (M4)
│   ├── forecasting/        # revenue forecast             (M6)
│   ├── scoring/            # opportunity score            (M6)
│   ├── optimization/       # territory & salesforce       (M7)
│   ├── financial/          # financial model              (M8)
│   ├── recommendation/     # recommendation engine        (M8)
│   ├── visualization/      # shared chart helpers
│   └── utils/              # config, logging, db, io
├── dashboard/
│   ├── powerbi/            # data model, DAX, page specs  (M9)
│   └── streamlit/          # runnable companion app       (M9)
├── notebooks/              # narrative EDA & analysis      (M3+)
├── reports/                # analytics reports, DQ report   (M2–M8)
├── tests/                  # pytest suite
├── scripts/                # CLI entry points (build_db, run_pipeline)
└── README.md               # enterprise front page
```

**Every module is reusable:** each `src/catalyst/*` package exposes a small, typed public API (e.g. `segmentation.segment_doctors(df, config) -> DataFrame`), reads from config, logs via the shared logger, and is unit-tested. No module hard-codes paths or constants.

---

## 5. Cross-cutting conventions

- **Logging:** one configured logger (`catalyst.utils.logging`), structured, level from config; no bare `print`.
- **Type hints & docstrings:** all public functions typed; NumPy-style docstrings.
- **Error handling:** validation failures raise typed exceptions; the pipeline fails loudly, never silently produces bad data.
- **Naming:** `dim_`/`fact_` tables; `vw_` views; `sp_` procedures; snake_case Python; verbs for functions, nouns for data.
- **Reproducibility:** `scripts/build_all.sh` regenerates data → DB → analytics artifacts deterministically.

---

## 6. Architecture Decision Log (ADRs)

| # | Decision | Alternatives considered | Rationale |
|---|----------|-------------------------|-----------|
| ADR-1 | PostgreSQL as system of record | SQLite; SQL Server | Needs stored procedures + window functions + Power BI; free and portable. SQLite lacks procs; SQL Server heavier to set up. |
| ADR-2 | Synthetic data with *planted* business logic | Pure random; public dataset | Random data yields no recoverable insight (fails credibility); no public dataset matches the exact entity model. Planted logic makes the diagnostic defensible. |
| ADR-3 | Transparent composite scores over ML classifiers | Gradient boosting / NN | Field must explain every score; interpretability > marginal accuracy. ML used only to *validate* segments and *baseline* forecasts. |
| ADR-4 | Dimensional (star) model | Fully normalised OLTP | Analytics workload; star schema simplifies KPIs, ranking, and BI. |
| ADR-5 | Power BI primary + Streamlit companion | Power BI only; Streamlit only | Power BI for credibility; Streamlit so it runs live in an interview demo. |
| ADR-6 | Driver-based financial model in Python/Excel-style | Black-box | Board needs a visible bridge from levers to rupees; sensitivity/scenario ready. |

---

## 7. Milestone → component mapping

| Milestone | Primary components produced |
|-----------|-----------------------------|
| M1 (this) | config, docs, `sql/schema` DDL, ERD |
| M2 | `data_generation`, `data_pipeline`, DB load, `sql/views`, `sql/procedures`, DQ report |
| M3 | `analytics` (EDA), `sql/analysis` query library, notebooks |
| M4 | `segmentation` (doctor, hospital) |
| M5 | `analytics` (Rx opportunity, regional, product, marketing) |
| M6 | `forecasting`, `scoring` |
| M7 | `optimization` (territory, salesforce) |
| M8 | `financial`, `recommendation` |
| M9 | `dashboard/powerbi`, `dashboard/streamlit` |
| M10 | `reports`, `presentation`, final README |
