"""
PDF-версия отчёта о соляре (вместо Word).
Кириллица в PDF требует встроенного TTF-шрифта — встроенные базовые шрифты
PDF (Helvetica и т.п.) кириллицу не поддерживают вообще.
"""

import os
import base64
import math
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

_REPORT_DIR = os.path.dirname(os.path.dirname(__file__))
_CHART_WHEEL_PATH = os.path.join(_REPORT_DIR, "assets", "chart-wheel.jpg")

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
    lines = markdown_text.split("\n")

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            html_parts.append("</ul>")
            in_list = False

    def is_table_line(value: str) -> bool:
        stripped = value.strip()
        return stripped.count("|") >= 1 and not stripped.startswith("```")

    def is_separator_line(value: str) -> bool:
        cells = [cell.strip() for cell in value.strip().strip("|").split("|")]
        return bool(cells) and all(re.match(r"^:?-{3,}:?$", cell or "") for cell in cells)

    def table_html(table_lines: list[str]) -> str:
        rows = []
        for table_line in table_lines:
            if is_separator_line(table_line):
                continue
            cells = [
                _md_inline_to_reportlab(cell.strip())
                for cell in table_line.strip().strip("|").split("|")
            ]
            rows.append(cells)
        if not rows:
            return ""

        head = rows[0]
        body_rows = rows[1:]
        header = "".join(f"<th>{cell}</th>" for cell in head)
        body = "\n".join(
            "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
            for row in body_rows
        )
        return (
            '<div class="table-wrap"><table class="report-table">'
            f"<thead><tr>{header}</tr></thead><tbody>{body}</tbody>"
            "</table></div>"
        )

    index = 0
    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.rstrip()
        if not line.strip():
            close_list()
            index += 1
            continue
        if re.match(r"^-{3,}\s*$", line.strip()):
            close_list()
            index += 1
            continue

        if is_table_line(line):
            close_list()
            table_lines = [line]
            index += 1
            while index < len(lines) and is_table_line(lines[index]):
                table_lines.append(lines[index].rstrip())
                index += 1
            html_parts.append(table_html(table_lines))
            continue

        if _is_heading_line(line):
            close_list()
            clean = _strip_heading_decoration(line)
            html_parts.append(f"<h2>{_md_inline_to_reportlab(clean)}</h2>")
            index += 1
            continue

        bullet_match = re.match(r"^[-*]\s+(.*)", line)
        if bullet_match:
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            html_parts.append(f"<li>{_md_inline_to_reportlab(bullet_match.group(1))}</li>")
            index += 1
            continue

        numbered_match = re.match(r"^(\d+[\.\)])\s+(.*)", line)
        if numbered_match:
            close_list()
            html_parts.append(
                f"<p><b>{saxutils.escape(numbered_match.group(1))}</b> "
                f"{_md_inline_to_reportlab(numbered_match.group(2))}</p>"
            )
            index += 1
            continue

        close_list()
        html_parts.append(f"<p>{_md_inline_to_reportlab(line)}</p>")
        index += 1

    close_list()
    return "\n".join(html_parts)


