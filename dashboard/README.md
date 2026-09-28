# Pharma Commercial Analytics Platform — Executive Dashboard

Two deliverables, one design:

| | |
|---|---|
| **[`powerbi/`](powerbi/)** | Build-ready **Power BI specification** — data model, relationships, full DAX measure library, and all 8 page layouts. A BI developer builds the `.pbix` from this. |
| **[`streamlit/`](streamlit/)** | A **runnable** Streamlit companion that mirrors the same 8 pages — launches instantly, no database, for a live demo. |

Both use the same validated colour palette and the same numbers, so the Power BI build can be validated against the running Streamlit app.

## Run the Streamlit companion

```bash
python scripts/prepare_dashboard.py          # build lightweight aggregate CSVs (once)
streamlit run dashboard/streamlit/app.py      # launches at http://localhost:8501
```
…or `make dashboard` (runs prep + launch).

**Pages:** Overview · Sales Performance · Regional Performance · Doctor Segmentation · Hospital Analysis · Marketing ROI · Product Analysis · Recommendations.

The app reads `data/processed/dashboard/*.csv` (precomputed aggregates) plus the segment / score / recommendation outputs — so it runs with zero setup once the pipeline has been run.
