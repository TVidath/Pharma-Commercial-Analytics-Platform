# Axtria Analyst Role — Interview Preparation Plan

> **Pre-Placement Talk:** 5th October 2026 (5:30 PM)
> **Online Assessment:** 5th October 2026 (7:30 PM)
> **Interview Process:** 7th October 2026 (10:00 AM onwards)
> **Days remaining:** ~6 days

---

## How This Project Maps to the Axtria JD

| Axtria JD Requirement | Your Project Coverage | What to Say |
|---|---|---|
| Data models (OLTP/OLAP) & ETL pipelines | ✅ Star schema, 16 tables, full ETL | "I designed a dimensional model with 12 dimension and 4 fact tables, built a complete ETL pipeline from generation through validation to PostgreSQL" |
| SQL, stored procedures, database scripts | ✅ DDL, views, procedures, 4-file analysis library | "I wrote KPI views, stored functions like fn_top_doctors(), and a SQL analysis library using window functions, NTILE, CTEs, ROLLUP" |
| Business rules via stored procedures | ✅ KPI views, territory functions | "Business KPIs like marketing ROI and doctor value are computed in SQL views for performance and reusability" |
| Database environments + documentation | ✅ Docker PostgreSQL, 4 design docs | "I containerized PostgreSQL with Docker Compose and documented the data model, data dictionary, and architecture" |
| Performance tuning (queries, indexing) | ✅ Composite indexes, ANALYZE, bulk COPY | "I used composite indexes on fact table grains, PostgreSQL COPY for bulk loading, and ANALYZE for query optimization" |
| Dashboards (Power BI, Tableau) | ✅ Streamlit + Power BI spec with DAX | "I built a 7-page Streamlit dashboard and created a Power BI specification with DAX measures" |
| Territory alignment, call plan | ✅ **This IS the project** | "I built territory optimization with capacity-neutral call reallocation — redistributing existing rep capacity by opportunity score" |
| Automation of business processes | ✅ Makefile, reproducible pipeline | "The entire pipeline is automated via Makefile — one command rebuilds everything from config" |
| Pharma / Life Sciences domain | ✅ Pharma commercial analytics | "The project simulates a pharma company with 50 reps, 1,500 doctors, territory alignment, and call planning" |

---

## Day-by-Day Study Plan (Sep 29 → Oct 5)

### Day 1 (Sep 29): SQL Deep Dive
**This is the most likely technical test topic.**

Study from your project:
- [ ] Read `sql/schema/01_create_tables.sql` — understand every CREATE TABLE, PK, FK
- [ ] Read `sql/views/01_kpi_views.sql` — understand how KPI views are built
- [ ] Read all 4 files in `sql/analysis/` — practice window functions, NTILE, CTEs

Practice writing:
- [ ] Ranking query: "Top 10 doctors by TTM revenue per region" (use RANK() OVER)
- [ ] Growth query: "YoY revenue growth by zone" (use LAG or self-join)
- [ ] Aggregation: "Marketing ROI by channel" (GROUP BY + CASE)
- [ ] Subquery: "Doctors with above-average prescriptions in their specialty"

Key SQL concepts to know cold:
- Window functions: ROW_NUMBER, RANK, DENSE_RANK, NTILE, LAG, LEAD
- Aggregations: GROUP BY, HAVING, ROLLUP, CUBE
- Joins: INNER, LEFT, CROSS, self-joins
- Subqueries: correlated vs uncorrelated
- CTEs: WITH clause
- Indexes: why composite indexes matter for fact tables

### Day 2 (Sep 30): Data Modelling & ETL
Study from your project:
- [ ] Read `docs/04_data_model_and_erd.md` — memorize the schema design rationale
- [ ] Read `docs/05_data_dictionary.md` — know every table and column
- [ ] Read `src/catalyst/data_pipeline/clean.py` — understand the cleaning logic
- [ ] Read `src/catalyst/data_pipeline/load.py` — understand bulk COPY approach

