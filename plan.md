# 3rd Deliverable — Revision Plan

## Context

The 3rd ZAKA deliverable (AI Transformation Proposal + PoC for "Atlas Paints & Tools") lives in `/Users/karim/Desktop/KARIM/zaka/deliverables/3rd/` and compiles cleanly today (PPTX, PDF, DOCX, running Streamlit PoC, walkthrough script). Two issues need surgical revision — **not a full rewrite**:

1. **Fact-check gap.** Several claims don't match the actual Atlas ERP data exported in `deliverables/2026/atlas_csv_exports/`. The ERP has 29 tables, 2.1M+ rows, 2015–2026, and supports far more than the proposal claims — e.g. "working-capital visibility: none" ignores a 673,825-row `Acctrans` ledger with Balance Sheet tagging. Fake supplier names (Bosch-TR, Makita-CN, Stanley-IT, DeWalt-US) aren't in the real 110-supplier list.
2. **Audience mismatch.** Per ZAKA guidance (Zack), the primary audience should be client stakeholders (GM, procurement lead, supply-chain manager) with evaluators as secondary. Narrative skeleton is already business-oriented, but ~3–5 slides are too technical and need plain-language glosses.

**Outcome:** a proposal that (a) is factually grounded in the real Atlas ERP and (b) reads as a business proposal for a non-technical GM while still demonstrating technical depth to evaluators. Estimated effort: ~2–3 hours of surgical edits + rebuild of PPTX / PDF / DOCX.

**Effort decision:** do NOT redo the whole assignment. Structure, value framing, timeline, risks, budget, success criteria are all at the right altitude. Only dense-technical slides and fact-check items need work.

---

## Part A — Fact-check fixes

All changes are surgical edits to MD sources + matching edits to `build_pptx.py` / `build_docx.py`. No PoC code changes needed (synthetic schema in PoC is intentional).

### A1. Supplier names — drop brand examples

**Problem.** Proposal MD line 96 and `data_gen.py` lines 55–88 cite "Bosch-TR, Makita-CN, Stanley-IT, DeWalt-US". The real `dbo_SetSupplier.csv` has 110 entries (فاميكس, CO.ME, FABITALY, GAOMISHI, RONIX, etc.) — none of the four brand examples match.

**Fix (proposal + tech overview only — PoC keeps them, since PoC is synthetic):**
- Proposal MD line 96: replace `"depending on supplier (Bosch-TR, Makita-CN, Stanley-IT, DeWalt-US)"` → `"depending on the supplier; per-supplier lead times are stored in the ERP."`
- No change needed in PoC code — synthetic fixtures can remain synthetic.

### A2. "Working capital visibility: none" — reframe

**Problem.** Proposal MD line 40 table cell and PPTX slide 5 (`build_pptx.py:277`) both say working-capital visibility is "none". The ERP has 4,395 accounts with BS/PL classifications, a 673,825-row `Acctrans` ledger, daily closings (`Dclose`), and multi-currency rates.

**Fix.**
- Proposal MD line 40: `"Working capital visibility"` → `"Inventory working-capital visibility"` ; `"none"` → `"general ledger only — no SKU-level coverage, deadstock, or forward-forecast view."`
- `build_pptx.py:277`: same edit in slide 5 table.

### A3. Deadstock "unmeasured" — reframe

**Problem.** Proposal MD line 38 and `build_pptx.py:275` say deadstock is "unmeasured, believed ~20–30%". The raw material exists to measure it directly: `Stock.QTY_ONHAND` × `Invod.QOUT` history spanning 11 years.

**Fix.**
- Proposal MD line 38: `"unmeasured, believed ~20–30% of hardware stock"` → `"not currently tracked on a dashboard; estimated ~20–30% from GM discovery — measurable from QTY_ONHAND + 11-year QOUT history."`
- `build_pptx.py:275`: mirror.

### A4. Schema names — add real-ERP mapping

**Problem.** Section 4.1 of proposal MD (lines 134–141), tech overview lines 16–19, and PPTX slide 13 (`build_pptx.py:437–441`) all use generic names `products / sales / inventory_snapshots / purchase_orders / bom`. These match the PoC's synthetic schema but aren't the real ERP.

**Fix (keep generic names in the main table for PoC continuity, add footnote mapping):**

Add one row below the Data Inputs table in both proposal MD and PPTX slide 13:

> **Real-ERP mapping for implementation (S1):** `products`→`Stock` (18,533 rows, with `QTY_ONHAND`, `MINIMUMQTY`, `ORDER_TIME`, `SUPPLIER`, `Categorycode`). `sales`→`Invoice` (167,199) + `Invod` (959,200) filtered by `Type='Sale'`. `inventory_snapshots`→derived from `Invod.QIN/QOUT` history (real ERP stores only current `QTY_ONHAND`; weekly snapshots will be materialised in S1). `purchase_orders`→`Invoice` filtered by `Type='Purchase'` / prefix `PU00`. `bom`→`Asm` (91,170 rows).

