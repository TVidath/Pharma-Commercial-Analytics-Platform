"""Project Catalyst — Executive Dashboard (Streamlit companion).

Runnable mirror of the Power BI spec. Reads the precomputed dashboard CSVs
(data/processed/dashboard/) plus segment/score/recommendation outputs, so it
launches instantly with no database.

Run:  streamlit run dashboard/streamlit/app.py
Prep: python scripts/prepare_dashboard.py   (regenerates the aggregates)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data" / "processed" / "dashboard"
P = ROOT / "data" / "processed"

# --- palette (matches the report/theme) -------------------------------------
BLUE, GREEN, MAGENTA, YELLOW, AQUA, ORANGE, VIOLET, RED = (
    "#2a78d6", "#008300", "#e87ba4", "#eda100", "#1baf7a", "#eb6834", "#4a3aa7", "#e34948")
SERIES = [BLUE, GREEN, MAGENTA, YELLOW, AQUA, ORANGE, VIOLET, RED]
MUTED, INK = "#898781", "#0b0b0b"
LIFECYCLE = {"Launch": BLUE, "Growth": GREEN, "Mature": MUTED, "Decline": RED}
ACTION = {"Increase": GREEN, "Maintain": BLUE, "Reduce / Efficient": ORANGE}

st.set_page_config(page_title="Project Catalyst — Executive Dashboard",
                   page_icon="💊", layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>
:root{
  --ink:#0b0b0b; --muted:#6b6a66; --line:#e6e6e2; --surface:#ffffff;
  --bg:#f5f6f8; --blue:#2a78d6; --navy:#0d366b;
}
html, body, [class*="css"], .stMarkdown, button, input, textarea{
  font-family:'Segoe UI','Helvetica Neue',Arial,sans-serif; }
[data-testid="stAppViewContainer"]{ background:var(--bg); }
[data-testid="stHeader"]{ background:transparent; }
.block-container{ padding-top:2.2rem; padding-bottom:2.5rem; max-width:1460px; }
h1{ font-weight:750; letter-spacing:-.02em; }
h2, h3{ font-weight:700; letter-spacing:-.01em; }
/* KPI cards */
.kpi-card{ background:var(--surface); border:1px solid var(--line); border-radius:12px;
  padding:14px 16px 16px; box-shadow:0 1px 3px rgba(16,24,40,.05); height:100%;
  margin-bottom:6px; }
.kpi-label{ font-size:12px; color:var(--muted); font-weight:600; letter-spacing:.03em;
  text-transform:uppercase; margin-bottom:8px; }
.kpi-value{ font-size:29px; font-weight:750; color:var(--ink); line-height:1.05; }
/* chart + table tiles */
[data-testid="stPlotlyChart"]{ background:var(--surface); border:1px solid var(--line);
  border-radius:12px; padding:10px 12px 6px; box-shadow:0 1px 3px rgba(16,24,40,.05); }
[data-testid="stDataFrame"]{ border:1px solid var(--line); border-radius:12px; overflow:hidden; }
[data-testid="stAlert"]{ border-radius:10px; }
/* sidebar: executive navy */
[data-testid="stSidebar"]{ background:var(--navy); }
[data-testid="stSidebar"] *{ color:#e9f1fb !important; }
[data-testid="stSidebar"] code{ background:rgba(255,255,255,.12); color:#dbe8fb !important;
  padding:1px 5px; border-radius:5px; }
[data-testid="stSidebar"] hr{ border-color:rgba(255,255,255,.18); }
</style>""", unsafe_allow_html=True)


@st.cache_data
def load(name: str, sub: bool = True) -> pd.DataFrame:
    return pd.read_csv((D if sub else P) / name)


def style(fig, h: int = 360, legend: bool = True):
    fig.update_layout(
        template="plotly_white", height=h, margin=dict(l=12, r=16, t=54, b=12),
        font=dict(family="Segoe UI, Helvetica Neue, Arial, sans-serif", size=13, color=INK),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="top", y=-0.16, x=0, title_text="",
                    bgcolor="rgba(0,0,0,0)", font=dict(size=12)),
        title=dict(x=0, xanchor="left", font=dict(size=16, color=INK)),
        hoverlabel=dict(bgcolor="white", bordercolor="#e6e6e2", font_size=12),
        paper_bgcolor="white", plot_bgcolor="white", colorway=SERIES)
    fig.update_xaxes(showgrid=False, showline=True, linecolor="#e6e6e2",
                     ticks="outside", tickcolor="#e6e6e2", title_font_size=12)
    fig.update_yaxes(gridcolor="#eeeee9", zeroline=False, title_font_size=12)
    return fig


