# Pharma Commercial Analytics Platform — Documentation Index

| # | Document | What it covers |
|---|----------|----------------|
| 02 | [KPI Framework](02_kpi_framework.md) | Metric tree, full KPI catalogue with formulas/grain, governance, the 5 headline numbers |
| 03 | [Solution Architecture](03_solution_architecture.md) | Layered architecture, tech stack + rationale, repo structure, ADRs |
| 04 | [Data Model & ERD](04_data_model_and_erd.md) | Dimensional model, ER diagram, grain, cardinality, keys, volumes |
| 05 | [Data Dictionary](05_data_dictionary.md) | Every table/column, type, raw-vs-derived, business meaning |

**SQL:** schema DDL in [`../sql/schema/`](../sql/schema/) · views/procedures/analysis queries.
**Config:** [`../config/engagement_config.yaml`](../config/engagement_config.yaml) — single source of truth.

**Reports:** [Data Quality Report](../reports/data_quality_report.md) · [Diagnostic EDA Report](../reports/eda_report.md) (10 figures) · [Segmentation Report](../reports/segmentation_report.md) (9-box + playbooks) · [Performance & Opportunity Report](../reports/performance_report.md) (₹ opportunity register) · [Forecast & Opportunity-Score Report](../reports/forecast_and_scoring_report.md) · [Optimization Report](../reports/optimization_report.md) (reallocation + deployment)
**Notebook:** [`notebooks/01_eda_diagnostic.ipynb`](../notebooks/01_eda_diagnostic.ipynb) — executed narrative EDA
**SQL analysis library:** [`sql/analysis/`](../sql/analysis/) — 4 files, ranking/growth/product-marketing/salesforce
**Dashboard:** [`dashboard/powerbi/`](../dashboard/powerbi/README.md) — Power BI build spec (data model + DAX + 7 pages) · [`dashboard/streamlit/`](../dashboard/streamlit/app.py) — 7-page Streamlit dashboard (`make dashboard`)