Mirror in tech overview MD as a one-paragraph note under the Inputs/Outputs table.

### A5. SKU count qualifier

**Problem.** "~200–500 active SKUs" (proposal MD lines 44, 197; PPTX slides 10 and 17) out of 18,533 total in the real Stock table — plausible, but not yet validated against `Invod` velocity data.

**Fix.**
- Proposal MD line 44: `"~200–500 SKUs"` → `"~200–500 actively traded SKUs (subject to S2 velocity analysis; the Stock master has 18,533 records, most of which are raw materials, packaging, or discontinued items)."`
- Shorten for PPTX slides 10 + 17: `"~200–500 active SKUs (subject to S2 velocity analysis)"`.

### A6. Lead-time data quality note

**Problem.** Proposal MD line 96 states "Lead times are known per supplier" and "55–75 days from order to arrival". The real `Stock.ORDER_TIME` field is sparse. Claim is directionally right but ignores the data-quality gap.

**Fix.** Add to proposal MD line 96 end (or as a new bullet under "Current state"):
> `ORDER_TIME` in the ERP is sparse and ad-hoc today — Phase 0 cycle-count work includes standardising lead-time capture per supplier.

---

## Part B — Audience-tone softening (primary audience: GM + procurement)

Structure is already business-oriented. Only 4 slides / sections need work. All other slides (Executive Overview, Business Objective, In/Out Scope, Success Criteria, Commercial, Risks, Next Steps) stay as-is.

### B1. Slide 12 — Appropriate AI Approach (`build_pptx.py:402–429`)

Today: dense formula bullets with Greek letters and no gloss.

**Fix — keep the formula but add one-line plain-English gloss per line:**

```
• Forecast = moving average + monthly seasonality, per SKU
  → we learn each SKU's normal monthly rhythm and project it forward.
• Deseasonalize trailing 180 days → baseline daily demand; reinflate over horizon
  → strip out the seasonal bump to see true baseline, then add it back for the forecast month.
• Reorder: ROP = avg_daily_demand × lead_time + safety_stock
  → order when stock drops below: what you'll sell during the wait + a buffer.
• safety_stock = z(SL) × σ × √LT
  → the noisier the demand or the longer the wait, the more buffer you hold.
• Defaults: service level 95% (z ≈ 1.645), review period 14 days
  → accept stockout on 1 review cycle in 20; revisit each SKU every 2 weeks.
• LLM layer (Claude Haiku) restates engine numbers — does not invent values
  → same numbers, plain language; falls back to template when offline.
```

Implementation: edit `s12_ai_approach()` in `build_pptx.py`. The `_bulleted` helper already supports sub-indent via `indent_levels`; use `lvl=1` for the gloss lines so they render smaller. Mirror the gloss in proposal MD section 4.2–4.3.

### B2. Slide 13 — Data Readiness (`build_pptx.py:432–454`)

Today: table with generic column names only.

**Fix.** Keep the 5-row table; add one sentence ABOVE the table: *"Five ERP tables already owned by Atlas — a decade of data, no new collection needed."* Add the A4 real-ERP mapping note below the table.

### B3. Slide 17 — Data Flow (`build_pptx.py:498–521`)

Today: ASCII art with `(expected_daily, std, seasonality)` and similar dev-speak.

**Fix.**
- Add a one-sentence header above: *"What happens every Monday, step by step."*
- Replace technical labels where trivial: `(expected_daily, std, seasonality)` → `(forecast + uncertainty + seasonal factor)`; `ROP + safety stock (classical formula, ~50 lines of Python)` → `Reorder point + buffer (ROP + safety stock)`.
- Add a closing sentence below: *"Every arrow is read-only against the ERP except the final step — a human places the PO through the existing process."*

### B4. Slide 18 — Technical Architecture (`build_pptx.py:524–554`)

Today: ASCII box diagram + component-sizing bullets.

**Fix.**
- Header sentence above the diagram: *"One small Python service on your existing server. LLM call is optional and degrades gracefully."*
- Keep the ASCII diagram.
- Rewrite the 3 component-sizing bullets (lines 549–552) to translate MB into business terms:
  - `"Python service ≈50 MB peak memory; SQLite cache <50 MB"` → `"Tiny footprint — entire system fits in 100 MB on your current server; no new hardware needed."`
  - `"LLM cost ~200 tokens/call × ~20 reorders/week"` → `"LLM cost: under $5 / month at Atlas volumes — and optional."`
  - `"Why on-prem: unreliable internet..."` → keep (already business-oriented).

### B5. Technical Overview document

