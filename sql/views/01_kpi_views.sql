-- =============================================================================
-- PHARMA COMMERCIAL ANALYTICS PLATFORM — Semantic KPI Views
-- Engine: PostgreSQL 15+   Schema: catalyst
-- One definition per KPI (see docs/02_kpi_framework.md). Dashboards, notebooks
-- and SQL analysis consume these views; they never re-derive metrics.
-- TTM = trailing 12 months; PY = the 12 months before that.
-- =============================================================================

SET search_path TO catalyst;

-- --- Period flags: tag each month as TTM / PY for YoY comparisons -----------
CREATE OR REPLACE VIEW catalyst.vw_period_flags AS
SELECT month_id,
       CASE WHEN rnk <= 12 THEN 'TTM'
            WHEN rnk <= 24 THEN 'PY' END AS period_band,
       rnk
FROM (
    SELECT month_id, ROW_NUMBER() OVER (ORDER BY month_id DESC) AS rnk
    FROM catalyst.dim_month
    WHERE is_forecast = FALSE
) x;

-- --- Enriched prescription grain (workhorse fact + all dimensions) ----------
CREATE OR REPLACE VIEW catalyst.vw_rx_enriched AS
SELECT r.rx_id, r.doctor_id, r.product_id, r.month_id,
       r.units_prescribed, r.revenue, r.new_patient_count,
       (r.units_prescribed * (p.unit_price - p.cost_per_unit)) AS margin,
       p.brand_name, p.ta_id, p.lifecycle_stage,
       d.specialty, d.kol_flag, d.territory_id,
       te.region_id, rg.region_name, rg.zone_id, z.zone_name,
       m.year, m.quarter, m.month_num, m.fiscal_year
FROM catalyst.fact_prescriptions r
JOIN catalyst.dim_product   p  ON p.product_id  = r.product_id
JOIN catalyst.dim_doctor    d  ON d.doctor_id   = r.doctor_id
JOIN catalyst.dim_territory te ON te.territory_id = d.territory_id
JOIN catalyst.dim_region    rg ON rg.region_id  = te.region_id
JOIN catalyst.dim_zone      z  ON z.zone_id     = rg.zone_id
JOIN catalyst.dim_month     m  ON m.month_id    = r.month_id;

-- --- Doctor KPI: TTM value, calls, and marginal productivity ----------------
CREATE OR REPLACE VIEW catalyst.vw_doctor_kpi AS
WITH rx AS (
    SELECT r.doctor_id,
           SUM(r.revenue)            AS ttm_revenue,
           SUM(r.units_prescribed)   AS ttm_units,
           SUM(r.new_patient_count)  AS ttm_new_patients
    FROM catalyst.fact_prescriptions r
    JOIN catalyst.vw_period_flags pf ON pf.month_id = r.month_id AND pf.period_band = 'TTM'
    GROUP BY r.doctor_id
),
cl AS (
    SELECT c.doctor_id, SUM(c.calls_made) AS ttm_calls
    FROM catalyst.fact_sales_calls c
    JOIN catalyst.vw_period_flags pf ON pf.month_id = c.month_id AND pf.period_band = 'TTM'
    GROUP BY c.doctor_id
)
SELECT d.doctor_id, d.specialty, d.kol_flag, d.patient_panel_size,
       te.region_id, rg.region_name, z.zone_name,
       COALESCE(rx.ttm_revenue, 0)       AS ttm_revenue,
       COALESCE(rx.ttm_units, 0)         AS ttm_units,
       COALESCE(rx.ttm_new_patients, 0)  AS ttm_new_patients,
       COALESCE(cl.ttm_calls, 0)         AS ttm_calls,
       CASE WHEN COALESCE(cl.ttm_calls, 0) > 0
            THEN ROUND(rx.ttm_units::numeric / cl.ttm_calls, 2) END AS rx_per_call
