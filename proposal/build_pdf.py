"""Generate Atlas_AI_Solution_Proposal.pdf from the markdown source.

A clean, portfolio-ready PDF rendered with reportlab. Independent of the PPTX path
so the content stays in sync with the markdown source of truth.
"""

from __future__ import annotations

import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
    Preformatted,
)

SRC = Path(__file__).resolve().parent / "Atlas_AI_Solution_Proposal.md"
OUT = Path(__file__).resolve().parent / "Atlas_AI_Solution_Proposal.pdf"

NAVY = colors.HexColor("#1F2A44")
ORANGE = colors.HexColor("#E67E22")
LIGHT = colors.HexColor("#F4F6F8")
GRAY = colors.HexColor("#5A6A7A")
MUTED = colors.HexColor("#8995A3")


def _styles():
    base = getSampleStyleSheet()
    s = {}
    s["Title"] = ParagraphStyle(
        "Title", parent=base["Title"], fontSize=26, leading=32, textColor=NAVY,
        spaceAfter=6, alignment=TA_LEFT,
    )
    s["Subtitle"] = ParagraphStyle(
        "Subtitle", parent=base["Title"], fontSize=16, leading=20, textColor=ORANGE,
        spaceAfter=18, alignment=TA_LEFT, fontName="Helvetica",
    )
    s["Meta"] = ParagraphStyle(
        "Meta", parent=base["Normal"], fontSize=10, textColor=GRAY, spaceAfter=3,
    )
    s["H1"] = ParagraphStyle(
        "H1", parent=base["Heading1"], fontSize=18, leading=22, textColor=NAVY,
        spaceBefore=16, spaceAfter=8, fontName="Helvetica-Bold",
    )
    s["H2"] = ParagraphStyle(
        "H2", parent=base["Heading2"], fontSize=14, leading=18, textColor=NAVY,
        spaceBefore=10, spaceAfter=6, fontName="Helvetica-Bold",
    )
    s["H3"] = ParagraphStyle(
        "H3", parent=base["Heading3"], fontSize=12, leading=16, textColor=ORANGE,
        spaceBefore=8, spaceAfter=4, fontName="Helvetica-Bold",
    )
    s["Body"] = ParagraphStyle(
        "Body", parent=base["BodyText"], fontSize=10, leading=14, textColor=NAVY,
        spaceAfter=6, alignment=TA_JUSTIFY,
    )
    s["Bullet"] = ParagraphStyle(
        "Bullet", parent=s["Body"], leftIndent=14, bulletIndent=2,
    )
    s["Code"] = ParagraphStyle(
        "Code", parent=base["Code"], fontSize=8.5, leading=11, textColor=NAVY,
        backColor=LIGHT, borderColor=LIGHT, borderPadding=6, spaceAfter=8,
    )
    s["Quote"] = ParagraphStyle(
        "Quote", parent=s["Body"], leftIndent=18, textColor=GRAY, fontName="Helvetica-Oblique",
    )
    s["Footer"] = ParagraphStyle(
        "Footer", parent=base["Normal"], fontSize=8, textColor=MUTED, alignment=TA_CENTER,
    )
    return s


