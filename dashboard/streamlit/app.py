"""Pharma Commercial Analytics Platform — Executive Dashboard (Streamlit companion)."""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data" / "processed" / "dashboard"
BLUE = "#2a78d6"

st.set_page_config(page_title="Pharma Commercial Analytics Dashboard", page_icon="💊", layout="wide")

@st.cache_data
def load(name: str) -> pd.DataFrame:
    return pd.read_csv(D / name)

def page_overview():
    st.title("Pharma Commercial Analytics Platform")
    try:
        kpis = load("kpis.csv").set_index("metric")["value"].to_dict()
        cols = st.columns(3)
        cols[0].metric("Annual Revenue", "₹" + kpis.get("Annual revenue (₹ Cr)", "—") + " Cr")
        cols[1].metric("Total Products", kpis.get("Total Products", "—"))
        cols[2].metric("Total Regions", kpis.get("Total Regions", "—"))
        
        m = load("monthly_portfolio.csv")
        fig = px.line(m, x="month_id", y="revenue_cr", title="Monthly Revenue (₹ Cr)")
        fig.update_traces(line=dict(color=BLUE, width=3))
        st.plotly_chart(fig, use_container_width=True)
    except FileNotFoundError:
        st.error("Dashboard data not found. Please run 'make dashboard' or 'python scripts/prepare_dashboard.py' first.")

def page_regional():
    st.header("Regional Performance")
    try:
        r = load("region_summary.csv")
        fig = px.bar(r.sort_values("revenue_cr"), x="revenue_cr", y="region_name", color="zone_name", orientation="h", title="Revenue by Region (₹ Cr)")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(r.sort_values("revenue_cr", ascending=False).round(1), use_container_width=True, hide_index=True)
    except FileNotFoundError:
        st.error("Data not found.")

def page_product():
    st.header("Product Performance")
    try:
        p = load("product_summary.csv")
        fig = px.pie(p, names="brand_name", values="revenue_cr", title="Revenue by Brand")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(p.sort_values("revenue_cr", ascending=False).round(1), use_container_width=True, hide_index=True)
    except FileNotFoundError:
        st.error("Data not found.")

PAGES = {
    "📊 Overview": page_overview,
    "🗺️ Regional Performance": page_regional,
    "💊 Product Analysis": page_product,
}

st.sidebar.title("💊 Pharma Dashboard")
st.sidebar.caption("Student DE & BI Project")
choice = st.sidebar.radio("Navigate", list(PAGES.keys()))
st.sidebar.divider()
st.sidebar.caption("Data: `data/processed/dashboard/`")
PAGES[choice]()
