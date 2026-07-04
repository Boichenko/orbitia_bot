"""
PDF-версия отчёта о соляре (вместо Word).
Кириллица в PDF требует встроенного TTF-шрифта — встроенные базовые шрифты
PDF (Helvetica и т.п.) кириллицу не поддерживают вообще.
"""

import os
import re
import xml.sax.saxutils as saxutils

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer

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
    (
        os.path.expanduser(
            "~/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/"
            "libreoffice-headless/libreoffice/LibreOfficeDev.app/Contents/Resources/fonts/"
            "truetype/DejaVuSans.ttf"
        ),
        os.path.expanduser(
            "~/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/"
            "libreoffice-headless/libreoffice/LibreOfficeDev.app/Contents/Resources/fonts/"
            "truetype/DejaVuSans-Bold.ttf"
        ),
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


class VisualSummaryPage(Flowable):
    def __init__(self, profile: dict):
        super().__init__()
        self.profile = profile
        self.width = A4[0] - 4 * cm
        self.height = A4[1] - 4 * cm

    def wrap(self, avail_width, avail_height):
        self.width = avail_width
        self.height = avail_height
        return avail_width, avail_height

    def _wrap_text(self, text, max_chars: int) -> list[str]:
        words = str(text).split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if len(candidate) <= max_chars:
                current = candidate
                continue
            if current:
                lines.append(current)
            current = word
        if current:
            lines.append(current)
        return lines

    def _text(
        self,
        text,
        x,
        y,
        size=10,
        font=_FONT_NAME,
        color="#202033",
        leading=None,
        max_chars: int | None = None,
        max_lines: int | None = None,
    ):
        self.canv.setFillColor(colors.HexColor(color))
        self.canv.setFont(font, size)
        lines = []
        for raw_line in str(text).split("\n"):
            lines.extend(self._wrap_text(raw_line, max_chars) if max_chars else [raw_line])
        was_truncated = max_lines is not None and len(lines) > max_lines
        if max_lines is not None:
            lines = lines[:max_lines]
        if was_truncated and lines:
            limit = max_chars or 80
            suffix = "..."
            lines[-1] = lines[-1][: max(0, limit - len(suffix))].rstrip() + suffix
        for i, line in enumerate(lines):
            self.canv.drawString(x, y - i * (leading or size * 1.25), line)

    def _donut(self, x, y, score, color):
        radius = 19
        self.canv.setLineWidth(6)
        self.canv.setStrokeColor(colors.HexColor("#f0ede5"))
        self.canv.circle(x, y, radius, stroke=1, fill=0)
        self.canv.setStrokeColor(colors.HexColor(color))
        start = 90
        extent = -360 * max(0, min(10, score)) / 10
        self.canv.arc(x - radius, y - radius, x + radius, y + radius, startAng=start, extent=extent)
        self.canv.setFillColor(colors.HexColor(color))
        self.canv.setFont(_FONT_BOLD, 15)
        self.canv.drawCentredString(x, y + 1, str(score))
        self.canv.setFillColor(colors.HexColor("#5d6074"))
        self.canv.setFont(_FONT_NAME, 6.5)
        self.canv.drawCentredString(x, y - 12, "из 10")

    def _card(self, x, y, w, h, card):
        self.canv.setFillColor(colors.HexColor("#fffdf8"))
        self.canv.setStrokeColor(colors.HexColor("#dfd7c8"))
        self.canv.roundRect(x, y, w, h, 12, stroke=1, fill=1)
        self._donut(x + 31, y + h / 2, card["score"], card["color"])
        self._text(
            card["title"],
            x + 64,
            y + h - 22,
            10,
            _FONT_BOLD,
            "#202033",
            leading=11,
            max_chars=16,
            max_lines=2,
        )
        self._text(
            card["note"],
            x + 64,
            y + h - 49,
            7.6,
            _FONT_NAME,
            "#5d6074",
            leading=9,
            max_chars=26,
            max_lines=2,
        )

    def draw(self):
        c = self.canv
        p = self.profile
        w = self.width
        h = self.height

        c.setFillColor(colors.HexColor("#fbf5e8"))
        c.roundRect(0, 0, w, h, 18, stroke=0, fill=1)

        # Hero.
        hero_h = 178
        c.setFillColor(colors.HexColor("#0b0820"))
        c.roundRect(0, h - hero_h, w, hero_h, 16, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#26123d"))
        c.circle(w - 86, h - 58, 55, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#522333"))
        c.circle(w - 76, h - 128, 48, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#ffffff"))
        for i in range(26):
            x = (i * 47) % int(w)
            y = h - hero_h + 18 + ((i * 31) % (hero_h - 30))
            c.circle(x, y, 0.7, stroke=0, fill=1)

        self._text("АСТРОЛОГИЧЕСКИЙ ОТЧЁТ", 34, h - 45, 7, _FONT_BOLD, "#f6bf68")
        self._text(p["hero_title"], 34, h - 82, 22, _FONT_BOLD, "#ffffff", max_chars=28)
        self._text(p["hero_accent"], 34, h - 112, 20, _FONT_BOLD, "#f6bf68", max_chars=31)
        self._text(
            p["hero_description"],
            34,
            h - 140,
            8.5,
            _FONT_NAME,
            "#d7d0df",
            leading=12,
            max_chars=72,
            max_lines=2,
        )
        meta_x = 34
        for label, value in p.get("meta", []):
            self._text(label, meta_x, h - 164, 5.5, _FONT_BOLD, "#8f879d")
            self._text(value, meta_x, h - 177, 7.2, _FONT_BOLD, "#ffffff", max_chars=17)
            meta_x += 120

        top_y = h - hero_h - 48
        self._text(p["eyebrow"], 34, top_y + 26, 7.5, _FONT_BOLD, "#696b83")
        section_size = 18 if len(p["section_title"]) > 18 else 22
        self._text(p["section_title"], 34, top_y, section_size, _FONT_BOLD, "#202033")
        self._text(
            p["subtitle"],
            34,
            top_y - 28,
            9.2,
            _FONT_NAME,
            "#606276",
            max_chars=52,
            max_lines=1,
        )
        self._text("СРЕДНИЙ БАЛЛ", w - 142, top_y + 24, 6.5, _FONT_BOLD, "#696b83")
        self._text(str(p["average"]), w - 116, top_y - 2, 13, _FONT_BOLD, "#202033")
        self._text("ТОП СФЕРА", w - 68, top_y + 24, 6.5, _FONT_BOLD, "#696b83")
        self._text(p["top_label"], w - 68, top_y - 2, 10, _FONT_BOLD, "#202033", max_chars=12)

        card_w = (w - 68 - 14) / 2
        card_h = 76
        y1 = top_y - 122
        for idx, card in enumerate(p["cards"]):
            row = idx // 2
            col = idx % 2
            self._card(34 + col * (card_w + 14), y1 - row * (card_h + 8), card_w, card_h, card)

        focus_y = 58
        focus_h = 126
        c.setFillColor(colors.HexColor("#fffdf8"))
        c.setStrokeColor(colors.HexColor("#dfd7c8"))
        c.roundRect(34, focus_y, w - 68, focus_h, 14, stroke=1, fill=1)
        self._text("ПРАКТИЧЕСКИЙ ФОКУС", 56, focus_y + 96, 7, _FONT_BOLD, "#696b83")
        self._text(p["focus_title"], 56, focus_y + 70, 16, _FONT_BOLD, "#202033", max_chars=38)
        items = p.get("focus_items", [])[:4]
        for idx, item in enumerate(items):
            col = idx % 2
            row = idx // 2
            x = 58 + col * ((w - 120) / 2)
            y = focus_y + 42 - row * 31
            c.setFillColor(colors.HexColor("#d5a600"))
            c.circle(x, y + 3, 2.5, stroke=0, fill=1)
            self._text(item, x + 12, y, 7.4, _FONT_NAME, "#202033", leading=8.5, max_chars=34, max_lines=1)


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


def markdown_to_pdf(
    title: str,
    markdown_text: str,
    output_path: str,
    visual_profile: dict | None = None,
) -> None:
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

    story = []
    if visual_profile:
        story.extend([VisualSummaryPage(visual_profile), PageBreak()])
    story.extend([Paragraph(saxutils.escape(title), title_style), Spacer(1, 10)])

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
