"""Exportación de un tema a PDF: cuestionario con preguntas y respuestas.

Dos formatos:
  - "examen": primero todas las preguntas (con espacio para responder) y al final la
    clave de respuestas. Sirve para practicar en papel (autoevaluación).
  - "estudio": cada pregunta seguida de su respuesta y de la evidencia en la fuente.
"""
from __future__ import annotations

import io
import os
from datetime import datetime
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from .generator import LEVELS

INK = colors.HexColor("#1C2541")
INK2 = colors.HexColor("#4A5470")
INK3 = colors.HexColor("#7A839C")
RED = colors.HexColor("#C21F35")
LINE = colors.HexColor("#D6DCEA")
MARKER = colors.HexColor("#FFF3B0")

KIND_LABEL = {"mc": "Opción múltiple", "tf": "Verdadero o falso", "cloze": "Completar",
              "open": "Respuesta abierta", "why": "¿Por qué?", "relate": "Relacionar conceptos"}

_FONT = "Helvetica"
_FONT_B = "Helvetica-Bold"
_FONT_I = "Helvetica-Oblique"
_GLYPHS: set[int] | None = None


def _register_fonts() -> None:
    """Usa la tipografía Vera incluida en reportlab (soporta acentos, ñ, ¿ ¡ « »)."""
    global _FONT, _FONT_B, _FONT_I, _GLYPHS
    if _GLYPHS is not None:
        return
    folder = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
    try:
        regular = TTFont("Vera", os.path.join(folder, "Vera.ttf"))
        pdfmetrics.registerFont(regular)
        pdfmetrics.registerFont(TTFont("Vera-Bold", os.path.join(folder, "VeraBd.ttf")))
        pdfmetrics.registerFont(TTFont("Vera-Italic", os.path.join(folder, "VeraIt.ttf")))
        _FONT, _FONT_B, _FONT_I = "Vera", "Vera-Bold", "Vera-Italic"
        _GLYPHS = set(regular.face.charToGlyph.keys())
    except Exception:  # noqa: BLE001 - si falla, Helvetica (sin algunos símbolos)
        _GLYPHS = set(range(32, 256))


REPLACE = {"−": "-", "–": "-", "—": "-", " ": " ", " ": " ", "→": "->",
           "←": "<-", "≤": "<=", "≥": ">=", "≠": "!=", "×": "x", "…": "..."}


def _t(text: str) -> str:
    """Texto seguro para el PDF: escapa XML y reemplaza caracteres que la fuente no tiene."""
    out = []
    for ch in str(text or ""):
        ch = REPLACE.get(ch, ch)
        if len(ch) == 1 and ord(ch) not in _GLYPHS and ch not in "\n\t":
            ch = "?"
        out.append(ch)
    return escape("".join(out))


def _styles() -> dict:
    base = dict(fontName=_FONT, textColor=INK, leading=15, fontSize=10.5, alignment=TA_LEFT)
    return {
        "title": ParagraphStyle("title", **{**base, "fontName": _FONT_B, "fontSize": 22, "leading": 27}),
        "sub": ParagraphStyle("sub", **{**base, "textColor": INK2, "fontSize": 11, "leading": 15}),
        "meta": ParagraphStyle("meta", **{**base, "textColor": INK3, "fontSize": 9, "leading": 12.5}),
        "h2": ParagraphStyle("h2", **{**base, "fontName": _FONT_B, "fontSize": 14, "leading": 18,
                                       "spaceBefore": 14, "spaceAfter": 6, "keepWithNext": 1}),
        "q": ParagraphStyle("q", **{**base, "fontSize": 11, "leading": 15.5}),
        "opt": ParagraphStyle("opt", **{**base, "leftIndent": 18, "leading": 14.5}),
        "ans": ParagraphStyle("ans", **{**base, "fontName": _FONT_B, "textColor": RED, "leftIndent": 18}),
        "ev": ParagraphStyle("ev", **{**base, "fontName": _FONT_I, "textColor": INK2, "fontSize": 9.5,
                                       "leading": 13, "leftIndent": 18}),
        "key": ParagraphStyle("key", **{**base, "fontSize": 10, "leading": 14}),
    }


