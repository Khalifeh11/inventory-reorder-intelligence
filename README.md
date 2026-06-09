# Atlas Inventory Reorder Intelligence

**Client:** Atlas Paints & Tools (Lebanon) · **Initiative:** Phase 2, Use Case B
**Author:** Karim Khalifeh · **Program:** ZAKA Certified AI Consultant

Atlas's procurement is reactive — SKUs are reordered only after a stockout, and hardware
imports take ~2 months to arrive. This deliverable reads Atlas's existing ERP history,
forecasts per-SKU demand over each supplier's lead time, and applies a classical
reorder-point + safety-stock formula to flag which SKUs need ordering this week. A bounded
LLM layer writes a weekly procurement briefing (triage / supplier consolidation / budget
sequencing) on top of the engine's numbers, grounding-checked so it cannot invent figures.
Everything runs on-prem with no cloud dependency.

---

## What's in this repo

| Path | Artifact | Audience |
| --- | --- | --- |
| [`poc/`](poc/) | Runnable proof-of-concept (Streamlit app + forecasting/reorder engine + LLM layer) | Implementation team |
| [`technical_overview/`](technical_overview/Atlas_Technical_Overview.md) | Technical overview — architecture, formulas, components, limitations | Implementation team |
| [`proposal/`](proposal/Atlas_AI_Solution_Proposal.pdf) | Solution proposal (PDF + PPTX) | GM / procurement |

The deeper technical detail lives in [`technical_overview/Atlas_Technical_Overview.md`](technical_overview/Atlas_Technical_Overview.md);
the PoC's own README is at [`poc/README.md`](poc/README.md).

---

## Quick start (run the PoC)

The PoC is a local Streamlit app. It ships with the synthetic ERP database already
committed, so no data-generation step is required to see it run.

```bash
cd poc

# 1. Create and activate a virtual environment (the app was built on Python 3.9+)
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) enable the LLM path — see note below
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# 4. Launch
streamlit run app.py                 # opens http://localhost:8501
```

> **Why activate the venv first?** The app auto-loads `ANTHROPIC_API_KEY` from `poc/.env`
> via `python-dotenv`, but only if the *running* interpreter has that package installed —
> i.e. the venv's. If you launch a system-wide `streamlit`, the app still runs but silently
> falls back to the offline deterministic template and the LLM never engages (the sidebar
> flags this). If you prefer not to activate, run it explicitly: `.venv/bin/streamlit run app.py`.

**Regenerating the data (optional).** The database is committed, but to rebuild it from
scratch (fixed seed, identical output):

```bash
python3 -m src.data_gen
```

---

## How it works (one diagram)

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
                   - Dashboard + weekly briefing   - Weekly triage briefing
                   - Drilldown                     - Per-SKU explanation
                   - What-if                       - Grounding-checked briefing;
                                                     template fallback offline
                              │
                              ▼
                   Human sign-off → PO placed → (existing workflow)
```

- **Forecasting** (`poc/src/forecasting.py`) — monthly seasonality indices over full
  history; trailing 180-day window, deseasonalized then re-inflated for the horizon.
  Statistical, not ML, per the Phase-2 roadmap.
- **Reorder engine** (`poc/src/reorder.py`) — `ROP = avg_daily_demand × lead_time + z·σ·√lead_time`;
  flags when `on_hand + open_POs ≤ ROP`; sizes the order to cover lead time + review period.
- **LLM layer** (`poc/src/explain.py`) — a weekly briefing (`summarize_week`) and per-SKU
  explanation (`explain`), both on engine-produced numbers only. The briefing is gated by a
  numeric-grounding guard: any figure that can't be traced to the engine is rejected and the
  deterministic template is shown instead. Falls back to the template when offline or no API key.

---

## Constraints honoured

- **On-prem, no cloud dependency** — SQLite + Python; the LLM call is optional.
- **Offline-capable** — full deterministic template path when the Anthropic API is unavailable.
- **Grounded AI** — the load-bearing briefing cannot display a number the engine didn't produce.
- **Human-in-the-loop** — the system recommends; a person approves and places the PO.

## Not in scope

Real ERP extract (PoC runs on synthetic data matching the ERP's shape), direct supplier EDI,
intermittent-demand models (Croston/TSB), and multi-location balancing — all flagged as
implementation or Phase-2.5 follow-ups in the technical overview.