`Atlas_Technical_Overview.md` stays technical (it's the implementation-team artifact). Apply the A4 schema-mapping note (lines 12–21) and add a header paragraph up top: *"This document accompanies the proposal PPTX and is intended for the implementation team. The proposal itself is the right artifact for GM / procurement review."*

### B6. Demo walkthrough script (`demo/walkthrough_script.md`)

- Align the 0:30–1:00 "Approach" paragraph with the new plain-language glosses from B1.
- 1:00–3:00 demo narration is already business-friendly — no changes.

---

## Files to modify

| # | File | Change scope |
|---|---|---|
| 1 | `deliverables/3rd/proposal/Atlas_AI_Solution_Proposal.md` | A1, A2, A3, A4, A5, A6, B1 gloss in §4 |
| 2 | `deliverables/3rd/proposal/build_pptx.py` | A2 (line 277), A3 (275), A4 (new row slide 13), A5 (slides 10, 17), B1 (`s12_ai_approach`), B2 (`s13_data_readiness`), B3 (`s17_data_flow`), B4 (`s18_tech_arch`) |
| 3 | `deliverables/3rd/proposal/build_pdf.py` | Re-run after MD edits — check if it reads MD or duplicates content; edit if it duplicates |
| 4 | `deliverables/3rd/technical_overview/Atlas_Technical_Overview.md` | A4 schema-mapping note, B5 header paragraph |
| 5 | `deliverables/3rd/technical_overview/build_docx.py` | Re-run; check if it duplicates content |
| 6 | `deliverables/3rd/demo/walkthrough_script.md` | B6 — minor alignment with new glosses |

**No changes to:** `deliverables/3rd/poc/` (PoC code stays — synthetic schema, synthetic suppliers are fine for PoC; the real-data swap is an S1 implementation task, not a PoC task).

---

## Execution order

1. **Part A — fact-check fixes** (≈45 min): edit proposal MD and `build_pptx.py` inline (sections A1–A6); edit tech overview MD (A4).
2. **Part B — audience glosses** (≈60 min): edit `s12_ai_approach`, `s13_data_readiness`, `s17_data_flow`, `s18_tech_arch` in `build_pptx.py`; mirror in proposal MD §4; update tech overview header (B5); align demo script (B6).
3. **Rebuild artifacts** (≈10 min):
   ```
   cd deliverables/3rd/proposal && python3 build_pptx.py && python3 build_pdf.py
   cd ../technical_overview && python3 build_docx.py
   ```
4. **Verify** (see below).

---

## Verification

- **PPTX**: open `Atlas_AI_Solution_Proposal.pptx` and visually check slides 5, 10, 12, 13, 17, 18 — confirm the 6 fact-check fixes are visible and the glosses render at the right size/indent. No overflow. No fake supplier names anywhere.
- **PDF**: open `Atlas_AI_Solution_Proposal.pdf`; spot-check section 4.1 for the real-ERP mapping note and section 3 for the reframed working-capital / deadstock lines.
- **DOCX**: open `Atlas_Technical_Overview.docx`; confirm schema-mapping note and "intended for implementation team" header.
- **Grep check**: `Grep pattern="Bosch|Makita|Stanley|DeWalt|Working capital visibility \| none|unmeasured"` across `deliverables/3rd/proposal/` and `deliverables/3rd/technical_overview/` — expect zero hits after fixes (PoC folder excluded; its synthetic fixtures can keep them).
- **Demo script sanity**: read `demo/walkthrough_script.md` end-to-end as if presenting — language should match the softened PPTX slides.
- **PoC still runs**: `cd deliverables/3rd/poc && streamlit run app.py` → open localhost:8501, confirm dashboard loads.

---

## Out of scope (explicit non-goals)

- Full rewrite of the proposal narrative — structure stays.
- PoC code changes — synthetic data and synthetic supplier names in the PoC are intentional.
- Swapping real Atlas schema into PoC — that's an S1 implementation activity, not a proposal revision.
- Changing scoring / prioritization numbers, timeline, budget, or roadmap tables — those remain as delivered.
- New slides. The 26-slide structure mirrors the ZAKA template exactly and should not be modified.

---

## Open questions to confirm at start of next chat

1. **Real-supplier names in the footnote?** Plan assumes "no — keep generic, since exposing real vendor relationships is unnecessary for a capstone." Flip to yes if you want the footnote to cite 2–3 real suppliers (e.g. فاميكس / FABITALY) to show real-data grounding.
2. **Speaker notes?** Plan glosses land on-slide. Alternative: formulas on-slide, glosses in PPTX speaker notes (less cluttered slides, but evaluators reading the PPTX cold miss the explanation). Default = on-slide.
3. **Rebuild PDF + DOCX or MD only?** Plan assumes rebuild all three. Flip if you want to hand-edit binaries later.
