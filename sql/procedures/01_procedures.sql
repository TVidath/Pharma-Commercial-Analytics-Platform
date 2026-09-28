-- =============================================================================
-- PROJECT CATALYST — Stored Procedures & Functions
-- Engine: PostgreSQL 15+   Schema: catalyst
-- Table-returning FUNCTIONS power parameterised business questions; the
-- PROCEDURE demonstrates an action/reporting routine (CALL).
-- Depends on views in sql/views/01_kpi_views.sql.
-- =============================================================================

SET search_path TO catalyst;

-- --- Top doctors by TTM value, optionally within a region -------------------
-- Business question: "Which doctors should reps prioritise (in region X)?"
CREATE OR REPLACE FUNCTION catalyst.fn_top_doctors(
    p_region_id INT DEFAULT NULL,
    p_limit     INT DEFAULT 20
)
RETURNS TABLE (
    rank_in_scope BIGINT,
    doctor_id     INT,
    doctor_name   TEXT,
    specialty     TEXT,
    region_name   TEXT,
    ttm_revenue   NUMERIC,
    ttm_units     BIGINT,
    decile        INT
)
LANGUAGE sql STABLE AS $$
    WITH ranked AS (
        SELECT k.doctor_id, k.specialty, k.region_name, k.ttm_revenue, k.ttm_units,
               NTILE(10) OVER (ORDER BY k.ttm_revenue DESC) AS decile,
               RANK()    OVER (ORDER BY k.ttm_revenue DESC) AS rnk
        FROM catalyst.vw_doctor_kpi k
        WHERE (p_region_id IS NULL OR k.region_id = p_region_id)
    )
    SELECT r.rnk, r.doctor_id, d.doctor_name::text, r.specialty::text,
           r.region_name::text, r.ttm_revenue, r.ttm_units::bigint, r.decile::int
    FROM ranked r
    JOIN catalyst.dim_doctor d ON d.doctor_id = r.doctor_id
    WHERE r.rnk <= p_limit
    ORDER BY r.rnk;
$$;

-- --- Top hospitals by aggregated affiliated-doctor value --------------------
-- Business question: "Which hospitals have the highest commercial potential?"
CREATE OR REPLACE FUNCTION catalyst.fn_top_hospitals(p_limit INT DEFAULT 20)
RETURNS TABLE (
    hospital_id        INT,
    hospital_name      TEXT,
    hospital_type      TEXT,
    region_name        TEXT,
    bed_count          INT,
    affiliated_doctors BIGINT,
    ttm_revenue        NUMERIC
)
LANGUAGE sql STABLE AS $$
    SELECT h.hospital_id, h.hospital_name::text, h.hospital_type::text,
           rg.region_name::text, h.bed_count,
           COUNT(DISTINCT d.doctor_id) AS affiliated_doctors,
           COALESCE(SUM(k.ttm_revenue), 0) AS ttm_revenue
    FROM catalyst.dim_hospital h
    JOIN catalyst.dim_territory te ON te.territory_id = h.territory_id
    JOIN catalyst.dim_region    rg ON rg.region_id = te.region_id
    LEFT JOIN catalyst.dim_doctor d ON d.hospital_id = h.hospital_id
    LEFT JOIN catalyst.vw_doctor_kpi k ON k.doctor_id = d.doctor_id
    GROUP BY h.hospital_id, h.hospital_name, h.hospital_type, rg.region_name, h.bed_count
    ORDER BY ttm_revenue DESC
    LIMIT p_limit;
$$;

-- --- Underperforming territories: high potential, low coverage --------------
-- Business question: "Which territories are underperforming / under-served?"
CREATE OR REPLACE FUNCTION catalyst.fn_underserved_territories(p_limit INT DEFAULT 20)
RETURNS TABLE (
    territory_id   INT,
    region_name    TEXT,
    zone_name      TEXT,
    rep_name       TEXT,
    n_doctors      BIGINT,
    coverage_pct   NUMERIC,
    total_panel    BIGINT,
    ttm_revenue    NUMERIC
)
LANGUAGE sql STABLE AS $$
    SELECT tk.territory_id, tk.region_name::text, tk.zone_name::text,
           tk.rep_name::text, tk.n_doctors::bigint, tk.coverage_pct,
           tk.total_panel::bigint, tk.ttm_revenue
    FROM catalyst.vw_territory_kpi tk
    WHERE tk.total_panel > (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY total_panel)
                            FROM catalyst.vw_territory_kpi)
    ORDER BY tk.coverage_pct ASC, tk.total_panel DESC
    LIMIT p_limit;
$$;

-- --- Procedure: print a data-summary scorecard to the server log ------------
CREATE OR REPLACE PROCEDURE catalyst.sp_data_summary()
LANGUAGE plpgsql AS $$
DECLARE
    v_rx   BIGINT;
    v_rev  NUMERIC;
    v_docs BIGINT;
BEGIN
    SELECT COUNT(*), SUM(revenue) INTO v_rx, v_rev FROM catalyst.fact_prescriptions;
    SELECT COUNT(*) INTO v_docs FROM catalyst.dim_doctor;
    RAISE NOTICE 'CATALYST DB SUMMARY --------------------------------';
    RAISE NOTICE '  Doctors           : %', v_docs;
    RAISE NOTICE '  Prescription rows : %', v_rx;
    RAISE NOTICE '  Total revenue     : Rs % Cr', ROUND(v_rev / 1e7, 0);
    RAISE NOTICE '----------------------------------------------------';
END;
$$;

-- Usage examples:
--   SELECT * FROM catalyst.fn_top_doctors(NULL, 20);      -- national top 20
--   SELECT * FROM catalyst.fn_top_doctors(13, 10);        -- top 10 in region 13
--   SELECT * FROM catalyst.fn_top_hospitals(15);
--   SELECT * FROM catalyst.fn_underserved_territories(15);
--   CALL   catalyst.sp_data_summary();