KPI_ACCENTS = [BLUE, GREEN, ORANGE, VIOLET, AQUA, MAGENTA, YELLOW, RED]


def kpi_row(pairs):
    cols = st.columns(len(pairs))
    for i, (c, (label, val)) in enumerate(zip(cols, pairs)):
        c.markdown(
            f'<div class="kpi-card" style="border-top:3px solid {KPI_ACCENTS[i % len(KPI_ACCENTS)]}">'
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{val}</div></div>',
            unsafe_allow_html=True)


# ============================================================================
# PAGES
# ============================================================================
def page_overview():
    st.title("Project Catalyst — Commercial Growth Diagnostic")
    st.caption("Global Pharmaceutical Company · pan-India · synthetic engagement data")
    k = load("kpis.csv").set_index("metric")["value"].to_dict()
    kpi_row([("Annual Revenue", "₹" + k.get("Annual revenue (₹ Cr)", "—") + " Cr"),
             ("Revenue Growth", k.get("Revenue growth YoY", "—")),
             ("Total White Space", "₹" + k.get("Total white space (₹ Cr)", "—") + " Cr"),
             ("Marketing ROI", k.get("Blended marketing ROI", "—"))])
    st.divider()
    c1, c2 = st.columns((3, 2))
    with c1:
        m = load("monthly_portfolio.csv")
        m["ma3"] = m["revenue_cr"].rolling(3).mean()
        fig = go.Figure()
        fig.add_scatter(x=m.index, y=m["revenue_cr"], name="Monthly", line=dict(color=MUTED, width=1.5))
        fig.add_scatter(x=m.index, y=m["ma3"], name="3-mo avg", line=dict(color=BLUE, width=3))
        fig.update_layout(title="Revenue is flat — the presenting symptom",
                          yaxis_title="₹ Cr / month")
        st.plotly_chart(style(fig), use_container_width=True)
    with c2:
        reg = load("opportunity_register.csv", sub=False)
        fig = px.bar(reg, x="value_cr", y="lever", orientation="h", color="type",
                     color_discrete_map={"Revenue": BLUE, "Margin": GREEN}, text="value_cr")
        fig.update_layout(title="Opportunity register (₹ Cr)", yaxis_title="", xaxis_title="")
        st.plotly_chart(style(fig), use_container_width=True)
    scen = load("scenarios.csv")
    fig = px.bar(scen, x="scenario", y="npv_cr", color="scenario",
                 color_discrete_map={"Conservative": MUTED, "Base": BLUE, "Aggressive": GREEN},
                 text="npv_cr")
    fig.update_layout(title="3-year NPV by scenario (₹ Cr)", xaxis_title="", yaxis_title="NPV ₹ Cr")
    st.plotly_chart(style(fig, 320, legend=False), use_container_width=True)


def page_sales():
    st.header("Sales Performance")
    ts = load("score_tier_summary.csv")
    kpi_row([("Priority-1 doctors", f"{int(ts.loc[ts.priority_tier=='P1','doctors'].iloc[0]):,}"),
             ("P1 avg calls", f"{ts.loc[ts.priority_tier=='P1','avg_calls'].iloc[0]:.0f}"),
             ("P3 avg calls", f"{ts.loc[ts.priority_tier=='P3','avg_calls'].iloc[0]:.0f}"),
             ("P1 white space", f"₹{ts.loc[ts.priority_tier=='P1','white_space_cr'].iloc[0]:.0f} Cr")])
    st.info("**The core finding:** effort runs backwards to opportunity — P1 (highest opportunity) "
            "receives the fewest calls, P3 (lowest) the most. Reallocating is the #1 lever.")
    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(ts, x="priority_tier", y="avg_calls", color="priority_tier",
                     color_discrete_map={"P1": RED, "P2": YELLOW, "P3": MUTED}, text_auto=".0f")
        fig.update_layout(title="Average calls per doctor by priority tier", xaxis_title="", yaxis_title="Calls")
        st.plotly_chart(style(fig, legend=False), use_container_width=True)
    with c2:
        fig = px.bar(ts, x="priority_tier", y="white_space_cr", color="priority_tier",
                     color_discrete_map={"P1": RED, "P2": YELLOW, "P3": MUTED}, text_auto=".0f")
        fig.update_layout(title="White-space opportunity by tier (₹ Cr)", xaxis_title="", yaxis_title="₹ Cr")
        st.plotly_chart(style(fig, legend=False), use_container_width=True)
    m = load("monthly_portfolio.csv")
    fig = px.line(m, x=m.index, y="revenue_cr")
    fig.update_traces(line=dict(color=BLUE, width=2.5))
    fig.update_layout(title="Monthly revenue trend", xaxis_title="Month", yaxis_title="₹ Cr")
    lo, hi = m["revenue_cr"].min(), m["revenue_cr"].max()
    fig.update_yaxes(range=[lo - (hi - lo) * 0.6, hi + (hi - lo) * 0.4])  # zoom so the trend reads
    st.plotly_chart(style(fig, 300, legend=False), use_container_width=True)


