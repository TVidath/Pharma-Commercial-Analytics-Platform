# Project Catalyst — Data Model & ER Diagram

**Status:** Milestone 1 baseline · **Engine:** PostgreSQL · **Schema:** `catalyst`
**Pattern:** Dimensional (star/snowflake) model optimised for commercial analytics.

---

## 1. Modelling approach

We model the commercial world as a **dimensional model**: descriptive *dimensions* (who/what/where) surround measurable *facts* (how much/how many). This is the right pattern for an analytics + BI workload — it makes KPIs, ranking, and Power BI relationships natural, and avoids the join sprawl of a normalised OLTP schema (ADR-4).

**Grain is the first design decision.** We fix it explicitly for each fact:

| Fact | Grain (one row per…) |
|------|----------------------|
| `fact_prescriptions` | doctor × product × month |
| `fact_competitor_rx` | doctor × therapeutic_area × month |
| `fact_sales_calls` | rep × doctor × month |
| `fact_marketing_spend` | campaign × region × month |

**Design decisions worth noting for review:**
- **Derived scores are not stored as raw source data.** Potential / influence / opportunity scores are *outputs* of the analytics layer, materialised into views/tables downstream (Milestones 4–6), not planted as columns in `dim_doctor`. `dim_doctor` holds only the *drivers* (panel size, specialty, hospital tier) from which scores are computed. This keeps source and model cleanly separated.
- **Light snowflaking** on geography (`zone → region → territory`) and therapeutic area, because these hierarchies are reused across many facts and drive roll-ups.
- **Denormalised `territory_id` on doctor and hospital** for query convenience (avoids a 3-hop join on the hottest path), accepting the small redundancy — a standard analytics trade-off.

---

## 2. Entity-relationship diagram

```mermaid
erDiagram
    DIM_ZONE                ||--o{ DIM_REGION            : contains
    DIM_REGION              ||--o{ DIM_TERRITORY         : contains
    DIM_REGION              ||--o| DIM_REGIONAL_MANAGER  : managed_by
    DIM_REGION              ||--o{ DIM_SALES_REP         : employs
    DIM_REGIONAL_MANAGER    ||--o{ DIM_SALES_REP         : supervises
    DIM_TERRITORY           ||--o| DIM_SALES_REP         : assigned_to
    DIM_TERRITORY           ||--o{ DIM_DOCTOR            : locates
    DIM_TERRITORY           ||--o{ DIM_HOSPITAL          : locates
    DIM_HOSPITAL            ||--o{ DIM_DOCTOR            : affiliates
    DIM_THERAPEUTIC_AREA    ||--o{ DIM_PRODUCT           : classifies
    DIM_THERAPEUTIC_AREA    ||--o{ DIM_COMPETITOR_PRODUCT: classifies
    DIM_PRODUCT             ||--o{ DIM_CAMPAIGN          : promotes

    DIM_DOCTOR              ||--o{ FACT_PRESCRIPTIONS     : writes
    DIM_PRODUCT             ||--o{ FACT_PRESCRIPTIONS     : prescribed_as
    DIM_MONTH               ||--o{ FACT_PRESCRIPTIONS     : dated

    DIM_DOCTOR              ||--o{ FACT_COMPETITOR_RX      : writes
    DIM_THERAPEUTIC_AREA    ||--o{ FACT_COMPETITOR_RX      : within
    DIM_MONTH               ||--o{ FACT_COMPETITOR_RX      : dated

    DIM_SALES_REP           ||--o{ FACT_SALES_CALLS        : makes
    DIM_DOCTOR              ||--o{ FACT_SALES_CALLS        : target_of
    DIM_MONTH               ||--o{ FACT_SALES_CALLS        : dated

    DIM_CAMPAIGN            ||--o{ FACT_MARKETING_SPEND     : incurs
    DIM_PRODUCT             ||--o{ FACT_MARKETING_SPEND     : supports
    DIM_REGION              ||--o{ FACT_MARKETING_SPEND     : targeted_at
    DIM_MONTH               ||--o{ FACT_MARKETING_SPEND     : dated

    DIM_ZONE {
        int zone_id PK
        varchar zone_name
    }
    DIM_REGION {
        int region_id PK
        int zone_id FK
        varchar region_name
        varchar state
        int rm_id FK
    }
    DIM_REGIONAL_MANAGER {
        int rm_id PK
        int region_id FK
        varchar rm_name
        int experience_years
    }
    DIM_TERRITORY {
        int territory_id PK
        int region_id FK
        int rep_id FK
        varchar territory_name
        varchar city
        varchar urbanicity_tier
    }
    DIM_SALES_REP {
        int rep_id PK
        int region_id FK
        int rm_id FK
        int territory_id FK
        varchar rep_name
        int experience_years
        date joining_date
        int monthly_call_target
        varchar employment_status
    }
    DIM_HOSPITAL {
        int hospital_id PK
        int territory_id FK
        varchar hospital_name
        varchar hospital_type
        int bed_count
        int annual_patient_volume
        smallint established_year
    }
    DIM_DOCTOR {
        int doctor_id PK
        int hospital_id FK
        int territory_id FK
        varchar doctor_name
        varchar specialty
        int years_in_practice
        int patient_panel_size
        boolean kol_flag
    }
    DIM_THERAPEUTIC_AREA {
        int ta_id PK
        varchar ta_name
        varchar seasonality_profile
    }
    DIM_PRODUCT {
        int product_id PK
        int ta_id FK
        varchar brand_name
        varchar molecule
        numeric unit_price
        numeric cost_per_unit
        varchar lifecycle_stage
        date launch_date
    }
    DIM_COMPETITOR_PRODUCT {
        int competitor_product_id PK
        int ta_id FK
        varchar competitor_brand
        varchar company
        numeric unit_price
    }
    DIM_CAMPAIGN {
        int campaign_id PK
        int product_id FK
        varchar campaign_name
        varchar channel
        int start_month_id
        int end_month_id
    }
    DIM_MONTH {
        int month_id PK
        date month_date
        smallint year
        smallint quarter
        smallint month_num
    }
    FACT_PRESCRIPTIONS {
        bigint rx_id PK
        int doctor_id FK
        int product_id FK
        int month_id FK
        int units_prescribed
        numeric revenue
        int new_patient_count
    }
    FACT_COMPETITOR_RX {
        bigint comp_rx_id PK
        int doctor_id FK
        int ta_id FK
        int month_id FK
        int competitor_units
    }
    FACT_SALES_CALLS {
        bigint call_id PK
        int rep_id FK
        int doctor_id FK
        int month_id FK
        int calls_planned
        int calls_made
        int samples_dropped
    }
    FACT_MARKETING_SPEND {
        bigint spend_id PK
        int campaign_id FK
        int product_id FK
        int region_id FK
        int month_id FK
        numeric spend
        int leads
        int conversions
    }
```

