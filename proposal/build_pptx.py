"""Build Atlas_AI_Solution_Proposal.pptx following the ZAKA template's 26-slide structure.

Slide titles and order mirror the program's "AI Solution Proposal Template" exactly;
the content at each slot is Atlas-specific and drawn from the proposal markdown.

Style: navy #1F2A44 + accent orange #E67E22 + light gray #F4F6F8. 16:9 (13.33 x 7.5).

Run: python3 build_pptx.py
"""

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

OUT = Path(__file__).resolve().parent / "Atlas_AI_Solution_Proposal.pptx"

NAVY = RGBColor(0x1F, 0x2A, 0x44)
ORANGE = RGBColor(0xE6, 0x7E, 0x22)
LIGHT = RGBColor(0xF4, 0xF6, 0xF8)
GRAY = RGBColor(0x5A, 0x6A, 0x7A)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

FOOTER_TEXT = "Atlas Paints & Tools — AI Transformation Proposal"


# ---------- primitives ----------

def _blank_slide(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def _fill(shape, color):
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    shape.shadow.inherit = False


def _add_bg(slide, color):
    rect = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, SLIDE_H)
    _fill(rect, color)
    return rect


def _add_header_bar(slide, title, subtitle=None):
    strip = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, Inches(0.9))
    _fill(strip, NAVY)
    accent = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(0.9), SLIDE_W, Inches(0.05))
    _fill(accent, ORANGE)

    tb = slide.shapes.add_textbox(Inches(0.5), Inches(0.12), SLIDE_W - Inches(1.0), Inches(0.75))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = title
    r.font.bold = True
    r.font.size = Pt(24)
    r.font.color.rgb = WHITE
    if subtitle:
        p2 = tf.add_paragraph()
        r2 = p2.add_run()
        r2.text = subtitle
        r2.font.size = Pt(12)
        r2.font.color.rgb = LIGHT


def _add_footer(slide, idx, total):
    tb = slide.shapes.add_textbox(Inches(0.5), SLIDE_H - Inches(0.4), SLIDE_W - Inches(1.0), Inches(0.3))
    p = tb.text_frame.paragraphs[0]
    p.alignment = PP_ALIGN.RIGHT
    r = p.add_run()
    r.text = f"{FOOTER_TEXT}  ·  {idx}/{total}"
    r.font.size = Pt(9)
    r.font.color.rgb = GRAY


def _bulleted(slide, top, left, width, height, items, title=None, indent_levels=None,
              size_l0=14, size_l1=12):
    if title:
        tb_title = slide.shapes.add_textbox(left, top, width, Inches(0.4))
        p = tb_title.text_frame.paragraphs[0]
        r = p.add_run()
        r.text = title
        r.font.size = Pt(16)
        r.font.bold = True
        r.font.color.rgb = NAVY
        top = top + Inches(0.5)
        height = height - Inches(0.5)

    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    indent_levels = indent_levels or [0] * len(items)
    for i, (txt, lvl) in enumerate(zip(items, indent_levels)):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.level = lvl
        r = p.add_run()
        r.text = ("• " if lvl == 0 else "– ") + txt
        r.font.size = Pt(size_l0) if lvl == 0 else Pt(size_l1)
        r.font.color.rgb = NAVY if lvl == 0 else GRAY
        p.space_after = Pt(4)


def _add_box(slide, left, top, width, height, title, body, color_accent=ORANGE,
             body_size=11, title_size=13):
    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    box.fill.solid()
    box.fill.fore_color.rgb = LIGHT
    box.line.color.rgb = color_accent
    box.line.width = Pt(1.25)
    box.shadow.inherit = False

    tb = slide.shapes.add_textbox(
        left + Inches(0.2), top + Inches(0.15), width - Inches(0.4), height - Inches(0.3)
    )
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = title
    r.font.size = Pt(title_size)
    r.font.bold = True
    r.font.color.rgb = NAVY
    p2 = tf.add_paragraph()
    r2 = p2.add_run()
    r2.text = body
    r2.font.size = Pt(body_size)
    r2.font.color.rgb = GRAY


def _add_table(slide, left, top, width, height, data, header=True, first_col_bold=False):
    rows, cols = len(data), len(data[0])
    tbl_shape = slide.shapes.add_table(rows, cols, left, top, width, height)
    tbl = tbl_shape.table
    for r_i, row in enumerate(data):
        for c_i, cell_text in enumerate(row):
            cell = tbl.cell(r_i, c_i)
            cell.text = ""
            tf = cell.text_frame
            p = tf.paragraphs[0]
            run = p.add_run()
            run.text = str(cell_text)
            run.font.size = Pt(11)
            if header and r_i == 0:
                run.font.bold = True
                run.font.color.rgb = WHITE
                cell.fill.solid()
                cell.fill.fore_color.rgb = NAVY
            else:
                run.font.color.rgb = NAVY
                if first_col_bold and c_i == 0:
                    run.font.bold = True
                cell.fill.solid()
                cell.fill.fore_color.rgb = WHITE if r_i % 2 == 1 else LIGHT