def page_regional():
    st.header("Regional Performance")
    reg = load("region_summary.csv")
    zones = ["All"] + sorted(reg["zone_name"].unique())
    z = st.selectbox("Zone", zones)
    r = reg if z == "All" else reg[reg.zone_name == z]
    kpi_row([("Regions", f"{len(r)}"),
             ("Revenue", f"₹{r['ttm_rev_cr'].sum():,.0f} Cr"),
             ("Avg growth", f"{r['growth_pct'].mean():+.1f}%"),
             ("White space", f"₹{r['white_space_cr'].sum():.0f} Cr")])
    c1, c2 = st.columns(2)
    with c1:
        fig = px.scatter(r, x="share_pct", y="growth_pct", size="ttm_rev_cr", color="zone_name",
                         hover_name="region_name", color_discrete_sequence=SERIES, size_max=40)
        fig.update_layout(title="Share vs growth (bubble = revenue)",
                          xaxis_title="Market share %", yaxis_title="YoY growth %")
        st.plotly_chart(style(fig), use_container_width=True)
    with c2:
        rr = r.sort_values("white_space_cr", ascending=True).tail(12)
        fig = px.bar(rr, x="white_space_cr", y="region_name", orientation="h", text_auto=".1f")
        fig.update_traces(marker_color=GREEN)
        fig.update_layout(title="White space by region (₹ Cr)", xaxis_title="", yaxis_title="")
        st.plotly_chart(style(fig, legend=False), use_container_width=True)
    st.dataframe(r.sort_values("ttm_rev_cr", ascending=False).round(1), width='stretch', hide_index=True)


def page_segmentation():
    st.header("Doctor Segmentation — Potential × Value")
    seg = load("doctor_segments.csv", sub=False)
    order_p = ["High", "Medium", "Low"]; order_v = ["Low", "Medium", "High"]
    piv = (seg.groupby(["potential_tier", "value_tier"]).size()
           .reindex(pd.MultiIndex.from_product([order_p, order_v])).fillna(0).unstack())
    piv = piv.reindex(index=order_p, columns=order_v)
    c1, c2 = st.columns((3, 2))
    with c1:
        fig = px.imshow(piv.values, x=[f"{v} value" for v in order_v], y=[f"{p} potential" for p in order_p],
                        color_continuous_scale="Blues", text_auto=True, aspect="auto")
        fig.update_layout(title="9-box: doctor counts")
        st.plotly_chart(style(fig, legend=False), use_container_width=True)
    with c2:
        ss = load("segment_summary.csv")
        act = ss.groupby("action").agg(doctors=("doctors", "sum"), ws=("white_space_cr", "sum")).reset_index()
        fig = px.pie(act, names="action", values="ws", color="action", color_discrete_map=ACTION, hole=0.5)
        fig.update_layout(title="White space by action (₹ Cr)")
        st.plotly_chart(style(fig), use_container_width=True)
    st.dataframe(load("segment_summary.csv").sort_values("white_space_cr", ascending=False).round(1),
                 width='stretch', hide_index=True)


