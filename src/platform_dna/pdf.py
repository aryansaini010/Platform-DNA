"""PDF export (plan Step 7: Markdown / PDF / DOCX — this module covers PDF).

Uses fpdf2 with core fonts only (no system font files needed). Unicode
outside latin-1 (e.g. rupee sign, em-dashes) is transliterated so the PDF
never crashes on Indian-market text.
"""
from __future__ import annotations

import re

from fpdf import FPDF

_CLEAN = {
    "\u20b9": "Rs.", "\u2014": "-", "\u2013": "-", "\u2018": "'",
    "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2022": "*",
    "\u00a0": " ", "\u200b": "", "\u2713": "[yes]", "\u2705": "[yes]",
    "\u274c": "[no]",
    "\u2795": "+", "\u2796": "-", "\u2b50": "*",
    "\u2026": "...", "\u2011": "-", "\u2010": "-", "\u00ad": "",
}


def clean(text: str) -> str:
    if not isinstance(text, str):
        text = str(text or "")
    for k, v in _CLEAN.items():
        text = text.replace(k, v)
    # Transliterate remaining non-latin-1 (Devanagari/Tamil/Telugu/emoji):
    # NFKD strips diacritics where possible, then replace unmappable with ?.
    import unicodedata as _ud
    text = _ud.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return text.encode("latin-1", "replace").decode("latin-1")


def _link_text(line: str) -> str:
    # [label](url) -> "label (url)"; ![alt](src) -> dropped
    line = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"[image: \1]", line)
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", line)


def _mc(pdf: FPDF, h: float, text: str) -> None:
    # fpdf2 >=2.7 leaves X at the right margin after multi_cell;
    # reset it so the next width-0 call has full page width.
    pdf.multi_cell(0, h, text, new_x="LMARGIN", new_y="NEXT")


def markdown_to_pdf_bytes(title: str, body: str) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(True, margin=20)
    pdf.add_page()
    pdf.set_title(clean(title)[:120])

    pdf.set_font("Helvetica", "B", 20)
    _mc(pdf, 10, clean(title))
    pdf.ln(4)

    for raw in body.splitlines():
        line = clean(_link_text(raw.rstrip()))
        if not line.strip():
            pdf.ln(3)
            continue
        s = line.strip()
        if s.startswith("### "):
            pdf.set_font("Helvetica", "B", 12)
            _mc(pdf, 7, s[4:])
        elif s.startswith("## "):
            pdf.set_font("Helvetica", "B", 14)
            _mc(pdf, 8, s[3:])
        elif s.startswith("# "):
            pdf.set_font("Helvetica", "B", 16)
            _mc(pdf, 9, s[2:])
        elif re.match(r"^\|[\s:|-]+\|$", s):
            continue  # markdown table separator row
        elif s.startswith("|") and s.endswith("|"):
            cells = [c.strip("* ") for c in s.strip("|").split("|")]
            pdf.set_font("Helvetica", "", 10)
            _mc(pdf, 6, " | ".join(cells))
        elif re.match(r"^(\d+\.\s+|[-*]\s+)", s):
            pdf.set_font("Helvetica", "", 11)
            _mc(pdf, 6, s)
        elif s.startswith("**") and s.endswith("**") and len(s) < 120:
            pdf.set_font("Helvetica", "B", 11)
            _mc(pdf, 6, s.strip("*"))
        else:
            pdf.set_font("Helvetica", "", 11)
            txt = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
            txt = re.sub(r"(?<!\w)\*([^*\n]+)\*(?!\w)", r"\1", txt)
            _mc(pdf, 6, txt)
    out = pdf.output()
    return bytes(out) if isinstance(out, (bytes, bytearray)) else out.encode("latin-1")
