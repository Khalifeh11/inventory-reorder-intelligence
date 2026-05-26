"""Streamlit UI for the Atlas Inventory Reorder Intelligence PoC.

Run locally:
    streamlit run app.py
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from src.data_gen import DB_PATH, generate
from src.explain import explain, summarize_week
from src.forecasting import backtest_sku, forecast_sku
from src.reorder import recommend, recommend_all


st.set_page_config(
    page_title="Atlas — Inventory Reorder Intelligence",
    page_icon=":package:",
    layout="wide",
)


@st.cache_resource
def _ensure_db() -> Path:
    if not DB_PATH.exists():
        generate()
    return DB_PATH


@st.cache_resource
def _connect() -> sqlite3.Connection:
    _ensure_db()
    return sqlite3.connect(str(DB_PATH), check_same_thread=False)


@st.cache_data
def _products(_conn) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT sku_id, sku_code, name, category, supplier, unit_cost, lead_time_days FROM products",
        _conn,
    )


@st.cache_data
def _recommendations(_conn, as_of_iso: str, service_level: float, review_period: int, lead_buffer: float) -> pd.DataFrame:
    recs = recommend_all(
        _conn,
        as_of=pd.Timestamp(as_of_iso).date(),
        service_level=service_level,
        review_period_days=review_period,
        lead_time_buffer_pct=lead_buffer,
    )
    recs.attrs["as_of"] = as_of_iso
    return recs


@st.cache_data(show_spinner="Generating weekly briefing…")
def _briefing(_conn, as_of_iso: str, service_level: float, review_period: int, lead_buffer: float,
              weekly_budget: int, prefer_llm: bool) -> tuple[str, str]:
    recs = _recommendations(_conn, as_of_iso, service_level, review_period, lead_buffer)
    return summarize_week(recs, weekly_budget=weekly_budget or None, prefer_llm=prefer_llm)


def _sidebar_controls() -> dict:
    with st.sidebar:
        st.header("Parameters")
        as_of = st.date_input("As of", value=date(2026, 3, 31), min_value=date(2019, 1, 1), max_value=date(2026, 3, 31))
        service_level = st.select_slider(
            "Service level",
            options=[0.80, 0.85, 0.90, 0.95, 0.975, 0.99],
            value=0.95,
            format_func=lambda v: f"{int(v*100)}%",
        )
        review_period = st.slider("Review period (days)", 7, 30, 14)
        lead_buffer = st.slider("Lead time buffer (%)", 0, 50, 0, step=5) / 100.0
        weekly_budget = st.number_input("Weekly PO budget ($, 0 = none)", min_value=0, value=0, step=1000)
        prefer_llm = st.checkbox("Use LLM (briefing + explanations; requires ANTHROPIC_API_KEY)", value=True)
        st.divider()
        st.caption(
            "Atlas Paints & Tools — Inventory Reorder Intelligence PoC. "
            "Synthetic ERP data; 10 years of history; on-prem capable."
        )
    return {
        "as_of": as_of,
        "service_level": service_level,
        "review_period": review_period,
        "lead_buffer": lead_buffer,
        "weekly_budget": weekly_budget,
        "prefer_llm": prefer_llm,
    }


def _tab_dashboard(conn, params, recs: pd.DataFrame) -> None:
    st.subheader("This week's procurement briefing")
    brief, brief_src = _briefing(
        conn, str(params["as_of"]), params["service_level"], params["review_period"],
        params["lead_buffer"], int(params["weekly_budget"]), params["prefer_llm"],
    )
    with st.container(border=True):
        st.markdown(brief)
        caption = (
            "AI-generated, numeric-grounding checked — every figure traces to the engine."
            if brief_src == "llm"
            else "Deterministic template (offline / no API key) — same numbers, no AI call."
        )
        st.caption(f"Briefing source: `{brief_src}` · {caption}")

    st.subheader("Overview")
    col1, col2, col3, col4 = st.columns(4)
    total_skus = len(recs)
    to_reorder = recs["should_reorder"].sum()
    high_risk = (recs["stockout_risk"] == "high").sum()
    reorder_value = recs.loc[recs["should_reorder"], "currency_value"].sum()

    col1.metric("SKUs tracked", f"{total_skus}")
    col2.metric("Reorder now", f"{int(to_reorder)}")
    col3.metric("High stockout risk", f"{int(high_risk)}")
    col4.metric("Recommended PO value", f"${reorder_value:,.0f}")

    st.subheader("Reorder queue — top priorities")
    queue = recs[recs["should_reorder"]].sort_values(
        ["stockout_risk", "currency_value"],
        ascending=[True, False],
        key=lambda s: s.map({"high": 0, "medium": 1, "low": 2}) if s.name == "stockout_risk" else s,
    )
    if queue.empty:
        st.info("No reorders recommended at the current parameters.")
    else:
        view = queue[[
            "sku_code", "name", "category", "supplier",
            "on_hand", "days_of_cover", "lead_time_days",
            "reorder_point", "suggested_order_qty", "currency_value", "stockout_risk",
        ]].copy()
        view.columns = [
            "SKU", "Name", "Cat.", "Supplier",
            "On-hand", "Days cover", "Lead (d)",
            "ROP", "Order qty", "PO value ($)", "Risk",
        ]
        view["Days cover"] = view["Days cover"].round(0).astype(int)
        view["ROP"] = view["ROP"].round(0).astype(int)
        view["PO value ($)"] = view["PO value ($)"].round(0).astype(int)
        st.dataframe(view, use_container_width=True, hide_index=True)

    st.subheader("Stockout risk distribution")
    risk_counts = recs["stockout_risk"].value_counts().reset_index()
    risk_counts.columns = ["risk", "count"]
    chart = (
        alt.Chart(risk_counts)
        .mark_bar()
        .encode(
            x=alt.X("risk:N", sort=["high", "medium", "low"], title="Stockout risk"),
            y=alt.Y("count:Q", title="# SKUs"),
            color=alt.Color(
                "risk:N",
                scale=alt.Scale(domain=["high", "medium", "low"], range=["#c0392b", "#e67e22", "#27ae60"]),
                legend=None,
            ),
        )
        .properties(height=220)
    )
    st.altair_chart(chart, use_container_width=True)


def _tab_drilldown(conn, params, products: pd.DataFrame, recs: pd.DataFrame) -> None:
    st.subheader("SKU drilldown")
    options = products.apply(lambda r: f"{r.sku_code} — {r['name']}", axis=1).tolist()
    sel = st.selectbox("Pick a SKU", options=options, index=0)
    sku_code = sel.split(" — ")[0]
    sku = products[products["sku_code"] == sku_code].iloc[0]

    rec = recommend(
        conn,
        int(sku.sku_id),
        params["as_of"],
        service_level=params["service_level"],
        review_period_days=params["review_period"],
        lead_time_buffer_pct=params["lead_buffer"],
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("On-hand", f"{rec.on_hand}")
    c1.metric("Open POs", f"{rec.open_po_qty}")
    c2.metric("Avg daily demand", f"{rec.avg_daily_demand:.1f}")
    c2.metric("Seasonality factor", f"{rec.seasonality_factor:.2f}")
    c3.metric("Reorder point", f"{rec.reorder_point:.0f}")
    c3.metric("Days of cover", f"{rec.days_of_cover:.0f}" if rec.days_of_cover >= 0 else "—")

    if rec.should_reorder:
        st.error(
            f"**Reorder now** — suggested qty: {rec.suggested_order_qty} units "
            f"(~${rec.currency_value:,.0f}), risk: {rec.stockout_risk.upper()}"
        )
    else:
        st.success(f"No action required. Days of cover: {rec.days_of_cover:.0f}. Risk: {rec.stockout_risk}.")

    text, source = explain(rec, prefer_llm=params["prefer_llm"])
    with st.container(border=True):
        st.markdown(f"**Why:** {text}")
        st.caption(f"Explanation source: `{source}`")

    # History + forecast chart
    daily = pd.read_sql_query(
        "SELECT sale_date, quantity FROM sales WHERE sku_id = ? ORDER BY sale_date",
        conn,
        params=(int(sku.sku_id),),
        parse_dates=["sale_date"],
    )
    if not daily.empty:
        daily = daily.groupby("sale_date", as_index=False)["quantity"].sum()
        daily["month"] = daily["sale_date"].dt.to_period("M").dt.to_timestamp()
        monthly = daily.groupby("month", as_index=False)["quantity"].sum()

        # Project forecast 3 months forward
        horizon_months = 3
        future_rows = []
        cursor = pd.Timestamp(params["as_of"]).to_period("M").to_timestamp()
        for i in range(horizon_months):
            month_start = cursor + pd.DateOffset(months=i)
            days_in_month = (month_start + pd.offsets.MonthEnd(0)).day
            fc = forecast_sku(conn, int(sku.sku_id), month_start.date(), horizon_days=days_in_month)
            future_rows.append({"month": month_start, "quantity": fc.expected_demand_total, "kind": "forecast"})
        monthly["kind"] = "actual"
        chart_df = pd.concat([monthly.assign(kind="actual"), pd.DataFrame(future_rows)], ignore_index=True)

        chart = (
            alt.Chart(chart_df)
            .mark_line(point=True)
            .encode(
                x=alt.X("month:T", title="Month"),
                y=alt.Y("quantity:Q", title="Units sold"),
                color=alt.Color(
                    "kind:N",
                    scale=alt.Scale(domain=["actual", "forecast"], range=["#2c3e50", "#e67e22"]),
                    legend=alt.Legend(title=None),
                ),
                strokeDash=alt.StrokeDash(
                    "kind:N",
                    scale=alt.Scale(domain=["actual", "forecast"], range=[[1, 0], [4, 3]]),
                    legend=None,
                ),
            )
            .properties(height=320)
        )
        st.altair_chart(chart, use_container_width=True)

    with st.expander("Backtest last 12 months (MAPE)"):
        bt = backtest_sku(conn, int(sku.sku_id), test_months=12)
        if not bt.empty:
            bt["abs_pct_error"] = bt["abs_pct_error"].round(3)
            mape = bt["abs_pct_error"].mean()
            st.write(f"**MAPE (last 12 months): {mape:.1%}**")
            st.dataframe(bt, use_container_width=True, hide_index=True)


def _tab_whatif(conn, params, recs_baseline: pd.DataFrame) -> None:
    st.subheader("What-if analysis")
    st.write(
        "Compare the baseline parameters (in the sidebar) with an alternative scenario. "
        "Useful for sensitivity on service level and lead-time assumptions."
    )
    col1, col2, col3 = st.columns(3)
    alt_service = col1.select_slider(
        "Alt service level",
        options=[0.80, 0.85, 0.90, 0.95, 0.975, 0.99],
        value=0.99,
        format_func=lambda v: f"{int(v*100)}%",
    )
    alt_review = col2.slider("Alt review period (days)", 7, 30, 21)
    alt_buffer = col3.slider("Alt lead-time buffer (%)", 0, 50, 20, step=5) / 100.0

    alt_recs = _recommendations(conn, str(params["as_of"]), alt_service, alt_review, alt_buffer)

    summary = pd.DataFrame(
        [
            {
                "Scenario": "Baseline",
                "Service level": f"{int(params['service_level']*100)}%",
                "Review": f"{params['review_period']}d",
                "Buffer": f"{int(params['lead_buffer']*100)}%",
                "Reorder now": int(recs_baseline["should_reorder"].sum()),
                "High risk": int((recs_baseline["stockout_risk"] == "high").sum()),
                "PO value ($)": int(recs_baseline.loc[recs_baseline["should_reorder"], "currency_value"].sum()),
            },
            {
                "Scenario": "Alternative",
                "Service level": f"{int(alt_service*100)}%",
                "Review": f"{alt_review}d",
                "Buffer": f"{int(alt_buffer*100)}%",
                "Reorder now": int(alt_recs["should_reorder"].sum()),
                "High risk": int((alt_recs["stockout_risk"] == "high").sum()),
                "PO value ($)": int(alt_recs.loc[alt_recs["should_reorder"], "currency_value"].sum()),
            },
        ]
    )
    st.dataframe(summary, use_container_width=True, hide_index=True)

    st.caption(
        "Higher service level + longer review period + lead-time buffer "
        "→ earlier and larger orders, reducing stockouts at the cost of more working capital tied in stock."
    )


def main() -> None:
    conn = _connect()
    params = _sidebar_controls()
    products = _products(conn)
    recs = _recommendations(
        conn,
        str(params["as_of"]),
        params["service_level"],
        params["review_period"],
        params["lead_buffer"],
    )

    st.title("Atlas Paints & Tools — Inventory Reorder Intelligence")
    st.caption(
        "Statistical forecasting + reorder-point logic + plain-language explanations. "
        "Phase 2 initiative, designed to run on-prem with zero cloud dependency."
    )

    tabs = st.tabs(["Dashboard", "SKU Drilldown", "What-if"])
    with tabs[0]:
        _tab_dashboard(conn, params, recs)
    with tabs[1]:
        _tab_drilldown(conn, params, products, recs)
    with tabs[2]:
        _tab_whatif(conn, params, recs)


if __name__ == "__main__":
    main()