def page_hospital():
    st.header("Hospital Analysis")
    h = load("hospital_segments.csv", sub=False)
    order = ["Platinum", "Gold", "Silver", "Bronze"]
    g = h.groupby("tier").agg(hospitals=("hospital_id", "count"),
                              value_cr=("affiliated_ttm_revenue", lambda s: s.sum() / 1e7)).reindex(order).reset_index()
    kpi_row([("Hospitals", f"{len(h):,}"),
             ("Platinum/Gold", f"{int(g.set_index('tier').loc[['Platinum','Gold'],'hospitals'].sum())}"),
             ("Affiliated value", f"₹{g['value_cr'].sum():,.0f} Cr")])
    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(g, x="tier", y="value_cr", text_auto=".0f",
                     color="tier", color_discrete_sequence=["#0d366b", "#256abf", "#6da7ec", "#cde2fb"])
        fig.update_layout(title="Affiliated value by tier (₹ Cr)", xaxis_title="", yaxis_title="₹ Cr")
        st.plotly_chart(style(fig, legend=False), use_container_width=True)
    with c2:
        byt = h.groupby("hospital_type").size().reset_index(name="hospitals")
        fig = px.bar(byt, x="hospital_type", y="hospitals", text_auto=True)
        fig.update_traces(marker_color=BLUE)
        fig.update_layout(title="Hospitals by type", xaxis_title="", yaxis_title="")
        st.plotly_chart(style(fig, legend=False), use_container_width=True)
    top = h.sort_values("affiliated_ttm_revenue", ascending=False).head(15)[
        ["hospital_name", "hospital_type", "region_name", "tier", "bed_count", "affiliated_doctors"]]
    st.dataframe(top, width='stretch', hide_index=True)


def page_marketing():
    st.header("Marketing ROI")
    ch = load("channel_roi.csv")
    st.warning("**The leak:** the largest budget sits in the lowest-ROI channel. Re-weighting toward "
               "Digital/CME and KOL lifts blended ROI at flat spend.")
    fig = px.scatter(ch, x="budget_share_pct", y="roi", size="spend_cr", color="roi",
                     hover_name="channel", color_continuous_scale="RdYlGn", size_max=55, text="channel")
    fig.update_traces(textposition="top center")
    fig.add_hline(y=1.0, line_dash="dash", line_color=MUTED)
    fig.update_layout(title="ROI vs budget share (bubble = spend)",
                      xaxis_title="Budget share %", yaxis_title="ROI (×)")
    st.plotly_chart(style(fig, 420, legend=False), use_container_width=True)
    st.dataframe(ch.sort_values("roi").round(2), width='stretch', hide_index=True)


def page_product():
    st.header("Product Analysis")
    p = load("product_summary.csv")
    c1, c2 = st.columns((3, 2))
    with c1:
        fig = px.scatter(p, x="growth_pct", y="margin_pct", size="ttm_rev_cr", color="lifecycle_stage",
                         hover_name="brand_name", color_discrete_map=LIFECYCLE, size_max=45, text="brand_name")
        fig.update_traces(textposition="top center")
        fig.add_vline(x=0, line_color=MUTED)
        fig.update_layout(title="Growth vs margin (bubble = revenue)",
                          xaxis_title="YoY growth %", yaxis_title="Gross margin %")
        st.plotly_chart(style(fig, 420), use_container_width=True)
    with c2:
        mk = load("market_ta.csv").sort_values("share_pct")
        fig = px.bar(mk, x="share_pct", y="ta_name", orientation="h", text_auto=".0f")
        fig.update_traces(marker_color=BLUE)
        fig.update_layout(title="Market share by TA (%)", xaxis_title="", yaxis_title="")
        st.plotly_chart(style(fig, 420, legend=False), use_container_width=True)
    st.dataframe(p.sort_values("growth_pct").round(1), width='stretch', hide_index=True)



# ============================================================================
PAGES = {
    "📊 Overview": page_overview,
    "📈 Sales Performance": page_sales,
    "🗺️ Regional Performance": page_regional,
    "👨‍⚕️ Doctor Segmentation": page_segmentation,
    "🏥 Hospital Analysis": page_hospital,
    "📣 Marketing ROI": page_marketing,
    "💊 Product Analysis": page_product,
}

st.sidebar.title("💊 Project Catalyst")
st.sidebar.caption("Executive Dashboard")
choice = st.sidebar.radio("Navigate", list(PAGES.keys()))
st.sidebar.divider()
st.sidebar.caption("Synthetic data · seed 42 · reproducible.\nData: `data/processed/dashboard/`")
PAGES[choice]()
