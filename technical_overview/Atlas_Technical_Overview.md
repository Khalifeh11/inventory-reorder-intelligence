# Atlas Inventory Reorder Intelligence — Technical Overview

**Client:** Atlas Paints & Tools (Lebanon) · **Initiative:** Phase 2, Use Case B
**Author:** Karim Khalifeh · **Date:** April 2026 · **Program:** ZAKA Certified AI Consultant

---

*This document accompanies the proposal PPTX and is intended for the implementation team. The proposal itself is the right artifact for GM / procurement review.*

## Solution in one paragraph

Atlas's procurement is reactive — SKUs are only reordered after a stockout, and hardware imports take ~2 months to arrive. This solution reads Atlas's existing ERP history, forecasts per-SKU demand over each supplier's lead time, and applies a classical reorder-point + safety-stock formula to flag which SKUs need to be ordered this week. Each flagged SKU is paired with a plain-language explanation (LLM-generated when online; deterministic template otherwise). The entire system runs on Atlas's on-prem server with no cloud dependency, matching the company's reliability and budget constraints.

## Inputs / outputs

| Inputs (read from ERP) | Outputs (to GM / procurement) |
| --- | --- |
| `products` — SKU, cost, supplier, lead time | Weekly reorder queue (ranked by risk + value) |
| `sales` — 10+ years of daily sales | Per-SKU forecast + current on-hand + ROP |
| `inventory_snapshots` — weekly on-hand | Suggested order quantity + expected $ value |
| `purchase_orders` — open and historical POs | Plain-language explanation per recommendation |
| | Stockout-risk dashboard + what-if sliders |

**Real-ERP mapping for S1 implementation.** The generic input names above map to the real Atlas ERP as follows: `products` → `Stock` (18,533 rows with `QTY_ONHAND`, `MINIMUMQTY`, `ORDER_TIME`, `SUPPLIER`, `Categorycode`); `sales` → `Invoice` (167,199) + `Invod` (959,200) filtered by `Type='Sale'`; `inventory_snapshots` → derived from `Invod.QIN / QOUT` history (the ERP stores only current `QTY_ONHAND`, so weekly snapshots will be materialised in S1); `purchase_orders` → `Invoice` filtered by `Type='Purchase'` / PO prefix `PU00`; `bom` → `Asm` (91,170 rows).

## Architecture (single diagram)

```
 ERP (SQL, read-only) → weekly extract → local SQLite cache
                                                │
                                                ▼
                                    Forecasting engine
                                    (moving avg + multiplicative seasonality)
                                                │
                                                ▼
                                    Reorder engine
                                    (ROP + z·σ·√lead_time)
                                                │
                              ┌─────────────────┴──────────────┐
                              ▼                                ▼
                   Streamlit UI (local)            LLM (Claude Haiku, optional)
                   - Dashboard                     - Explanation text only
                   - Drilldown                     - Template fallback if offline
                   - What-if
                              │
                              ▼
                   Human sign-off → PO placed → (existing workflow)
```

## Key components

**1. Forecasting (`src/forecasting.py`)**
Compute monthly seasonality indices from full history; take a trailing 180-day window, deseasonalize, and re-inflate for the forecast horizon. Output: expected daily demand, daily standard deviation, seasonality factor. Deliberately statistical, not ML, per the Phase-2 roadmap decision.

**2. Reorder engine (`src/reorder.py`)**
```
ROP          = avg_daily_demand × lead_time + safety_stock
safety_stock = z(service_level) × σ_daily × √lead_time
flag         = (on_hand + open_POs) ≤ ROP
order_qty    = target_stock − (on_hand + open_POs)
```
Default service level 95% (z=1.645). Review period and lead-time buffer are user-tunable.

**3. LLM explanation (`src/explain.py`)**
Calls `claude-haiku-4-5` with a structured prompt containing only values from the reorder engine. The system prompt forbids inventing numbers — the LLM only rephrases. Falls back to a deterministic Python template if `ANTHROPIC_API_KEY` is unset or the network is down. UI labels each explanation's source.

**4. Streamlit UI (`app.py`)**
Three tabs:
- **Dashboard** — KPIs, reorder queue, risk distribution
- **SKU Drilldown** — per-SKU 10-year chart + 3-month forecast + full recommendation + explanation
- **What-if** — service level, review period, lead-time buffer sensitivity

## How to run the PoC

```bash
cd deliverables/3rd/poc
python3 -m pip install -r requirements.txt
python3 -m src.data_gen           # generate synthetic ERP
streamlit run app.py              # open http://localhost:8501
```

Optional: `export ANTHROPIC_API_KEY=sk-ant-...` before launching to enable LLM explanations.

## Limitations

- Synthetic data in the PoC; real-data performance validated during implementation S2.
- Backtest median MAPE ~12% on paint, ~70% on hardware. Hardware demand is lumpy — safety stock (sized to service level) absorbs forecast error; Croston / TSB is the planned Phase 2.5 upgrade if needed.
- Single-location only; multi-location balancing is out of scope.
- No direct supplier EDI — human-in-the-loop places POs through the existing manual workflow.

## Next steps

1. Complete Phase 0 (inventory-accuracy cycle count) — hard prerequisite.
2. Replace synthetic SQLite with a weekly read-only extract from the real ERP.
3. Backtest on actual Atlas history; compare system recommendations against past stockout events.
4. 2-week paper-parallel UAT with GM and procurement.
5. Go-live with weekly review cadence; monthly accuracy review thereafter.
