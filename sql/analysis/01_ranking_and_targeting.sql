-- =============================================================================
-- PHARMA COMMERCIAL ANALYTICS PLATFORM — Business Query Library 1/4: Ranking & Targeting
-- "Which doctors and hospitals should reps prioritise?"
-- Techniques: RANK, DENSE_RANK, ROW_NUMBER, NTILE, SUM() OVER, PARTITION BY.
-- Run:  psql -f sql/analysis/01_ranking_and_targeting.sql
-- =============================================================================
SET search_path TO catalyst;

-- Q1 ── National top-25 prescribers with value decile and cumulative share.
--      Shows how concentrated revenue is (Pareto) via a running window total.
SELECT
    RANK()       OVER (ORDER BY ttm_revenue DESC)                       AS rnk,
    NTILE(10)    OVER (ORDER BY ttm_revenue DESC)                       AS decile,
    doctor_id, specialty, region_name,
    ROUND(ttm_revenue / 1e5, 1)                                        AS ttm_rev_lakh,
    ROUND(100.0 * ttm_revenue / SUM(ttm_revenue) OVER (), 3)           AS pct_of_total,
    ROUND(100.0 * SUM(ttm_revenue) OVER (ORDER BY ttm_revenue DESC)
                / SUM(ttm_revenue) OVER (), 1)                          AS cumulative_pct
FROM vw_doctor_kpi
ORDER BY ttm_revenue DESC
LIMIT 25;

-- Q2 ── The #1 prescriber in every region (one row per region).
--      ROW_NUMBER partitioned by region -> pick the leader.
SELECT region_name, doctor_id, specialty, ROUND(ttm_revenue / 1e5, 1) AS ttm_rev_lakh
FROM (
    SELECT k.*, ROW_NUMBER() OVER (PARTITION BY region_id ORDER BY ttm_revenue DESC) AS rn
    FROM vw_doctor_kpi k
) x
WHERE rn = 1
ORDER BY ttm_rev_lakh DESC;

-- Q3 ── Doctor decile MIGRATION: are top prescribers growing or slipping?
--      Compare TTM decile vs prior-year decile per doctor.
WITH per_doc AS (
    SELECT r.doctor_id,
           SUM(r.revenue) FILTER (WHERE pf.period_band = 'TTM') AS ttm_rev,
           SUM(r.revenue) FILTER (WHERE pf.period_band = 'PY')  AS py_rev
    FROM fact_prescriptions r
    JOIN vw_period_flags pf ON pf.month_id = r.month_id
    GROUP BY r.doctor_id
),
deciled AS (
    SELECT doctor_id,
           NTILE(10) OVER (ORDER BY COALESCE(ttm_rev, 0) DESC) AS ttm_decile,
           NTILE(10) OVER (ORDER BY COALESCE(py_rev, 0)  DESC) AS py_decile
    FROM per_doc
)
SELECT (py_decile - ttm_decile) AS deciles_improved,   -- +ve = moved UP
       COUNT(*)                 AS doctors
FROM deciled
GROUP BY 1
ORDER BY 1 DESC;

-- Q4 ── Top-15 hospitals by aggregated affiliated-doctor value + doctors/bed.
SELECT h.hospital_id, h.hospital_name, h.hospital_type, rg.region_name,
       h.bed_count,
       COUNT(DISTINCT d.doctor_id)                             AS affiliated_doctors,
       ROUND(SUM(k.ttm_revenue) / 1e5, 1)                      AS ttm_rev_lakh,
       DENSE_RANK() OVER (ORDER BY SUM(k.ttm_revenue) DESC)    AS value_rank
FROM dim_hospital h
JOIN dim_territory te ON te.territory_id = h.territory_id
JOIN dim_region    rg ON rg.region_id = te.region_id
JOIN dim_doctor    d  ON d.hospital_id = h.hospital_id
JOIN vw_doctor_kpi k  ON k.doctor_id = d.doctor_id
GROUP BY h.hospital_id, h.hospital_name, h.hospital_type, rg.region_name, h.bed_count
ORDER BY SUM(k.ttm_revenue) DESC
LIMIT 15;
