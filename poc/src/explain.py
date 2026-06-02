"""LLM-generated plain-language explanations for reorder recommendations.

Calls the Anthropic API (claude-haiku-4-5 for speed) when a key is available;
otherwise falls back to a deterministic template. Either way, the explanation
only restates numbers that are already in the ReorderRecommendation — no new
figures are invented. This is the governance posture emphasized in Module 12
(no hallucinated financial / operational facts).
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional

import pandas as pd

from .reorder import ReorderRecommendation

SYSTEM_PROMPT = """You explain inventory reorder recommendations in plain business English
for a procurement manager at a paint/hardware wholesaler in Lebanon. Write 2-3 short
sentences. Do NOT invent numbers — only use values explicitly provided. Be concrete
about the risk, the reason (lead time, seasonality, or both), and the recommended action."""


def _template_explanation(rec: ReorderRecommendation) -> str:
    if not rec.should_reorder:
        return (
            f"No action needed now. On-hand of {rec.on_hand} units covers ~{rec.days_of_cover:.0f} days "
            f"at expected demand ({rec.avg_daily_demand:.1f}/day), above the reorder point of "
            f"{rec.reorder_point:.0f}."
        )
    season_note = ""
    if rec.seasonality_factor >= 1.15:
        season_note = " Seasonal demand is elevated."
    elif rec.seasonality_factor <= 0.85:
        season_note = " Demand is seasonally low, but lead time still dominates."
    risk_phrase = {
        "high": "stockout risk is HIGH",
        "medium": "stockout risk is moderate",
        "low": "stockout risk is low but the reorder point has been crossed",
    }[rec.stockout_risk]
    return (
        f"Reorder {rec.suggested_order_qty} units of {rec.name} from {rec.supplier}. "
        f"Current on-hand is {rec.on_hand} ({rec.days_of_cover:.0f} days of cover) vs. a reorder "
        f"point of {rec.reorder_point:.0f}; with a {rec.lead_time_days}-day lead time, {risk_phrase}.{season_note}"
    )


def _call_anthropic(rec: ReorderRecommendation) -> Optional[str]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        from anthropic import Anthropic
    except ImportError:
        return None

    client = Anthropic(api_key=api_key)
    user_msg = (
        "Reorder recommendation:\n"
        f"- SKU: {rec.sku_code} — {rec.name} ({rec.category})\n"
        f"- Supplier: {rec.supplier}\n"
        f"- On-hand: {rec.on_hand} units\n"
        f"- Open POs: {rec.open_po_qty} units\n"
        f"- Avg daily demand: {rec.avg_daily_demand:.2f} units/day (seasonality factor {rec.seasonality_factor:.2f})\n"
        f"- Daily std dev: {rec.daily_std:.2f}\n"
        f"- Lead time: {rec.lead_time_days} days\n"
        f"- Service level: {int(rec.service_level * 100)}%\n"
        f"- Safety stock: {rec.safety_stock:.0f} units\n"
        f"- Reorder point: {rec.reorder_point:.0f} units\n"
        f"- Days of cover at current on-hand: {rec.days_of_cover:.0f}\n"
        f"- Should reorder now: {rec.should_reorder}\n"
        f"- Suggested order qty: {rec.suggested_order_qty} units (~${rec.currency_value:,.0f})\n"
        f"- Stockout risk: {rec.stockout_risk}\n\n"
        "Write the 2-3 sentence explanation."
    )
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=200,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        return "".join(block.text for block in resp.content if block.type == "text").strip()
    except Exception:
        return None


def explain(rec: ReorderRecommendation, prefer_llm: bool = True) -> tuple[str, str]:
    """Return (explanation_text, source) where source is 'llm' or 'template'."""
    if prefer_llm:
        llm_text = _call_anthropic(rec)
        if llm_text:
            return llm_text, "llm"
    return _template_explanation(rec), "template"


# ---------------------------------------------------------------------------
# Load-bearing layer: a weekly procurement briefing over the FULL reorder batch.
#
# Unlike explain() — which restates one recommendation — this asks the model to
# do analysis the deterministic engine cannot: triage the week (which few orders
# truly matter today), spot supplier-consolidation opportunities, and sequence
# against a fixed weekly budget. The numbers still come only from the engine; the
# model's job is judgement and synthesis, not arithmetic.
#
# Governance: every figure in the model's output is checked against the engine's
# numbers (the "grounding guard"). If the model emits any number we did not give
# it, the output is rejected and we fall back to the deterministic template. This
# turns "the LLM cannot invent figures" from a prompt instruction into an enforced
# invariant — the posture from Module 12.
# ---------------------------------------------------------------------------

SUMMARY_SYSTEM_PROMPT = """You write the Monday-morning procurement briefing for the GM of a
paint/hardware wholesaler in Lebanon. You are given a JSON object of reorder figures the
planning engine already computed. Write a short markdown briefing with these sections:

