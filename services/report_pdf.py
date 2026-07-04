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


def _markdown_to_html(markdown_text: str) -> str:
    html_parts = []
    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            html_parts.append("</ul>")
            in_list = False

    for raw_line in markdown_text.split("\n"):
        line = raw_line.rstrip()
        if not line.strip():
            close_list()
            continue
        if re.match(r"^-{3,}\s*$", line.strip()):
            close_list()
            continue

        if _is_heading_line(line):
            close_list()
            clean = _strip_heading_decoration(line)
            html_parts.append(f"<h2>{_md_inline_to_reportlab(clean)}</h2>")
            continue

        bullet_match = re.match(r"^[-*]\s+(.*)", line)
        if bullet_match:
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            html_parts.append(f"<li>{_md_inline_to_reportlab(bullet_match.group(1))}</li>")
            continue

        numbered_match = re.match(r"^(\d+[\.\)])\s+(.*)", line)
        if numbered_match:
            close_list()
            html_parts.append(
                f"<p><b>{saxutils.escape(numbered_match.group(1))}</b> "
                f"{_md_inline_to_reportlab(numbered_match.group(2))}</p>"
            )
            continue

        close_list()
        html_parts.append(f"<p>{_md_inline_to_reportlab(line)}</p>")

    close_list()
    return "\n".join(html_parts)


def _profile_html(profile: dict | None) -> str:
    if not profile:
        return ""

    meta = "\n".join(
        f"<div class=\"meta-item\"><span>{saxutils.escape(label)}</span><b>{saxutils.escape(value)}</b></div>"
        for label, value in profile.get("meta", [])
    )
    cards = "\n".join(
        f"""
        <article class="metric-card">
          <div class="donut" style="--score:{card['score']}; --color:{card['color']}">
            <strong>{card['score']}</strong><span>из 10</span>
          </div>
          <div>
            <h3>{saxutils.escape(card['title'])}</h3>
            <p>{saxutils.escape(card['note'])}</p>
          </div>
        </article>
        """
        for card in profile.get("cards", [])
    )
    focus_items = "\n".join(
        f"<li>{saxutils.escape(item)}</li>" for item in profile.get("focus_items", [])[:4]
    )

    return f"""
    <section class="visual-page">
      <header class="hero">
        <div class="stars"></div>
        <div class="orb orb-a"></div>
        <div class="orb orb-b"></div>
        <div class="hero-content">
          <div class="kicker">АСТРОЛОГИЧЕСКИЙ ОТЧЁТ</div>
          <h1>{saxutils.escape(profile['hero_title'])}</h1>
          <h2>{saxutils.escape(profile['hero_accent'])}</h2>
          <p>{saxutils.escape(profile['hero_description'])}</p>
          <div class="meta-row">{meta}</div>
        </div>
      </header>

      <section class="summary-head">
        <div>
          <div class="eyebrow">{saxutils.escape(profile['eyebrow'])}</div>
          <h2>{saxutils.escape(profile['section_title'])}</h2>
          <p>{saxutils.escape(profile['subtitle'])}</p>
        </div>
        <div class="summary-stats">
          <div><span>СРЕДНИЙ БАЛЛ</span><strong>{profile['average']}</strong></div>
          <div><span>ТОП СФЕРА</span><strong>{saxutils.escape(profile['top_label'])}</strong></div>
        </div>
      </section>

      <section class="metric-grid">{cards}</section>

      <section class="focus-box">
        <div class="eyebrow">ПРАКТИЧЕСКИЙ ФОКУС</div>
        <h2>{saxutils.escape(profile['focus_title'])}</h2>
        <ul>{focus_items}</ul>
      </section>
    </section>
    """


