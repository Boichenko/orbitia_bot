"""Fillable Lovable-style HTML template for structured solar reports."""

from __future__ import annotations

import base64
from functools import lru_cache
import math
from pathlib import Path
import struct
import xml.sax.saxutils as saxutils
import zlib


_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_HTML_TEMPLATE = _TEMPLATE_DIR / "solar_report.html"
_CSS_TEMPLATE = _TEMPLATE_DIR / "solar_report.css"
_CHART_WHEEL = _ROOT / "assets" / "chart-wheel.jpg"
_FONT_DIR = _ROOT / "assets" / "fonts"

_DEFAULT_TITLES = {
    "career": "Карьера",
    "money": "Деньги",
    "relationships": "Отношения",
    "home": "Дом",
    "health": "Здоровье и режим",
    "communication": "Общение",
    "inner": "Внутреннее",
    "sex": "Секс",
}

_RADAR_TITLES = {
    "career": "Карьера",
    "money": "Деньги",
    "relationships": "Отношения",
    "home": "Дом",
    "health": "Здоровье",
    "communication": "Общение",
    "inner": "Внутреннее",
    "sex": "Секс",
}

_CATEGORY_ORDER = [
    "career",
    "money",
    "relationships",
    "home",
    "health",
    "communication",
    "inner",
    "sex",
]


def render_solar_html(report: dict, *, pdf_url: str | None = None) -> str:
    """Render a complete HTML document from normalized solar JSON."""
    cover = report.get("cover") or {}
    theme = report.get("main_theme") or {}
    cards = _sphere_cards(report)

    values = {
        "SOLAR_REPORT_CSS": _font_face_css() + _read_text(_CSS_TEMPLATE),
        "WEB_DOWNLOAD_BUTTON": (
            f'<a class="floating-pdf-button" href="{_safe(pdf_url)}" download>Скачать PDF</a>'
            if pdf_url else ""
        ),
        "COVER_TITLE": _safe(cover.get("title"), "Соляр"),
        "COVER_SUBTITLE": _safe(cover.get("subtitle"), "Персональный прогноз по сферам жизни"),
        "COVER_PERIOD": _safe(cover.get("period")),
        "COVER_PLACE": _safe(cover.get("place")),
        "COVER_SCORE": _display_score(cover.get("overall_score"), _average_score(cards)),
        "COVER_TOP": _safe(cover.get("top_sphere")),
        "COVER_ART": _cover_art(),
        "SPHERE_ROWS": _sphere_rows(cards),
        "RADAR_SVG": _radar_svg(cards),
        "MAP_SUMMARY": _safe(
            report.get("map_summary"),
            "Карта сфер показывает, где год даёт максимум движения, а где важнее действовать спокойнее. Самые высокие баллы формируют главный ресурс периода, низкие - зоны внимания и бережной настройки.",
        ),
        "THEME_TITLE": _theme_title_markup(theme.get("title") or "Главная тема года"),
        "THEME_TEXT": _safe(theme.get("text")),
        "THEME_PILLS": _pill_list(theme.get("accents")),
        "ADDITIONAL_ACCENTS": _additional_accents(theme),
        "CATEGORY_PAGES": _category_pages(report),
        "RISK_ROWS": _risk_rows(report.get("risk_summary")),
        "OPPORTUNITY_CARDS": _opportunity_cards(report.get("opportunities")),
        "PLAN_STEPS": _plan_steps(report.get("plan"), report),
        "FINAL_FORMULA": _safe(report.get("final_formula")),
        "HEATMAP_CARDS": _heatmap_cards(report, cards),
    }

    html = _read_text(_HTML_TEMPLATE)
    for key, value in values.items():
        html = html.replace("{{" + key + "}}", value)
    return html


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _safe(value, fallback: str = "") -> str:
    return saxutils.escape(str(value if value not in (None, "") else fallback))


def _theme_title_markup(value: str) -> str:
    title = str(value).strip()
    prefix = "Год про "
    if title.startswith(prefix) and "," in title:
        highlighted, remainder = title[len(prefix):].split(",", 1)
        return f"{_safe(prefix)}<em>{_safe(highlighted)}</em>,{_safe(remainder)}"
    return _safe(title)