def _section_divider(slide, section_title):
    """Full-bleed navy divider slide with large white title and an orange accent bar."""
    _add_bg(slide, NAVY)
    accent = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                    Inches(0.9), Inches(3.2),
                                    Inches(1.2), Inches(0.08))
    _fill(accent, ORANGE)
    tb = slide.shapes.add_textbox(Inches(0.9), Inches(3.4), Inches(12), Inches(2.0))
    p = tb.text_frame.paragraphs[0]
    r = p.add_run()
    r.text = section_title
    r.font.bold = True
    r.font.size = Pt(48)
    r.font.color.rgb = WHITE


def _mono_block(slide, left, top, width, height, text, size=12):
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    for i, line in enumerate(text.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        r = p.add_run()
        r.text = line
        r.font.name = "Menlo"
        r.font.size = Pt(size)
        r.font.color.rgb = NAVY


# ---------- slide builders (26 total) ----------

def s01_title(slide):
    _add_bg(slide, NAVY)
    accent = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                    Inches(0.9), Inches(2.8),
                                    Inches(1.2), Inches(0.08))
    _fill(accent, ORANGE)

    tb = slide.shapes.add_textbox(Inches(0.9), Inches(3.0), Inches(12), Inches(3.0))
    tf = tb.text_frame
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = "AI Transformation Proposal"
    r.font.bold = True
    r.font.size = Pt(44)
    r.font.color.rgb = WHITE

    p2 = tf.add_paragraph()
    r2 = p2.add_run()
    r2.text = "Inventory Reorder Intelligence"
    r2.font.size = Pt(28)
    r2.font.color.rgb = ORANGE

    p3 = tf.add_paragraph()
    r3 = p3.add_run()
    r3.text = "\nAtlas Paints & Tools"
    r3.font.size = Pt(20)
    r3.font.color.rgb = LIGHT

    tb2 = slide.shapes.add_textbox(Inches(0.9), Inches(6.3), Inches(12), Inches(0.9))
    tf2 = tb2.text_frame
    for i, line in enumerate([
        "Submitted by: Karim Khalifeh",
        "Program: ZAKA Certified AI Consultant  ·  April 2026",
    ]):
        p = tf2.paragraphs[0] if i == 0 else tf2.add_paragraph()
        r = p.add_run()
        r.text = line
        r.font.size = Pt(12)
        r.font.color.rgb = LIGHT


def s02_outline(slide):
    _add_header_bar(slide, "Outline")
    items = [
        "Executive Overview",
        "Use Case Selection & Scope",
        "Technical Architecture",
        "Commercial & Pricing Considerations",
    ]
    _bulleted(slide, Inches(1.4), Inches(1.4), Inches(10.5), Inches(5.2),
              items, size_l0=20)


def s03_divider_exec(slide):
    _section_divider(slide, "Executive Overview")


def s04_exec_1(slide):
    _add_header_bar(slide, "Executive Overview (1)",
                    "The problem Atlas is solving, and what this initiative delivers")
    _bulleted(
        slide, Inches(1.0), Inches(1.3), Inches(11.3), Inches(5.6),
        [
            "Atlas Paints & Tools — a family-owned Lebanese paint manufacturer and hardware / power-tools wholesaler — is losing revenue because procurement is reactive.",
            "Hardware imports are ordered only after a SKU hits zero, triggering stockouts that routinely last 2+ months (entire supplier lead time).",
            "In parallel, slow-moving items accumulate as deadstock because reorder points have never been formalized in the ERP.",
            "This proposal: Inventory Reorder Intelligence — a statistical forecasting + classical reorder-point system that turns 10+ years of existing ERP data into weekly reorder recommendations with plain-language explanations.",
            "Runs fully on-prem. No cloud dependency. No ML tooling. Matches Atlas's unreliable internet and zero-budget reality.",
            "Human-in-the-loop: the system recommends; the GM and procurement approve; the existing manual PO workflow continues unchanged.",
        ],
    )


def s05_exec_2(slide):
    _add_header_bar(slide, "Executive Overview (2)",
                    "Priority Initiative — the top Business Impact × Feasibility candidate in the roadmap")
    data = [
        ["Lever", "Current state", "Target with this initiative"],
        ["Stockout duration on import SKUs", "~2 months (full lead time)", "<2 weeks on >80% of events"],
        ["Deadstock tied in slow-movers", "not on a dashboard; ~20–30% from GM discovery (measurable from QTY_ONHAND + QOUT history)", "reduce 30–50% in year 1"],
        ["Procurement decisions", "reactive, discovered via stockout", "1 review cycle / week, proactive"],
        ["Inventory working-capital visibility", "general ledger only — no SKU-level coverage / deadstock / forecast view", "weekly dashboard"],
    ]
    _add_table(slide, Inches(0.6), Inches(1.4), Inches(12.1), Inches(3.2), data)

    tb = slide.shapes.add_textbox(Inches(0.6), Inches(4.9), Inches(12.1), Inches(1.8))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = "Selected from the 2nd-deliverable roadmap as the top Phase-2 initiative — Business Impact 3.8 / Feasibility 3.8 (the 'Priority Initiative' quadrant)."
    r.font.size = Pt(13)
    r.font.bold = True
    r.font.color.rgb = NAVY
    p2 = tf.add_paragraph()
    r2 = p2.add_run()
    r2.text = "Figures above are illustrative ranges, not commitments. Year-1 gains depend on execution plus the Phase 0 inventory-accuracy prerequisite."
    r2.font.size = Pt(11)
    r2.font.italic = True
    r2.font.color.rgb = GRAY


