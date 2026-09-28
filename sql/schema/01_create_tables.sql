-- =============================================================================
-- PHARMA COMMERCIAL ANALYTICS PLATFORM — Database Schema (DDL)
-- Engine   : PostgreSQL 15+
-- Schema   : catalyst
-- Pattern  : Dimensional (star/snowflake) model for commercial analytics
-- Milestone: M1 (schema) — views & stored procedures added in M2
-- Notes    : Derived scores (potential/influence/opportunity) are NOT stored
--            here; they are computed in the analytics layer. Dimensions hold
--            only the drivers from which those scores are derived.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS catalyst;
SET search_path TO catalyst;

-- Idempotent rebuild (safe re-run during development)
DROP TABLE IF EXISTS catalyst.fact_marketing_spend  CASCADE;
DROP TABLE IF EXISTS catalyst.fact_sales_calls       CASCADE;
DROP TABLE IF EXISTS catalyst.fact_competitor_rx     CASCADE;
DROP TABLE IF EXISTS catalyst.fact_prescriptions     CASCADE;
DROP TABLE IF EXISTS catalyst.dim_campaign           CASCADE;
DROP TABLE IF EXISTS catalyst.dim_competitor_product CASCADE;
DROP TABLE IF EXISTS catalyst.dim_product            CASCADE;
DROP TABLE IF EXISTS catalyst.dim_therapeutic_area   CASCADE;
DROP TABLE IF EXISTS catalyst.dim_doctor             CASCADE;
DROP TABLE IF EXISTS catalyst.dim_hospital           CASCADE;
DROP TABLE IF EXISTS catalyst.dim_sales_rep          CASCADE;
DROP TABLE IF EXISTS catalyst.dim_territory          CASCADE;
DROP TABLE IF EXISTS catalyst.dim_regional_manager   CASCADE;
DROP TABLE IF EXISTS catalyst.dim_region             CASCADE;
DROP TABLE IF EXISTS catalyst.dim_zone               CASCADE;
DROP TABLE IF EXISTS catalyst.dim_month              CASCADE;

-- =============================================================================
-- DIMENSIONS
-- =============================================================================

-- --- Time (monthly grain) ----------------------------------------------------
CREATE TABLE catalyst.dim_month (
    month_id     INTEGER      PRIMARY KEY,               -- YYYYMM, e.g. 202307
    month_date   DATE         NOT NULL,                  -- first day of month
    year         SMALLINT     NOT NULL,
    quarter      SMALLINT     NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    month_num    SMALLINT     NOT NULL CHECK (month_num BETWEEN 1 AND 12),
    month_name   VARCHAR(9)   NOT NULL,
    fiscal_year  VARCHAR(9)   NOT NULL,                  -- e.g. 'FY2024-25'
    is_forecast  BOOLEAN      NOT NULL DEFAULT FALSE
);
COMMENT ON TABLE catalyst.dim_month IS 'Monthly calendar dimension; month_id is a sortable YYYYMM integer.';

-- --- Geography hierarchy: Zone -> Region -> Territory ------------------------
CREATE TABLE catalyst.dim_zone (
    zone_id      INTEGER      PRIMARY KEY,
    zone_name    VARCHAR(20)  NOT NULL UNIQUE            -- North / South / East / West
);

CREATE TABLE catalyst.dim_region (
    region_id    INTEGER      PRIMARY KEY,
    zone_id      INTEGER      NOT NULL REFERENCES catalyst.dim_zone(zone_id),
    region_name  VARCHAR(60)  NOT NULL,
    state        VARCHAR(60)  NOT NULL,
    rm_id        INTEGER                                 -- FK added after RM table (avoids cycle)
);

CREATE TABLE catalyst.dim_regional_manager (
    rm_id            INTEGER  PRIMARY KEY,
    region_id        INTEGER  NOT NULL REFERENCES catalyst.dim_region(region_id),
    rm_name          VARCHAR(80) NOT NULL,
    experience_years SMALLINT NOT NULL CHECK (experience_years >= 0)
);
-- close the region -> RM reference now that the table exists.
-- DEFERRABLE: dim_region and dim_regional_manager reference each other (a 1:1
-- cycle), so the check is deferred to COMMIT, letting a single bulk-load
-- transaction insert both before validation.
ALTER TABLE catalyst.dim_region
    ADD CONSTRAINT fk_region_rm FOREIGN KEY (rm_id)
    REFERENCES catalyst.dim_regional_manager(rm_id)
    DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE catalyst.dim_territory (
    territory_id     INTEGER  PRIMARY KEY,
    region_id        INTEGER  NOT NULL REFERENCES catalyst.dim_region(region_id),
    rep_id           INTEGER,                            -- FK added after rep table
    territory_name   VARCHAR(60) NOT NULL,
    city             VARCHAR(60) NOT NULL,
    urbanicity_tier  VARCHAR(10) NOT NULL
        CHECK (urbanicity_tier IN ('Metro','Tier-1','Tier-2','Tier-3'))
);

