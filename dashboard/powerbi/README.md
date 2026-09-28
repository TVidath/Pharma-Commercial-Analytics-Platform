# Pharma Commercial Analytics Platform — Power BI Executive Dashboard (Build Spec)

**Status:** Build-ready specification · **Audience:** BI developer
**Companion:** a runnable Streamlit mirror lives in [`../streamlit/`](../streamlit/) — use it to preview the layouts and validate numbers.

This document specifies the Power BI dashboard end-to-end: data model, relationships, the DAX measure library, and all eight page layouts. It is written so a developer can build the `.pbix` without further input. (A native `.pbix` can't be generated outside Power BI Desktop, so this spec + the Streamlit app are the deliverable.)

---

## 1. Data source & refresh

**Connect** to the PostgreSQL `catalyst` schema (Get Data → PostgreSQL → `localhost:5432/catalyst`), **Import** mode.

Import these tables/views (all built by Milestones 2–7):

| Object | Role | Grain |
|--------|------|-------|
| `dim_month` | Date dimension | month |
| `dim_zone`, `dim_region`, `dim_territory` | Geography | — |
| `dim_sales_rep`, `dim_regional_manager` | Field org | — |
| `dim_doctor`, `dim_hospital` | Customers | — |
| `dim_therapeutic_area`, `dim_product`, `dim_campaign` | Product/promo | — |
| `fact_prescriptions` | Sales fact | doctor×product×month |
| `fact_competitor_rx` | Competitor volume | doctor×TA×month |
| `fact_sales_calls` | Field activity | rep×doctor×month |
| `fact_marketing_spend` | Marketing | campaign×region×month |
| `doctor_segments` | Segmentation (M4) | doctor |
| `hospital_segments` | Hospital tiers (M4) | hospital |
| `doctor_opportunity_score` | Opportunity score (M6) | doctor |
| `territory_plan`, `doctor_call_plan` | Optimization (M7) | territory / doctor |

> For a **no-database** build, point Get Data at `data/processed/*.csv` and `data/processed/dashboard/*.csv` instead — identical schema.

**Refresh:** scheduled daily; the pipeline (`make build && make db-load`) rebuilds sources deterministically.

---

## 2. Star data model

```
                         dim_month (Date table)
                              │
   dim_zone ─ dim_region ─ dim_territory ─ dim_doctor ─┬─ fact_prescriptions ─ dim_product ─ dim_therapeutic_area
                    │            │             │        ├─ fact_sales_calls ── dim_sales_rep
                    │            │             │        ├─ fact_competitor_rx
             fact_marketing_spend│             ├─ doctor_segments (1:1)
                    │       dim_hospital        ├─ doctor_opportunity_score (1:1)
               dim_campaign  hospital_segments  └─ doctor_call_plan (1:1)
```

**Relationships** (single-direction, one→many from dim to fact):

| From (1) | To (many) | Key |
|----------|-----------|-----|
| dim_month[month_id] | each fact[month_id] | month_id |
| dim_doctor[doctor_id] | fact_prescriptions, fact_sales_calls, fact_competitor_rx, doctor_segments, doctor_opportunity_score, doctor_call_plan | doctor_id |
| dim_product[product_id] | fact_prescriptions, fact_marketing_spend, dim_campaign | product_id |
| dim_therapeutic_area[ta_id] | dim_product, fact_competitor_rx | ta_id |
| dim_territory[territory_id] | dim_doctor, dim_hospital, dim_sales_rep, territory_plan | territory_id |
| dim_region[region_id] | dim_territory, fact_marketing_spend | region_id |
| dim_zone[zone_id] | dim_region | zone_id |
| dim_campaign[campaign_id] | fact_marketing_spend | campaign_id |
| dim_hospital[hospital_id] | dim_doctor, hospital_segments | hospital_id |

**Mark `dim_month` as the Date table** (`month_date`). Hierarchies:
- **Geography:** Zone → Region → Territory → City
- **Date:** Year → Quarter → Month
- **Product:** Therapeutic Area → Brand

---

## 3. DAX measure library

Create a dedicated `_Measures` table. Grouped below.

```DAX
-- ===== Core volume & value =====
Revenue          = SUM ( fact_prescriptions[revenue] )
Units            = SUM ( fact_prescriptions[units_prescribed] )
New Patients     = SUM ( fact_prescriptions[new_patient_count] )
Gross Margin =
    SUMX ( fact_prescriptions,
        fact_prescriptions[units_prescribed]
        * ( RELATED ( dim_product[unit_price] ) - RELATED ( dim_product[cost_per_unit] ) ) )
Gross Margin %   = DIVIDE ( [Gross Margin], [Revenue] )

-- ===== Time intelligence =====
Revenue TTM =
    CALCULATE ( [Revenue],
        DATESINPERIOD ( dim_month[month_date], MAX ( dim_month[month_date] ), -12, MONTH ) )
Revenue PY  = CALCULATE ( [Revenue], DATEADD ( dim_month[month_date], -12, MONTH ) )
Revenue YoY % = DIVIDE ( [Revenue] - [Revenue PY], [Revenue PY] )
Revenue 3M Avg =
    AVERAGEX ( DATESINPERIOD ( dim_month[month_date], MAX(dim_month[month_date]), -3, MONTH ),
               [Revenue] )

-- ===== Market / competition =====
Competitor Units = SUM ( fact_competitor_rx[competitor_units] )
Market Share %   = DIVIDE ( [Units], [Units] + [Competitor Units] )
Market Size      = [Units] + [Competitor Units]

-- ===== Field-force effectiveness =====
Calls Made       = SUM ( fact_sales_calls[calls_made] )
Calls Planned    = SUM ( fact_sales_calls[calls_planned] )
Rx per Call      = DIVIDE ( [Units], [Calls Made] )
Call Adherence % = DIVIDE ( [Calls Made], [Calls Planned] )
Doctors Covered  = CALCULATE ( DISTINCTCOUNT ( fact_sales_calls[doctor_id] ),
                               fact_sales_calls[calls_made] > 0 )
Coverage %       = DIVIDE ( [Doctors Covered], DISTINCTCOUNT ( dim_doctor[doctor_id] ) )
Rep Productivity = DIVIDE ( [Revenue TTM], DISTINCTCOUNT ( dim_sales_rep[rep_id] ) )

-- ===== Marketing =====
Marketing Spend  = SUM ( fact_marketing_spend[spend] )
Conversions      = SUM ( fact_marketing_spend[conversions] )
Marketing ROI    = DIVIDE ( [Conversions] * 5000, [Marketing Spend] )   -- ₹5,000 margin/conversion
Cost per Conversion = DIVIDE ( [Marketing Spend], [Conversions] )
Marketing % of Rev  = DIVIDE ( [Marketing Spend], [Revenue] )

-- ===== Segmentation & opportunity =====
White Space (Cr)  = DIVIDE ( SUM ( doctor_segments[white_space_value] ), 10000000 )
Avg Opportunity Score = AVERAGE ( doctor_opportunity_score[opportunity_score] )
P1 Doctors = CALCULATE ( COUNTROWS ( doctor_opportunity_score ),
                         doctor_opportunity_score[priority_tier] = "P1" )
Doctors = DISTINCTCOUNT ( dim_doctor[doctor_id] )

-- ===== RAG / target example =====
Coverage RAG =
    VAR c = [Coverage %]
    RETURN SWITCH ( TRUE(), c >= 0.85, "🟢", c >= 0.70, "🟡", "🔴" )
```

Format: Revenue/Margin as `#,0,,` "₹ Cr" where dividing by 1e7, percentages 1 dp, ROI as `0.0"×"`.

---

## 4. Report theme

Apply a JSON theme with the validated palette:

| Role | Hex |
|------|-----|
| Primary / series-1 | `#2a78d6` |
| Positive | `#008300` |
| Warning | `#eda100` |
| Negative | `#e34948` |
| Neutral | `#898781` |
| Background | `#fcfcfb` |
| Gridline | `#e1e0d9` |

Fonts: Segoe UI. Slicers as a top strip: **Date range, Zone, Region, Therapeutic Area, Product**. Sync slicers across pages.

---

## 5. Page layouts (7)

Each page: KPI cards top strip, 2–3 core visuals, one detail table.

### Page 1 — Overview
- **Cards:** Revenue TTM, Revenue YoY %, White Space (Cr), Marketing ROI.
- **Line:** Revenue by month + 3-mo avg (title flags the flat trend).
- **Bar (h):** Opportunity register (White space / Share recapture / Marketing) by ₹ Cr.

### Page 2 — Sales Performance
- **Cards:** Units TTM, Rx per Call, Coverage %, Call Adherence %.
- **Column:** Avg calls/doctor by **priority tier** (P1/P2/P3) — the "effort inverted to opportunity" story.
- **Column:** White space by tier.
- **Table:** Rep productivity by rep (Revenue, Calls, Rx/Call, Coverage %, quartile).

### Page 3 — Regional Performance
- **Map (or filled bar):** Revenue by region.
- **Scatter:** Market Share % (x) vs Revenue YoY % (y), bubble = Revenue — laggard quadrant highlighted.
- **Bar (h):** White Space by region.
- **Slicer:** Zone. **Table:** region scorecard (Rev, YoY, Share, Coverage, White space).

### Page 4 — Doctor Segmentation
- **Matrix / heatmap:** Potential tier × Value tier (doctor counts) — the 9-box.
- **Donut:** White space by action (Increase/Maintain/Reduce).
- **Table:** segment summary (segment, action, doctors, % revenue, white space) + drill to doctor list with opportunity score.

### Page 5 — Hospital Analysis
- **Cards:** Hospitals, Platinum+Gold count, Affiliated value.
- **Column:** Affiliated value by tier (Platinum→Bronze).
- **Column:** Hospitals by type.
- **Table:** top hospitals (name, type, region, tier, beds, affiliated doctors, value).

### Page 6 — Marketing ROI
- **Scatter:** Budget share % (x) vs ROI (y), bubble = spend, break-even line at 1.0× — the misallocation.
- **Column:** ROI by channel (colour = good/warning/critical).
- **Table:** channel (spend, ROI, cost/conversion, budget share) + recommended reweight.

### Page 7 — Product Analysis
- **Scatter:** YoY growth (x) vs Gross Margin % (y), bubble = revenue, colour = lifecycle — portfolio matrix.
- **Bar (h):** Market share by therapeutic area (headroom).
- **Table:** product scorecard (brand, TA, lifecycle, revenue, growth, margin, spend, rank-in-TA).

---

## 6. Interactivity
- Cross-filtering enabled within each page; slicers synced across pages (Date, Zone, Region, TA, Product).
- Drill-through from any region/segment/product to a doctor-level detail page (opportunity score, calls, white space).
- Bookmarks for "Diagnosis" vs "Recommendation" story flow in a review meeting.

---

## 7. Validation
Reconcile Power BI cards against the Streamlit companion and `reports/*` — Revenue TTM ≈ ₹1,424 Cr, blended Marketing ROI ≈ 1.2×. If they match, the model is wired correctly.