---

## 3. Cardinality summary

| Relationship | Cardinality | Note |
|--------------|-------------|------|
| Zone → Region | 1 : many | 2 zones, 5 regions |
| Region → Territory | 1 : many | 10 territories per region |
| Region → Regional Manager | 1 : 1 | 5 RMs |
| Territory → Sales Rep | 1 : 1 | 50 reps ↔ 50 territories (UNIQUE) |
| Territory → Doctor | 1 : many | ~30 doctors per territory |
| Territory → Hospital | 1 : many | ~3 hospitals per territory |
| Hospital → Doctor | 1 : many | a doctor has one primary affiliation |
| Therapeutic Area → Product | 1 : many | 2 TAs, 5 products |
| Product → Campaign | 1 : many | campaigns promote one product |
| Doctor × Product × Month → Prescriptions | fact | core commercial fact |

---

## 4. Referential integrity & keys

- **Primary keys:** surrogate integer keys on all dimensions; `BIGSERIAL` on facts.
- **Foreign keys:** every fact FK references its dimension PK; ON DELETE RESTRICT (data is analytical, not transactional — we never cascade-delete history).
- **Natural/business keys:** e.g. `month_id` = `YYYYMM` integer (human-readable, sortable, join-friendly).
- **Unique constraints:** `dim_sales_rep.territory_id` UNIQUE (one rep per territory); composite uniqueness on facts at their declared grain to prevent duplicate loads.
- **Check constraints:** non-negative units/spend; `calls_made <= calls_planned * tolerance`; valid enum values (lifecycle_stage, hospital_type, channel).

Full DDL: `sql/schema/01_create_tables.sql`; indexes and constraints: `sql/schema/02_indexes_constraints.sql`.

---

## 5. Volume estimate (for indexing/perf planning)

| Table | Approx. rows | Basis |
|-------|-------------|-------|
| dim_doctor | 1,500 | brief |
| dim_hospital | 150 | brief |
| dim_sales_rep | 50 | brief |
| fact_prescriptions | ~200 K | 1.5k doctors × ~2 products each × 36 months |
| fact_sales_calls | ~180 K | reps call a subset of doctors × 36 months |
| fact_marketing_spend | ~10k | campaigns × regions × months |
| fact_competitor_rx | ~100 K | doctors × relevant TAs × 36 months |

Facts are indexed on `month_id`, the FK columns, and the hot composite `(doctor_id, month_id)` — see indexes DDL.
