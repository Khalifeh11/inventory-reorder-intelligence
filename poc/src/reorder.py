"""Reorder-point logic: classical ROP + safety stock, plus stockout-risk heuristic.

ROP = avg_daily_demand * lead_time + safety_stock
safety_stock = z(service_level) * sigma_daily * sqrt(lead_time)

If on_hand <= ROP, recommend a PO sized for (lead_time + review_period) days of
seasonally adjusted demand, less any open POs and current on-hand.
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path

import pandas as pd

from .forecasting import forecast_sku, ForecastResult

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "synthetic_erp.sqlite"

SERVICE_LEVEL_Z = {
    0.80: 0.84,
    0.85: 1.04,
    0.90: 1.28,
    0.95: 1.645,
    0.975: 1.96,
    0.99: 2.33,
}


@dataclass
class ReorderRecommendation:
    sku_id: int
    sku_code: str
    name: str
    category: str
    supplier: str
    on_hand: int
    open_po_qty: int
    lead_time_days: int
    avg_daily_demand: float
    daily_std: float
    seasonality_factor: float
    service_level: float
    safety_stock: float
    reorder_point: float
    coverage_days: float
    should_reorder: bool
    suggested_order_qty: int
    stockout_risk: str  # 'low', 'medium', 'high'
    days_of_cover: float
    unit_cost: float
    currency_value: float


def _nearest_z(service_level: float) -> float:
    # Clamp to table
    if service_level <= 0.80:
        return SERVICE_LEVEL_Z[0.80]
    if service_level >= 0.99:
        return SERVICE_LEVEL_Z[0.99]
    keys = sorted(SERVICE_LEVEL_Z.keys())
    for k in keys:
        if service_level <= k:
            return SERVICE_LEVEL_Z[k]
    return SERVICE_LEVEL_Z[0.95]


def _latest_on_hand(conn: sqlite3.Connection, sku_id: int, as_of: date) -> int:
    row = conn.execute(
        """SELECT on_hand FROM inventory_snapshots
           WHERE sku_id = ? AND snapshot_date <= ?
           ORDER BY snapshot_date DESC LIMIT 1""",
        (sku_id, as_of.isoformat()),
    ).fetchone()
    return int(row[0]) if row else 0


def _open_po_qty(conn: sqlite3.Connection, sku_id: int, as_of: date) -> int:
    row = conn.execute(
        """SELECT COALESCE(SUM(quantity), 0) FROM purchase_orders
           WHERE sku_id = ? AND status = 'open' AND order_date <= ?""",
        (sku_id, as_of.isoformat()),
    ).fetchone()
    return int(row[0]) if row else 0


def recommend(
    conn: sqlite3.Connection,
    sku_id: int,
    as_of: date,
    service_level: float = 0.95,
    review_period_days: int = 14,
    lead_time_buffer_pct: float = 0.0,
) -> ReorderRecommendation:
    product = conn.execute(
        """SELECT sku_id, sku_code, name, category, supplier, lead_time_days, unit_cost
           FROM products WHERE sku_id = ?""",
        (sku_id,),
    ).fetchone()
    if product is None:
        raise ValueError(f"Unknown sku_id {sku_id}")
    sku_id, sku_code, name, category, supplier, lead_time_base, unit_cost = product
    lead_time = int(lead_time_base * (1.0 + lead_time_buffer_pct))

    fc: ForecastResult = forecast_sku(conn, sku_id, as_of, horizon_days=lead_time + review_period_days)

    z = _nearest_z(service_level)
    safety_stock = z * fc.daily_std * math.sqrt(max(lead_time, 1))
    rop = fc.expected_daily_demand * lead_time + safety_stock

    on_hand = _latest_on_hand(conn, sku_id, as_of)
    open_po = _open_po_qty(conn, sku_id, as_of)
    inventory_position = on_hand + open_po

    should_reorder = inventory_position <= rop
    # Order enough to cover lead_time + review_period at expected demand, minus what's already in pipeline
    target_stock = fc.expected_daily_demand * (lead_time + review_period_days) + safety_stock
    suggested = max(0, math.ceil(target_stock - inventory_position))

    days_of_cover = on_hand / fc.expected_daily_demand if fc.expected_daily_demand > 0 else float("inf")

    if days_of_cover < lead_time * 0.4:
        risk = "high"
    elif days_of_cover < lead_time:
        risk = "medium"
    else:
        risk = "low"

    return ReorderRecommendation(
        sku_id=sku_id,
        sku_code=sku_code,
        name=name,
        category=category,
        supplier=supplier,
        on_hand=on_hand,
        open_po_qty=open_po,
        lead_time_days=lead_time,
        avg_daily_demand=fc.expected_daily_demand,
        daily_std=fc.daily_std,
        seasonality_factor=fc.seasonality_factor,
        service_level=service_level,
        safety_stock=float(safety_stock),
        reorder_point=float(rop),
        coverage_days=float(lead_time + review_period_days),
        should_reorder=bool(should_reorder),
        suggested_order_qty=int(suggested),
        stockout_risk=risk,
        days_of_cover=float(days_of_cover) if math.isfinite(days_of_cover) else -1.0,
        unit_cost=float(unit_cost),
        currency_value=float(suggested) * float(unit_cost),
    )


def recommend_all(
    conn: sqlite3.Connection,
    as_of: date,
    service_level: float = 0.95,
    review_period_days: int = 14,
    lead_time_buffer_pct: float = 0.0,
) -> pd.DataFrame:
    skus = conn.execute("SELECT sku_id FROM products").fetchall()
    rows = []
    for (sku_id,) in skus:
        rec = recommend(conn, sku_id, as_of, service_level, review_period_days, lead_time_buffer_pct)
        rows.append(asdict(rec))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    df = recommend_all(conn, date(2026, 3, 31))
    reorders = df[df["should_reorder"]].sort_values("currency_value", ascending=False)
    print(f"{len(reorders)} of {len(df)} SKUs flagged for reorder")
    print(reorders[["sku_code", "name", "on_hand", "reorder_point", "suggested_order_qty", "stockout_risk"]].head(10))
    conn.close()