def _score(value, fallback: int = 5) -> int:
    try:
        result = int(round(float(value)))
    except (TypeError, ValueError):
        result = fallback
    return max(1, min(10, result))


def _display_score(value, fallback: int = 5) -> str:
    try:
        score = max(1.0, min(10.0, float(value)))
    except (TypeError, ValueError):
        score = float(fallback)
    if score.is_integer():
        return str(int(score))
    return f"{score:.1f}"


def _average_score(cards: list[dict]) -> int:
    if not cards:
        return 8
    return _score(sum(_score(card.get("score")) for card in cards) / len(cards), 8)


def _asset_data_uri(path: Path) -> str:
    if not path.exists():
        return ""
    mime = "image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def _font_face_css() -> str:
    fonts = [
        ("Cormorant Garamond", "CormorantGaramond-Regular.ttf", "normal", 400),
        ("Cormorant Garamond", "CormorantGaramond-Italic.ttf", "italic", 400),
        ("Manrope", "Manrope-Regular.ttf", "normal", 400),
        ("Manrope", "Manrope-Medium.ttf", "normal", 500),
        ("Manrope", "Manrope-Medium.ttf", "normal", 600),
        ("Manrope", "Manrope-Medium.ttf", "normal", 700),
        ("Manrope", "Manrope-Medium.ttf", "normal", 800),
        ("JetBrains Mono", "JetBrainsMono-Regular.ttf", "normal", 400),
        ("JetBrains Mono", "JetBrainsMono-Regular.ttf", "normal", 500),
        ("JetBrains Mono", "JetBrainsMono-Regular.ttf", "normal", 800),
    ]
    rules = []
    for family, filename, style, weight in fonts:
        path = _FONT_DIR / filename
        if not path.exists():
            continue
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        rules.append(
            "@font-face{"
            f"font-family:'{family}';font-style:{style};font-weight:{weight};"
            f"font-display:block;src:url(data:font/ttf;base64,{data}) format('truetype');"
            "}"
        )
    return "".join(rules)


def _cover_art() -> str:
    src = _asset_data_uri(_CHART_WHEEL)
    if not src:
        return ""
    return f'<img src="{src}" alt="" />'


def _category_by_key(report: dict, key: str) -> dict:
    for category in report.get("categories") or []:
        if category.get("key") == key:
            return category
    return {"key": key, "title": _DEFAULT_TITLES.get(key, key), "score": 5}


def _sphere_cards(report: dict) -> list[dict]:
    source = report.get("sphere_map") or []
    cards = []
    for index, key in enumerate(_CATEGORY_ORDER):
        row = next((item for item in source if item.get("key") == key), None) or {}
        category = _category_by_key(report, key)
        cards.append(
            {
                "key": key,
                "title": row.get("title") or _DEFAULT_TITLES.get(key, key),
                "score": _score(row.get("score", category.get("score"))),
                "meaning": row.get("meaning") or category.get("summary") or "",
                "index": index,
            }
        )
    return cards


def _sphere_rows(cards: list[dict]) -> str:
    return "".join(
        f"""
        <div class="score-row">
          <span>{_safe(card.get("title"))}</span>
          <b>{_score(card.get("score"))}<small>/10</small></b>
        </div>
        """
        for card in cards
    )


def _heatmap_cards(report: dict, fallback_cards: list[dict]) -> str:
    source = report.get("heatmap")
    if not isinstance(source, list) or not source:
        source = fallback_cards

    cards = []
    for item in source[:8]:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("sphere") or item.get("name")
        score = _score(item.get("score") or item.get("level"), 5)
        background = _heatmap_background(score)
        cards.append(
            f"""
            <article class="heatmap-card" style="{background}">
              <h3>{_safe(title)}</h3>
              <strong>{score}<span>/10</span></strong>
            </article>
            """
        )

    return "".join(cards)