def s06_divider_use_case(slide):
    _section_divider(slide, "Use Case Selection & Scope")


def s07_use_case_1(slide):
    _add_header_bar(slide, "Use Case Selection (1)",
                    "Prioritization matrix — why Use Case B was chosen")
    data = [
        ["#", "Use Case", "Impact", "Feasibility", "Quadrant"],
        ["A", "Production Planning & Cost Optimization", "3.8", "3.0", "Strategic Bet"],
        ["B", "Inventory Reorder Intelligence  ← selected", "3.8", "3.8", "Priority Initiative"],
        ["C", "Customer Profitability Analysis", "2.4", "4.8", "Quick Win"],
        ["D", "Pricing Optimization", "2.6", "4.6", "Quick Win"],
        ["E", "Sales Forecasting", "2.6", "3.8", "Quick Win"],
    ]
    _add_table(slide, Inches(0.5), Inches(1.3), Inches(12.3), Inches(3.6), data)
    tb = slide.shapes.add_textbox(Inches(0.6), Inches(5.2), Inches(12.1), Inches(1.8))
    p = tb.text_frame.paragraphs[0]
    r = p.add_run()
    r.text = ("B is the single best impact-per-effort candidate in Atlas's portfolio and the first "
              "initiative in the roadmap where the deliverable is a working planning system — a "
              "step up from the dashboard-grade Quick Wins (C, D) that precede it.")
    r.font.size = Pt(12)
    r.font.color.rgb = NAVY


def s08_use_case_2(slide):
    _add_header_bar(slide, "Use Case Selection (2)",
                    "Justification — why this works for Atlas specifically, right now")
    _bulleted(
        slide, Inches(0.8), Inches(1.2), Inches(11.7), Inches(5.8),
        [
            "Pain is concrete and measurable. 2-month stockouts and deadstock accumulation were surfaced by the GM during 1st-deliverable discovery — they translate directly into lost sales and tied-up working capital.",
            "Data exists and is clean. 10+ years of sales, BOM, POs and inventory snapshots are already in the ERP and SQL-accessible. Lead times are known per supplier.",
            "Technique is mature and transparent. Classical reorder-point + safety stock has been the inventory-theory standard since the 1950s — no black box, which matters for a company with zero AI experience and no internal data team.",
            "Phase 0 is already scheduled. Inventory-accuracy cycle counting + populating reorder-point fields in the ERP is the named Phase 0 in the roadmap; this initiative consumes that output directly.",
            "Organizational fit. 16-person company, direct-decision-maker GM — a weekly review cadence is realistic from week one with no multi-layer change management.",
        ],
    )


def s09_business_objective(slide):
    _add_header_bar(slide, "Business Objective",
                    "What the Monday-morning workflow looks like, and the dual value lever")
    _bulleted(
        slide, Inches(0.6), Inches(1.2), Inches(6.3), Inches(5.8),
        [
            "Every Monday, GM + procurement open a local dashboard.",
            "AI briefing up top: which few orders truly matter now, what to defer, where to consolidate by supplier.",
            "SKUs to reorder this week — ranked by stockout risk and PO value.",
            "Why each SKU — plain-language 2–3 sentence explanation.",
            "Suggested order qty, expected arrival date, total PO value.",
            "Drill-down: 10-yr history + forward forecast per SKU.",
            "Procurement reviews, approves (or edits), sends POs through the existing manual channel.",
            "Monthly: accuracy review + service-level tuning per SKU segment.",
        ],
        title="Target-state workflow",
    )
    _add_box(
        slide, Inches(7.1), Inches(1.2), Inches(5.8), Inches(5.8),
        "DUAL VALUE LEVER",
        "1. AVOID REVENUE LOSS\n"
        "   Prevent stockouts on hardware imports — the primary revenue category — "
        "where a SKU at zero means B2B customers buy from competitors for 2 months.\n\n"
        "2. RELEASE WORKING CAPITAL\n"
        "   Stop over-ordering slow-movers. Coverage-days become visible; deadstock "
        "surfaces for the first time.\n\n"
        "This combined effect is typically the largest single P&L move a small "
        "wholesaler can make — even with a basic statistical baseline. "
        "2nd-deliverable Business Impact score: 3.8 / 5.",
        title_size=14,
    )


def s10_in_scope(slide):
    _add_header_bar(slide, "In Scope Boundaries",
                    "What this initiative will deliver")
    _bulleted(
        slide, Inches(0.8), Inches(1.2), Inches(11.7), Inches(5.8),
        [
            "Weekly reorder recommendations for active paint + hardware SKUs (~200–500, subject to S2 velocity analysis; ERP Stock master holds 18,533 records incl. raw materials / packaging / discontinued).",
            "Forecast horizon = supplier lead time + review period (typically 7–75 days per SKU).",
            "Human sign-off UI: GM / procurement lead reviews and approves recommendations before any PO is sent.",
            "Weekly AI briefing (triage + supplier consolidation) + plain-language 'why' per recommendation (LLM-generated, grounding-checked; offline template fallback).",
            "Backtest MAPE + stockout-days tracking dashboard for continuous improvement.",
            "Runs on the existing on-prem server — no cloud dependency; LAN-only browser access.",
        ],
    )