CREATE TABLE catalyst.dim_sales_rep (
    rep_id             INTEGER PRIMARY KEY,
    region_id          INTEGER NOT NULL REFERENCES catalyst.dim_region(region_id),
    rm_id              INTEGER NOT NULL REFERENCES catalyst.dim_regional_manager(rm_id),
    territory_id       INTEGER NOT NULL UNIQUE          -- one rep per territory
                                REFERENCES catalyst.dim_territory(territory_id),
    rep_name           VARCHAR(80) NOT NULL,
    experience_years   SMALLINT NOT NULL CHECK (experience_years >= 0),
    joining_date       DATE     NOT NULL,
    monthly_call_target SMALLINT NOT NULL CHECK (monthly_call_target > 0),
    employment_status  VARCHAR(12) NOT NULL DEFAULT 'Active'
        CHECK (employment_status IN ('Active','On-Leave','Vacant'))
);
-- close the territory -> rep reference (territory <-> rep is also a 1:1 cycle)
ALTER TABLE catalyst.dim_territory
    ADD CONSTRAINT fk_territory_rep FOREIGN KEY (rep_id)
    REFERENCES catalyst.dim_sales_rep(rep_id)
    DEFERRABLE INITIALLY DEFERRED;

-- --- Customers: Hospital, Doctor --------------------------------------------
CREATE TABLE catalyst.dim_hospital (
    hospital_id           INTEGER PRIMARY KEY,
    territory_id          INTEGER NOT NULL REFERENCES catalyst.dim_territory(territory_id),
    hospital_name         VARCHAR(100) NOT NULL,
    hospital_type         VARCHAR(20)  NOT NULL
        CHECK (hospital_type IN ('Corporate','Private','Government','Nursing Home','Clinic')),
    bed_count             INTEGER  NOT NULL CHECK (bed_count >= 0),
    annual_patient_volume INTEGER  NOT NULL CHECK (annual_patient_volume >= 0),
    established_year      SMALLINT NOT NULL
);

CREATE TABLE catalyst.dim_doctor (
    doctor_id          INTEGER PRIMARY KEY,
    hospital_id        INTEGER REFERENCES catalyst.dim_hospital(hospital_id),  -- nullable: standalone practitioners
    territory_id       INTEGER NOT NULL REFERENCES catalyst.dim_territory(territory_id),
    doctor_name        VARCHAR(80) NOT NULL,
    specialty          VARCHAR(40) NOT NULL,
    years_in_practice  SMALLINT NOT NULL CHECK (years_in_practice >= 0),
    patient_panel_size INTEGER  NOT NULL CHECK (patient_panel_size >= 0),  -- driver of potential
    kol_flag           BOOLEAN  NOT NULL DEFAULT FALSE                     -- key opinion leader
);
COMMENT ON COLUMN catalyst.dim_doctor.patient_panel_size IS
    'Latent prescribing-capacity driver; potential/opportunity scores are derived downstream, not stored here.';

-- --- Products & competition --------------------------------------------------
CREATE TABLE catalyst.dim_therapeutic_area (
    ta_id                INTEGER PRIMARY KEY,
    ta_name              VARCHAR(40) NOT NULL UNIQUE,
    seasonality_profile  VARCHAR(20) NOT NULL           -- e.g. 'Winter-peak','Flat','Summer-peak'
);

CREATE TABLE catalyst.dim_product (
    product_id       INTEGER PRIMARY KEY,
    ta_id            INTEGER NOT NULL REFERENCES catalyst.dim_therapeutic_area(ta_id),
    brand_name       VARCHAR(40) NOT NULL UNIQUE,
    molecule         VARCHAR(60) NOT NULL,
    dosage_form      VARCHAR(30) NOT NULL,
    unit_price       NUMERIC(10,2) NOT NULL CHECK (unit_price > 0),
    cost_per_unit    NUMERIC(10,2) NOT NULL CHECK (cost_per_unit >= 0),
    launch_date      DATE NOT NULL,
    lifecycle_stage  VARCHAR(12) NOT NULL
        CHECK (lifecycle_stage IN ('Launch','Growth','Mature','Decline')),
    CONSTRAINT chk_margin_positive CHECK (unit_price > cost_per_unit)
);

CREATE TABLE catalyst.dim_competitor_product (
    competitor_product_id INTEGER PRIMARY KEY,
    ta_id                 INTEGER NOT NULL REFERENCES catalyst.dim_therapeutic_area(ta_id),
    competitor_brand      VARCHAR(40) NOT NULL,
    company               VARCHAR(60) NOT NULL,
    unit_price            NUMERIC(10,2) NOT NULL CHECK (unit_price > 0)
);