def _heatmap_background(score: int) -> str:
    score = max(1, min(10, score))
    alpha = round(255 * score / 10)
    gradient = _gradient_png_data_uri("#947041", "#50315b", alpha)
    return (
        f"background-color:#0b0c25;background-image:url('{gradient}');"
        "background-size:100% 100%;background-repeat:no-repeat;"
    )


@lru_cache(maxsize=16)
def _gradient_png_data_uri(start_hex: str, end_hex: str, alpha: int, width: int = 600, height: int = 180) -> str:
    """Raster gradient avoids macOS PDF vector-gradient seams inside rounded cards."""
    start = tuple(int(start_hex[index:index + 2], 16) for index in (1, 3, 5))
    end = tuple(int(end_hex[index:index + 2], 16) for index in (1, 3, 5))
    rows = bytearray()
    denominator = max(1, (width - 1) + (height - 1) * .22)
    for y in range(height):
        rows.append(0)
        for x in range(width):
            ratio = min(1, (x + y * .22) / denominator)
            rows.extend(round(a + (b - a) * ratio) for a, b in zip(start, end))
            rows.append(max(0, min(255, alpha)))

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + chunk(b"IEND", b"")
    )
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def _radar_svg(cards: list[dict]) -> str:
    size = 320
    center = size / 2
    radius = 104
    count = max(1, len(cards))
    rings = []
    for ring in range(1, 5):
        r = radius * ring / 4
        points = []
        for index in range(count):
            angle = (2 * math.pi * index / count) - math.pi / 2
            points.append(f"{center + math.cos(angle) * r:.2f},{center + math.sin(angle) * r:.2f}")
        rings.append(f"<polygon points=\"{' '.join(points)}\" />")

    axis = []
    dots = []
    labels = []
    area_points = []
    for index, card in enumerate(cards):
        angle = (2 * math.pi * index / count) - math.pi / 2
        outer_x = center + math.cos(angle) * radius
        outer_y = center + math.sin(angle) * radius
        value_r = radius * _score(card.get("score")) / 10
        point_x = center + math.cos(angle) * value_r
        point_y = center + math.sin(angle) * value_r
        label_distance = radius + (24 if index in (2, 6) else 30)
        label_x = center + math.cos(angle) * label_distance
        label_y = center + math.sin(angle) * label_distance
        anchor = "middle"
        if math.cos(angle) > .25:
            anchor = "start"
        elif math.cos(angle) < -.25:
            anchor = "end"
        axis.append(f'<line x1="{center:.2f}" y1="{center:.2f}" x2="{outer_x:.2f}" y2="{outer_y:.2f}" />')
        dots.append(f'<circle cx="{point_x:.2f}" cy="{point_y:.2f}" r="4" />')
        labels.append(
            f"""
            <text class="radar-label-title" x="{label_x:.2f}" y="{label_y - 5:.2f}" text-anchor="{anchor}" dominant-baseline="middle">{_safe(_RADAR_TITLES.get(card.get("key"), card.get("title")))}</text>
            <text class="radar-label-score" x="{label_x:.2f}" y="{label_y + 8:.2f}" text-anchor="{anchor}" dominant-baseline="middle">{_score(card.get("score"))}/10</text>
            """
        )
        area_points.append(f"{point_x:.2f},{point_y:.2f}")

    return f"""
    <svg class="radar-svg" viewBox="0 0 {size} {size}">
      <g class="radar-grid">{''.join(rings)}{''.join(axis)}</g>
      <polygon class="radar-area" points="{' '.join(area_points)}" />
      <polygon class="radar-line" points="{' '.join(area_points)}" />
      <g class="radar-dots">{''.join(dots)}</g>
      <g class="radar-labels">{''.join(labels)}</g>
    </svg>
    """


def _pill_list(items) -> str:
    if not isinstance(items, list) or not items:
        return ""
    return "".join(f"<span>{_safe(item)}</span>" for item in items[:4])