Key concepts to explain:
- [ ] What is a star schema? Why not snowflake? (Answer: simpler joins, faster queries)
- [ ] What is grain? (Answer: the most granular level of a fact table)
- [ ] Fact vs dimension table? (Answer: facts store measurements, dimensions store descriptors)
- [ ] What is ETL vs ELT? (Answer: ETL transforms before loading, ELT loads then transforms)
- [ ] Why COPY instead of INSERT? (Answer: 10-100x faster for bulk loads)
- [ ] What is referential integrity? (Answer: every FK value exists in the parent table)
- [ ] What are deferred constraints? (Answer: allows loading in any order within a transaction)

### Day 3 (Oct 1): Python & Analytics
Study from your project:
- [ ] Read `src/catalyst/segmentation/doctors.py` — the 9-box segmentation logic
- [ ] Read `src/catalyst/scoring/opportunity_score.py` — the 5-component score
- [ ] Read `src/catalyst/analytics/eda.py` — how EDA charts are generated
- [ ] Run through `notebooks/01_eda_diagnostic.ipynb`

Key Pandas operations to know:
- [ ] groupby().agg() — you use this everywhere
- [ ] merge() — left, inner, how it maps to SQL joins
- [ ] pd.cut() / pd.qcut() — for binning (used in segmentation)
- [ ] rank(pct=True) — percentile ranking
- [ ] pivot_table() — reshaping data

### Day 4 (Oct 2): Domain Knowledge — Pharma Commercial Analytics
**This is Axtria's core business. Knowing this sets you apart.**

Study these concepts:
- [ ] What is SFE (Sales Force Effectiveness)?
  → Measuring and optimizing how sales reps convert effort into prescriptions
- [ ] What is territory alignment?
  → Assigning doctors/hospitals to sales territories to balance workload and opportunity
- [ ] What is call planning?
  → Deciding how many visits each rep makes to each doctor (your P1/P2/P3 system)
- [ ] What is incentive compensation?
  → Designing bonus structures based on rep performance vs targets
- [ ] What is a call-to-Rx conversion rate?
  → How many prescriptions result per sales call
- [ ] What is white space?
  → Untapped revenue opportunity in under-served doctors/territories
- [ ] What is an opportunity score?
  → A composite index that ranks doctors by growth potential (your 5-component score)
- [ ] What is a 9-box segmentation?
  → Two-axis grid (Potential × Value) creating 9 action segments

### Day 5 (Oct 3): Dashboard & BI
Study from your project:
- [ ] Read `dashboard/streamlit/app.py` — understand the 7 pages
- [ ] Read `dashboard/powerbi/README.md` — understand the DAX measures

Key concepts:
- [ ] What is a DAX measure? (Answer: calculated metric in Power BI)
- [ ] KPIs for pharma: revenue, growth %, Rx share, calls per doctor, marketing ROI

### Day 6 (Oct 4): Mock Interview & Review
- [ ] Practice explaining the project in 2 minutes (elevator pitch — see below)
- [ ] Practice explaining any module in 5 minutes with whiteboard
- [ ] Review all SQL concepts one more time
- [ ] Practice writing 3-4 SQL queries from scratch

### Day 7 (Oct 5): Pre-Placement Talk + Assessment
- [ ] Attend PPT at 5:30 PM — take notes on what Axtria emphasizes
- [ ] Online assessment at 7:30 PM — expect SQL, logic, and aptitude questions

---

## Your 2-Minute Project Pitch