def s11_out_of_scope(slide):
    _add_header_bar(slide, "Out of Scope Boundaries",
                    "What is explicitly excluded — to protect scope and timeline")
    _bulleted(
        slide, Inches(0.8), Inches(1.2), Inches(11.7), Inches(5.8),
        [
            "Direct EDI / API integration with suppliers. Manual PO placement through the existing workflow continues.",
            "Multi-location inventory balancing. Atlas is single-location for the SKUs in scope.",
            "Production scheduling. That is Phase 3 (Use Case A); this initiative feeds it but does not solve it.",
            "ML models beyond the statistical baseline (Croston, TSB, Prophet, etc.) — queued as Phase 2.5 if the baseline underperforms on specific SKU segments.",
            "Automated PO placement. No machine action against supplier systems in this phase.",
        ],
    )


def s12_ai_approach(slide):
    _add_header_bar(slide, "Appropriate AI Approach",
                    "Statistical forecasting + classical ROP + bounded LLM layer (weekly briefing + explanations)")
    _bulleted(
        slide, Inches(0.6), Inches(1.2), Inches(6.2), Inches(5.8),
        [
            "Forecast: moving average + multiplicative monthly seasonality, per SKU.",
            "we learn each SKU's normal monthly rhythm and project it forward.",
            "Deseasonalize trailing 180 days → baseline daily demand; reinflate over horizon.",
            "strip out the seasonal bump to see true baseline, then add it back for the forecast month.",
            "Reorder: ROP = avg_daily_demand × lead_time + safety_stock.",
            "order when stock drops below what you'll sell during the wait + a buffer.",
            "Buffer: safety_stock = z(SL) × σ × √LT.",
            "the noisier the demand or the longer the wait, the more buffer you hold.",
            "Defaults: service level 95% (z ≈ 1.645), review period 14 days.",
            "accept stockout on 1 review cycle in 20; revisit each SKU every 2 weeks.",
            "LLM layer (Claude Haiku): weekly triage briefing + per-SKU 'why'.",
            "synthesises act-now / defer / consolidate; a grounding check rejects any invented figure → template fallback.",
        ],
        indent_levels=[0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
        title="The approach",
        size_l0=12,
        size_l1=10,
    )
    _add_box(
        slide, Inches(7.0), Inches(1.2), Inches(5.9), Inches(5.8),
        "WHY NOT A FULL ML / AGENT SOLUTION",
        "• Start with a transparent baseline the business understands — ML is a "
        "Phase 2.5 upgrade path if specific SKU segments underperform.\n\n"
        "• A conversational agent over the ERP (text-to-SQL, multi-step reasoning) "
        "is over-scoped: Atlas has no team to maintain a production LLM pipeline, "
        "connectivity is unreliable, and the GM's question pattern is narrow "
        "('what do I order this week?') — a dashboard answers it directly.\n\n"
        "• The bounded LLM layer adds genuine value — it triages the weekly batch "
        "(which orders matter, what to defer, where to consolidate by supplier) and "
        "explains each call in plain language — without creating an operational "
        "dependency Atlas cannot support. A grounding check keeps it from inventing figures.",
        title_size=13,
    )


def s13_data_readiness(slide):
    _add_header_bar(slide, "Data Readiness and Constraints",
                    "Five ERP tables, no PII, no external data — all on-prem")
    # Plain-language header sentence above the table
    tb_intro = slide.shapes.add_textbox(Inches(0.5), Inches(1.1), Inches(12.3), Inches(0.35))
    p_intro = tb_intro.text_frame.paragraphs[0]
    r_intro = p_intro.add_run()
    r_intro.text = "Five ERP tables already owned by Atlas — a decade of data, no new collection needed."
    r_intro.font.size = Pt(12)
    r_intro.font.italic = True
    r_intro.font.color.rgb = NAVY

    data = [
        ["Table", "Role", "Key columns"],
        ["products", "Catalogue", "sku_id, name, category, unit_cost, lead_time_days, supplier"],
        ["sales", "10+ yr demand history", "sale_date, sku_id, quantity, unit_price"],
        ["inventory_snapshots", "On-hand, historical", "snapshot_date, sku_id, on_hand"],
        ["purchase_orders", "Open + historical POs", "sku_id, order_date, eta_date, received_date, qty, status"],
        ["bom (future)", "For Phase 3 production", "not used in this initiative"],
    ]
    _add_table(slide, Inches(0.5), Inches(1.5), Inches(12.3), Inches(2.4), data)

    # Real-ERP mapping note (A4)
    tb_map = slide.shapes.add_textbox(Inches(0.5), Inches(4.0), Inches(12.3), Inches(1.1))
    tf_map = tb_map.text_frame
    tf_map.word_wrap = True
    p_map = tf_map.paragraphs[0]
    r_map1 = p_map.add_run()
    r_map1.text = "Real-ERP mapping for S1: "
    r_map1.font.size = Pt(10)
    r_map1.font.bold = True
    r_map1.font.color.rgb = NAVY
    r_map2 = p_map.add_run()
    r_map2.text = (
        "products→Stock (18,533 rows; QTY_ONHAND, MINIMUMQTY, ORDER_TIME, SUPPLIER). "
        "sales→Invoice (167,199) + Invod (959,200) filtered Type='Sale'. "
        "inventory_snapshots→derived from Invod.QIN/QOUT history (weekly snapshots materialised in S1). "
        "purchase_orders→Invoice Type='Purchase' / prefix PU00. bom→Asm (91,170)."
    )
    r_map2.font.size = Pt(10)
    r_map2.font.italic = True
    r_map2.font.color.rgb = GRAY

    _bulleted(
        slide, Inches(0.6), Inches(5.2), Inches(12.2), Inches(2.0),
        [
            "No PII. Product + supplier data only; customer data is not touched by this initiative.",
            "On-prem SQL-only ERP with 10+ years of history — enough signal for statistical forecasting.",
            "Constraints: unreliable internet, zero cloud budget, no internal IT / data team.",
            "Inventory-accuracy (Phase 0 cycle count) is a hard prerequisite; the math is only as good as the on-hand figures it reads.",
        ],
        title="Data posture + constraints",
        size_l0=11,
    )


def s14_tech_success(slide):
    _add_header_bar(slide, "Technical Success Criteria",
                    "Measurable, per-SKU-segment; tracked weekly")
    data = [
        ["Metric", "Definition", "Target (12 mo post-launch)"],
        ["Forecast MAPE — paint", "mean abs pct error, monthly forecast vs actual", "≤ 20% median"],
        ["Forecast MAPE — hardware", "same (lumpy demand; safety stock compensates)", "≤ 50% median"],
        ["PO placement lead time", "days from weekly review to PO sent", "≤ 2 days"],
        ["Service-level compliance", "actual fill-rate vs. configured SL per segment", "≥ 95% on top-80% SKUs"],
        ["Pipeline runtime (weekly)", "end-to-end: extract → forecast → reorder → UI refresh", "< 10 minutes on on-prem server"],
        ["LLM fallback coverage", "% of recommendations with an explanation (llm OR template)", "100%"],
        ["LLM numeric-grounding pass", "% AI outputs whose every figure traces to the engine (else auto-fallback)", "100%"],
    ]
    _add_table(slide, Inches(0.4), Inches(1.3), Inches(12.5), Inches(5.6), data)


def s15_business_success(slide):
    _add_header_bar(slide, "Business Success Criteria",
                    "The P&L and behavioural metrics that define a successful roll-out")
    data = [
        ["Metric", "Definition", "Target (12 mo post-launch)"],
        ["Stockout-days avoided (top-20% SKUs)", "YoY change in days a top-20% SKU was below ROP", "−40%"],
        ["Deadstock reduction", "$ value of SKUs with >6 months of coverage", "−30%"],
        ["Recommendation acceptance rate", "% of recommendations approved as-is by GM", "≥ 70% by month 3"],
        ["Weekly review cadence established", "weeks / 12 with a Monday review executed", "≥ 10 / 12"],
        ["Decisions-per-month (planned)", "procurement decisions made on schedule vs. reactive", "≥ 4 planned / month"],
    ]
    _add_table(slide, Inches(0.4), Inches(1.3), Inches(12.5), Inches(4.8), data)
    tb = slide.shapes.add_textbox(Inches(0.5), Inches(6.3), Inches(12.3), Inches(0.8))
    p = tb.text_frame.paragraphs[0]
    r = p.add_run()
    r.text = ("Targets are illustrative ranges — year-1 gains depend on execution and the Phase 0 "
              "inventory-accuracy prerequisite. No figure is a commitment.")
    r.font.size = Pt(10)
    r.font.italic = True
    r.font.color.rgb = GRAY


def s16_divider_arch(slide):
    _section_divider(slide, "Technical Architecture")


def s17_data_flow(slide):
    _add_header_bar(slide, "Data Flow",
                    "Weekly read-only extract → forecast → reorder → explain → human sign-off")

    # Plain-language header
    tb_intro = slide.shapes.add_textbox(Inches(0.4), Inches(1.1), Inches(12.5), Inches(0.35))
    p_intro = tb_intro.text_frame.paragraphs[0]
    r_intro = p_intro.add_run()
    r_intro.text = "What happens every Monday, step by step."
    r_intro.font.size = Pt(12)
    r_intro.font.italic = True
    r_intro.font.color.rgb = NAVY

    flow = (
        "ERP (SQL, read-only)                     5 tables, 10+ yr history, ~200–500 active SKUs (subject to S2 velocity analysis)\n"
        "      │  weekly extract (SELECT only, no writes)\n"
        "      ▼\n"
        "Local SQLite cache (≈10 MB)              refreshed weekly on the on-prem server\n"
        "      │\n"
        "      ▼\n"
        "Forecasting engine  ─── moving avg + multiplicative seasonality   (pandas + numpy)\n"
        "      │  (forecast + uncertainty + seasonal factor)\n"
        "      ▼\n"
        "Reorder engine      ─── Reorder point + buffer (ROP + safety stock)\n"
        "      │\n"
        "      ├─────────▶  LLM (Claude Haiku)    optional, cloud — weekly briefing + per-SKU explanation\n"
        "      │◀─────────   OR offline template  deterministic fallback; grounding check guards every figure\n"
        "      ▼\n"
        "Streamlit UI  (LAN-only)   Dashboard · SKU Drilldown · What-if     1–3 concurrent users\n"
        "      │\n"
        "      ▼\n"
        "Human sign-off  ─▶  Manual PO to supplier  ─▶  ERP update  (existing workflow, unchanged)"
    )
    _mono_block(slide, Inches(0.4), Inches(1.5), Inches(12.5), Inches(5.1), flow, size=11)

    # Closing plain-language note
    tb_close = slide.shapes.add_textbox(Inches(0.4), Inches(6.7), Inches(12.5), Inches(0.4))
    p_close = tb_close.text_frame.paragraphs[0]
    r_close = p_close.add_run()
    r_close.text = "Every arrow is read-only against the ERP except the final step — a human places the PO through the existing process."
    r_close.font.size = Pt(11)
    r_close.font.italic = True
    r_close.font.color.rgb = GRAY


def s18_tech_arch(slide):
    _add_header_bar(slide, "Technical Architecture",
                    "Single on-prem server; LLM path is optional and degrades gracefully offline")

    tb_intro = slide.shapes.add_textbox(Inches(0.4), Inches(1.0), Inches(12.5), Inches(0.35))
    p_intro = tb_intro.text_frame.paragraphs[0]
    r_intro = p_intro.add_run()
    r_intro.text = "One small Python service on your existing server. The LLM call is optional and degrades gracefully."
    r_intro.font.size = Pt(12)
    r_intro.font.italic = True
    r_intro.font.color.rgb = NAVY

    arch = (
        "┌─────────────────────────── Atlas on-prem server ──────────────────────────┐\n"
        "│                                                                              │\n"
        "│   ERP DB  ──▶  Python service  (venv, scheduled)  ──▶  SQLite cache         │\n"
        "│   MSSQL/       • extract   • forecasting                                    │\n"
        "│   custom       • reorder   • explain                                        │\n"
        "│                       │                                                     │\n"
        "│                       ▼                                                     │\n"
        "│              Streamlit app  (port 8501, LAN-only)                           │\n"
        "│                       │                                                     │\n"
        "└───────────────────────┼─────────────────────────────────────────────────────┘\n"
        "                        │  LAN\n"
        "                        ▼\n"
        "              GM + Procurement browsers\n"
        "\n"
        "OPTIONAL  ·  Python service  ── HTTPS ──▶  Anthropic API   (weekly briefing + explanations)\n"
        "             grounding-checked; falls back to deterministic template whenever unreachable"
    )
    _mono_block(slide, Inches(0.4), Inches(1.45), Inches(12.5), Inches(4.3), arch, size=10)
    _bulleted(
        slide, Inches(0.6), Inches(5.85), Inches(12.2), Inches(1.5),
        [
            "Tiny footprint — the entire system fits in ~100 MB on your current server; no new hardware needed.",
            "LLM cost: under $5 / month at Atlas volumes — and entirely optional.",
            "Why on-prem: unreliable internet + zero cloud budget + legal preference to keep ERP data on-site.",
        ],
        size_l0=11,
    )


def s19_build_vs_buy(slide):
    _add_header_bar(slide, "Build vs Buy Considerations",
                    "Build the thin orchestration; buy (rent, optionally) only the LLM")
    data = [
        ["Component", "Choice", "Rationale"],
        ["Forecasting + reorder engine", "BUILD — ~200 lines of Python (pandas, numpy)",
         "Classical formulas; transparent; no recurring license"],
        ["LLM for explanations", "BUY/RENT — Anthropic API (claude-haiku-4-5), optional",
         "<$5/month; offline template fallback means zero hard dependency"],
        ["UI / dashboard", "BUILD — Streamlit (open source)",
         "Runs on-prem, LAN-only, no vendor lock-in, $0 license"],
        ["Data store", "BUILD — SQLite cache on the existing ERP server",
         "No new infra; backup = copy one file"],
        ["Inventory-planning SaaS (e.g. NetSuite / SAP IBP)", "REJECTED",
         "Cloud-hosted; monthly license; overkill for 200–500 SKUs; does not respect the zero-budget / unreliable-internet constraints"],
        ["Forecasting library (Prophet, statsforecast)", "DEFERRED to Phase 2.5",
         "Not needed for baseline; adds dependency weight; revisit for specific SKU segments only"],
    ]
    _add_table(slide, Inches(0.3), Inches(1.3), Inches(12.7), Inches(5.7), data)


def s20_roadmap(slide):
    _add_header_bar(slide, "Phased AI Roadmap",
                    "~4-month engagement; Phase-2 slot of the overall Atlas AI roadmap")
    data = [
        ["Sprint", "Weeks", "Scope", "Output"],
        ["S0  Prerequisite", "-4 → 0", "Phase 0 cycle count; populate reorder-point fields in ERP",
         "Trusted on-hand; ROP fields filled (GM + warehouse)"],
        ["S1  Data extract", "1–2", "Read-only SQL extract into local SQLite; weekly refresh job",
         "Scheduled extract, validated row counts"],
        ["S2  Forecasting v1", "3–4", "Moving avg + seasonality; historical backtest + tune baseline window",
         "Forecast module + per-SKU MAPE report"],
        ["S3  Reorder engine", "5", "ROP + safety stock; replay past stockouts; integrate with forecast",
         "Reorder module + list of past stockouts that would have been pre-flagged"],
        ["S4  Streamlit UI + LLM", "6–7", "Dashboard / drilldown / what-if; LLM layer with template fallback",
         "Usable app on the Atlas server"],
        ["S5  UAT (paper-parallel)", "8–9", "System recs run alongside existing reactive process; decisions compared",
         "Decision log; acceptance-rate evidence"],
        ["S6  Go-live", "10", "System becomes authoritative; weekly review cadence starts",
         "First weekly PO batch based on system recs"],
        ["S7  Stabilization", "11–16", "Tune service levels per segment; add Croston for intermittent hardware if needed; monthly accuracy report",
         "Tuned system; go/no-go on Phase 3"],
    ]
    _add_table(slide, Inches(0.25), Inches(1.3), Inches(12.83), Inches(5.8), data)


def s21_divider_commercial(slide):
    _section_divider(slide, "Commercial & Pricing Considerations")


def s22_commercial(slide):
    _add_header_bar(slide, "Commercial & Pricing Considerations",
                    "Zero-budget-compatible by design — the only hard cost is consultant time")
    data = [
        ["Category", "Estimate", "Notes"],
        ["Consultant time (S0–S7)", "8–12 person-weeks", "Single consultant over ~4 months; principal AI / data eng."],
        ["Software", "$0", "Python, Streamlit, pandas, numpy, SQLite — all open source"],
        ["LLM API (optional)", "< $5 / month", "Claude Haiku; ~80 recs × ~200 tokens; entirely optional"],
        ["Infrastructure", "$0", "Runs on Atlas's existing on-prem server"],
        ["Training", "2 × half-day sessions", "GM + procurement, covered during S5 UAT"],
        ["Ongoing maintenance", "≈1 day / month", "Service-level tuning + monthly accuracy review; retainer or internal champion"],
    ]
    _add_table(slide, Inches(0.4), Inches(1.3), Inches(12.5), Inches(4.2), data)
    _bulleted(
        slide, Inches(0.6), Inches(5.7), Inches(12.2), Inches(1.6),
        [
            "GM: ~2 hrs/week during S5–S7; ~30 min/week steady state.",
            "Procurement: ~2 hrs/week steady state (weekly review + PO placement).",
            "Warehouse lead: sign-off on Phase 0 cycle count (one-time, ~1 week distributed).",
        ],
        title="Internal time commitment",
        size_l0=12,
    )


def s23_evaluation(slide):
    _add_header_bar(slide, "Evaluation & Validation Plan",
                    "Paper-parallel UAT → weekly metrics → monthly accuracy review")
    _bulleted(
        slide, Inches(0.6), Inches(1.2), Inches(6.2), Inches(5.8),
        [
            "S5 UAT: 2-week paper-parallel run — system recs produced alongside existing reactive process; decisions compared per SKU.",
            "Backtest evidence: list of historical stockouts the system would have pre-flagged, with the PO date it would have suggested.",
            "Weekly: forecast MAPE, acceptance rate, PO placement lead-time tracked automatically in the app.",
            "Monthly: accuracy review with GM — service levels re-tuned per SKU segment; override patterns analyzed for parameter drift.",
            "Quarterly: business review — stockout-days YoY, deadstock $ change, go/no-go on Phase 2.5 (Croston, advanced models).",
        ],
        title="Validation cadence",
        size_l0=12,
    )
    _add_box(
        slide, Inches(7.0), Inches(1.2), Inches(5.9), Inches(5.8),
        "MODEL & PARAMETER CHANGE CONTROL",
        "• Any change to forecasting parameters, service level, prompt template, "
        "or LLM model is version-controlled in the Python package.\n\n"
        "• Monthly override review asks: are recent GM edits signalling parameter "
        "drift? If so, we re-fit — we do not silently ignore.\n\n"
        "• Recommendation vs. final decision logged per SKU per week, with reason "
        "if overridden.\n\n"
        "• Every explanation in the UI is labelled with its source ('llm' or "
        "'template') so that the evaluation loop can detect LLM-path regressions.",
        title_size=13,
    )


def s24_risk_ethics(slide):
    _add_header_bar(slide, "Risk & Ethics Checklist",
                    "Top operational risks + Module-12-aligned ethics posture")
    data = [
        ["Risk", "L", "I", "Mitigation"],
        ["R1. Inventory accuracy poor → wrong reorders", "High", "Critical",
         "Phase 0 cycle count is a hard prerequisite for go-live"],
        ["R2. Weak forecast on low-volume hardware (MAPE ~70%)", "Med", "Med",
         "Service level + safety stock absorbs error by design; Croston in Phase 2.5"],
        ["R3. Staff distrust the recommendations", "Med", "High",
         "2-week paper-parallel UAT creates evidence; plain-language 'why' aids adoption"],
        ["R4. Connectivity drops disable LLM explanations", "High", "Low",
         "Deterministic template fallback runs fully offline with the same numbers"],
        ["R5. FX / import volatility shifts lead times", "High", "Med",
         "Lead-time buffer % is a tunable UI parameter; monthly re-fit"],
        ["R6. LLM hallucinates a number", "Low", "Med",
         "Automated grounding check rejects any ungrounded figure → auto-fallback to deterministic template; source labeled in UI"],
    ]
    _add_table(slide, Inches(0.3), Inches(1.25), Inches(12.7), Inches(3.8), data)
    _add_box(
        slide, Inches(0.3), Inches(5.2), Inches(12.7), Inches(1.9),
        "ETHICS CHECKLIST (Module 12)",
        "✓ Human-in-the-loop — system recommends, human places POs     "
        "✓ No PII — product + supplier data only     "
        "✓ Audit log — every rec + decision stored weekly\n"
        "✓ LLM bounded — enforced grounding check; ungrounded output auto-falls back to template     "
        "✓ Source-labelled output — 'llm' vs 'template' shown per explanation     "
        "✓ Opt-out — LLM path is optional, fully offline mode is first-class",
        title_size=13,
        body_size=11,
    )


def s25_next_steps(slide):
    _add_header_bar(slide, "Key Decisions & Next Steps",
                    "What Atlas needs to approve for S0–S1 to start")
    _bulleted(
        slide, Inches(0.6), Inches(1.2), Inches(6.2), Inches(5.8),
        [
            "Approve Phase 0 — inventory-accuracy cycle count on hardware top-80% (GM + warehouse).",
            "Confirm consultant engagement S1–S4 (~8 person-weeks over 2 months).",
            "Decide LLM opt-in: enable ANTHROPIC_API_KEY, or ship offline-template-only.",
            "Agree weekly review cadence + named decision-makers (GM + procurement lead).",
            "Sign off on the success criteria on slides 14 + 15 as the 12-month scorecard.",
            "Schedule S5 UAT kick-off meeting (paper-parallel run with both processes).",
        ],
        title="Decisions needed now",
        size_l0=12,
    )
    _add_box(
        slide, Inches(7.0), Inches(1.2), Inches(5.9), Inches(5.8),
        "FIRST 30 DAYS IF APPROVED",
        "Week 1 — Kick-off; ERP extract permissions confirmed; Phase 0 cycle count begins "
        "on hardware top-80% SKUs.\n\n"
        "Week 2 — Scheduled weekly SQL extract running; SQLite cache validated; "
        "10-yr history ingested.\n\n"
        "Week 3 — Forecasting module v1 on real data; first MAPE-by-segment report "
        "shared with GM.\n\n"
        "Week 4 — Reorder engine integrated; historical-stockout replay presented "
        "to GM as evidence ahead of S4 UI build.",
        title_size=13,
    )


def s26_thank_you(slide):
    _add_bg(slide, NAVY)
    tb = slide.shapes.add_textbox(Inches(0.9), Inches(2.5), Inches(12), Inches(3.0))
    tf = tb.text_frame
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = "Thank You!"
    r.font.size = Pt(60)
    r.font.bold = True
    r.font.color.rgb = WHITE

    p2 = tf.add_paragraph()
    r2 = p2.add_run()
    r2.text = "Karim Khalifeh  ·  ZAKA Certified AI Consultant  ·  April 2026"
    r2.font.size = Pt(16)
    r2.font.color.rgb = ORANGE

    p3 = tf.add_paragraph()
    r3 = p3.add_run()
    r3.text = "Questions & discussion welcome."
    r3.font.size = Pt(14)
    r3.font.color.rgb = LIGHT


# ---------- orchestration ----------

SLIDE_BUILDERS = [
    s01_title,
    s02_outline,
    s03_divider_exec,
    s04_exec_1,
    s05_exec_2,
    s06_divider_use_case,
    s07_use_case_1,
    s08_use_case_2,
    s09_business_objective,
    s10_in_scope,
    s11_out_of_scope,
    s12_ai_approach,
    s13_data_readiness,
    s14_tech_success,
    s15_business_success,
    s16_divider_arch,
    s17_data_flow,
    s18_tech_arch,
    s19_build_vs_buy,
    s20_roadmap,
    s21_divider_commercial,
    s22_commercial,
    s23_evaluation,
    s24_risk_ethics,
    s25_next_steps,
    s26_thank_you,
]

# Slides that should NOT show the header footer (cover + section dividers + closing).
NO_FOOTER = {1, 3, 6, 16, 21, 26}


def build() -> Path:
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    total = len(SLIDE_BUILDERS)
    for i, builder in enumerate(SLIDE_BUILDERS, start=1):
        slide = _blank_slide(prs)
        builder(slide)
        if i not in NO_FOOTER:
            _add_footer(slide, i, total)

    prs.save(OUT)
    return OUT


if __name__ == "__main__":
    path = build()
    print(f"Built {path} ({path.stat().st_size // 1024} KB, {len(SLIDE_BUILDERS)} slides)")