def _additional_accents(theme: dict) -> str:
    source = theme.get("additional_accents") or [{"title": item, "text": ""} for item in (theme.get("accents") or [])]
    if not source:
        source = [
            {"title": "Сильная сфера", "text": "Там, где год даёт больше всего движения, важно действовать смело и конкретно."},
            {"title": "Зона внимания", "text": "Низкие баллы не слабость, а место, где лучше выбирать бережный темп."},
            {"title": "Практический фокус", "text": "Главная польза отчёта - превратить прогноз в понятные решения."},
        ]
    cards = []
    for item in source[:3]:
        if isinstance(item, dict):
            title = item.get("title")
            text = item.get("text")
        else:
            title = item
            text = ""
        cards.append(f"<article><b>{_safe(title)}</b><span>{_safe(text)}</span></article>")
    return "".join(cards)


def _list_items(items, limit: int | None = None) -> str:
    if not isinstance(items, list):
        return ""
    visible = items if limit is None else items[:limit]
    return "".join(f"<li>{_safe(item)}</li>" for item in visible)


def _category_pages(report: dict) -> str:
    return "".join(_category_page(_category_by_key(report, key), key) for key in _CATEGORY_ORDER)


def _category_page(category: dict, key: str) -> str:
    score = _score(category.get("score"))
    main_takeaway = _category_takeaway(category)
    return f"""
    <section class="page category-page category-{_safe(key)}">
      <div class="section-head category-section-head">
        <span>03</span>
        <b>Категории</b>
      </div>
      <div class="category-shell">
        <header class="category-header">
          <div>
            <h2>{_safe(category.get("title"), _DEFAULT_TITLES.get(key, key))}</h2>
            <p>{_safe(category.get("summary"))}</p>
          </div>
          <div class="score-badge"><span class="score-dot">●</span><b>{score}</b><em>/10</em></div>
        </header>
        <div class="category-divider"></div>
        <div class="category-layout">
          <div class="category-copy">
            <div class="category-meaning">
              <div class="block-title">Главный смысл</div>
              <p>{_safe(main_takeaway)}</p>
            </div>
            <div class="category-columns">
              <div><div class="block-title">Что усиливается</div><ul>{_list_items(category.get("amplified"))}</ul></div>
              <div><div class="block-title">Риски</div><ul>{_list_items(category.get("risks"))}</ul></div>
            </div>
            <div class="category-actions"><div class="block-title">Что делать</div><ul>{_list_items(category.get("actions"))}</ul></div>
            <div class="astro-basis">
              <div class="block-title">Астрологическое основание</div>
              <p>{_safe(" · ".join(str(item) for item in (category.get("astro_basis") or [])))}</p>
            </div>
          </div>
          {_category_visual(key, score, category)}
        </div>
      </div>
    </section>
    """


def _category_takeaway(category: dict) -> str:
    value = category.get("main_takeaway")
    summary = category.get("summary")
    if value and value != summary:
        return str(value)

    amplified = _first_item(category.get("amplified"))
    risk = _first_item(category.get("risks"))
    action = _first_item(category.get("actions"))
    pieces = []
    if amplified:
        pieces.append(f"Главный ресурс здесь - {amplified.rstrip('.')}.")
    if risk:
        pieces.append(f"Зона внимания - {risk.rstrip('.')}.")
    if action:
        pieces.append(f"Опора года - {action.rstrip('.')}.")
    if pieces:
        return " ".join(pieces)
    return summary or "Эта сфера показывает, где важно соединить активность, честность с собой и конкретное действие."


def _category_visual(key: str, score: int, category: dict | None = None) -> str:
    category = category or {}
    if key == "inner":
        return _inner_core(score, category)
    if key == "relationships":
        return _relationship_axis(_score(category.get("balance_score"), score))
    if key == "sex":
        return _intimacy_pulse(category.get("energy_percent", score * 10), category)
    return {
        "career": _career_ladder,
        "money": _money_ring,
        "home": _foundation,
        "health": _battery,
        "communication": _communication_bars,
    }.get(key, _career_ladder)(score)


def _first_item(items) -> str:
    if isinstance(items, list) and items:
        return str(items[0])
    return ""


