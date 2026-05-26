"""LLM-generated plain-language explanations for reorder recommendations.

Calls the Anthropic API (claude-haiku-4-5 for speed) when a key is available;
otherwise falls back to a deterministic template. Either way, the explanation
only restates numbers that are already in the ReorderRecommendation — no new
figures are invented. This is the governance posture emphasized in Module 12
(no hallucinated financial / operational facts).
"""

from __future__ import annotations

import os
from typing import Optional

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


if __name__ == "__main__":
    import sqlite3
    from datetime import date
    from pathlib import Path

    from .reorder import DB_PATH, recommend

    conn = sqlite3.connect(DB_PATH)
    # Pick a medium/high risk SKU for the demo
    rec = recommend(conn, sku_id=30, as_of=date(2026, 3, 31))
    text, source = explain(rec)
    print(f"[{source}] {rec.name}")
    print(text)
    conn.close()
