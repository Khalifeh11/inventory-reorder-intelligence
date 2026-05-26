# Atlas — Inventory Reorder Intelligence PoC

Proof-of-concept for the Phase 2 initiative in the Atlas Paints & Tools AI roadmap:
**automated reorder recommendations** driven by statistical forecasting, with optional
LLM-generated plain-language explanations.

Designed to match Atlas's real-world constraints:

- **Runs fully on-prem** — no cloud dependency. SQLite + Python only.
- **No API integration required** — reads from a SQL snapshot of the ERP.
- **Offline-capable** — the LLM explanation layer falls back to a deterministic template when the Anthropic API is unavailable.
- **Statistical, not ML** — moving average + multiplicative seasonality + classical reorder-point formula. Transparent to a non-technical GM.

---

## Quick start

```bash
# 1. Install dependencies (virtualenv recommended)
python3 -m pip install -r requirements.txt

# 2. Generate the synthetic ERP database (10 years, 60 SKUs, ~128k sales rows)
python3 -m src.data_gen

# 3. (Optional) Enable LLM-generated explanations
export ANTHROPIC_API_KEY=sk-ant-...

# 4. Launch the Streamlit app
streamlit run app.py
# or: python3 -m streamlit run app.py
```

Open `http://localhost:8501` (or whichever port Streamlit binds to).

---

## What's inside

```
poc/
├── app.py                         Streamlit UI (Dashboard, Drilldown, What-if)
├── src/
│   ├── data_gen.py                Synthetic ERP SQLite generator
│   ├── forecasting.py             Moving avg + multiplicative seasonality
│   ├── reorder.py                 ROP + safety stock + recommendation
│   └── explain.py                 LLM (Anthropic) explanation + template fallback
├── notebooks/
│   ├── 01_methodology.ipynb       Walk through data, forecast, reorder, MAPE
│   └── 01_methodology_executed.ipynb   Same notebook, pre-executed with outputs
├── data/
│   └── synthetic_erp.sqlite       Generated on first run
├── requirements.txt
└── README.md
```

## Architecture

```
 ┌──────────────┐  SQL read        ┌─────────────────┐
 │  Atlas ERP   │  (in PoC: sim.)  │  Forecasting    │
 │  (SQLite /   │ ──────────────▶  │  moving avg +   │
 │   MSSQL)     │                  │  seasonality    │
 └──────────────┘                  └───────┬─────────┘
                                           │
                                           ▼
                                  ┌──────────────────┐
                                  │  Reorder logic   │
                                  │  ROP + safety    │
                                  │  stock           │
                                  └───────┬──────────┘
                                          │
                         ┌────────────────┴─────────────────┐
                         ▼                                  ▼
                 ┌──────────────┐                   ┌──────────────────┐
                 │  Streamlit   │◀──── optional ───▶│  Anthropic LLM   │
                 │  dashboard   │                   │  (explanations)  │
                 └──────────────┘                   └──────────────────┘
                                                    Falls back to local
                                                    template if offline.
```

## Key modelling choices

- **Service level 95% by default** — matches typical retail wholesaler target; adjustable in the sidebar.
- **Seasonality = multiplicative monthly indices** derived from full 10-year history. Works for paint (smooth, high-volume). Hardware is lumpier, so the safety-stock term — sized to service level — absorbs most of the forecast error.
- **Horizon = lead_time + review_period** — we order enough today to cover the full time until the next review cycle.
- **Reactive reorder simulated in the synthetic history**, so the "before" state matches Atlas's current pain: SKUs hit zero and only then trigger a PO.

## Backtest results (synthetic data, 2026-Q1)

- **60 SKUs** tracked (20 paint, 40 hardware)
- **Paint median MAPE**: ~12% (baseline model is strong)
- **Hardware median MAPE**: ~70% (lumpy, slow-moving; safety stock compensates)
- **~13 SKUs flagged for reorder** as-of 2026-03-31 → total recommended PO value ~$44k
- **High-stockout-risk SKUs** surfaced prominently so the GM and procurement can action them first

Full numbers in `notebooks/01_methodology.ipynb`.

## LLM explanation layer

Every reorder recommendation gets a 2–3 sentence plain-language explanation. Two paths:

- **LLM path** (when `ANTHROPIC_API_KEY` is set): calls `claude-haiku-4-5` with a structured prompt containing only the numbers the reorder engine produced. The system prompt explicitly forbids inventing new numbers — governance posture aligned with Module 12.
- **Template path** (default, offline): deterministic rendering of the same underlying numbers. No surprise behavior; fully reproducible.

The Streamlit UI shows which path produced each explanation (`llm` vs. `template`).

## Not included / out of scope

- Real Atlas ERP extract — this PoC runs on fully synthetic data that matches the shape of the real ERP.
- Direct PO placement with suppliers — the PoC recommends; a human approves and places orders (Module 12 human-in-the-loop posture).
- Intermittent-demand models (Croston, TSB) — natural upgrade path for low-velocity hardware SKUs.
- Multi-location inventory balancing — Atlas is single-location in this scope.

## Reproducibility

Seed is fixed (`SEED = 42` in `src/data_gen.py`) so regenerating the DB produces identical data. MAPE and reorder counts are therefore stable across runs.