def _career_ladder(score: int) -> str:
    score = max(1, min(10, score))
    rows = []
    for level in range(10, 0, -1):
        active = level <= score
        rung_alpha = min(.98, .22 + level * .045 + score * .03) if active else .055
        classes = "ladder-row"
        rung_style = ""
        if active:
            classes += " active"
            gradient = _gradient_png_data_uri("#e9c36d", "#b9650d", round(rung_alpha * 255))
            rung_style = (
                f"background-color:#24243d;background-image:url('{gradient}');"
                "background-size:100% 100%;background-repeat:no-repeat;"
            )
        rows.append(
            f'<div class="{classes}" style="--rung-alpha:{rung_alpha:.2f};">'
            f'<i>{level}</i><span style="{rung_style}"></span></div>'
        )

    if score <= 2:
        stage = "подготовка"
        summary = "Роста почти нет. Год про наведение порядка, обучение и накопление опыта - не про повышение."
    elif score <= 4:
        stage = "набор темпа"
        summary = "Первые возможности уже появляются, но карьерный рост требует инициативы, ясной позиции и терпения."
    elif score <= 6:
        stage = "середина пути"
        summary = "Движение есть, но рывками. Работают только те шаги, где вы сами инициируете разговор о позиции."
    elif score <= 8:
        stage = "уверенный подъём"
        summary = "Ступени идут одна за другой: новые задачи, видимость, предложения. Важно не распыляться."
    else:
        stage = "пик"
        summary = "Максимум лестницы: смена уровня, публичность, статус. Год, когда просить и заявлять - обязательно."

    bars = "".join(rows)
    return f"""
    <div class="visual-card career-ladder-card score-{score}">
      <div class="visual-title">карьерная лестница</div>
      <div class="ladder">{bars}</div>
      <div class="ladder-insight">
        <b>{score} / 10 - {stage}</b>
        <p>{summary}</p>
      </div>
    </div>
    """


def _money_ring(score: int) -> str:
    score = max(1, min(10, score))
    values = {
        "income": score,
        "selfworth": max(1, score - 1),
        "control": max(1, score - 2),
        "strategy": score,
    }

    def sector(value: int, start: float, end: float, color: str) -> str:
        cx, cy, inner = 130.0, 112.0, 39.0
        outer = 44.0 + value * 4.8

        def point(radius: float, angle: float) -> tuple[float, float]:
            radians = math.radians(angle)
            return cx + radius * math.cos(radians), cy + radius * math.sin(radians)

        outer_start = point(outer, start)
        outer_end = point(outer, end)
        inner_end = point(inner, end)
        inner_start = point(inner, start)
        path = (
            f"M {outer_start[0]:.2f},{outer_start[1]:.2f} "
            f"A {outer:.2f},{outer:.2f} 0 0 1 {outer_end[0]:.2f},{outer_end[1]:.2f} "
            f"L {inner_end[0]:.2f},{inner_end[1]:.2f} "
            f"A {inner:.2f},{inner:.2f} 0 0 0 {inner_start[0]:.2f},{inner_start[1]:.2f} Z"
        )
        middle = (start + end) / 2
        text_radius = (inner + outer) / 2
        tx, ty = point(text_radius, middle)
        return f'<path d="{path}" fill="{color}"/><text class="sector-value" x="{tx:.2f}" y="{ty + 3:.2f}" text-anchor="middle">{value}</text>'

    sectors = "".join([
        sector(values["income"], -88, -2, "#bf9342"),
        sector(values["selfworth"], 2, 88, "#96723d"),
        sector(values["control"], 92, 178, "#68398d"),
        sector(values["strategy"], 182, 268, "#7941a1"),
    ])

    if score <= 2:
        stage = "режим экономии"
        summary = "Все секторы короткие: доход не растёт, самооценка проседает. Задача - перестать терять."
    elif score <= 4:
        stage = "пересборка"
        summary = "Ресурс начинает собираться, но стратегия ещё важнее скорости. Нужны учёт и ясные правила трат."
    elif score <= 6:
        stage = "нестабильно"
        summary = "Доходы средние, контроль слабый. Деньги приходят, но утекают: нужен учёт и понятные правила трат."
    elif score <= 8:
        stage = "рост ресурса"
        summary = "Доход и стратегия усиливаются. Важно удерживать темп, укреплять самооценку и не распылять ресурс."
    else:
        stage = "ресурсный пик"
        summary = "Сильный финансовый год: доход, стратегия и ценность поддерживают рост. Контроль закрепляет результат."

    return f"""
    <div class="visual-card resource-card score-{score}">
      <div class="visual-title">ресурсная карта</div>
      <svg class="resource-donut" viewBox="0 0 260 230">
        <circle class="resource-limit" cx="130" cy="112" r="96" />
        {sectors}
        <circle class="donut-hole" cx="130" cy="112" r="36" />
        <text class="donut-label" x="130" y="107" text-anchor="middle">ДЕНЬГИ</text>
        <text class="donut-score" x="130" y="126" text-anchor="middle">{score}/10</text>
        <text x="209" y="48">Доходы</text><text x="204" y="190">Самооценка</text>
        <text x="22" y="190">Контроль</text><text x="18" y="48">Стратегия</text>
      </svg>
      <p class="resource-rule">Чем длиннее сектор - тем сильнее в этом году работает эта опора денег.</p>
      <div class="resource-insight"><b>{score} / 10 - {stage}</b><p>{summary}</p></div>
    </div>
    """


