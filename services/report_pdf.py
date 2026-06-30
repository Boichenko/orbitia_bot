"""
PDF-версия отчёта о соляре (вместо Word).
Кириллица в PDF требует встроенного TTF-шрифта — встроенные базовые шрифты
PDF (Helvetica и т.п.) кириллицу не поддерживают вообще.
"""

import os
import re
import xml.sax.saxutils as saxutils

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

_FONT_NAME = "DejaVuSans"
_FONT_BOLD = "DejaVuSans-Bold"
_FONT_REGISTERED = False

_FONT_CANDIDATES = [
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    (
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    ),
]

_KNOWN_SECTION_TITLES = [
    "ключевые данные",
    "предварительное извлечение",
    "ключевые показатели",
    "главная тема года",
    "асцендент соляра",
    "управитель асцендента",
    "mc и 10 дом соляра",
    "солнце соляра",
    "луна соляра",
    "самые загруженные дома",
    "деньги и ресурсы",
    "работа, карьера",
    "отношения и личная жизнь",
    "дом, семья, недвижимость",
    "поездки, документы",
    "здоровье, тело, режим",
    "лунные узлы",
    "медленные планеты",
    "ключевые аспекты",
    "повторяющиеся темы",
    "сложные зоны года",
    "сильные возможности года",
    "психологический смысл года",
    "прогноз по периодам",
    "итоговая выжимка",
]


def _ensure_font() -> None:
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return
    for regular, bold in _FONT_CANDIDATES:
        if os.path.exists(regular) and os.path.exists(bold):
            pdfmetrics.registerFont(TTFont(_FONT_NAME, regular))
            pdfmetrics.registerFont(TTFont(_FONT_BOLD, bold))
            pdfmetrics.registerFontFamily(
                _FONT_NAME,
                normal=_FONT_NAME,
                bold=_FONT_BOLD,
                italic=_FONT_NAME,
                boldItalic=_FONT_BOLD,
            )
            _FONT_REGISTERED = True
            return
    raise RuntimeError(
        "Не найден шрифт с поддержкой кириллицы (DejaVu Sans). "
        "Установи на сервере: sudo apt install fonts-dejavu-core"
    )


def _md_inline_to_reportlab(text: str) -> str:
    escaped = saxutils.escape(text)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)


def _strip_heading_decoration(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^#{1,4}\s*", "", line)
    line = re.sub(r"^\*\*(.*)\*\*$", r"\1", line)
    line = re.sub(r"^ЧАСТЬ\s+[IVXLCDM\d]+\.?\s*", "", line, flags=re.IGNORECASE)
    line = re.sub(r"^\**\d+[\.\)]\s*", "", line)
    line = re.sub(r"^[^\w\s]+\s*", "", line)
    return line.strip()


def _is_heading_line(line: str) -> bool:
    if re.match(r"^#{1,4}\s+\S", line):
        return True
    if re.match(r"^ЧАСТЬ\s+\S", line, re.IGNORECASE):
        return True
    stripped = _strip_heading_decoration(line).lower()
    return any(title in stripped for title in _KNOWN_SECTION_TITLES)


def markdown_to_pdf(title: str, markdown_text: str, output_path: str) -> None:
    _ensure_font()

    styles = getSampleStyleSheet()
    normal_style = ParagraphStyle(
        "NormalRu",
        parent=styles["Normal"],
        fontName=_FONT_NAME,
        fontSize=11,
        leading=15,
        spaceAfter=8,
    )
    bullet_style = ParagraphStyle("BulletRu", parent=normal_style, leftIndent=14)
    heading_style = ParagraphStyle(
        "HeadingRu",
        parent=styles["Normal"],
        fontName=_FONT_BOLD,
        fontSize=15,
        leading=19,
        spaceBefore=16,
        spaceAfter=8,
    )
    title_style = ParagraphStyle(
        "TitleRu",
        parent=styles["Normal"],
        fontName=_FONT_BOLD,
        fontSize=22,
        leading=26,
        spaceAfter=20,
    )

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )

    story = [Paragraph(saxutils.escape(title), title_style), Spacer(1, 10)]

    for raw_line in markdown_text.split("\n"):
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if re.match(r"^-{3,}\s*$", line.strip()):
            continue

        if _is_heading_line(line):
            clean = _strip_heading_decoration(line)
            story.append(Paragraph(_md_inline_to_reportlab(clean), heading_style))
            continue

        bullet_match = re.match(r"^[-*]\s+(.*)", line)
        if bullet_match:
            story.append(
                Paragraph("•  " + _md_inline_to_reportlab(bullet_match.group(1)), bullet_style)
            )
            continue

        numbered_match = re.match(r"^(\d+[\.\)])\s+(.*)", line)
        if numbered_match:
            story.append(
                Paragraph(
                    f"{numbered_match.group(1)} {_md_inline_to_reportlab(numbered_match.group(2))}",
                    normal_style,
                )
            )
            continue

        story.append(Paragraph(_md_inline_to_reportlab(line), normal_style))

    doc.build(story)