def _build_report_html(title: str, markdown_text: str, visual_profile: dict | None) -> str:
    body = _markdown_to_html(markdown_text)
    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <style>
    @page {{ size: A4; margin: 0; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: #ffffff;
      color: #202033;
      font-family: DejaVu Sans, Arial, sans-serif;
    }}
    .visual-page {{
      width: 210mm;
      height: 297mm;
      padding: 10mm 13mm;
      background: #fbf5e8;
      page-break-after: always;
      overflow: hidden;
    }}
    .hero {{
      position: relative;
      height: 69mm;
      border-radius: 7mm;
      overflow: hidden;
      background: #08061c;
      color: white;
      padding: 13mm 17mm;
    }}
    .hero-content {{ position: relative; z-index: 2; max-width: 145mm; }}
    .kicker, .eyebrow, .meta-item span, .summary-stats span {{
      color: #6b6d84;
      font-size: 8px;
      font-weight: 700;
      letter-spacing: 5px;
    }}
    .kicker {{ color: #ffc66d; letter-spacing: 3px; margin-bottom: 7mm; }}
    .hero h1 {{ margin: 0; font-size: 31px; line-height: 1.02; }}
    .hero h2 {{ margin: 2mm 0 5mm; color: #ffc66d; font-size: 25px; line-height: 1.04; }}
    .hero p {{ margin: 0; max-width: 122mm; color: #d9d4e2; font-size: 10.5px; line-height: 1.35; }}
    .meta-row {{ display: flex; gap: 18mm; margin-top: 3mm; }}
    .meta-item b {{ display: block; margin-top: 2mm; color: white; font-size: 10px; }}
    .orb {{ position: absolute; border-radius: 50%; opacity: .95; }}
    .orb-a {{ width: 48mm; height: 48mm; right: 20mm; top: 3mm; background: #2a123f; }}
    .orb-b {{ width: 39mm; height: 39mm; right: 14mm; top: 30mm; background: #642538; }}
    .stars {{
      position: absolute; inset: 0;
      background-image:
        radial-gradient(circle at 12% 70%, #fff 0 1px, transparent 1.5px),
        radial-gradient(circle at 33% 22%, #fff 0 1px, transparent 1.5px),
        radial-gradient(circle at 53% 61%, #fff 0 1px, transparent 1.5px),
        radial-gradient(circle at 84% 15%, #fff 0 1px, transparent 1.5px),
        radial-gradient(circle at 72% 44%, #fff 0 1px, transparent 1.5px);
    }}
    .summary-head {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 10mm;
      align-items: start;
      padding: 8mm 10mm 4mm;
    }}
    .summary-head h2 {{ margin: 3mm 0 3mm; font-size: 27px; line-height: 1.02; }}
    .summary-head p {{ margin: 0; color: #606276; font-size: 11.5px; line-height: 1.25; }}
    .summary-stats {{ display: flex; gap: 8mm; padding-top: 1mm; }}
    .summary-stats strong {{ display: block; margin-top: 3mm; font-size: 16px; }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 3.5mm;
      padding: 0 10mm;
    }}
    .metric-card {{
      display: grid;
      grid-template-columns: 30mm 1fr;
      gap: 4mm;
      align-items: center;
      min-height: 23mm;
      padding: 3.2mm;
      border: 1px solid #dfd7c8;
      border-radius: 6mm;
      background: #fffdf8;
      box-shadow: 0 5px 0 #ded7c8;
      overflow: hidden;
    }}
    .metric-card h3 {{ margin: 0 0 1.4mm; font-size: 13.5px; line-height: 1.05; }}
    .metric-card p {{
      margin: 0;
      color: #5d6074;
      font-size: 9.5px;
      line-height: 1.28;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }}
    .donut {{
      width: 19mm;
      height: 19mm;
      border-radius: 50%;
      display: grid;
      place-items: center;
      background:
        radial-gradient(circle, #fffdf8 0 49%, transparent 50%),
        conic-gradient(var(--color) calc(var(--score) * 10%), #f0ede5 0);
      color: var(--color);
    }}
    .donut strong {{ font-size: 17px; line-height: 1; }}
    .donut span {{ margin-top: -7mm; color: #5d6074; font-size: 7px; }}
    .focus-box {{
      margin: 8mm 10mm 0;
      padding: 7mm 10mm;
      border: 1px solid #dfd7c8;
      border-radius: 8mm;
      background: #fffdf8;
      box-shadow: 0 5px 0 #ded7c8;
    }}
    .focus-box h2 {{ margin: 3mm 0 5mm; font-size: 22px; line-height: 1.05; }}
    .focus-box ul {{
      margin: 0;
      padding: 0;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 3.5mm 8mm;
      list-style: none;
    }}
    .focus-box li {{
      position: relative;
      padding-left: 7mm;
      font-size: 9.5px;
      line-height: 1.25;
    }}
    .focus-box li::before {{
      content: "";
      position: absolute;
      left: 0;
      top: 1.5mm;
      width: 2mm;
      height: 2mm;
      border-radius: 50%;
      background: #d5a600;
    }}
    .text-report {{
      padding: 18mm 20mm;
      font-size: 12px;
      line-height: 1.55;
    }}
    .text-report h1 {{ margin: 0 0 10mm; font-size: 28px; }}
    .text-report h2 {{ margin: 8mm 0 3mm; font-size: 18px; }}
    .text-report p {{ margin: 0 0 3.5mm; }}
    .text-report li {{ margin-bottom: 2mm; }}
  </style>
</head>
<body>
  {_profile_html(visual_profile)}
  <main class="text-report">
    <h1>{saxutils.escape(title)}</h1>
    {body}
  </main>
</body>
</html>"""


async def _html_to_pdf(
    title: str,
    markdown_text: str,
    output_path: str,
    visual_profile: dict | None,
) -> None:
    from playwright.async_api import async_playwright

    html = _build_report_html(title, markdown_text, visual_profile)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(html, wait_until="networkidle")
        await page.pdf(path=output_path, format="A4", print_background=True, prefer_css_page_size=True)
        await browser.close()


def _reportlab_markdown_to_pdf(
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


async def markdown_to_pdf(
    title: str,
    markdown_text: str,
    output_path: str,
    visual_profile: dict | None = None,
) -> None:
    try:
        await _html_to_pdf(title, markdown_text, output_path, visual_profile)
    except Exception:
        _reportlab_markdown_to_pdf(title, markdown_text, output_path, visual_profile)