def _relationship_axis(score: int) -> str:
    score = max(1, min(10, score))
    position = 8 + ((score - 1) / 9) * 84
    return f"""
    <div class="visual-card axis-card" data-balance-score="{score}">
      <div class="axis">
        <div class="axis-title">близость ↔ свобода</div>
        <div class="axis-line" style="--pos:{position}%"><span></span></div>
        <div class="axis-labels"><span>близость</span><span>свобода</span></div>
        <p>Баланс близости и личного пространства</p>
      </div>
    </div>
    """


def _foundation(score: int) -> str:
    score = max(1, min(10, score))
    levels = [
        ("Крыша · внешний быт", max(0, score - 2)),
        ("Стены · семейные роли", max(0, score - 1)),
        ("Пол · корни, родители", score),
        ("Фундамент · база", min(10, score + 1)),
    ]

    def state(value: int) -> str:
        if value <= 2:
            return "пусто"
        if value <= 5:
            return "шатко"
        if value <= 8:
            return "крепнет"
        return "опора"

    rows = []
    for index, (label, value) in enumerate(levels):
        y = 83 + index * 39
        rows.append(
            f"""
            <g class="foundation-level" data-value="{value}" data-state="{state(value)}">
              <rect class="foundation-track" x="42" y="{y}" width="190" height="31" />
              <rect class="foundation-fill" x="42" y="{y}" width="{value * 19}" height="31" fill-opacity="{value / 10:.1f}" />
              <text class="foundation-label" x="52" y="{y + 20}">{_safe(label)}</text>
              <text class="foundation-state" x="242" y="{y + 20}">{state(value)}</text>
            </g>
            """
        )

    if score <= 2:
        stage = "пусто"
        summary = "Почти все уровни пустые: тема дома в этом году заморожена. Не время для переездов и ремонтов."
    elif score <= 4:
        stage = "формируется"
        summary = "Основание только собирается: сначала нужны ясные правила быта, спокойные разговоры и порядок в обязательствах."
    elif score <= 6:
        stage = "шатко"
        summary = "Фундамент держит, но стены и крыша слабые: договорённости в семье размыты, быт требует внимания."
    elif score <= 8:
        stage = "крепнет"
        summary = "Дом становится устойчивее: роли и правила уже складываются, но внешнему быту ещё нужна последовательная забота."
    else:
        stage = "опора"
        summary = "Все уровни собраны: дом, близкие и привычный уклад становятся надёжной опорой для остальных задач года."

    return f"""
    <div class="visual-card foundation-card" data-foundation-score="{score}">
      <div class="visual-title">дом с уровнями</div>
      <svg class="foundation-shape" viewBox="0 0 320 250" role="img" aria-label="Устойчивость уровней дома">
        <polygon class="foundation-roof" points="137,15 42,75 232,75" />
        {''.join(rows)}
      </svg>
      <p class="foundation-rule">Чем больше залит уровень - тем устойчивее эта часть темы дома в этом году.</p>
      <div class="foundation-insight"><b>{score} / 10 - {stage}</b><p>{summary}</p></div>
    </div>
    """


