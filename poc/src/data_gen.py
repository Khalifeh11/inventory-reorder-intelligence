"""Generate a synthetic ERP-like SQLite database for the Atlas Inventory Reorder PoC.

Simulates ~10 years of sales, inventory snapshots, purchase orders, and a product
catalogue that reflects Atlas Paints & Tools' two business lines (paint manufacturing
and hardware/power-tools import) with realistic seasonality and lead-time variability.
"""

from __future__ import annotations

import math
import os
import random
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "synthetic_erp.sqlite"

START_DATE = date(2016, 1, 1)
END_DATE = date(2026, 3, 31)
SEED = 42

# Seasonal demand multiplier by month (peak March + summer, trough Dec-Feb ~2:1 ratio)
MONTHLY_SEASONALITY = {
    1: 0.55, 2: 0.60, 3: 1.80, 4: 1.40, 5: 1.25, 6: 1.35,
    7: 1.45, 8: 1.30, 9: 1.05, 10: 0.95, 11: 0.70, 12: 0.55,
}

PAINT_LINES = [
    ("Interior Emulsion White 4L", 18.50, 7, "In-house"),
    ("Interior Emulsion White 20L", 82.00, 7, "In-house"),
    ("Interior Emulsion Colored 4L", 22.00, 7, "In-house"),
    ("Interior Emulsion Colored 20L", 95.00, 7, "In-house"),
    ("Exterior Facade White 20L", 110.00, 10, "In-house"),
    ("Exterior Facade Colored 20L", 125.00, 10, "In-house"),
    ("Primer Water-based 4L", 14.00, 7, "In-house"),
    ("Primer Water-based 20L", 64.00, 7, "In-house"),
    ("Primer Oil-based 4L", 19.00, 10, "In-house"),
    ("Enamel Gloss White 1L", 9.50, 7, "In-house"),
    ("Enamel Gloss Colored 1L", 11.00, 7, "In-house"),
    ("Wood Varnish 1L", 12.00, 10, "In-house"),
    ("Anti-Rust Primer 4L", 26.00, 10, "In-house"),
    ("Masonry Waterproofer 20L", 140.00, 14, "In-house"),
    ("Thinner 4L", 8.00, 7, "In-house"),
    ("Roller 9in Standard", 1.50, 7, "In-house"),
    ("Roller 9in Premium", 2.80, 7, "In-house"),
    ("Brush 2in", 1.10, 7, "In-house"),
    ("Brush 4in", 2.20, 7, "In-house"),
    ("Paint Tray Plastic", 1.80, 7, "In-house"),
]

HARDWARE_LINES = [
    ("Cordless Drill 18V", 85.00, 60, "Makita-CN"),
    ("Cordless Drill 12V", 55.00, 60, "Makita-CN"),
    ("Impact Driver 18V", 110.00, 60, "Makita-CN"),
    ("Angle Grinder 115mm", 45.00, 55, "Bosch-TR"),
    ("Angle Grinder 230mm", 78.00, 55, "Bosch-TR"),
    ("Circular Saw 185mm", 95.00, 65, "Makita-CN"),
    ("Jigsaw Variable Speed", 62.00, 60, "Bosch-TR"),
    ("Hammer Drill SDS-Plus", 125.00, 65, "Bosch-TR"),
    ("Demolition Hammer 5kg", 220.00, 70, "Bosch-TR"),
    ("Rotary Hammer 3kg", 175.00, 70, "Makita-CN"),
    ("Orbital Sander", 48.00, 55, "Bosch-TR"),
    ("Belt Sander 76mm", 88.00, 60, "Makita-CN"),
    ("Router 1200W", 105.00, 60, "Makita-CN"),
    ("Miter Saw 210mm", 185.00, 70, "Bosch-TR"),
    ("Table Saw 254mm", 340.00, 75, "DeWalt-US"),
    ("Air Compressor 24L", 165.00, 65, "Stanley-IT"),
    ("Nail Gun Pneumatic", 95.00, 60, "Stanley-IT"),
    ("Heat Gun 2000W", 32.00, 55, "Bosch-TR"),
    ("Laser Level Cross-line", 58.00, 60, "Bosch-TR"),
    ("Measuring Tape 5m", 3.20, 55, "Stanley-IT"),
    ("Measuring Tape 8m", 5.50, 55, "Stanley-IT"),
    ("Spirit Level 60cm", 8.00, 55, "Stanley-IT"),
    ("Spirit Level 120cm", 15.00, 55, "Stanley-IT"),
    ("Drill Bit Set HSS 19pc", 9.50, 55, "Stanley-IT"),
    ("Drill Bit Set Masonry 8pc", 6.80, 55, "Bosch-TR"),
    ("Screwdriver Set 12pc", 12.00, 55, "Stanley-IT"),
    ("Pliers Combination 200mm", 6.00, 55, "Stanley-IT"),
    ("Adjustable Wrench 250mm", 7.50, 55, "Stanley-IT"),
    ("Socket Set 1/2in 26pc", 38.00, 60, "Stanley-IT"),
    ("Hex Key Set Metric 9pc", 4.00, 55, "Stanley-IT"),
    ("Utility Knife Retractable", 2.50, 55, "Stanley-IT"),
    ("Claw Hammer 450g", 6.50, 55, "Stanley-IT"),
    ("Sledge Hammer 3kg", 18.00, 60, "Stanley-IT"),
    ("Crowbar 600mm", 11.00, 60, "Stanley-IT"),
    ("Wheelbarrow Steel 80L", 55.00, 65, "Generic-IT"),
    ("Extension Cord 20m", 14.00, 55, "Generic-CN"),
    ("Extension Cord 30m", 20.00, 55, "Generic-CN"),
    ("Safety Goggles", 2.00, 55, "Generic-CN"),
    ("Work Gloves Leather", 3.50, 55, "Generic-TR"),
    ("Dust Mask N95 (10pc)", 4.50, 55, "Generic-CN"),
]