FROM catalyst.dim_doctor d
JOIN catalyst.dim_territory te ON te.territory_id = d.territory_id
JOIN catalyst.dim_region    rg ON rg.region_id = te.region_id
JOIN catalyst.dim_zone      z  ON z.zone_id = rg.zone_id
LEFT JOIN rx ON rx.doctor_id = d.doctor_id
LEFT JOIN cl ON cl.doctor_id = d.doctor_id;

-- --- Territory KPI: coverage, workload, TTM revenue -------------------------
CREATE OR REPLACE VIEW catalyst.vw_territory_kpi AS
WITH doc AS (
    SELECT territory_id, COUNT(*) AS n_doctors, SUM(patient_panel_size) AS total_panel
    FROM catalyst.dim_doctor GROUP BY territory_id
),
rev AS (
    SELECT d.territory_id, SUM(r.revenue) AS ttm_revenue
    FROM catalyst.fact_prescriptions r
    JOIN catalyst.dim_doctor d ON d.doctor_id = r.doctor_id
    JOIN catalyst.vw_period_flags pf ON pf.month_id = r.month_id AND pf.period_band = 'TTM'
    GROUP BY d.territory_id
),
cov AS (
    SELECT d.territory_id,
           COUNT(DISTINCT c.doctor_id) FILTER (WHERE c.calls_made > 0) AS doctors_covered,
           SUM(c.calls_made) AS total_calls
    FROM catalyst.fact_sales_calls c
    JOIN catalyst.dim_doctor d ON d.doctor_id = c.doctor_id
    GROUP BY d.territory_id
)
SELECT t.territory_id, t.region_id, rg.region_name, z.zone_name, t.city, t.urbanicity_tier,
       sr.rep_id, sr.rep_name, sr.experience_years, sr.employment_status,
       doc.n_doctors, doc.total_panel,
       COALESCE(cov.doctors_covered, 0) AS doctors_covered,
       ROUND(COALESCE(cov.doctors_covered, 0)::numeric / NULLIF(doc.n_doctors, 0) * 100, 1) AS coverage_pct,
       COALESCE(cov.total_calls, 0) AS total_calls,
       COALESCE(rev.ttm_revenue, 0) AS ttm_revenue
FROM catalyst.dim_territory t
JOIN catalyst.dim_region rg ON rg.region_id = t.region_id
JOIN catalyst.dim_zone   z  ON z.zone_id = rg.zone_id
LEFT JOIN catalyst.dim_sales_rep sr ON sr.territory_id = t.territory_id
LEFT JOIN doc ON doc.territory_id = t.territory_id
LEFT JOIN rev ON rev.territory_id = t.territory_id
LEFT JOIN cov ON cov.territory_id = t.territory_id;

-- --- Product performance: TTM vs PY growth and margin -----------------------
CREATE OR REPLACE VIEW catalyst.vw_product_performance AS
SELECT p.product_id, p.brand_name, p.molecule, ta.ta_name, p.lifecycle_stage,
       SUM(r.revenue) FILTER (WHERE pf.period_band = 'TTM') AS ttm_revenue,
       SUM(r.revenue) FILTER (WHERE pf.period_band = 'PY')  AS py_revenue,
       SUM(r.units_prescribed) FILTER (WHERE pf.period_band = 'TTM') AS ttm_units,
       SUM(r.units_prescribed * (p.unit_price - p.cost_per_unit))
           FILTER (WHERE pf.period_band = 'TTM') AS ttm_margin,
       ROUND(
         (SUM(r.revenue) FILTER (WHERE pf.period_band = 'TTM')
          - SUM(r.revenue) FILTER (WHERE pf.period_band = 'PY'))
          / NULLIF(SUM(r.revenue) FILTER (WHERE pf.period_band = 'PY'), 0) * 100, 1
       ) AS yoy_growth_pct