def _battery(score: int) -> str:
    score = max(1, min(10, score))
    percent = score * 10
    return f"""
    <div class="visual-card battery-card" data-energy-score="{score}">
      <div class="visual-title">батарея энергии</div>
      <div class="battery" style="--fill:{percent}%;--fill-opacity:{score / 10:.1f}">
        <span></span>
        <b class="battery-value battery-value-light">{percent}%</b>
        <b class="battery-value battery-value-dark">{percent}%</b>
      </div>
      <div class="visual-caption"><span>усталость</span><span>восстановление</span></div>
    </div>
    """


def _communication_bars(score: int) -> str:
    score = max(1, min(10, score))
    rows = [
        ("Обучение", min(100, score * 10 + 15)),
        ("Тексты и публикации", min(100, score * 10 + 5)),
        ("Встречи и звонки", max(10, score * 10 - 5)),
        ("Короткие поездки", max(10, score * 10 - 25)),
    ]
    content = "".join(
        f"""
        <div class="bar-row">
          <div><b>{_safe(label)}</b><em>{value}%</em></div>
          <span><i style="--fill:{value}%"></i></span>
        </div>
        """
        for label, value in rows
    )
    return f"""
    <div class="visual-card communication-card" data-communication-score="{score}">
      <div class="visual-title">каналы общения</div>
      <div class="bar-list">{content}</div>
      <p class="communication-rule">Куда в этом году больше всего идёт информации и разговоров.</p>
    </div>
    """


def _inner_keywords(category: dict) -> list[str]:
    keywords = category.get("keywords")
    if not isinstance(keywords, list):
        keywords = []
    words = [str(word).strip() for word in keywords if str(word).strip()]
    fallback = ["глубина", "тишина", "сила"]
    return (words + fallback)[:3]


def _inner_core(score: int, category: dict) -> str:
    words = _inner_keywords(category)
    word_markup = "".join(
        f"<span>{_safe(word)}</span>{'<em>·</em>' if index < len(words) - 1 else ''}"
        for index, word in enumerate(words)
    )
    return f"""
    <div class="visual-card">
      <div class="visual-title">внутреннее ядро</div>
      <div class="core">
        <svg viewBox="0 0 220 220">
          <circle cx="110" cy="110" r="82" fill="none" stroke="rgba(214,181,109,.22)"/>
          <circle cx="110" cy="110" r="62" fill="none" stroke="rgba(214,181,109,.18)" stroke-dasharray="4 6"/>
          <circle cx="110" cy="110" r="43" fill="none" stroke="rgba(214,181,109,.22)"/>
          <circle cx="110" cy="110" r="25" fill="none" stroke="rgba(214,181,109,.24)"/>
        </svg>
        <b>{score}</b>
      </div>
      <div class="core-words">{word_markup}</div>
    </div>
    """


