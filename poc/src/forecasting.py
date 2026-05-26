"""Statistical forecasting: trailing moving average + multiplicative seasonality.

Deliberately simple — no ML — to match the Phase 2 roadmap decision that the first
deployment should be statistical-only. ML can be layered in later once the baseline
is trusted by the GM and procurement.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "synthetic_erp.sqlite"


@dataclass
class ForecastResult:
    sku_id: int
    as_of: date
    horizon_days: int
    expected_demand_total: float
    expected_daily_demand: float
    daily_std: float
    seasonality_factor: float  # factor applied for the horizon (avg across months touched)
    baseline_daily: float


def _load_daily_sales(conn: sqlite3.Connection, sku_id: int) -> pd.DataFrame:
    df = pd.read_sql_query(
        "SELECT sale_date, quantity FROM sales WHERE sku_id = ? ORDER BY sale_date",
        conn,
        params=(sku_id,),
        parse_dates=["sale_date"],
    )
    if df.empty:
        return df
    df = df.groupby("sale_date", as_index=False)["quantity"].sum()
    full_range = pd.date_range(df["sale_date"].min(), df["sale_date"].max(), freq="D")
    df = df.set_index("sale_date").reindex(full_range, fill_value=0).rename_axis("sale_date").reset_index()
    return df


def compute_seasonality(conn: sqlite3.Connection, sku_id: int) -> dict[int, float]:
    """Multiplicative monthly seasonality index derived from full history.

    Returns a dict month -> factor, where the average across months is 1.0.
    """
    df = _load_daily_sales(conn, sku_id)
    if df.empty:
        return {m: 1.0 for m in range(1, 13)}
    df["month"] = df["sale_date"].dt.month
    monthly = df.groupby("month")["quantity"].mean()
    overall = monthly.mean()
    if overall == 0:
        return {m: 1.0 for m in range(1, 13)}
    factors = (monthly / overall).to_dict()
    for m in range(1, 13):
        factors.setdefault(m, 1.0)
    return factors


def forecast_sku(
    conn: sqlite3.Connection,
    sku_id: int,
    as_of: date,
    horizon_days: int,
    baseline_window_days: int = 180,
) -> ForecastResult:
    """Forecast expected demand over the next `horizon_days` from `as_of`.

    baseline = mean daily demand over the trailing `baseline_window_days`, seasonally
    deflated (divided by the average seasonality factor for that window), then re-inflated
    by the seasonality factor for the forecast horizon.
    """
    df = _load_daily_sales(conn, sku_id)
    if df.empty:
        return ForecastResult(sku_id, as_of, horizon_days, 0.0, 0.0, 0.0, 1.0, 0.0)

    # Trailing window
    as_of_ts = pd.Timestamp(as_of)
    window_start = as_of_ts - pd.Timedelta(days=baseline_window_days)
    window = df[(df["sale_date"] >= window_start) & (df["sale_date"] < as_of_ts)].copy()
    if window.empty:
        window = df.tail(baseline_window_days).copy()

    seasonality = compute_seasonality(conn, sku_id)
    window["month"] = window["sale_date"].dt.month
    window["season_factor"] = window["month"].map(seasonality)
    window["deseasonalized"] = window["quantity"] / window["season_factor"].replace(0, 1.0)

    baseline_daily = float(window["deseasonalized"].mean())
    daily_std = float(window["deseasonalized"].std(ddof=0))
    if np.isnan(baseline_daily):
        baseline_daily = 0.0
    if np.isnan(daily_std):
        daily_std = 0.0

    # Seasonality factor over horizon: average of daily factors across the horizon window
    horizon_dates = pd.date_range(as_of_ts, periods=horizon_days, freq="D")
    horizon_factor = float(np.mean([seasonality[d.month] for d in horizon_dates]))

    expected_daily = baseline_daily * horizon_factor
    expected_total = expected_daily * horizon_days

    return ForecastResult(
        sku_id=sku_id,
        as_of=as_of,
        horizon_days=horizon_days,
        expected_demand_total=expected_total,
        expected_daily_demand=expected_daily,
        daily_std=daily_std,
        seasonality_factor=horizon_factor,
        baseline_daily=baseline_daily,
    )


def backtest_sku(
    conn: sqlite3.Connection,
    sku_id: int,
    test_months: int = 12,
    baseline_window_days: int = 180,
) -> pd.DataFrame:
    """Rolling 30-day forecasts for the last `test_months` months, with MAPE.

    Returns a DataFrame with forecast_month, forecast, actual, abs_pct_error.
    """
    df = _load_daily_sales(conn, sku_id)
    if df.empty:
        return pd.DataFrame()
    last = df["sale_date"].max()
    rows = []
    cursor = pd.Timestamp(year=last.year, month=last.month, day=1) - pd.DateOffset(months=test_months - 1)
    for _ in range(test_months):
        as_of = cursor.date()
        fc = forecast_sku(conn, sku_id, as_of, horizon_days=30, baseline_window_days=baseline_window_days)
        month_end = (cursor + pd.offsets.MonthEnd(0)).date()
        actual_df = df[(df["sale_date"] >= pd.Timestamp(as_of)) & (df["sale_date"] <= pd.Timestamp(month_end))]
        actual = float(actual_df["quantity"].sum())
        rows.append(
            {
                "forecast_month": cursor.strftime("%Y-%m"),
                "forecast": fc.expected_demand_total,
                "actual": actual,
                "abs_pct_error": abs(fc.expected_demand_total - actual) / actual if actual > 0 else np.nan,
            }
        )
        cursor = cursor + pd.DateOffset(months=1)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    skus = pd.read_sql_query("SELECT sku_id, name, category FROM products LIMIT 5", conn)
    for _, row in skus.iterrows():
        fc = forecast_sku(conn, row["sku_id"], date(2026, 3, 31), horizon_days=60)
        print(
            f"{row['name'][:40]:40s} | daily={fc.expected_daily_demand:.2f} "
            f"season={fc.seasonality_factor:.2f} 60d={fc.expected_demand_total:.0f}"
        )
    conn.close()