> "I built a pharma commercial analytics platform called Pharma Commercial Analytics Platform. It simulates a pharmaceutical company with 50 sales reps covering 1,500 doctors across India.
>
> The core problem: the company has stagnant revenue despite rising promotional spend. My analysis showed that sales effort was mis-allocated — reps were spending time on saturated, high-volume doctors instead of high-potential, under-served ones.
>
> I designed a star schema data model with 16 tables — 4 fact tables with ~500,000 rows — and built a complete ETL pipeline from data generation through validation to PostgreSQL. I wrote SQL views, stored procedures, and a business query library using window functions and CTEs.
>
> The analytics pipeline includes doctor segmentation using a Potential × Value 9-box framework, a Commercial Opportunity Score that ranks every doctor on 5 transparent components, and territory optimization that reallocates existing call capacity by priority — shifting 34% of calls from over-served to under-served doctors at flat cost.
>
> I also built a 7-page Streamlit dashboard that presents everything to leadership."

---

## Resume Bullet Points

```
PROJECT: Pharma Commercial Analytics Platform
Tech: Python, PostgreSQL, SQL, Pandas, Streamlit, scikit-learn, Docker

• Designed dimensional star-schema data model (12 dimensions, 4 fact tables,
  ~500,000 rows) for a simulated pharmaceutical sales-force dataset
• Built end-to-end ETL pipeline: data generation → cleaning → validation →
  PostgreSQL bulk load with referential integrity checks
• Wrote SQL semantic layer: KPI views, stored procedures, and 4-file business
  query library using window functions, NTILE, CTEs, and ROLLUP
• Implemented doctor segmentation (Potential × Value 9-box) with transparent
  scoring and K-Means validation (ARI + silhouette)
• Developed territory optimization: capacity-neutral call reallocation across
  50 territories using opportunity-based prioritization (P1/P2/P3 tiers)
• Built 7-page interactive Streamlit executive dashboard with regional,
  product, and marketing analytics views
• Automated full pipeline via Makefile; pytest tests; reproducible (seed=42)
```

---

## Common Interview Questions & How to Answer

**Q: Walk me through your project.**
→ Use the 2-minute pitch above. Focus on: problem → data model → ETL → analytics → dashboard.

**Q: Why did you use a star schema?**
→ "Star schema is optimal for analytical queries — simple joins between fact and dimension tables, fast aggregations, and it maps naturally to BI tools like Power BI."

**Q: How does your ETL pipeline work?**
→ "Three stages: 1) Generate synthetic data with embedded business patterns, 2) Clean — enforce types, remove negatives, deduplicate on grain, 3) Validate — structural integrity, business plausibility, then bulk COPY into PostgreSQL."

**Q: What is your opportunity score?**
→ "A transparent 0-100 composite: 30% Potential + 30% Headroom + 15% Momentum + 15% Accessibility + 10% Competitive. Each component is interpretable — a sales manager can explain any doctor's score to a rep."

**Q: How does territory optimization work?**
→ "I set ideal call frequencies by priority tier (P1=18/year, P2=9, P3=3), then redistribute each rep's existing call capacity proportionally. About 34% of calls shift from over-served P3 doctors to under-served P1 doctors — same total calls, better allocation."

**Q: What SQL did you write?**
→ "Views for marketing ROI and doctor value rankings, stored functions for parameterized queries, and a 4-file analysis library using window functions like RANK, NTILE for decile analysis, LAG for YoY growth, and ROLLUP for zone-level aggregations."

**Q: Why Streamlit instead of Power BI?**
→ "I built both — Streamlit for a runnable prototype that needs no licenses, and a full Power BI specification with DAX measures for enterprise deployment. Streamlit was faster to iterate on in Python."

---

## Key Numbers to Remember

- 50 reps, 5 regions, 1,500 doctors, 150 hospitals
- ~500,000 rows across 4 fact tables
- 16 tables in the star schema (12 dims + 4 facts)
- 9-box segmentation (3×3: Potential × Value)
- 5-component opportunity score (weights: 0.30, 0.30, 0.15, 0.15, 0.10)
- P1=18 calls/yr, P2=9, P3=3 (ideal frequency)
- 34% of calls reallocated (capacity-neutral)