CREATE TABLE catalyst.dim_campaign (
    campaign_id     INTEGER PRIMARY KEY,
    product_id      INTEGER NOT NULL REFERENCES catalyst.dim_product(product_id),
    campaign_name   VARCHAR(80) NOT NULL,
    channel         VARCHAR(30) NOT NULL
        CHECK (channel IN ('Digital & CME','Print & Conferences','Field Samples',
                           'Patient Programs','KOL Engagement')),
    objective       VARCHAR(60) NOT NULL,
    start_month_id  INTEGER NOT NULL REFERENCES catalyst.dim_month(month_id),
    end_month_id    INTEGER NOT NULL REFERENCES catalyst.dim_month(month_id)
);

-- =============================================================================
-- FACTS
-- =============================================================================

-- Core commercial fact: our prescriptions.  Grain: doctor x product x month
CREATE TABLE catalyst.fact_prescriptions (
    rx_id             BIGSERIAL PRIMARY KEY,
    doctor_id         INTEGER NOT NULL REFERENCES catalyst.dim_doctor(doctor_id),
    product_id        INTEGER NOT NULL REFERENCES catalyst.dim_product(product_id),
    month_id          INTEGER NOT NULL REFERENCES catalyst.dim_month(month_id),
    units_prescribed  INTEGER NOT NULL CHECK (units_prescribed >= 0),
    revenue           NUMERIC(14,2) NOT NULL CHECK (revenue >= 0),
    new_patient_count INTEGER NOT NULL DEFAULT 0 CHECK (new_patient_count >= 0),
    CONSTRAINT uq_rx_grain UNIQUE (doctor_id, product_id, month_id)   -- enforce grain
);

-- Competitor volume for share-of-market.  Grain: doctor x TA x month
CREATE TABLE catalyst.fact_competitor_rx (
    comp_rx_id       BIGSERIAL PRIMARY KEY,
    doctor_id        INTEGER NOT NULL REFERENCES catalyst.dim_doctor(doctor_id),
    ta_id            INTEGER NOT NULL REFERENCES catalyst.dim_therapeutic_area(ta_id),
    month_id         INTEGER NOT NULL REFERENCES catalyst.dim_month(month_id),
    competitor_units INTEGER NOT NULL CHECK (competitor_units >= 0),
    CONSTRAINT uq_comp_rx_grain UNIQUE (doctor_id, ta_id, month_id)
);

-- Field activity.  Grain: rep x doctor x month
CREATE TABLE catalyst.fact_sales_calls (
    call_id         BIGSERIAL PRIMARY KEY,
    rep_id          INTEGER NOT NULL REFERENCES catalyst.dim_sales_rep(rep_id),
    doctor_id       INTEGER NOT NULL REFERENCES catalyst.dim_doctor(doctor_id),
    month_id        INTEGER NOT NULL REFERENCES catalyst.dim_month(month_id),
    calls_planned   SMALLINT NOT NULL CHECK (calls_planned >= 0),
    calls_made      SMALLINT NOT NULL CHECK (calls_made >= 0),
    samples_dropped SMALLINT NOT NULL DEFAULT 0 CHECK (samples_dropped >= 0),
    CONSTRAINT uq_call_grain UNIQUE (rep_id, doctor_id, month_id),
    CONSTRAINT chk_calls_made_reasonable CHECK (calls_made <= calls_planned + 2)
);

-- Marketing investment.  Grain: campaign x region x month
CREATE TABLE catalyst.fact_marketing_spend (
    spend_id     BIGSERIAL PRIMARY KEY,
    campaign_id  INTEGER NOT NULL REFERENCES catalyst.dim_campaign(campaign_id),
    product_id   INTEGER NOT NULL REFERENCES catalyst.dim_product(product_id),
    region_id    INTEGER NOT NULL REFERENCES catalyst.dim_region(region_id),
    month_id     INTEGER NOT NULL REFERENCES catalyst.dim_month(month_id),
    spend        NUMERIC(14,2) NOT NULL CHECK (spend >= 0),
    leads        INTEGER NOT NULL DEFAULT 0 CHECK (leads >= 0),
    conversions  INTEGER NOT NULL DEFAULT 0 CHECK (conversions >= 0),
    CONSTRAINT uq_spend_grain UNIQUE (campaign_id, region_id, month_id),
    CONSTRAINT chk_conv_le_leads CHECK (conversions <= leads)
);

-- =============================================================================
-- End of schema DDL. Indexes & performance constraints: 02_indexes_constraints.sql
-- =============================================================================