def _month_seasonality(d: date) -> float:
    return MONTHLY_SEASONALITY[d.month]


def _seed_everything() -> None:
    random.seed(SEED)
    np.random.seed(SEED)


def _schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.executescript(
        """
        DROP TABLE IF EXISTS products;
        DROP TABLE IF EXISTS sales;
        DROP TABLE IF EXISTS inventory_snapshots;
        DROP TABLE IF EXISTS purchase_orders;

        CREATE TABLE products (
            sku_id INTEGER PRIMARY KEY,
            sku_code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,          -- 'paint' or 'hardware'
            unit_cost REAL NOT NULL,
            unit_price REAL NOT NULL,
            lead_time_days INTEGER NOT NULL,
            supplier TEXT NOT NULL,
            baseline_daily_demand REAL NOT NULL,
            trend_pct_per_year REAL NOT NULL
        );

        CREATE TABLE sales (
            sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_date TEXT NOT NULL,
            sku_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            FOREIGN KEY (sku_id) REFERENCES products(sku_id)
        );
        CREATE INDEX idx_sales_sku_date ON sales(sku_id, sale_date);

        CREATE TABLE inventory_snapshots (
            snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date TEXT NOT NULL,
            sku_id INTEGER NOT NULL,
            on_hand INTEGER NOT NULL,
            FOREIGN KEY (sku_id) REFERENCES products(sku_id)
        );
        CREATE INDEX idx_inv_sku_date ON inventory_snapshots(sku_id, snapshot_date);

        CREATE TABLE purchase_orders (
            po_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku_id INTEGER NOT NULL,
            order_date TEXT NOT NULL,
            eta_date TEXT NOT NULL,
            received_date TEXT,
            quantity INTEGER NOT NULL,
            unit_cost REAL NOT NULL,
            status TEXT NOT NULL,            -- 'open', 'received'
            FOREIGN KEY (sku_id) REFERENCES products(sku_id)
        );
        CREATE INDEX idx_po_sku ON purchase_orders(sku_id);
        """
    )
    conn.commit()


def _insert_products(conn: sqlite3.Connection) -> list[dict]:
    products: list[dict] = []
    sku_id = 1
    for name, cost, lead, supplier in PAINT_LINES:
        baseline = random.uniform(1.5, 8.0)  # daily units
        trend = random.uniform(-0.03, 0.06)
        products.append(
            {
                "sku_id": sku_id,
                "sku_code": f"P{sku_id:04d}",
                "name": name,
                "category": "paint",
                "unit_cost": cost,
                "unit_price": round(cost * random.uniform(1.35, 1.60), 2),
                "lead_time_days": lead,
                "supplier": supplier,
                "baseline_daily_demand": baseline,
                "trend_pct_per_year": trend,
            }
        )
        sku_id += 1
    for name, cost, lead, supplier in HARDWARE_LINES:
        baseline = random.uniform(0.3, 4.0)
        trend = random.uniform(-0.04, 0.08)
        products.append(
            {
                "sku_id": sku_id,
                "sku_code": f"H{sku_id:04d}",
                "name": name,
                "category": "hardware",
                "unit_cost": cost,
                "unit_price": round(cost * random.uniform(1.30, 1.55), 2),
                "lead_time_days": lead,
                "supplier": supplier,
                "baseline_daily_demand": baseline,
                "trend_pct_per_year": trend,
            }
        )
        sku_id += 1

    cur = conn.cursor()
    cur.executemany(
        """INSERT INTO products
           (sku_id, sku_code, name, category, unit_cost, unit_price,
            lead_time_days, supplier, baseline_daily_demand, trend_pct_per_year)
           VALUES (:sku_id,:sku_code,:name,:category,:unit_cost,:unit_price,
                   :lead_time_days,:supplier,:baseline_daily_demand,:trend_pct_per_year)""",
        products,
    )
    conn.commit()
    return products


