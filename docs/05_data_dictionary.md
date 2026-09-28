# Pharma Commercial Analytics Platform — Data Dictionary

**Status:** Milestone 1 baseline · **Schema:** `catalyst` (PostgreSQL)

Every column, its type, whether it is a raw driver or a modelled input, and its business meaning. "Gen." column: **R** = raw generated attribute, **D** = derived downstream (not stored in source), **K** = key.

---

## Dimension: `dim_month`
| Column | Type | Gen | Description |
|--------|------|-----|-------------|
| month_id | INT PK | K | `YYYYMM` (e.g. 202307). Sortable, join-friendly business key. |
| month_date | DATE | R | First day of the month. |
| year, quarter, month_num | SMALLINT | R | Calendar parts. |
| month_name | VARCHAR | R | 'January'… |
| fiscal_year | VARCHAR | R | Indian FY (Apr–Mar), e.g. 'FY2024-25'. |
| is_forecast | BOOL | R | TRUE for forecast months (Milestone 6). |

## Dimension: `dim_zone` / `dim_region` / `dim_territory`
| Column | Type | Gen | Description |
|--------|------|-----|-------------|
| zone_id / zone_name | INT / VARCHAR | K/R | North, South, East, West. |
| region_id | INT PK | K | 25 regions. |
| region_name, state | VARCHAR | R | Region label + Indian state. |
| rm_id | INT FK | R | Managing Regional Manager. |
| territory_id | INT PK | K | 600 territories (1 per rep). |
| territory_name, city | VARCHAR | R | Territory label + base city. |
| urbanicity_tier | VARCHAR | R | Metro / Tier-1/2/3 — drives potential & travel. |

## Dimension: `dim_regional_manager`
| Column | Type | Gen | Description |
|--------|------|-----|-------------|
| rm_id | INT PK | K | 25 RMs. |
| region_id | INT FK | R | Region overseen. |
| rm_name | VARCHAR | R | Name. |
| experience_years | SMALLINT | R | Tenure — correlates with region performance. |

## Dimension: `dim_sales_rep`
| Column | Type | Gen | Description |
|--------|------|-----|-------------|
| rep_id | INT PK | K | 600 reps. |
| region_id, rm_id, territory_id | INT FK | R | Org placement; `territory_id` UNIQUE (1 rep/territory). |
| rep_name | VARCHAR | R | Name. |
| experience_years | SMALLINT | R | Tenure — drives conversion/effectiveness. |
| joining_date | DATE | R | Hire date. |
| monthly_call_target | SMALLINT | R | Planned calls/month (capacity). |
| employment_status | VARCHAR | R | Active / On-Leave / Vacant (vacancies create coverage gaps). |

## Dimension: `dim_hospital`
| Column | Type | Gen | Description |
|--------|------|-----|-------------|
| hospital_id | INT PK | K | 1,800 hospitals. |
| territory_id | INT FK | R | Location. |
| hospital_name | VARCHAR | R | Name. |
| hospital_type | VARCHAR | R | Corporate/Private/Government/Nursing Home/Clinic — drives volume & potential. |
| bed_count | INT | R | Size proxy. |
| annual_patient_volume | INT | R | Throughput → commercial potential. |
| established_year | SMALLINT | R | Maturity. |
| *hospital_potential_score* | — | D | Derived (Milestone 7): potential tier. |

## Dimension: `dim_doctor`
| Column | Type | Gen | Description |
|--------|------|-----|-------------|
| doctor_id | INT PK | K | 1,500 doctors. |
| hospital_id | INT FK | R | Primary affiliation (nullable → standalone). |
| territory_id | INT FK | R | Assigned territory (denormalised for query speed). |
| doctor_name | VARCHAR | R | Name. |
| specialty | VARCHAR | R | Cardiologist, Diabetologist, GP, Physician — drives product affinity. |
| years_in_practice | SMALLINT | R | Experience → panel size. |
| patient_panel_size | INT | R | **Latent capacity driver** of potential Rx. |
| kol_flag | BOOL | R | Key opinion leader (influence). |
| *potential_score* | — | D | Derived (M4/M6): modelled prescribing capacity 0–100. |
| *influence_score* | — | D | Derived: KOL + panel + centrality 0–100. |
| *decile* | — | D | Derived: value rank 1–10 within TA/region. |
| *opportunity_realisation* | — | D | Derived: actual Rx ÷ potential Rx. |
| *commercial_opportunity_score* | — | D | Derived (M6): master prioritisation composite. |