def _asset_data_uri(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as image:
        encoded = base64.b64encode(image.read()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _radar_svg(cards: list[dict]) -> str:
    items = cards[:6]
    if len(items) < 3:
        return ""

    center = 150
    max_radius = 104
    points = []
    labels = []
    spokes = []
    for index, card in enumerate(items):
        angle = -math.pi / 2 + (2 * math.pi * index / len(items))
        score = max(0, min(10, int(card.get("score", 0)))) / 10
        x = center + math.cos(angle) * max_radius * score
        y = center + math.sin(angle) * max_radius * score
        lx = center + math.cos(angle) * 128
        ly = center + math.sin(angle) * 128
        sx = center + math.cos(angle) * max_radius
        sy = center + math.sin(angle) * max_radius
        points.append(f"{x:.1f},{y:.1f}")
        spokes.append(f'<line x1="{center}" y1="{center}" x2="{sx:.1f}" y2="{sy:.1f}" />')
        labels.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle">'
            f"{saxutils.escape(str(card.get('title', '')))[:18]}</text>"
        )

    rings = []
    for radius in (35, 70, 104):
        ring_points = []
        for index in range(len(items)):
            angle = -math.pi / 2 + (2 * math.pi * index / len(items))
            ring_points.append(
                f"{center + math.cos(angle) * radius:.1f},"
                f"{center + math.sin(angle) * radius:.1f}"
            )
        rings.append(f'<polygon points="{" ".join(ring_points)}" />')

    return f"""
    <svg class="radar-svg" viewBox="0 0 300 300" role="img" aria-label="Карта сфер">
      <g class="radar-grid">{"".join(rings)}{"".join(spokes)}</g>
      <polygon class="radar-area" points="{" ".join(points)}" />
      <polyline class="radar-line" points="{" ".join(points)} {points[0]}" />
      <g class="radar-labels">{"".join(labels)}</g>
    </svg>
    """


def _score_by_title(cards: list[dict], needle: str) -> int:
    for card in cards:
        if needle.lower() in str(card.get("title", "")).lower():
            return int(card.get("score", 0))
    return int(cards[0].get("score", 0)) if cards else 0


def _relationship_type(average: float, top_label: str) -> str:
    if average >= 8:
        return "Глубокая, яркая, с сильным потенциалом роста"
    if average >= 6:
        return f"Живая и рабочая связь, где главный ключ - {top_label.lower()}"
    return "Неровная, но важная связь, требующая зрелых договорённостей"


def _synastry_label_case(label: str, grammatical_case: str) -> str:
    forms = {
        "Эмоциональная связь": {
            "accusative": "эмоциональную связь",
            "prepositional": "эмоциональной связи",
        },
        "Химия": {"accusative": "химию", "prepositional": "химии"},
        "Коммуникация": {"accusative": "коммуникацию", "prepositional": "коммуникации"},
        "Бытовая совместимость": {
            "accusative": "бытовую совместимость",
            "prepositional": "бытовой совместимости",
        },
        "Долгосрочность": {
            "accusative": "долгосрочность",
            "prepositional": "долгосрочности",
        },
        "Зоны напряжения": {
            "accusative": "зоны напряжения",
            "prepositional": "зонах напряжения",
        },
    }
    return forms.get(label, {}).get(grammatical_case, label.lower())


def _synastry_profile_html(profile: dict) -> str:
    cards_data = profile.get("cards", [])
    average = float(profile.get("average", 0))
    top_label = str(profile.get("top_label", "связь"))
    top_accusative = _synastry_label_case(top_label, "accusative")
    top_prepositional = _synastry_label_case(top_label, "prepositional")
    pair = next((value for label, value in profile.get("meta", []) if label == "ПАРА"), "")
    chemistry = _score_by_title(cards_data, "Химия")
    communication = _score_by_title(cards_data, "Коммуникация")
    tension = _score_by_title(cards_data, "напряж")
    long_term = _score_by_title(cards_data, "Долгосроч")
    relationship_type = _relationship_type(average, top_label)
    main_risk = "Разные языки любви и накопленное напряжение"
    if communication <= 5:
        main_risk = "Недосказанность, разные формулировки и обиды в диалоге"
    elif tension >= 8:
        main_risk = "Высокая интенсивность, ревность или борьба за контроль"

    score_rows = "\n".join(
        f"""
        <div class="syn-score-row">
          <span>{saxutils.escape(card['title'])}</span>
          <b><em>{card['score']}</em>/10</b>
        </div>
        """
        for card in cards_data
    )
    vector_tiles = "\n".join(
        f"""
        <div class="vector-tile">
          <span>{saxutils.escape(card['title'])}</span>
          <strong>{card['score']}/10</strong>
        </div>
        """
        for card in cards_data[:5]
    )
    sphere_cards = "\n".join(
        f"""
        <article class="syn-detail-card" style="--sphere:{card['color']}">
          <div class="syn-detail-score">{card['score']}</div>
          <h3>{saxutils.escape(card['title'])}</h3>
          <p>{saxutils.escape(card['note'])}</p>
        </article>
        """
        for card in cards_data
    )
    resources = [
        ("Физическая химия", "Сильное притяжение и энергия контакта" if chemistry >= 7 else "Притяжение включается через бережность и доверие"),
        ("Долгосрочный фундамент", "Способность строить связь со временем" if long_term >= 7 else "Фундаменту нужны правила, ритм и ясные ожидания"),
        (top_label, "Главный ресурс пары, на который можно опираться"),
        ("Совместное развитие", "Отношения подсвечивают рост и новые решения"),
        ("Честный разговор", "Прямота снижает напряжение быстрее, чем догадки"),
        ("Ритуалы близости", "Регулярные маленькие действия держат тепло"),
    ]
    risks = [
        ("Давление и критика", "высокий" if tension >= 8 else "средний"),
        ("Разный язык любви", "высокий" if communication <= 5 else "средний"),
        ("Ревность и контроль", "высокий" if tension >= 8 else "низкий"),
        ("Неясность мотивов", "средний"),
        ("Эмоциональное перенасыщение", "высокий" if average >= 8 else "средний"),
        ("Конфликт свободы и стабильности", "средний"),
    ]
    recommendations = [
        ("Если появляется критика", "Просить конкретику без оценки личности"),
        ("Если копится обида", "Разделять факты, эмоции и ожидания"),
        ("Если пропадает близость", "Обсудить ритм инициативы и поддержки"),
        ("Если слишком много интенсивности", "Делать паузы и возвращаться к разговору позже"),
        ("Если разные языки любви", "Проговаривать: для меня любовь - это..."),
    ]
    resource_cards = "\n".join(
        f"""
        <article class="mini-card">
          <div class="eyebrow">РЕСУРС</div>
          <h3>{saxutils.escape(title)}</h3>
          <p>{saxutils.escape(text)}</p>
        </article>
        """
        for title, text in resources
    )
    risk_cards = "\n".join(
        f"""
        <article class="risk-card">
          <div><span class="eyebrow">РИСК</span><b>{saxutils.escape(level)}</b></div>
          <h3>{saxutils.escape(title)}</h3>
        </article>
        """
        for title, level in risks
    )
    recommendation_rows = "\n".join(
        f"""
        <div class="recommendation-row">
          <span>{saxutils.escape(situation)}</span>
          <b>{saxutils.escape(action)}</b>
        </div>
        """
        for situation, action in recommendations
    )

    return f"""
    <section class="pdf-page syn-page syn-cover">
      <div class="syn-line"><span></span><b>Синастрия · Разбор пары</b></div>
      <h1><em>Синастрия</em><br>{saxutils.escape(pair or profile['hero_title'])}</h1>
      <p>{saxutils.escape(profile['hero_description'])}</p>
      <div class="syn-hero-grid">
        <div>
          <span class="eyebrow">ОБЩАЯ СОВМЕСТИМОСТЬ</span>
          <strong><em>{profile['average']}</em><small>/10</small></strong>
        </div>
        <div>
          <span class="eyebrow">ТИП СВЯЗИ</span>
          <b>{saxutils.escape(relationship_type)}</b>
        </div>
        <div>
          <span class="eyebrow">ГЛАВНЫЙ РЕСУРС</span>
          <b>{saxutils.escape(top_label)}</b>
        </div>
        <div>
          <span class="eyebrow">ГЛАВНЫЙ РИСК</span>
          <b>{saxutils.escape(main_risk)}</b>
        </div>
      </div>
    </section>

    <section class="pdf-page syn-page">
      <div class="section-mark">— 02 · Быстрая карта отношений</div>
      <div class="syn-surface syn-wheel-card">
        <div>
          <h2>Колесо совместимости</h2>
          <p>Карта показывает, какие сферы отношений работают в паре сильнее. Чем ближе к краю - тем ярче проявлена сфера.</p>
          <div class="syn-score-list">{score_rows}</div>
        </div>
        <div class="syn-radar">{_radar_svg(cards_data)}</div>
      </div>
    </section>

    <section class="pdf-page syn-page">
      <div class="section-mark">— 03 · Главная формула связи</div>
      <div class="syn-surface formula-card">
        <span class="eyebrow">ФОРМУЛА ПАРЫ</span>
        <h2>Эта синастрия — про <em>{saxutils.escape(top_accusative)}</em>, притяжение и обучение через отношения.</h2>
        <p>Потенциал пары раскрывается, когда вы говорите прямо, не копите напряжение и уважаете разные способы проявлять любовь.</p>
        <div class="vector-grid">{vector_tiles}</div>
      </div>
    </section>

    <section class="pdf-page syn-page">
      <div class="section-mark">— 04 · Сферы отношений</div>
      <div class="syn-detail-grid">{sphere_cards}</div>
    </section>

    <section class="pdf-page syn-page">
      <div class="section-mark">— 05 · Главные ресурсы пары</div>
      <div class="mini-grid">{resource_cards}</div>
    </section>

    <section class="pdf-page syn-page">
      <div class="section-mark">— 06 · Главные риски пары</div>
      <div class="risk-grid">{risk_cards}</div>
    </section>

    <section class="pdf-page syn-page">
      <div class="section-mark">— 07 · Практические рекомендации</div>
      <div class="syn-surface recommendation-card">
        <h2>Что делать в конкретных ситуациях</h2>
        <div class="recommendation-table">
          <div class="recommendation-head"><span>Ситуация</span><span>Что делать</span></div>
          {recommendation_rows}
        </div>
      </div>
    </section>

    <section class="pdf-page syn-page final-formula">
      <div class="syn-surface">
        <span class="eyebrow">ИТОГ РАЗБОРА</span>
        <h2>Эта связь держится на <em>{saxutils.escape(top_prepositional)}</em> и становится сильнее через честный разговор.</h2>
        <p>Главная активная сфера пары - {saxutils.escape(top_label.lower())}. Ключ пары - не избегать напряжения, а превращать его в понятные договорённости.</p>
      </div>
    </section>
    """


def _profile_html(profile: dict | None) -> str:
    if not profile:
        return ""
    if profile.get("kind") == "synastry":
        return _synastry_profile_html(profile)

    wheel_uri = _asset_data_uri(_CHART_WHEEL_PATH)
    meta = "\n".join(
        f"<div class=\"meta-item\"><span>{saxutils.escape(label)}</span><b>{saxutils.escape(value)}</b></div>"
        for label, value in profile.get("meta", [])
    )
    cards_data = profile.get("cards", [])
    cards = "\n".join(
        f"""
        <article class="sphere-card" style="--sphere:{card['color']}">
          <div class="score-ring" style="--score:{card['score']}">
            <strong>{card['score']}</strong>
            <span>из 10</span>
          </div>
          <div class="sphere-copy">
            <h3>{saxutils.escape(card['title'])}</h3>
            <p>{saxutils.escape(card['note'])}</p>
          </div>
        </article>
        """
        for card in cards_data
    )
    score_rows = "\n".join(
        f"""
        <div class="score-row" style="--sphere:{card['color']}">
          <span>{saxutils.escape(card['title'])}</span>
          <b>{card['score']}</b>
        </div>
        """
        for card in cards_data[:7]
    )
    focus_items = "\n".join(
        f"<li>{saxutils.escape(item)}</li>" for item in profile.get("focus_items", [])[:4]
    )
    wheel_image = (
        f'<img class="wheel-image" src="{wheel_uri}" alt="Астрологическое колесо">'
        if wheel_uri
        else ""
    )

    return f"""
    <section class="pdf-page cover-page">
        <div class="stars"></div>
        <div class="cover-glow"></div>
        {wheel_image}
        <div class="cover-copy">
          <div class="kicker">АСТРОЛОГИЧЕСКИЙ ОТЧЁТ</div>
          <h1>{saxutils.escape(profile['hero_title'])}</h1>
          <h2>{saxutils.escape(profile['hero_accent'])}</h2>
          <p>{saxutils.escape(profile['hero_description'])}</p>
          <div class="meta-row">{meta}</div>
        </div>
      </section>

      <section class="pdf-page intro-page">
        <div class="page-kicker">{saxutils.escape(profile['eyebrow'])}</div>
        <div class="intro-head">
          <div>
            <h2>{saxutils.escape(profile['section_title'])}</h2>
            <p>{saxutils.escape(profile['subtitle'])}</p>
          </div>
          <div class="summary-stats">
            <div><span>СРЕДНИЙ БАЛЛ</span><strong>{profile['average']}</strong></div>
            <div><span>ТОП СФЕРА</span><strong>{saxutils.escape(profile['top_label'])}</strong></div>
          </div>
        </div>
        <div class="wheel-grid">
          <div class="radar-panel">
            {_radar_svg(cards_data)}
          </div>
          <div class="score-list">{score_rows}</div>
        </div>
      </section>

      <section class="pdf-page cards-page">
        <div class="page-kicker">СФЕРЫ И АКЦЕНТЫ</div>
        <h2>Где будет больше всего движения</h2>
        <div class="sphere-grid">{cards}</div>
      </section>

      <section class="pdf-page focus-page">
        <div class="focus-panel">
        <div class="eyebrow">ПРАКТИЧЕСКИЙ ФОКУС</div>
        <h2>{saxutils.escape(profile['focus_title'])}</h2>
        <ul>{focus_items}</ul>
        </div>
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
      background: #080614;
      color: #f8f1df;
      font-family: DejaVu Sans, Arial, sans-serif;
    }}
    .pdf-page {{
      width: 210mm;
      height: 297mm;
      padding: 18mm;
      position: relative;
      page-break-after: always;
      overflow: hidden;
      background:
        radial-gradient(circle at 82% 14%, rgba(125, 56, 166, .32), transparent 34%),
        radial-gradient(circle at 12% 78%, rgba(157, 63, 90, .24), transparent 42%),
        linear-gradient(135deg, #070514 0%, #110b25 48%, #1b0d21 100%);
    }}
    .cover-page {{
      padding: 24mm 19mm;
    }}
    .stars {{
      position: absolute;
      inset: 0;
      opacity: .85;
      background-image:
        radial-gradient(circle at 10% 20%, #fff 0 1px, transparent 1.5px),
        radial-gradient(circle at 18% 62%, #fff 0 1px, transparent 1.5px),
        radial-gradient(circle at 32% 30%, #fff 0 1px, transparent 1.5px),
        radial-gradient(circle at 42% 72%, #fff 0 1px, transparent 1.5px),
        radial-gradient(circle at 55% 18%, #fff 0 1px, transparent 1.5px),
        radial-gradient(circle at 69% 54%, #fff 0 1px, transparent 1.5px),
        radial-gradient(circle at 84% 22%, #fff 0 1px, transparent 1.5px),
        radial-gradient(circle at 91% 76%, #fff 0 1px, transparent 1.5px);
    }}
    .cover-glow {{
      position: absolute;
      width: 118mm;
      height: 118mm;
      right: -25mm;
      top: 33mm;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(255, 198, 109, .28), transparent 62%);
      filter: blur(3px);
    }}
    .wheel-image {{
      position: absolute;
      right: -8mm;
      bottom: 10mm;
      width: 118mm;
      height: 118mm;
      border-radius: 50%;
      object-fit: cover;
      opacity: .82;
      mix-blend-mode: screen;
      filter: sepia(1) saturate(.8) hue-rotate(350deg) brightness(.95);
    }}
    .cover-copy {{
      position: relative;
      z-index: 2;
      width: 128mm;
      padding-top: 34mm;
    }}
    .kicker, .page-kicker, .eyebrow, .meta-item span, .summary-stats span {{
      color: #f3bd62;
      font-size: 9px;
      font-weight: 700;
      letter-spacing: 4px;
    }}
    .cover-page h1 {{
      margin: 9mm 0 2mm;
      font-size: 52px;
      line-height: .98;
      letter-spacing: 0;
    }}
    .cover-page h2 {{
      margin: 0 0 8mm;
      color: #ffc66d;
      font-size: 34px;
      line-height: 1.05;
    }}
    .cover-page p {{
      max-width: 116mm;
      margin: 0;
      color: #d8d1e6;
      font-size: 13px;
      line-height: 1.55;
    }}
    .meta-row {{
      display: grid;
      grid-template-columns: repeat(3, max-content);
      gap: 13mm;
      margin-top: 18mm;
    }}
    .meta-item span, .summary-stats span, .eyebrow {{ color: #7f829f; }}
    .meta-item b {{
      display: block;
      margin-top: 2mm;
      color: #fff9ea;
      font-size: 11px;
    }}
    .intro-head {{
      display: grid;
      grid-template-columns: 1fr 58mm;
      gap: 12mm;
      align-items: start;
      margin-top: 8mm;
    }}
    .intro-head h2, .cards-page h2 {{
      margin: 0 0 5mm;
      color: #fff9ea;
      font-size: 38px;
      line-height: 1.04;
    }}
    .intro-head p {{
      margin: 0;
      color: #c9c0d4;
      font-size: 14px;
      line-height: 1.55;
    }}
    .summary-stats {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 5mm;
    }}
    .summary-stats strong {{
      display: block;
      margin-top: 3mm;
      color: #fff9ea;
      font-size: 21px;
      line-height: 1.05;
    }}
    .wheel-grid {{
      display: grid;
      grid-template-columns: 105mm 1fr;
      gap: 13mm;
      margin-top: 18mm;
      align-items: center;
    }}
    .radar-panel {{
      min-height: 125mm;
      border: 1px solid rgba(255, 231, 179, .2);
      border-radius: 10mm;
      background: rgba(255, 255, 255, .045);
      box-shadow: inset 0 0 45px rgba(255, 198, 109, .08);
      display: grid;
      place-items: center;
    }}
    .radar-svg {{ width: 94mm; height: 94mm; overflow: visible; }}
    .radar-grid polygon, .radar-grid line {{
      fill: none;
      stroke: rgba(255, 231, 179, .22);
      stroke-width: 1;
    }}
    .radar-area {{
      fill: rgba(255, 198, 109, .22);
      stroke: none;
    }}
    .radar-line {{
      fill: none;
      stroke: #ffc66d;
      stroke-width: 3;
    }}
    .radar-labels text {{
      fill: #d6cce5;
      font-size: 9px;
      font-weight: 700;
    }}
    .score-list {{
      display: grid;
      gap: 4mm;
    }}
    .score-row {{
      display: grid;
      grid-template-columns: 1fr 12mm;
      align-items: center;
      gap: 5mm;
      padding: 4mm 0;
      border-bottom: 1px solid rgba(255, 231, 179, .16);
      color: #e8e0ef;
      font-size: 13px;
    }}
    .score-row::before {{
      content: "";
      width: 3mm;
      height: 3mm;
      border-radius: 50%;
      background: var(--sphere);
      box-shadow: 0 0 14px var(--sphere);
      grid-column: 1;
      grid-row: 1;
    }}
    .score-row span {{ padding-left: 7mm; grid-column: 1; grid-row: 1; }}
    .score-row b {{ color: #fff9ea; font-size: 17px; }}
    .sphere-grid {{
      margin: 0;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 5mm;
      margin-top: 10mm;
    }}
    .sphere-card {{
      min-height: 40mm;
      display: grid;
      grid-template-columns: 28mm 1fr;
      gap: 5mm;
      align-items: center;
      padding: 6mm;
      border: 1px solid rgba(255, 231, 179, .18);
      border-radius: 7mm;
      background:
        linear-gradient(135deg, rgba(255,255,255,.08), rgba(255,255,255,.035)),
        radial-gradient(circle at 16% 24%, color-mix(in srgb, var(--sphere), transparent 75%), transparent 45%);
    }}
    .score-ring {{
      width: 24mm;
      height: 24mm;
      border-radius: 50%;
      display: grid;
      place-items: center;
      background:
        radial-gradient(circle, #0d0a1e 0 52%, transparent 53%),
        conic-gradient(var(--sphere) calc(var(--score) * 10%), rgba(255,255,255,.13) 0);
      color: var(--sphere);
      box-shadow: 0 0 18px color-mix(in srgb, var(--sphere), transparent 55%);
    }}
    .score-ring strong {{ font-size: 24px; line-height: 1; }}
    .score-ring span {{
      margin-top: -9mm;
      color: #ddd3e9;
      font-size: 8px;
    }}
    .sphere-copy h3 {{
      margin: 0 0 2mm;
      color: #fff9ea;
      font-size: 18px;
      line-height: 1.08;
    }}
    .sphere-copy p {{
      margin: 0;
      color: #c9c0d4;
      font-size: 11.2px;
      line-height: 1.38;
    }}
    .focus-page {{
      display: grid;
      place-items: center;
    }}
    .focus-panel {{
      width: 172mm;
      padding: 14mm;
      border: 1px solid rgba(255, 231, 179, .2);
      border-radius: 10mm;
      background:
        radial-gradient(circle at 100% 0%, rgba(125, 56, 166, .26), transparent 42%),
        rgba(255, 255, 255, .06);
    }}
    .focus-panel h2 {{
      margin: 6mm 0 10mm;
      color: #fff9ea;
      font-size: 34px;
      line-height: 1.08;
    }}
    .focus-panel ul {{
      padding: 0;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 6mm 10mm;
      list-style: none;
    }}
    .focus-panel li {{
      position: relative;
      padding: 5mm 5mm 5mm 11mm;
      border-radius: 5mm;
      background: rgba(255, 255, 255, .055);
      color: #f4edfa;
      font-size: 12px;
      line-height: 1.45;
    }}
    .focus-panel li::before {{
      content: "";
      position: absolute;
      left: 5mm;
      top: 6mm;
      width: 2.3mm;
      height: 2.3mm;
      border-radius: 50%;
      background: #d5a600;
      box-shadow: 0 0 10px #d5a600;
    }}
    .syn-page {{
      padding: 20mm;
      background:
        radial-gradient(circle at 82% 15%, rgba(110, 68, 145, .22), transparent 34%),
        radial-gradient(circle at 18% 88%, rgba(108, 63, 86, .18), transparent 38%),
        #090814;
    }}
    .syn-line {{
      display: flex;
      align-items: center;
      gap: 4mm;
      color: #f0c66a;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 3px;
      text-transform: uppercase;
    }}
    .syn-line span {{
      width: 12mm;
      height: 1px;
      background: #f0c66a;
    }}
    .syn-cover h1 {{
      margin: 28mm 0 7mm;
      color: #f7f0df;
      font-size: 58px;
      line-height: .98;
      letter-spacing: 0;
    }}
    .syn-cover h1 em, .formula-card h2 em, .final-formula h2 em {{
      color: #d8ae55;
      font-style: italic;
    }}
    .syn-cover p {{
      max-width: 132mm;
      margin: 0;
      color: rgba(247, 240, 223, .76);
      font-size: 15px;
      line-height: 1.55;
    }}
    .syn-hero-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 13mm 18mm;
      margin-top: 28mm;
      max-width: 160mm;
    }}
    .syn-hero-grid strong {{
      display: block;
      margin-top: 2mm;
      color: #f7f0df;
      font-size: 38px;
      line-height: 1;
    }}
    .syn-hero-grid strong em {{
      color: #d8ae55;
      font-style: normal;
    }}
    .syn-hero-grid small {{
      color: rgba(247, 240, 223, .38);
      font-size: 23px;
    }}
    .syn-hero-grid b {{
      display: block;
      margin-top: 2mm;
      max-width: 70mm;
      color: rgba(247, 240, 223, .88);
      font-size: 15px;
      line-height: 1.45;
    }}
    .section-mark {{
      margin-bottom: 9mm;
      color: #b2a784;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 3px;
      text-transform: uppercase;
    }}
    .syn-surface {{
      border: 1px solid rgba(255,255,255,.06);
      border-radius: 8mm;
      background:
        radial-gradient(circle at 95% 10%, rgba(216, 174, 85, .08), transparent 40%),
        rgba(255,255,255,.035);
      box-shadow: 0 22px 60px rgba(0,0,0,.24);
    }}
    .syn-wheel-card {{
      display: grid;
      grid-template-columns: 72mm 1fr;
      gap: 12mm;
      align-items: center;
      padding: 12mm;
    }}
    .syn-wheel-card h2, .formula-card h2, .recommendation-card h2, .final-formula h2 {{
      margin: 0 0 4mm;
      color: #f7f0df;
      font-size: 34px;
      line-height: 1.08;
    }}
    .syn-wheel-card p, .formula-card p, .final-formula p {{
      margin: 0 0 6mm;
      color: rgba(247, 240, 223, .68);
      font-size: 12.5px;
      line-height: 1.55;
    }}
    .syn-score-list {{
      display: grid;
      margin-top: 6mm;
    }}
    .syn-score-row {{
      display: flex;
      justify-content: space-between;
      gap: 6mm;
      padding: 3.5mm 0;
      border-bottom: 1px solid rgba(255,255,255,.055);
      color: rgba(247, 240, 223, .86);
      font-size: 12px;
    }}
    .syn-score-row b {{
      color: rgba(247, 240, 223, .56);
      font-weight: 400;
    }}
    .syn-score-row em {{
      color: #d8ae55;
      font-style: normal;
      font-weight: 700;
    }}
    .syn-radar .radar-svg {{
      width: 88mm;
      height: 88mm;
    }}
    .formula-card {{
      padding: 14mm;
    }}
    .formula-card h2 {{
      max-width: 142mm;
      margin-top: 4mm;
      font-size: 35px;
    }}
    .formula-card p {{
      max-width: 140mm;
      margin-top: 6mm;
      font-size: 14px;
    }}
    .vector-grid {{
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 4mm;
      margin-top: 12mm;
    }}
    .vector-tile {{
      min-height: 28mm;
      padding: 4mm;
      border: 1px solid rgba(255,255,255,.055);
      border-radius: 5mm;
      background: rgba(255,255,255,.025);
    }}
    .vector-tile span {{
      display: block;
      color: #b2a784;
      font-size: 9.5px;
      line-height: 1.25;
    }}
    .vector-tile strong {{
      display: block;
      margin-top: 4mm;
      color: #d8ae55;
      font-size: 17px;
    }}
    .syn-detail-grid, .mini-grid, .risk-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 5mm;
    }}
    .syn-detail-card, .mini-card, .risk-card {{
      min-height: 38mm;
      padding: 6mm;
      border: 1px solid rgba(255,255,255,.06);
      border-radius: 6mm;
      background: rgba(255,255,255,.035);
    }}
    .syn-detail-card {{
      position: relative;
      overflow: hidden;
    }}
    .syn-detail-card::before {{
      content: "";
      position: absolute;
      inset: 0;
      background: radial-gradient(circle at 10% 10%, color-mix(in srgb, var(--sphere), transparent 70%), transparent 38%);
      opacity: .95;
    }}
    .syn-detail-card > * {{
      position: relative;
      z-index: 1;
    }}
    .syn-detail-score {{
      color: var(--sphere);
      font-size: 31px;
      font-weight: 800;
      line-height: 1;
    }}
    .syn-detail-card h3, .mini-card h3, .risk-card h3 {{
      margin: 3mm 0 2mm;
      color: #f7f0df;
      font-size: 18px;
      line-height: 1.12;
    }}
    .syn-detail-card p, .mini-card p {{
      margin: 0;
      color: rgba(247, 240, 223, .66);
      font-size: 11.5px;
      line-height: 1.4;
    }}
    .mini-grid, .risk-grid {{
      grid-template-columns: repeat(3, 1fr);
    }}
    .mini-card {{
      min-height: 42mm;
    }}
    .risk-card {{
      min-height: 34mm;
    }}
    .risk-card div {{
      display: flex;
      justify-content: space-between;
      gap: 4mm;
      align-items: center;
    }}
    .risk-card b {{
      border-radius: 999px;
      padding: 1.4mm 2.6mm;
      background: rgba(216, 174, 85, .16);
      color: #d8ae55;
      font-size: 9px;
      font-weight: 700;
      text-transform: uppercase;
    }}
    .recommendation-card {{
      padding: 11mm;
    }}
    .recommendation-table {{
      margin-top: 8mm;
      overflow: hidden;
      border: 1px solid rgba(255,255,255,.06);
      border-radius: 6mm;
    }}
    .recommendation-head, .recommendation-row {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8mm;
      padding: 4mm 6mm;
    }}
    .recommendation-head {{
      background: rgba(255,255,255,.035);
      color: rgba(247, 240, 223, .5);
      font-size: 9px;
      font-weight: 700;
      letter-spacing: 2px;
      text-transform: uppercase;
    }}
    .recommendation-row {{
      border-top: 1px solid rgba(255,255,255,.06);
      color: rgba(247, 240, 223, .88);
      font-size: 12px;
      line-height: 1.35;
    }}
    .recommendation-row b {{
      color: #d8ae55;
      font-weight: 600;
    }}
    .final-formula {{
      display: grid;
      place-items: center;
    }}
    .final-formula .syn-surface {{
      width: 160mm;
      padding: 16mm;
      text-align: center;
    }}
    .text-report {{
      min-height: 297mm;
      padding: 18mm 20mm;
      background: #0a0718;
      color: #f4edfa;
      font-size: 12.5px;
      line-height: 1.55;
    }}
    .text-report h1 {{ margin: 0 0 10mm; color: #ffc66d; font-size: 31px; }}
    .text-report h2 {{ margin: 8mm 0 3mm; color: #fff9ea; font-size: 19px; }}
    .text-report p {{ margin: 0 0 3.5mm; }}
    .text-report li {{ margin-bottom: 2mm; }}
    .table-wrap {{
      margin: 5mm 0 7mm;
      overflow: hidden;
      border: 1px solid rgba(255, 231, 179, .14);
      border-radius: 4mm;
      break-inside: avoid;
    }}
    .report-table {{
      width: 100%;
      border-collapse: collapse;
      color: #f4edfa;
      font-size: 10.5px;
      line-height: 1.38;
    }}
    .report-table th {{
      padding: 3.4mm 4mm;
      background: rgba(216, 174, 85, .12);
      color: #d8ae55;
      font-size: 8.5px;
      letter-spacing: 1.5px;
      text-align: left;
      text-transform: uppercase;
    }}
    .report-table td {{
      padding: 3.2mm 4mm;
      border-top: 1px solid rgba(255, 231, 179, .1);
      color: rgba(244, 237, 250, .86);
      vertical-align: top;
    }}
    .report-table tr:nth-child(even) td {{
      background: rgba(255, 255, 255, .025);
    }}
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
