-- =============================================================================
-- PHARMA COMMERCIAL ANALYTICS PLATFORM — Indexes & Performance Objects
-- Engine   : PostgreSQL 15+   Schema: catalyst
-- Run after: 01_create_tables.sql
-- Rationale : Analytics workload is read-heavy with roll-ups by month, region,
--             product, doctor. We index the hot join/filter paths and the
--             composite (doctor_id, month_id) used across the diagnostic.
-- =============================================================================

SET search_path TO catalyst;

-- --- Foreign-key / filter indexes on dimensions -----------------------------
CREATE INDEX IF NOT EXISTS ix_region_zone        ON catalyst.dim_region(zone_id);
CREATE INDEX IF NOT EXISTS ix_territory_region   ON catalyst.dim_territory(region_id);
CREATE INDEX IF NOT EXISTS ix_rep_region         ON catalyst.dim_sales_rep(region_id);
CREATE INDEX IF NOT EXISTS ix_rep_rm             ON catalyst.dim_sales_rep(rm_id);
CREATE INDEX IF NOT EXISTS ix_hospital_territory ON catalyst.dim_hospital(territory_id);
CREATE INDEX IF NOT EXISTS ix_doctor_territory   ON catalyst.dim_doctor(territory_id);
CREATE INDEX IF NOT EXISTS ix_doctor_hospital    ON catalyst.dim_doctor(hospital_id);
CREATE INDEX IF NOT EXISTS ix_doctor_specialty   ON catalyst.dim_doctor(specialty);
CREATE INDEX IF NOT EXISTS ix_product_ta         ON catalyst.dim_product(ta_id);
CREATE INDEX IF NOT EXISTS ix_campaign_product   ON catalyst.dim_campaign(product_id);
CREATE INDEX IF NOT EXISTS ix_campaign_channel   ON catalyst.dim_campaign(channel);

-- --- Fact indexes: FK columns + hot composites ------------------------------
-- fact_prescriptions (largest table; drives most KPIs)
CREATE INDEX IF NOT EXISTS ix_rx_month           ON catalyst.fact_prescriptions(month_id);
CREATE INDEX IF NOT EXISTS ix_rx_product         ON catalyst.fact_prescriptions(product_id);
CREATE INDEX IF NOT EXISTS ix_rx_doctor_month    ON catalyst.fact_prescriptions(doctor_id, month_id);
CREATE INDEX IF NOT EXISTS ix_rx_product_month   ON catalyst.fact_prescriptions(product_id, month_id);

-- fact_competitor_rx (share-of-market)
CREATE INDEX IF NOT EXISTS ix_comp_doctor_month  ON catalyst.fact_competitor_rx(doctor_id, month_id);
CREATE INDEX IF NOT EXISTS ix_comp_ta_month      ON catalyst.fact_competitor_rx(ta_id, month_id);

-- fact_sales_calls (field effectiveness)
CREATE INDEX IF NOT EXISTS ix_calls_rep_month    ON catalyst.fact_sales_calls(rep_id, month_id);
CREATE INDEX IF NOT EXISTS ix_calls_doctor_month ON catalyst.fact_sales_calls(doctor_id, month_id);

-- fact_marketing_spend (marketing ROI)
CREATE INDEX IF NOT EXISTS ix_spend_region_month ON catalyst.fact_marketing_spend(region_id, month_id);
CREATE INDEX IF NOT EXISTS ix_spend_product      ON catalyst.fact_marketing_spend(product_id);
CREATE INDEX IF NOT EXISTS ix_spend_campaign     ON catalyst.fact_marketing_spend(campaign_id);

-- --- Analyzer hint -----------------------------------------------------------
-- After bulk load (Milestone 2), run ANALYZE so the planner has fresh stats:
--   ANALYZE catalyst.fact_prescriptions;
--   ANALYZE catalyst.fact_sales_calls;
--   ANALYZE catalyst.fact_competitor_rx;
--   ANALYZE catalyst.fact_marketing_spend;

-- =============================================================================
-- End of indexes.
-- =============================================================================