## Dimension: `dim_therapeutic_area`
| Column | Type | Gen | Description |
|--------|------|-----|-------------|
| ta_id | INT PK | K | 5 TAs. |
| ta_name | VARCHAR | R | Cardiology, Diabetology, Respiratory, Gastroenterology, Neurology. |
| seasonality_profile | VARCHAR | R | Winter-peak / Summer-peak / Flat — shapes monthly Rx. |

## Dimension: `dim_product`
| Column | Type | Gen | Description |
|--------|------|-----|-------------|
| product_id | INT PK | K | 12 brands. |
| ta_id | INT FK | R | Therapeutic area. |
| brand_name | VARCHAR | R | Marketed brand. |
| molecule | VARCHAR | R | Active ingredient. |
| dosage_form | VARCHAR | R | Tablet/Capsule/Injection/etc. |
| unit_price | NUMERIC | R | Selling price per unit (₹). |
| cost_per_unit | NUMERIC | R | COGS per unit (₹) → margin. |
| launch_date | DATE | R | Market entry. |
| lifecycle_stage | VARCHAR | R | Launch/Growth/Mature/Decline — shapes trend. |

## Dimension: `dim_competitor_product`
| Column | Type | Gen | Description |
|--------|------|-----|-------------|
| competitor_product_id | INT PK | K | 15 competitor brands. |
| ta_id | INT FK | R | Therapeutic area they compete in. |
| competitor_brand, company | VARCHAR | R | Brand & maker. |
| unit_price | NUMERIC | R | Competitor price (share/price analysis). |

## Dimension: `dim_campaign`
| Column | Type | Gen | Description |
|--------|------|-----|-------------|
| campaign_id | INT PK | K | Marketing campaigns. |
| product_id | INT FK | R | Product promoted. |
| campaign_name | VARCHAR | R | Label. |
| channel | VARCHAR | R | Digital & CME / Print & Conferences / Field Samples / Patient Programs / KOL Engagement. |
| objective | VARCHAR | R | Awareness/Adoption/Retention. |
| start_month_id, end_month_id | INT FK | R | Flight window. |

---

## Fact: `fact_prescriptions` — grain: doctor × product × month
| Column | Type | Gen | Description |
|--------|------|-----|-------------|
| rx_id | BIGSERIAL PK | K | Surrogate key. |
| doctor_id, product_id, month_id | INT FK | R | Grain keys (UNIQUE together). |
| units_prescribed | INT | R | Units our brand, that doctor, that month. |
| revenue | NUMERIC | R | units × unit_price (₹). |
| new_patient_count | INT | R | New patients started (acquisition signal). |

## Fact: `fact_competitor_rx` — grain: doctor × TA × month
| Column | Type | Gen | Description |
|--------|------|-----|-------------|
| comp_rx_id | BIGSERIAL PK | K | Surrogate key. |
| doctor_id, ta_id, month_id | INT FK | R | Grain keys. |
| competitor_units | INT | R | Total competitor volume for that doctor/TA/month → market share. |

## Fact: `fact_sales_calls` — grain: rep × doctor × month
| Column | Type | Gen | Description |
|--------|------|-----|-------------|
| call_id | BIGSERIAL PK | K | Surrogate key. |
| rep_id, doctor_id, month_id | INT FK | R | Grain keys. |
| calls_planned | SMALLINT | R | Planned detailing calls. |
| calls_made | SMALLINT | R | Actual calls (adherence, effort). |
| samples_dropped | SMALLINT | R | Samples left (promotional intensity). |

## Fact: `fact_marketing_spend` — grain: campaign × region × month
| Column | Type | Gen | Description |
|--------|------|-----|-------------|
| spend_id | BIGSERIAL PK | K | Surrogate key. |
| campaign_id, product_id, region_id, month_id | INT FK | R | Grain keys. |
| spend | NUMERIC | R | Promotional spend (₹). |
| leads | INT | R | Leads generated. |
| conversions | INT | R | Leads converted (≤ leads). |

---

### Reading note
Columns marked **D (derived)** are shown in *italics* and are **not** present in the raw schema (`sql/schema/01_create_tables.sql`). They are produced by the analytics layer and materialised into views/tables in later milestones. This separation — raw drivers in source, scores in the model — is deliberate and is a point worth making in an architecture review.