def _question_block(n: int, it: dict, st: dict, with_answer: bool) -> list:
    tag = f'<font color="#7A839C" size="8.5">{_t(KIND_LABEL.get(it["kind"], ""))}, {_t(LEVELS.get(it["level"], ""))}</font>'
    prompt = _t(it["prompt"]).replace("_____", "__________")
    parts = [Paragraph(f"<b>{n}.</b> {prompt}<br/>{tag}", st["q"])]
    if it["kind"] == "mc" and it.get("options"):
        for letter, opt in zip("abcd", it["options"]):
            parts.append(Paragraph(f"{letter}) {_t(opt)}", st["opt"]))
    elif it["kind"] == "tf":
        parts.append(Paragraph("( ) Verdadero &nbsp;&nbsp;&nbsp; ( ) Falso", st["opt"]))
    elif not with_answer and it["kind"] in ("open", "why", "relate"):
        rule = Table([[""], [""], [""]], colWidths=[165 * mm], rowHeights=[8 * mm] * 3)
        rule.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE), ("LEFTPADDING", (0, 0), (-1, -1), 18)]))
        parts.append(rule)
    if with_answer:
        parts.append(Spacer(1, 3))
        parts.append(Paragraph(f"Respuesta: {_t(_answer_text(it))}", st["ans"]))
        if it.get("context") and it["context"] != it["answer"]:
            parts.append(Paragraph(f"Fuente: «{_t(it['context'])}»", st["ev"]))
    parts.append(Spacer(1, 9))
    return [KeepTogether(parts)]


def _answer_text(it: dict) -> str:
    if it["kind"] == "mc" and it.get("options") and it["answer"] in it["options"]:
        return f"{'abcd'[it['options'].index(it['answer'])]}) {it['answer']}"
    return it["answer"]


def build_pdf(topic: dict, sources: list[dict], sections: list[dict], items_by_section: dict,
              layout: str = "examen", level_label: str = "Todos los niveles") -> bytes:
    _register_fonts()
    st = _styles()
    buf = io.BytesIO()

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont(_FONT, 8)
        canvas.setFillColor(INK3)
        canvas.drawString(18 * mm, 10 * mm, _plain(f"{topic['title']}  |  Estudio Dunlosky"))
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Página {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm,
                            bottomMargin=18 * mm, title=_plain(topic["title"]), author="Estudio Dunlosky",
                            subject="Preguntas y respuestas")
    story: list = []
    total = sum(len(v) for v in items_by_section.values())
    story.append(Paragraph(_t(topic["title"]), st["title"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph(_t(f"Cuestionario de {total} preguntas, {level_label.lower()}. "
                              + ("Respondé sin mirar el material; la clave de respuestas está al final."
                                 if layout == "examen" else "Cada pregunta incluye su respuesta y la evidencia en la fuente.")),
                           st["sub"]))
    story.append(Spacer(1, 6))
    src_lines = []
    for s in sources:
        line = f"{s['name']}: {s['title']}"
        if s.get("url"):
            line += f" ({s['url']})"
        if s.get("license"):
            line += f", licencia {s['license']}"
        src_lines.append(_t(line))
    story.append(Paragraph("Fuentes: " + "<br/>".join(src_lines), st["meta"]))
    story.append(Paragraph(_t(f"Generado el {datetime.now().strftime('%d/%m/%Y')}."), st["meta"]))
    story.append(Spacer(1, 8))

    n = 0
    numbered: list[tuple[int, dict]] = []
    for sec in sections:
        its = items_by_section.get(sec["id"], [])
        if not its:
            continue
        story.append(Paragraph(_t(sec["title"]), st["h2"]))
        for it in its:
            n += 1
            numbered.append((n, it))
            story.extend(_question_block(n, it, st, with_answer=(layout == "estudio")))

    if layout == "examen" and numbered:
        story.append(PageBreak())
        story.append(Paragraph("Clave de respuestas", st["title"]))
        story.append(Spacer(1, 8))
        for num, it in numbered:
            story.append(Paragraph(f"<b>{num}.</b> {_t(_answer_text(it))}", st["key"]))
            if it["kind"] in ("open", "why", "relate", "tf") and it.get("context") and it["context"] != it["answer"]:
                story.append(Paragraph(f"Fuente: «{_t(it['context'])}»", st["ev"]))
            story.append(Spacer(1, 4))

    if not numbered:
        story.append(Paragraph("No hay preguntas para el nivel elegido.", st["sub"]))
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()


def _plain(text: str) -> str:
    return "".join(ch if ord(ch) in (_GLYPHS or set()) else "?" for ch in text)
