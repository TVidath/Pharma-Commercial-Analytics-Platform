# Project Catalyst — KPI Framework & Metric Tree

**Status:** Milestone 1 baseline · **Purpose:** Define every metric once, with formula, grain, and decision use, so the SQL layer, Python analytics, dashboard, and deck all speak the same language.

A KPI that does not change a decision is not a KPI — it is a number. Each metric below names the decision it serves.

---

## 1. The metric tree (North Star → drivers)

Revenue growth is decomposed into levers a commercial leader can actually pull. Reading top-down tells you *what to fix*; reading bottom-up tells you *why it moved*.

```
                         NORTH STAR
                    Revenue Growth %  (YoY)
                              |
        ┌─────────────────────┴─────────────────────┐
     VOLUME growth                               VALUE growth
   (units / Rx count)                        (revenue per unit)
        |                                           |
   ┌────┴─────┐                          ┌──────────┴──────────┐
 Reach     Depth                      Price / Mix          Margin
 (breadth) (Rx per                    (ASP, product        (gross
  of        prescriber)                mix shift)           margin %)
 prescribers
        |
   ┌────┴───────────────────────────────────┐
 FIELD EFFECTIVENESS                    MARKETING EFFECTIVENESS
        |                                     |
  ┌─────┼───────┐                    ┌────────┼─────────┐
Coverage Frequency Conversion     ROI     Cost/Rx   Channel mix
(% target (calls   (call→Rx      (₹ back  (spend    (share by
 covered)  /doctor) response)     per ₹)   per Rx)   channel)
        |
   OPPORTUNITY REALISATION
   (actual Rx ÷ potential Rx)  ← the core diagnostic ratio
```

**The single most important derived metric is Opportunity Realisation** = actual Rx ÷ potential Rx. Low realisation on high-potential customers = white space = the reallocation prize.

---

## 2. Metric catalogue

Legend — **Dir**: desired direction (▲ higher better, ▼ lower better). **Grain**: lowest level computed.

### 2.1 Growth & revenue (North Star layer)

| Metric | Formula | Grain | Dir | Decision it drives |
|--------|---------|-------|-----|--------------------|
| Revenue | Σ (units × unit_price) | doctor×product×month | ▲ | Overall performance tracking |
| Revenue Growth % (YoY) | (rev_period − rev_prior_year) ÷ rev_prior_year | region / product / total | ▲ | Where is growth created/lost |
| Units (Rx volume) | Σ units_prescribed | any | ▲ | Volume driver of revenue |
| Rx Growth % (YoY) | (units − units_prior_yr) ÷ units_prior_yr | doctor / product | ▲ | Separate volume vs. price effects |
| Gross Margin ₹ | Σ units × (unit_price − cost_per_unit) | product / region | ▲ | Profit, not just revenue |
| Gross Margin % | margin ₹ ÷ revenue | product | ▲ | Product mix quality |

### 2.2 Market & competitive

| Metric | Formula | Grain | Dir | Decision |
|--------|---------|-------|-----|----------|
| Rx Market Share % | our_units ÷ (our_units + competitor_units) | doctor / region / TA | ▲ | Competitive position |
| Share Change (bps) | share_period − share_prior | region / TA | ▲ | Winning or losing ground |
| Competitor Pressure Index | competitor_units ÷ total market units | territory / TA | ▼ | Where competition bites |
| Market Size (₹) | Σ (our + competitor) units × price | TA / region | — | Sizing the prize |

### 2.3 Field-force effectiveness

| Metric | Formula | Grain | Dir | Decision |
|--------|---------|-------|-----|----------|
| Coverage % | doctors_with ≥1 call ÷ target doctors | rep / territory | ▲ | Are targets being seen at all |
| Call Frequency | calls_made ÷ doctors_covered | rep / month | ▲/optimal | Right contact cadence |
| Call Plan Adherence % | calls_made ÷ calls_planned | rep | ▲ | Field discipline |
| Rx per Call | units ÷ calls_made | rep / doctor | ▲ | Marginal productivity of effort |
| Call→Rx Conversion | doctors prescribing after call ÷ doctors called | rep | ▲ | Quality of detailing |
| Rep Productivity | revenue ÷ rep (annualised) | rep | ▲ | Field ROI, sizing |
| Workload Index | Σ opportunity in territory ÷ rep capacity | territory | balance to 1.0 | Over/under-served territories |

### 2.4 Marketing effectiveness

| Metric | Formula | Grain | Dir | Decision |
|--------|---------|-------|-----|----------|
| Marketing ROI | (attributable margin − spend) ÷ spend | campaign / channel / region | ▲ | Keep / cut / scale a channel |
| Cost per Rx | spend ÷ attributable units | product / channel | ▼ | Efficiency of promotion |
| Cost per Acquired Prescriber | spend ÷ new prescribers | product / region | ▼ | Acquisition efficiency |
| Lead Conversion % | conversions ÷ leads | campaign | ▲ | Funnel quality |
| Channel Mix % | channel spend ÷ total spend | region | balance | Rebalance toward high-ROI |
| SOV vs SOM gap | share of voice − share of market | product / region | →0 | Over/under-investment signal |

### 2.5 Customer value & opportunity (the diagnostic core)

| Metric | Formula | Grain | Dir | Decision |
|--------|---------|-------|-----|----------|
| Potential Score (0–100) | model of latent prescribing capacity (panel, specialty, hospital tier, city) | doctor / hospital | — | Sizing each customer |
| Actual Value (₹) | trailing-12-month revenue | doctor / hospital | ▲ | Current worth |
| **Opportunity Realisation %** | actual Rx ÷ potential Rx | doctor | →100% | White space detection |
| **White Space (₹)** | (potential − actual) × price × capture_rate | doctor / territory | quantify | The reallocation prize |
| Decile | rank of doctor by value, 1–10 | within TA/region | — | Standard pharma targeting unit |
| Decile Migration | Δ decile YoY | doctor | ▲ | Who is growing/declining |
| Influence Score (0–100) | KOL status, panel size, referral centrality | doctor | — | Beyond-volume importance |
| **Commercial Opportunity Score** | weighted composite: potential × realisation gap × growth × accessibility | doctor / territory | ▲ | **Master prioritisation rank** |


---

## 3. KPI governance rules

1. **One definition, one place.** Every metric above is implemented once as a SQL view or Python function; the dashboard and deck consume those, never re-derive.
2. **Grain discipline.** Never average an average. Ratios are recomputed from summed numerators/denominators at the target grain.
3. **Time consistency.** "Growth" is always YoY on same-length windows to neutralise seasonality; "trend" uses trailing-3-month moving averages.
4. **Trailing-12-month (TTM)** is the default value window for customer worth, to smooth monthly noise.
5. **Targets & RAG.** Each dashboard KPI carries a target and Red/Amber/Green threshold, defined with VP Sales/Marketing (documented in the dashboard spec, Milestone 9).

---

## 4. The five numbers the CCO will remember

Executive attention is scarce. The deck leads with exactly five headline KPIs:

1. **Revenue growth %** — the problem.
2. **Total quantified White Space (₹ Cr)** — the prize.
3. **Opportunity Realisation % on high-potential doctors** — the smoking gun.
4. **Blended Marketing ROI** and the high-vs-low channel gap — the leak.
5. **Projected uplift & ROI of the reallocation plan** — the answer.

Everything else in the engagement exists to defend these five.