def _generate_sales_and_inventory(conn: sqlite3.Connection, products: list[dict]) -> None:
    cur = conn.cursor()
    total_days = (END_DATE - START_DATE).days + 1

    sales_rows: list[tuple] = []
    inv_rows: list[tuple] = []
    po_rows: list[tuple] = []

    for p in products:
        on_hand = int(p["baseline_daily_demand"] * p["lead_time_days"] * 1.6)
        target_stock = on_hand
        pending_pos: list[tuple[date, int]] = []  # (arrival_date, qty)

        day = START_DATE
        snapshot_counter = 0
        while day <= END_DATE:
            years_elapsed = (day - START_DATE).days / 365.0
            trend_mult = (1.0 + p["trend_pct_per_year"]) ** years_elapsed
            season_mult = _month_seasonality(day)
            expected = p["baseline_daily_demand"] * trend_mult * season_mult

            # Poisson-like draw with extra noise for lumpy B2B orders
            raw_demand = np.random.poisson(max(expected, 0.01))
            if random.random() < 0.08:  # ~8% of days see a lumpy wholesale order
                raw_demand += np.random.poisson(max(expected * 2, 1))

            sold = min(raw_demand, on_hand)
            if sold > 0:
                unit_price_fluct = p["unit_price"] * random.uniform(0.92, 1.02)
                sales_rows.append((day.isoformat(), p["sku_id"], int(sold), round(unit_price_fluct, 2)))
            on_hand -= sold

            # Receive any PO landing today
            pending_pos = [po for po in pending_pos if _receive_if_due(po, day, cur_hook := None) or True]
            arrived = [qty for (d_eta, qty) in pending_pos if d_eta <= day]
            pending_pos = [(d_eta, qty) for (d_eta, qty) in pending_pos if d_eta > day]
            for qty in arrived:
                on_hand += qty

            # Reactive reorder (simulates current Atlas behavior)
            if on_hand < p["baseline_daily_demand"] * 5 and not pending_pos:
                lead_actual = int(p["lead_time_days"] * random.uniform(0.85, 1.35))
                order_qty = int(max(target_stock - on_hand, p["baseline_daily_demand"] * 30))
                order_date = day
                eta = order_date + timedelta(days=lead_actual)
                received = eta + timedelta(days=random.randint(-2, 5))
                pending_pos.append((eta, order_qty))
                po_rows.append(
                    (
                        p["sku_id"],
                        order_date.isoformat(),
                        eta.isoformat(),
                        received.isoformat() if received <= END_DATE else None,
                        order_qty,
                        p["unit_cost"],
                        "received" if received <= END_DATE else "open",
                    )
                )

            # Weekly inventory snapshot (every Monday)
            if day.weekday() == 0:
                inv_rows.append((day.isoformat(), p["sku_id"], max(on_hand, 0)))
                snapshot_counter += 1

            day += timedelta(days=1)

    cur.executemany("INSERT INTO sales (sale_date, sku_id, quantity, unit_price) VALUES (?, ?, ?, ?)", sales_rows)
    cur.executemany("INSERT INTO inventory_snapshots (snapshot_date, sku_id, on_hand) VALUES (?, ?, ?)", inv_rows)
    cur.executemany(
        """INSERT INTO purchase_orders
           (sku_id, order_date, eta_date, received_date, quantity, unit_cost, status)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        po_rows,
    )
    conn.commit()


def _receive_if_due(po, day, cur_hook):  # placeholder; kept for readability in the loop above
    return True


def generate(db_path: Path = DB_PATH) -> Path:
    _seed_everything()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    try:
        _schema(conn)
        products = _insert_products(conn)
        _generate_sales_and_inventory(conn, products)
    finally:
        conn.close()
    return db_path


if __name__ == "__main__":
    path = generate()
    size_mb = os.path.getsize(path) / 1_048_576
    print(f"Generated {path} ({size_mb:.1f} MB)")
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    for table in ("products", "sales", "inventory_snapshots", "purchase_orders"):
        n = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {n:,} rows")
    conn.close()
