"""Fillable Lovable-style HTML template for structured solar reports."""

from __future__ import annotations

import base64
import math
from pathlib import Path
import xml.sax.saxutils as saxutils


_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_HTML_TEMPLATE = _TEMPLATE_DIR / "solar_report.html"
_CSS_TEMPLATE = _TEMPLATE_DIR / "solar_report.css"
_CHART_WHEEL = _ROOT / "assets" / "chart-wheel.jpg"

_DEFAULT_TITLES = {
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


def render_solar_html(report: dict) -> str:
    """Render a complete HTML document from normalized solar JSON."""
    cover = report.get("cover") or {}
    theme = report.get("main_theme") or {}
    cards = _sphere_cards(report)

    values = {
        "SOLAR_REPORT_CSS": _read_text(_CSS_TEMPLATE),
        "COVER_TITLE": _safe(cover.get("title"), "Соляр"),
        "COVER_SUBTITLE": _safe(cover.get("subtitle"), "Персональный прогноз по сферам жизни"),
        "COVER_PERIOD": _safe(cover.get("period")),
        "COVER_PLACE": _safe(cover.get("place")),
        "COVER_SCORE": str(_score(cover.get("overall_score"), _average_score(cards))),
        "COVER_TOP": _safe(cover.get("top_sphere")),
        "COVER_ART": _cover_art(),
        "SPHERE_ROWS": _sphere_rows(cards),
        "RADAR_SVG": _radar_svg(cards),
        "MAP_SUMMARY": _safe(
            report.get("map_summary"),
            "Карта сфер показывает, где год даёт максимум движения, а где важнее действовать спокойнее. Самые высокие баллы формируют главный ресурс периода, низкие - зоны внимания и бережной настройки.",
        ),
        "THEME_TITLE": _safe(theme.get("title"), "Главная тема года"),
        "THEME_TEXT": _safe(theme.get("text")),
        "THEME_PILLS": _pill_list(theme.get("accents")),
        "ADDITIONAL_ACCENTS": _additional_accents(theme),
        "CATEGORY_PAGES": _category_pages(report),
        "RISK_ROWS": _risk_rows(report.get("risk_summary")),
        "OPPORTUNITY_CARDS": _opportunity_cards(report.get("opportunities")),
        "PLAN_STEPS": _plan_steps(report.get("plan")),
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


def _score(value, fallback: int = 5) -> int:
    try:
        result = int(round(float(value)))
    except (TypeError, ValueError):
        result = fallback
    return max(1, min(10, result))


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
          <span>{_safe(card.get("title"))}<small>{_safe(card.get("meaning"))}</small></span>
          <b>{_score(card.get("score"))}</b>
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
        intensity = max(0, min(100, score * 10))
        cards.append(
            f"""
            <article class="heatmap-card" style="--heat:{intensity}%">
              <h3>{_safe(title)}</h3>
              <strong>{score}<span>/10</span></strong>
            </article>
            """
        )

    return "".join(cards)


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
        label_x = center + math.cos(angle) * (radius + 30)
        label_y = center + math.sin(angle) * (radius + 30)
        anchor = "middle"
        if math.cos(angle) > .25:
            anchor = "start"
        elif math.cos(angle) < -.25:
            anchor = "end"
        axis.append(f'<line x1="{center:.2f}" y1="{center:.2f}" x2="{outer_x:.2f}" y2="{outer_y:.2f}" />')
        dots.append(f'<circle cx="{point_x:.2f}" cy="{point_y:.2f}" r="4" />')
        labels.append(
            f"""
            <text class="radar-label-title" x="{label_x:.2f}" y="{label_y - 5:.2f}" text-anchor="{anchor}" dominant-baseline="middle">{_safe(card.get("title"))}</text>
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


def _list_items(items, limit: int = 4) -> str:
    if not isinstance(items, list):
        return ""
    return "".join(f"<li>{_safe(item)}</li>" for item in items[:limit])


def _category_pages(report: dict) -> str:
    return "".join(_category_page(_category_by_key(report, key), key) for key in _CATEGORY_ORDER)


def _category_page(category: dict, key: str) -> str:
    score = _score(category.get("score"))
    return f"""
    <section class="page category-page">
      <div class="category-shell">
        <div class="section-head category-section-head">
          <span>03</span>
          <b>Категория</b>
        </div>
        <header class="category-header">
          <div>
            <h2>{_safe(category.get("title"), _DEFAULT_TITLES.get(key, key))}</h2>
            <p>{_safe(category.get("summary"))}</p>
          </div>
          <div class="score-badge"><span class="score-dot">●</span><b>{score}</b><em>/10</em></div>
        </header>
        <div class="category-divider"></div>
        <div class="category-layout">
          <div>
            <div class="category-columns">
              <div><div class="block-title">Что усиливается</div><ul>{_list_items(category.get("amplified"), 4)}</ul></div>
              <div><div class="block-title">Возможные события</div><ul>{_list_items(category.get("manifestations"), 4)}</ul></div>
              <div><div class="block-title">Риски</div><ul>{_list_items(category.get("risks"), 3)}</ul></div>
              <div><div class="block-title">Что делать</div><ul>{_list_items(category.get("actions"), 4)}</ul></div>
            </div>
            <div class="astro-basis">
              <div class="block-title">Астрологическое основание</div>
              <p>{_safe(" · ".join(str(item) for item in (category.get("astro_basis") or [])[:4]))}</p>
            </div>
          </div>
          {_category_visual(key, score, category)}
        </div>
        <div class="category-focus">
          <article>
            <div class="block-title">Главный вывод</div>
            <p>{_safe(category.get("summary"))}</p>
          </article>
          <article>
            <div class="block-title">Практическая опора</div>
            <p>{_safe(_first_item(category.get("actions")), "Держать фокус на конкретном действии, а не на тревожном ожидании.")}</p>
          </article>
        </div>
      </div>
    </section>
    """


def _category_visual(key: str, score: int, category: dict | None = None) -> str:
    if key == "inner":
        return _inner_core(score, category or {})
    return {
        "career": _career_ladder,
        "money": _money_ring,
        "relationships": _relationship_axis,
        "home": _foundation,
        "health": _battery,
        "communication": _communication_bars,
        "sex": _intimacy_pulse,
    }.get(key, _career_ladder)(score)


def _first_item(items) -> str:
    if isinstance(items, list) and items:
        return str(items[0])
    return ""


def _career_ladder(score: int) -> str:
    bars = "".join(
        f"""
        <span class="{'active' if index < score else ''}"></span>
        """
        for index in range(10)
    )
    return f"""
    <div class="visual-card">
      <div class="visual-title">карьерная лестница</div>
      <div class="ladder-score"><b>{score}/10</b><span>{score * 10}% активации статуса</span></div>
      <div class="ladder">{bars}</div>
      <div class="visual-caption"><span>сейчас</span><span>пик года</span></div>
    </div>
    """


def _money_ring(score: int) -> str:
    percent = score * 10
    circumference = 2 * math.pi * 74
    dash = circumference * percent / 100
    gap = circumference - dash
    metrics = [
        ("Доходы", min(100, percent + 5)),
        ("Ценность", percent),
        ("Контроль", max(20, percent - 10)),
        ("Стратегия", min(100, percent + 10)),
    ]
    rows = "".join(
        f"<div><span>{_safe(label)}</span><b>{value}%</b></div>"
        for label, value in metrics
    )
    return f"""
    <div class="visual-card">
      <div class="visual-title">ресурсная карта</div>
      <div class="ring-wrap">
        <svg class="magic-ring" viewBox="0 0 200 200">
          <circle class="magic-ring-track" cx="100" cy="100" r="74" />
          <circle class="magic-ring-progress" cx="100" cy="100" r="74" pathLength="{circumference:.2f}" stroke-dasharray="{dash:.2f} {gap:.2f}" />
        </svg>
        <div class="ring-center"><b>{score}/10</b><span>ресурс</span></div>
      </div>
      <div class="resource-metrics">{rows}</div>
    </div>
    """


def _relationship_axis(score: int) -> str:
    position = max(16, min(84, score * 10))
    return f"""
    <div class="visual-card axis-card">
      <div class="axis">
        <div class="axis-title">близость ↔ свобода</div>
        <div class="axis-line" style="--pos:{position}%"><span></span></div>
        <div class="axis-labels"><span>близость</span><span>свобода</span></div>
        <p>Баланс близости и личного пространства</p>
      </div>
    </div>
    """


def _foundation(score: int) -> str:
    return f"""
    <div class="visual-card">
      <div class="visual-title">дом с уровнями</div>
      <svg class="foundation-shape" viewBox="0 0 240 210">
        <polygon points="120,18 36,82 204,82" fill="rgba(214,181,109,.18)" stroke="#d6b56d"/>
        <rect x="54" y="82" width="132" height="29" fill="rgba(122,92,255,.18)" stroke="rgba(214,181,109,.35)"/>
        <rect x="54" y="113" width="132" height="29" fill="rgba(122,92,255,.26)" stroke="rgba(214,181,109,.35)"/>
        <rect x="54" y="144" width="132" height="29" fill="rgba(122,92,255,.34)" stroke="rgba(214,181,109,.35)"/>
        <rect x="54" y="175" width="132" height="29" fill="rgba(214,181,109,.24)" stroke="rgba(214,181,109,.48)"/>
        <text x="120" y="101" text-anchor="middle" fill="#f5efdf" font-size="10">внешний быт</text>
        <text x="120" y="132" text-anchor="middle" fill="#f5efdf" font-size="10">семейные роли</text>
        <text x="120" y="163" text-anchor="middle" fill="#f5efdf" font-size="10">корни</text>
        <text x="120" y="194" text-anchor="middle" fill="#d6b56d" font-size="10">база · {score}/10</text>
      </svg>
    </div>
    """


def _battery(score: int) -> str:
    percent = score * 10
    return f"""
    <div class="visual-card">
      <div class="visual-title">батарея энергии</div>
      <div class="battery" style="--fill:{percent}%"><span></span><b>{percent}%</b></div>
      <div class="visual-caption"><span>усталость</span><span>восстановление</span></div>
    </div>
    """


def _communication_bars(score: int) -> str:
    rows = [
        ("Обучение", min(10, score + 1)),
        ("Тексты", score),
        ("Встречи", max(1, score - 1)),
        ("Поездки", max(1, score - 2)),
    ]
    content = "".join(
        f"""
        <div class="bar-row">
          <div><b>{_safe(label)}</b><em>{value * 10}%</em></div>
          <span><i style="--fill:{value * 10}%"></i></span>
        </div>
        """
        for label, value in rows
    )
    return f"""
    <div class="visual-card">
      <div class="visual-title">каналы общения</div>
      <div class="bar-list">{content}</div>
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


def _intimacy_pulse(score: int) -> str:
    percent = score * 10
    return f"""
    <div class="visual-card intimacy-card">
      <div class="visual-title">пульс интимности</div>
      <svg class="intimacy-pulse" viewBox="0 0 240 140">
        <defs>
          <linearGradient id="pulseGrad" x1="0" x2="1">
            <stop offset="0" stop-color="#d6b56d" />
            <stop offset="1" stop-color="#a75bdc" />
          </linearGradient>
        </defs>
        <circle cx="80" cy="70" r="34" fill="rgba(214,181,109,.18)" stroke="rgba(214,181,109,.62)" stroke-width="1.5" />
        <circle cx="160" cy="70" r="34" fill="rgba(122,92,255,.18)" stroke="rgba(167,91,220,.62)" stroke-width="1.5" />
        <path d="M 113 70 Q 120 48, 126 70 T 139 70" fill="none" stroke="url(#pulseGrad)" stroke-width="2" stroke-linecap="round" />
        <text x="120" y="126" text-anchor="middle">{percent}% энергии</text>
      </svg>
      <div class="core-words"><span>близость</span><em>·</em><span>желание</span><em>·</em><span>честность</span></div>
    </div>
    """


def _risk_rows(items) -> str:
    if not isinstance(items, list) or not items:
        items = [{"title": "Зона внимания", "level": 7, "risk": "Не перегружать слабые места года.", "support": "Действовать постепенно."}]
    return "".join(
        f"""
        <article class="risk-card" style="--level:{_score(item.get("level")) * 10}%">
          <b>{_safe(item.get("title"))}</b>
          <span>{_safe(item.get("risk"))}</span>
          <em>{_safe(item.get("support"))}</em>
        </article>
        """
        for item in items[:4]
    )


def _opportunity_cards(items) -> str:
    if not isinstance(items, list) or not items:
        items = [{"title": "Главная возможность", "text": "Вложиться в самые активные сферы года и зафиксировать результат."}]
    return "".join(
        f"<article class=\"op-card\"><h3>{_safe(item.get('title'))}</h3><p>{_safe(item.get('text'))}</p></article>"
        for item in items[:4]
    )


def _plan_steps(items) -> str:
    if not isinstance(items, list) or not items:
        items = [{"step": 1, "action": "Выбрать главный фокус года и держать его в приоритете."}]
    return "".join(
        f"<div class=\"plan-step\"><b>{_safe(item.get('step'), index + 1)}</b><span>{_safe(item.get('action'))}</span></div>"
        for index, item in enumerate(items[:5])
    )
