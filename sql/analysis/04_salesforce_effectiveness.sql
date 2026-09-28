-- =============================================================================
-- PROJECT CATALYST — Business Query Library 4/4: Sales-Force Effectiveness
-- "How productive is the field, and where is effort mis-allocated?"
-- Techniques: NTILE quartiles, PERCENT_RANK / CUME_DIST, correlation, coverage.
-- =============================================================================
SET search_path TO catalyst;

-- Q1 ── Rep productivity scorecard with performance quartile and percentile.
SELECT rep_name, region_name, experience_years,
       n_doctors, coverage_pct, total_calls,
       ROUND(ttm_revenue / 1e5, 1)                                   AS ttm_rev_lakh,
       NTILE(4)       OVER (ORDER BY ttm_revenue DESC)               AS performance_quartile,
       ROUND((PERCENT_RANK() OVER (ORDER BY ttm_revenue) * 100)::numeric, 0) AS revenue_percentile
FROM vw_territory_kpi
WHERE employment_status = 'Active'
ORDER BY ttm_revenue DESC
LIMIT 30;

-- Q2 ── Coverage-gap watchlist: high potential, low coverage (re-alignment targets).
SELECT region_name, zone_name, rep_name, employment_status,
       n_doctors, coverage_pct,
       ROUND(total_panel / 1000.0, 1)                                AS panel_000,
       NTILE(4) OVER (ORDER BY total_panel DESC)                     AS potential_quartile
FROM vw_territory_kpi
WHERE coverage_pct < (SELECT percentile_cont(0.25) WITHIN GROUP (ORDER BY coverage_pct)
                      FROM vw_territory_kpi)
  AND total_panel  > (SELECT percentile_cont(0.50) WITHIN GROUP (ORDER BY total_panel)
                      FROM vw_territory_kpi)
ORDER BY total_panel DESC
LIMIT 20;

-- Q3 ── Diminishing returns in SQL: Rx-per-call by call-intensity decile.
WITH doc AS (
    SELECT d.doctor_id,
           COALESCE(c.calls_made, 0) AS calls,
           COALESCE(r.units, 0)      AS units
    FROM dim_doctor d
    LEFT JOIN (SELECT doctor_id, SUM(calls_made) AS calls_made FROM fact_sales_calls GROUP BY doctor_id) c
           ON c.doctor_id = d.doctor_id
    LEFT JOIN (SELECT doctor_id, SUM(units_prescribed) AS units FROM fact_prescriptions GROUP BY doctor_id) r
           ON r.doctor_id = d.doctor_id
),
binned AS (
    SELECT doctor_id, calls, units,
           NTILE(10) OVER (ORDER BY calls) AS call_decile
    FROM doc
)
SELECT call_decile,
       COUNT(*)                                            AS doctors,
       ROUND(AVG(calls), 1)                                AS avg_calls,
       ROUND(SUM(units)::numeric / NULLIF(SUM(calls), 0), 1) AS rx_per_call
FROM binned
GROUP BY call_decile
ORDER BY call_decile;

-- Q4 ── Effort-vs-opportunity correlation (P1) straight from SQL:
--       corr(calls, current Rx) should far exceed corr(calls, potential/panel).
WITH doc AS (
    SELECT d.doctor_id, d.patient_panel_size AS panel,
           COALESCE(SUM(c.calls_made), 0)     AS calls,
           COALESCE(SUM(r.units_prescribed), 0) AS units
    FROM dim_doctor d
    LEFT JOIN fact_sales_calls   c ON c.doctor_id = d.doctor_id
    LEFT JOIN fact_prescriptions r ON r.doctor_id = d.doctor_id
    GROUP BY d.doctor_id, d.patient_panel_size
)
SELECT ROUND(corr(calls, units)::numeric, 2) AS corr_calls_vs_current_rx,
       ROUND(corr(calls, panel)::numeric, 2) AS corr_calls_vs_potential
FROM doc;
