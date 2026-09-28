-- =============================================================================
-- PHARMA COMMERCIAL ANALYTICS PLATFORM — Business Query Library 3/4: Product & Marketing
-- "Which products need support, and where is marketing money wasted?"
-- Techniques: PARTITION BY (rank within TA), share-of-voice vs share-of-market,
--             running budget share, portfolio mix shift.
-- =============================================================================
SET search_path TO catalyst;

-- Q1 ── Product performance with rank WITHIN therapeutic area and margin.
SELECT ta_name, brand_name, lifecycle_stage,
       ROUND(ttm_revenue / 1e7, 1)  AS ttm_rev_cr,
       yoy_growth_pct,
       ROUND(ttm_margin / 1e7, 1)   AS ttm_margin_cr,
       RANK() OVER (PARTITION BY ta_name ORDER BY ttm_revenue DESC) AS rank_in_ta
FROM vw_product_performance
ORDER BY ta_name, ttm_revenue DESC;

-- Q2 ── Marketing ROI ladder with cumulative budget share (worst ROI first).
SELECT channel,
       ROUND(total_spend / 1e7, 2)                                   AS spend_cr,
       roi,
       budget_share_pct,
       ROUND(SUM(budget_share_pct) OVER (ORDER BY roi ASC), 1)       AS cum_budget_share_pct
FROM vw_marketing_roi
ORDER BY roi ASC;

-- Q3 ── Portfolio MIX SHIFT: each product's share of revenue, TTM vs PY.
WITH p AS (
    SELECT r.product_id,
           SUM(r.revenue) FILTER (WHERE pf.period_band = 'TTM') AS ttm,
           SUM(r.revenue) FILTER (WHERE pf.period_band = 'PY')  AS py
    FROM fact_prescriptions r
    JOIN vw_period_flags pf ON pf.month_id = r.month_id
    GROUP BY r.product_id
)
SELECT pr.brand_name, pr.lifecycle_stage,
       ROUND(100.0 * p.ttm / SUM(p.ttm) OVER (), 1) AS ttm_share_pct,
       ROUND(100.0 * p.py  / SUM(p.py)  OVER (), 1) AS py_share_pct,
       ROUND(100.0 * p.ttm / SUM(p.ttm) OVER ()
           - 100.0 * p.py / SUM(p.py) OVER (), 1)   AS share_shift_pts
FROM p
JOIN dim_product pr ON pr.product_id = p.product_id
ORDER BY share_shift_pts DESC;

-- Q4 ── Share-of-Voice vs Share-of-Market gap by product (over/under-invested).
WITH som AS (   -- share of our units (market presence proxy) by product
    SELECT product_id,
           100.0 * SUM(units_prescribed) / SUM(SUM(units_prescribed)) OVER () AS som_pct
    FROM fact_prescriptions GROUP BY product_id
),
sov AS (        -- share of marketing spend (voice) by product
    SELECT product_id,
           100.0 * SUM(spend) / SUM(SUM(spend)) OVER () AS sov_pct
    FROM fact_marketing_spend GROUP BY product_id
)
SELECT pr.brand_name, pr.lifecycle_stage,
       ROUND(sov.sov_pct, 1) AS share_of_voice_pct,
       ROUND(som.som_pct, 1) AS share_of_market_pct,
       ROUND(sov.sov_pct - som.som_pct, 1) AS sov_minus_som   -- +ve = over-invested
FROM sov JOIN som USING (product_id)
JOIN dim_product pr USING (product_id)
ORDER BY sov_minus_som DESC;