FROM catalyst.dim_product p
JOIN catalyst.dim_therapeutic_area ta ON ta.ta_id = p.ta_id
LEFT JOIN catalyst.fact_prescriptions r ON r.product_id = p.product_id
LEFT JOIN catalyst.vw_period_flags pf ON pf.month_id = r.month_id
GROUP BY p.product_id, p.brand_name, p.molecule, ta.ta_name, p.lifecycle_stage;

-- --- Regional market share (our units vs competitor, TTM, by TA) ------------
CREATE OR REPLACE VIEW catalyst.vw_region_market_share AS
WITH ours AS (
    SELECT te.region_id, p.ta_id, SUM(r.units_prescribed) AS our_units
    FROM catalyst.fact_prescriptions r
    JOIN catalyst.dim_product p ON p.product_id = r.product_id
    JOIN catalyst.dim_doctor d ON d.doctor_id = r.doctor_id
    JOIN catalyst.dim_territory te ON te.territory_id = d.territory_id
    JOIN catalyst.vw_period_flags pf ON pf.month_id = r.month_id AND pf.period_band = 'TTM'
    GROUP BY te.region_id, p.ta_id
),
comp AS (
    SELECT te.region_id, cr.ta_id, SUM(cr.competitor_units) AS comp_units
    FROM catalyst.fact_competitor_rx cr
    JOIN catalyst.dim_doctor d ON d.doctor_id = cr.doctor_id
    JOIN catalyst.dim_territory te ON te.territory_id = d.territory_id
    JOIN catalyst.vw_period_flags pf ON pf.month_id = cr.month_id AND pf.period_band = 'TTM'
    GROUP BY te.region_id, cr.ta_id
)
SELECT rg.region_id, rg.region_name, z.zone_name, ta.ta_name,
       o.our_units, COALESCE(c.comp_units, 0) AS competitor_units,
       ROUND(o.our_units::numeric
             / NULLIF(o.our_units + COALESCE(c.comp_units, 0), 0) * 100, 1) AS market_share_pct
FROM ours o
LEFT JOIN comp c ON c.region_id = o.region_id AND c.ta_id = o.ta_id
JOIN catalyst.dim_region rg ON rg.region_id = o.region_id
JOIN catalyst.dim_zone   z  ON z.zone_id = rg.zone_id
JOIN catalyst.dim_therapeutic_area ta ON ta.ta_id = o.ta_id;

-- --- Marketing ROI by channel (INR 5,000 gross margin per conversion) -------
CREATE OR REPLACE VIEW catalyst.vw_marketing_roi AS
SELECT ca.channel,
       SUM(ms.spend)        AS total_spend,
       SUM(ms.leads)        AS total_leads,
       SUM(ms.conversions)  AS total_conversions,
       ROUND(SUM(ms.conversions) * 5000.0 / NULLIF(SUM(ms.spend), 0), 2) AS roi,
       ROUND(SUM(ms.spend) / NULLIF(SUM(ms.conversions), 0), 0)          AS cost_per_conversion,
       ROUND(SUM(ms.spend) / SUM(SUM(ms.spend)) OVER () * 100, 1)        AS budget_share_pct
FROM catalyst.fact_marketing_spend ms
JOIN catalyst.dim_campaign ca ON ca.campaign_id = ms.campaign_id
GROUP BY ca.channel;

-- --- Monthly portfolio trend (the stagnation the CCO sees) ------------------
CREATE OR REPLACE VIEW catalyst.vw_monthly_portfolio AS
SELECT m.month_id, m.month_date, m.year, m.quarter, m.fiscal_year,
       COALESCE(SUM(r.revenue), 0)           AS revenue,
       COALESCE(SUM(r.units_prescribed), 0)  AS units,
       COALESCE(SUM(r.new_patient_count), 0) AS new_patients
FROM catalyst.dim_month m
LEFT JOIN catalyst.fact_prescriptions r ON r.month_id = m.month_id
WHERE m.is_forecast = FALSE
GROUP BY m.month_id, m.month_date, m.year, m.quarter, m.fiscal_year
ORDER BY m.month_id;
