-- =============================================================================
-- PHARMA COMMERCIAL ANALYTICS PLATFORM — Business Query Library 2/4: Regional & Growth
-- "Which regions are winning/losing, and how fast?"
-- Techniques: LAG/LEAD, moving-average window frames, ROLLUP, RANK, share.
-- =============================================================================
SET search_path TO catalyst;

-- Q1 ── Regional scorecard: TTM revenue, YoY growth, rank, contribution.
WITH reg AS (
    SELECT te.region_id,
           SUM(r.revenue) FILTER (WHERE pf.period_band = 'TTM') AS ttm_rev,
           SUM(r.revenue) FILTER (WHERE pf.period_band = 'PY')  AS py_rev
    FROM fact_prescriptions r
    JOIN dim_doctor d    ON d.doctor_id = r.doctor_id
    JOIN dim_territory te ON te.territory_id = d.territory_id
    JOIN vw_period_flags pf ON pf.month_id = r.month_id
    GROUP BY te.region_id
)
SELECT rg.region_name, z.zone_name,
       ROUND(reg.ttm_rev / 1e7, 1)                                       AS ttm_rev_cr,
       ROUND(100.0 * (reg.ttm_rev - reg.py_rev) / NULLIF(reg.py_rev, 0), 1) AS yoy_growth_pct,
       RANK() OVER (ORDER BY reg.ttm_rev DESC)                           AS revenue_rank,
       ROUND(100.0 * reg.ttm_rev / SUM(reg.ttm_rev) OVER (), 1)          AS pct_of_national
FROM reg
JOIN dim_region rg ON rg.region_id = reg.region_id
JOIN dim_zone   z  ON z.zone_id = rg.zone_id
ORDER BY reg.ttm_rev DESC;

-- Q2 ── Portfolio momentum: month-over-month growth + 3-month moving average.
--      Window frame ROWS BETWEEN 2 PRECEDING AND CURRENT ROW.
SELECT month_id,
       ROUND(revenue / 1e7, 2)                                                   AS rev_cr,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month_id))
                   / NULLIF(LAG(revenue) OVER (ORDER BY month_id), 0), 1)        AS mom_growth_pct,
       ROUND(AVG(revenue) OVER (ORDER BY month_id
             ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) / 1e7, 2)                 AS rev_cr_ma3
FROM vw_monthly_portfolio
ORDER BY month_id;

-- Q3 ── Zone -> nation revenue rollup (subtotals + grand total via ROLLUP).
SELECT COALESCE(z.zone_name, 'ALL ZONES')      AS zone,
       ROUND(SUM(r.revenue) / 1e7, 1)          AS ttm_rev_cr,
       COUNT(DISTINCT d.doctor_id)             AS active_doctors
FROM fact_prescriptions r
JOIN dim_doctor d     ON d.doctor_id = r.doctor_id
JOIN dim_territory te ON te.territory_id = d.territory_id
JOIN dim_region rg    ON rg.region_id = te.region_id
JOIN dim_zone z       ON z.zone_id = rg.zone_id
JOIN vw_period_flags pf ON pf.month_id = r.month_id AND pf.period_band = 'TTM'
GROUP BY ROLLUP (z.zone_name)
ORDER BY (z.zone_name IS NULL), ttm_rev_cr DESC;

-- Q4 ── Weakest market share: region x TA cells where we trail, ranked worst-first.
SELECT region_name, zone_name, ta_name, market_share_pct,
       RANK() OVER (ORDER BY market_share_pct ASC) AS weakest_rank
FROM vw_region_market_share
WHERE market_share_pct < 45
ORDER BY market_share_pct ASC
LIMIT 15;