def _intimacy_pulse(energy_percent: int, category: dict | None = None) -> str:
    category = category or {}
    try:
        percent = int(round(float(energy_percent)))
    except (TypeError, ValueError):
        percent = 50
    percent = max(1, min(100, percent))
    ratio = max(0, min(1, (percent - 20) / 75))
    radius = 34 + ratio * 12
    center_distance = 130 - ratio * 65
    left_center = 130 - center_distance / 2
    right_center = 130 + center_distance / 2
    connector_start = left_center + radius
    connector_end = right_center - radius
    connector_mid = (connector_start + connector_end) / 2
    connector_span = connector_end - connector_start
    control = connector_span * .22
    keywords = _inner_keywords(category)
    keyword_markup = "<em>·</em>".join(f"<span>{_safe(word)}</span>" for word in keywords)

    if percent <= 25:
        state = "тема спит"
        summary = "Минимальная активация. Фокус - восстановление, безопасность и контакт с собой."
    elif percent <= 65:
        state = "умеренная активация"
        summary = "Желание есть, но присутствует сопротивление. Важно проговаривать границы и не торопить интимность."
    elif percent <= 85:
        state = "сильная активация"
        summary = "Год переформатирует сценарии близости. Честность с желаниями становится главным ресурсом."
    else:
        state = "максимальное напряжение"
        summary = "Интимность становится мощным триггером. Осознанность важнее импульса и интенсивности переживаний."

    return f"""
    <div class="visual-card intimacy-card" data-energy-percent="{percent}">
      <div class="visual-title">пульс интимности</div>
      <div class="intimacy-pulse">
        <svg class="intimacy-graphic" viewBox="0 20 260 110" role="img" aria-label="Пульс интимности {percent}%">
          <defs><filter id="intimacy-halo"><feGaussianBlur stdDeviation="7" /></filter></defs>
          <circle class="intimacy-halo intimacy-halo-gold" cx="{left_center:.1f}" cy="75" r="{radius + 5:.1f}" />
          <circle class="intimacy-halo intimacy-halo-violet" cx="{right_center:.1f}" cy="75" r="{radius + 5:.1f}" />
          <circle class="intimacy-circle intimacy-circle-gold" cx="{left_center:.1f}" cy="75" r="{radius:.1f}" />
          <circle class="intimacy-circle intimacy-circle-violet" cx="{right_center:.1f}" cy="75" r="{radius:.1f}" />
          <path class="intimacy-connector" d="M {connector_start:.1f} 75 C {connector_start + control:.1f} 75, {connector_start + control:.1f} 58, {connector_mid:.1f} 58 S {connector_end - control:.1f} 92, {connector_end:.1f} 75" />
        </svg>
      </div>
      <div class="core-words intimacy-keywords">{keyword_markup}</div>
      <div class="intimacy-insight"><b>{percent}% · {state}</b><p>{summary}</p></div>
    </div>
    """


def _risk_rows(items) -> str:
    if not isinstance(items, list) or not items:
        items = [{"title": "Зона внимания", "level": 7, "risk": "Не перегружать слабые места года.", "support": "Действовать постепенно."}]
    return "".join(
        f"""
        <article class="risk-card" style="--level:{_score(item.get("level")) * 10}%">
          <small>Осторожно</small>
          <h3>{_safe(item.get("title"))}</h3>
          <span>{_safe(item.get("risk"))}</span>
        </article>
        """
        for item in items[:5]
    )


def _opportunity_cards(items) -> str:
    if not isinstance(items, list) or not items:
        items = [{"title": "Главная возможность", "text": "Вложиться в самые активные сферы года и зафиксировать результат."}]
    return "".join(
        f"<article class=\"op-card\"><small>Возможность</small><h3>{_safe(item.get('title'))}</h3><p>{_safe(item.get('text'))}</p></article>"
        for item in items[:5]
    )


def _plan_steps(items, report: dict) -> str:
    rows = []
    if isinstance(items, list) and any(isinstance(item, dict) and (item.get("title") or item.get("sphere")) for item in items):
        rows = [
            (item.get("title") or item.get("sphere"), item.get("action"))
            for item in items
            if isinstance(item, dict) and (item.get("title") or item.get("sphere")) and item.get("action")
        ]
    if not rows:
        plan_order = ["money", "career", "health", "relationships", "home", "communication", "inner", "sex"]
        for key in plan_order:
            category = _category_by_key(report, key)
            action = _first_item(category.get("actions"))
            if action:
                rows.append((category.get("title") or _DEFAULT_TITLES.get(key, key), action))
    if not rows:
        rows = [("Главный фокус", "Выбрать главный фокус года и держать его в приоритете.")]
    return "".join(
        f'<div class="plan-step"><b>{_safe(title)}</b><span>{_safe(action)}</span></div>'
        for title, action in rows[:8]
    )