def _parse_inline(text: str) -> str:
    """Very small markdown inline → RML string conversion."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"`([^`]+)`", r'<font face="Courier">\1</font>', text)
    return text


def _parse_table(lines: list[str]) -> list[list[str]]:
    rows = []
    for ln in lines:
        ln = ln.strip()
        if not ln.startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if all(re.match(r"^:?-{2,}:?$", c) for c in cells):
            continue
        rows.append(cells)
    return rows


def _build_flow(md: str, styles):
    flow = []
    lines = md.splitlines()
    i = 0
    in_code = False
    code_buf = []
    while i < len(lines):
        line = lines[i]

        if line.strip().startswith("```"):
            if not in_code:
                in_code = True
                code_buf = []
            else:
                in_code = False
                flow.append(Preformatted("\n".join(code_buf), styles["Code"]))
                flow.append(Spacer(1, 4))
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue

        if line.startswith("# "):
            flow.append(Paragraph(_parse_inline(line[2:]), styles["Title"]))
            i += 1
            continue
        if line.startswith("## "):
            flow.append(Paragraph(_parse_inline(line[3:]), styles["H1"]))
            i += 1
            continue
        if line.startswith("### "):
            flow.append(Paragraph(_parse_inline(line[4:]), styles["H2"]))
            i += 1
            continue
        if line.startswith("#### "):
            flow.append(Paragraph(_parse_inline(line[5:]), styles["H3"]))
            i += 1
            continue
        if line.strip() == "---":
            flow.append(Spacer(1, 6))
            i += 1
            continue

        # Tables
        if line.strip().startswith("|"):
            tbl_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                tbl_lines.append(lines[i])
                i += 1
            data = _parse_table(tbl_lines)
            if data:
                # Wrap each cell in Paragraph for word-wrap
                wrapped = []
                for r_i, row in enumerate(data):
                    wrapped_row = []
                    for cell in row:
                        st = ParagraphStyle(
                            "C", parent=styles["Body"], fontSize=9, leading=11,
                            textColor=colors.white if r_i == 0 else NAVY,
                            fontName="Helvetica-Bold" if r_i == 0 else "Helvetica",
                            alignment=TA_LEFT,
                        )
                        wrapped_row.append(Paragraph(_parse_inline(cell), st))
                    wrapped.append(wrapped_row)
                col_count = len(wrapped[0])
                table_width = 6.5 * inch
                col_widths = [table_width / col_count] * col_count
                t = Table(wrapped, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("BOX", (0, 0), (-1, -1), 0.4, GRAY),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D8DEE4")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]))
                flow.append(t)
                flow.append(Spacer(1, 8))
            continue

        # Bullets
        if re.match(r"^\s*[-*] ", line):
            bullet_lines = []
            while i < len(lines) and re.match(r"^\s*[-*] ", lines[i]):
                txt = re.sub(r"^\s*[-*] ", "", lines[i])
                bullet_lines.append(txt)
                i += 1
            for b in bullet_lines:
                flow.append(Paragraph("• " + _parse_inline(b), styles["Bullet"]))
            flow.append(Spacer(1, 4))
            continue

        if line.startswith("> "):
            flow.append(Paragraph(_parse_inline(line[2:]), styles["Quote"]))
            i += 1
            continue

        if line.strip() == "":
            flow.append(Spacer(1, 4))
            i += 1
            continue

        # Numbered list
        if re.match(r"^\s*\d+\.\s", line):
            txt = re.sub(r"^\s*\d+\.\s", "", line)
            flow.append(Paragraph(_parse_inline(txt), styles["Bullet"]))
            i += 1
            continue

        # Plain paragraph
        para_lines = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not _is_block_start(lines[i]):
            para_lines.append(lines[i])
            i += 1
        flow.append(Paragraph(_parse_inline(" ".join(para_lines)), styles["Body"]))

    return flow


def _is_block_start(line: str) -> bool:
    if not line:
        return True
    if line.startswith("#") or line.startswith("|") or line.startswith("```") or line.strip() == "---":
        return True
    if re.match(r"^\s*[-*] ", line):
        return True
    if re.match(r"^\s*\d+\.\s", line):
        return True
    if line.startswith("> "):
        return True
    return False


def _on_page(canvas, doc):
    canvas.saveState()
    # Top accent line
    canvas.setFillColor(ORANGE)
    canvas.rect(0.75 * inch, 10.6 * inch, 7.0 * inch, 0.03 * inch, fill=1, stroke=0)
    # Footer
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(
        4.25 * inch, 0.5 * inch,
        f"Atlas Paints & Tools — AI Transformation Proposal  ·  {doc.page}",
    )
    canvas.restoreState()


def build() -> Path:
    md = SRC.read_text()
    styles = _styles()
    flow = _build_flow(md, styles)

    doc = BaseDocTemplate(
        str(OUT),
        pagesize=LETTER,
        leftMargin=0.9 * inch,
        rightMargin=0.9 * inch,
        topMargin=1.0 * inch,
        bottomMargin=0.9 * inch,
        title="Atlas AI Transformation Proposal — Inventory Reorder Intelligence",
        author="Karim Khalifeh",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=_on_page)])
    doc.build(flow)
    return OUT


if __name__ == "__main__":
    path = build()
    size_kb = path.stat().st_size // 1024
    print(f"Built {path} ({size_kb} KB)")