**Act today** — the high-risk items that cannot wait, each with one reason (days of cover vs lead time).
**Consolidate by supplier** — where multiple flagged SKUs share a supplier, suggest one combined PO.
**Safe to defer** — low-risk items that crossed the reorder point but still have cover.
If a weekly budget is given and the total exceeds it, say so and prioritise the high-risk items.

Rules: Use ONLY numbers present in the JSON. Never invent or compute new figures — in particular,
do NOT add up individual item values yourself. When suggesting a combined PO for a supplier, cite
the supplier's provided `po_value` from `consolidate_by_supplier`; do not sum the items. Be decisive
and brief — a busy GM should grasp the week in 20 seconds. Refer to items by SKU code and name."""

# Small calendar/cycle integers (days, weeks, review cycles) are linguistic, not
# fabricated data, so they are always allowed. Money values and quantities are
# large and specific — those must trace to the engine.
_GROUNDING_SMALL_INT_MAX = 31

# Match standalone figures only — not digits embedded in identifiers (SKU codes
# like "H0037") or unit descriptors ("12V", "20L"). The \w boundaries on both
# sides keep "$4,400" and "95%" while ignoring the "37" inside "H0037".
_NUM_RE = re.compile(r"(?<!\w)\$?\d[\d,]*(?:\.\d+)?(?!\w)")


def _collect_numbers(obj) -> set[float]:
    """Recursively gather every numeric value in a payload.

    Also pulls figures out of string values (e.g. the as_of date "2026-03-31"
    contributes 2026/3/31) so that legitimately restating a value the engine
    put in the payload — most importantly the date in the briefing header —
    counts as grounded. Without this, the year in any date the model writes
    would trip the guard and force a fallback to the template.
    """
    nums: set[float] = set()
    if isinstance(obj, bool):
        return nums
    if isinstance(obj, (int, float)):
        nums.add(float(obj))
    elif isinstance(obj, str):
        nums |= set(_parse_numbers(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            nums |= _collect_numbers(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            nums |= _collect_numbers(v)
    return nums


def _parse_numbers(text: str) -> list[float]:
    out: list[float] = []
    for m in _NUM_RE.findall(text):
        s = m.replace("$", "").replace(",", "").strip()
        try:
            out.append(float(s))
        except ValueError:
            pass
    return out


def _is_grounded(val: float, allowed: set[float]) -> bool:
    if abs(val) <= _GROUNDING_SMALL_INT_MAX and float(val).is_integer():
        return True
    for a in allowed:
        if abs(val - a) <= max(1.0, 0.02 * abs(a)):  # tolerate rounding ("~$4,400")
            return True
    return False


def numbers_are_grounded(text: str, allowed: set[float]) -> bool:
    """True iff every figure in `text` traces to an engine-produced number."""
    return all(_is_grounded(v, allowed) for v in _parse_numbers(text))


def _build_payload(recs: pd.DataFrame, weekly_budget: Optional[float]) -> dict:
    queue = recs[recs["should_reorder"]].copy()
    high = queue[queue["stockout_risk"] == "high"].sort_values("currency_value", ascending=False)
    low = queue[queue["stockout_risk"] == "low"].sort_values("days_of_cover", ascending=False)
    service_level_pct = int(round(float(recs["service_level"].iloc[0]) * 100)) if len(recs) else 95

    def items(df: pd.DataFrame, n: int) -> list[dict]:
        cols = df.head(n).to_dict("records")
        return [
            {
                "sku": r["sku_code"],
                "name": r["name"],
                "supplier": r["supplier"],
                "on_hand": int(r["on_hand"]),
                "days_of_cover": int(round(r["days_of_cover"])) if r["days_of_cover"] >= 0 else None,
                "lead_time_days": int(r["lead_time_days"]),
                "order_qty": int(r["suggested_order_qty"]),
                "po_value": int(round(r["currency_value"])),
            }
            for r in cols
        ]

    by_supplier = (
        queue.groupby("supplier")
        .agg(skus=("sku_code", "count"), value=("currency_value", "sum"))
        .reset_index()
        .sort_values("value", ascending=False)
    )
    consolidate = [
        {"supplier": r["supplier"], "skus": int(r["skus"]), "po_value": int(round(r["value"]))}
        for r in by_supplier[by_supplier["skus"] >= 2].to_dict("records")
    ]

    return {
        "as_of": str(recs.attrs.get("as_of", "")),
        "service_level_pct": service_level_pct,
        "total_flagged": int(len(queue)),
        "total_po_value": int(round(queue["currency_value"].sum())) if len(queue) else 0,
        "high_risk_count": int(len(high)),
        "high_risk_po_value": int(round(high["currency_value"].sum())) if len(high) else 0,
        "low_risk_count": int(len(low)),
        "weekly_budget": int(weekly_budget) if weekly_budget else None,
        "high_risk_items": items(high, 6),
        "consolidate_by_supplier": consolidate,
        "defer_items": items(low, 5),
    }


def _template_summary(payload: dict) -> str:
    lines: list[str] = []
    total, value = payload["total_flagged"], payload["total_po_value"]
    if total == 0:
        return "**Weekly procurement briefing** — no SKUs are below their reorder point at the current parameters. Nothing to order this week."

    head = f"**Weekly procurement briefing** — {total} SKUs flagged for reorder, ~${value:,.0f} total."
    budget = payload["weekly_budget"]
    if budget and value > budget:
        head += (
            f" Budget is ${budget:,.0f}; the high-risk items alone are ~${payload['high_risk_po_value']:,.0f}, "
            f"so cover those first and defer the rest."
        )
    elif budget:
        head += f" This fits within the ${budget:,.0f} weekly budget."
    lines.append(head)

    if payload["high_risk_items"]:
        lines.append(f"\n**Act today — {payload['high_risk_count']} high-risk item(s):**")
        for it in payload["high_risk_items"]:
            cover = f"{it['days_of_cover']}d cover" if it["days_of_cover"] is not None else "out of stock"
            lines.append(
                f"- {it['sku']} {it['name']}: {cover} vs {it['lead_time_days']}d lead time "
                f"→ order {it['order_qty']} (~${it['po_value']:,.0f}) from {it['supplier']}."
            )

    if payload["consolidate_by_supplier"]:
        lines.append("\n**Consolidate by supplier:**")
        for c in payload["consolidate_by_supplier"]:
            lines.append(
                f"- {c['supplier']}: {c['skus']} flagged SKUs (~${c['po_value']:,.0f}) "
                f"→ combine into one PO to save on lead time and order overhead."
            )

    if payload["defer_items"]:
        lines.append(f"\n**Safe to defer — {payload['low_risk_count']} low-risk item(s):**")
        for it in payload["defer_items"]:
            cover = f"{it['days_of_cover']}d cover" if it["days_of_cover"] is not None else "covered"
            lines.append(f"- {it['sku']} {it['name']}: crossed reorder point but still has {cover}.")

    return "\n".join(lines)


def _call_anthropic_summary(payload: dict, allowed: set[float]) -> Optional[str]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        from anthropic import Anthropic
    except ImportError:
        return None

    client = Anthropic(api_key=api_key)
    user_msg = "Reorder figures (JSON):\n" + json.dumps(payload, indent=2) + "\n\nWrite the briefing."
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=600,
            system=SUMMARY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = "".join(block.text for block in resp.content if block.type == "text").strip()
    except Exception:
        return None
    # Grounding guard: reject (→ fall back to template) if any figure was invented.
    if not numbers_are_grounded(text, allowed):
        return None
    return text


def summarize_week(
    recs: pd.DataFrame,
    weekly_budget: Optional[float] = None,
    prefer_llm: bool = True,
) -> tuple[str, str]:
    """Analytical weekly briefing over the full reorder batch.

    Returns (markdown_briefing, source) where source is 'llm' or 'template'.
    The LLM path is gated by a numeric-grounding check; on any failure (no key,
    offline, or an ungrounded figure) it falls back to the deterministic template.
    """
    payload = _build_payload(recs, weekly_budget)
    if prefer_llm:
        allowed = _collect_numbers(payload)
        # Allow the service level restated as a probability (e.g. 0.95 vs "95%").
        allowed.add(payload["service_level_pct"] / 100.0)
        llm_text = _call_anthropic_summary(payload, allowed)
        if llm_text:
            return llm_text, "llm"
    return _template_summary(payload), "template"


if __name__ == "__main__":
    import sqlite3
    from datetime import date
    from pathlib import Path

    from .reorder import DB_PATH, recommend, recommend_all

    # Match the Streamlit app: load ANTHROPIC_API_KEY from poc/.env so this
    # smoke-test exercises the real LLM path instead of silently falling back
    # to the template. No-op if python-dotenv or .env is missing.
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    except ImportError:
        pass

    conn = sqlite3.connect(DB_PATH)
    as_of = date(2026, 3, 31)

    # Per-SKU explanation
    rec = recommend(conn, sku_id=30, as_of=as_of)
    text, source = explain(rec)
    print(f"[{source}] {rec.name}")
    print(text)

    # Weekly briefing over the full batch
    recs = recommend_all(conn, as_of=as_of)
    recs.attrs["as_of"] = as_of.isoformat()
    brief, brief_src = summarize_week(recs, weekly_budget=20000)
    print(f"\n=== Weekly briefing [{brief_src}] ===")
    print(brief)

    # Grounding guard self-check
    allowed = _collect_numbers(_build_payload(recs, 20000))
    assert numbers_are_grounded("Order 80 units (~$4,400) — 0 days of cover.", allowed | {80.0, 4400.0}), \
        "grounded text should pass"
    assert not numbers_are_grounded("This will save you $999999 next quarter.", allowed), \
        "invented figure should be rejected"
    print("\nGrounding guard: OK (grounded text passes, invented figure rejected)")

    conn.close()
