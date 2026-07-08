"""Fillable HTML template for structured synastry reports."""

from __future__ import annotations

import math
from pathlib import Path
import xml.sax.saxutils as saxutils


_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_HTML_TEMPLATE = _TEMPLATE_DIR / "synastry_report.html"
_CSS_TEMPLATE = _TEMPLATE_DIR / "synastry_report.css"


def render_synastry_html(report: dict) -> str:
    cover = report.get("cover") or {}
    formula = report.get("formula") or {}
    emotions = report.get("emotions") or {}
    chemistry = report.get("chemistry") or {}
    love = report.get("love_languages") or {}
    communication = report.get("communication") or {}
    longterm = report.get("longterm") or {}
    influence = report.get("influence") or {}
    final = report.get("final") or {}
    first_love = love.get("first") or {}
    partner_love = love.get("partner") or {}
    first_influence = influence.get("first_to_partner") or {}
    partner_influence = influence.get("partner_to_first") or {}
    cards = _synastry_map_cards(report)
    overall = _score(cover.get("overall_score"), _average_score(cards))
    chemistry_score = _score(chemistry.get("score"), 8)
    longterm_score = _score(longterm.get("score"), 8)

    values = {
        "SYNASTRY_REPORT_CSS": _read_text(_CSS_TEMPLATE),
        "COVER_TITLE": _safe(cover.get("title"), "Синастрия"),
        "COVER_SUBTITLE": _safe(cover.get("subtitle"), "Разбор совместимости по ключевым сферам отношений."),
        "CONNECTION_TYPE": _safe(cover.get("connection_type")),
        "MAIN_RESOURCE": _safe(cover.get("main_resource")),
        "MAIN_RISK": _safe(cover.get("main_risk")),
        "OVERALL_SCORE": str(overall),
        "SCORE_WORDS": _word_chips(cover.get("score_words")),
        "COVER_METRICS": _cover_metrics(cards),
        "MAP_ROWS": _map_rows(cards),
        "RADAR_SVG": _radar_svg(cards),
        "FORMULA_TITLE": _safe(formula.get("title"), "Формула пары"),
        "FORMULA_PHRASE": _safe(formula.get("phrase")),
        "FORMULA_TEXT": _safe(formula.get("text")),
        "FORMULA_BARS": _value_bars(formula.get("indicators"), 5),
        "EMOTION_SCALES": _emotion_scales(emotions.get("scales")),
        "EMOTIONS_SUMMARY": _safe(emotions.get("summary")),
        "EMOTIONS_SUPPORT": _list_items(emotions.get("support"), 3),
        "EMOTIONS_MISMATCH": _list_items(emotions.get("mismatch"), 3),
        "CHEMISTRY_SCORE": str(chemistry_score),
        "CHEMISTRY_FILL": str(chemistry_score * 10),
        "CHEMISTRY_LABEL": _safe(chemistry.get("label"), "Притяжение"),
        "CHEMISTRY_SUMMARY": _safe(chemistry.get("summary")),
        "CHEMISTRY_AMPLIFIES": _list_items(chemistry.get("amplifies"), 3),
        "CHEMISTRY_DIMS": _list_items(chemistry.get("dims"), 3),
        "CHEMISTRY_PARAMETERS": _value_bars(chemistry.get("parameters"), 4),
        "FIRST_LOVE_NAME": _safe(first_love.get("name"), "Первый партнёр"),
        "FIRST_LOVE_ITEMS": _love_items(first_love.get("items")),
        "PARTNER_LOVE_NAME": _safe(partner_love.get("name"), "Партнёр"),
        "PARTNER_LOVE_ITEMS": _love_items(partner_love.get("items")),
        "LOVE_BRIDGE": _safe(love.get("bridge"), "переводить ожидания в слова"),
        "LOVE_SUMMARY": _safe(love.get("summary")),
        "COMMUNICATION_SUMMARY": _safe(communication.get("summary")),
        "TRANSLATOR_ROWS": _translator_rows(communication.get("rows")),
        "TRIGGER_CARDS": _trigger_cards(report.get("triggers")),
        "LONGTERM_SCORE": str(longterm_score),
        "LONGTERM_SUMMARY": _safe(longterm.get("summary")),
        "LONGTERM_PILLARS": _pillars(longterm.get("pillars")),
        "LONGTERM_WEAK_SPOT": _safe(longterm.get("weak_spot")),
        "FIRST_INFLUENCE_TITLE": _safe(first_influence.get("title")),
        "FIRST_INFLUENCE_ITEMS": _list_items(first_influence.get("items"), 4),
        "PARTNER_INFLUENCE_TITLE": _safe(partner_influence.get("title")),
        "PARTNER_INFLUENCE_ITEMS": _list_items(partner_influence.get("items"), 4),
        "RESOURCE_CARDS": _resource_cards(report.get("resources")),
        "RISK_CARDS": _risk_cards(report.get("risks")),
        "RECOMMENDATIONS": _recommendations(report.get("recommendations")),
        "FINAL_TITLE": _safe(final.get("title"), "Итоговая формула"),
        "FINAL_TEXT": _safe(final.get("text")),
        "FINAL_KEEPS": _safe(final.get("keeps")),
        "FINAL_BREAKS": _safe(final.get("breaks")),
        "FINAL_GROWTH": _safe(final.get("growth")),
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


def _synastry_map_cards(report: dict) -> list[dict]:
    defaults = [
        ("emotions", "Эмоции", 8),
        ("chemistry", "Химия", 8),
        ("communication", "Коммуникация", 6),
        ("sex", "Секс", 8),
        ("longterm", "Долгосрочность", 7),
        ("home", "Быт", 6),
        ("risks", "Риски", 6),
    ]
    source = report.get("relationship_map") or []
    cards = []
    for key, title, score in defaults:
        item = next((row for row in source if row.get("key") == key), {})
        cards.append(
            {
                "key": key,
                "title": item.get("title") or title,
                "score": _score(item.get("score"), score),
                "note": item.get("meaning") or "",
            }
        )
    return cards


def _word_chips(items) -> str:
    if not isinstance(items, list):
        return ""
    return "".join(f"<span>{_safe(item)}</span>" for item in items[:3])


def _cover_metrics(cards: list[dict]) -> str:
    priority = ["chemistry", "emotions", "communication", "longterm"]
    selected = []
    for key in priority:
        card = next((item for item in cards if item.get("key") == key), None)
        if card:
            selected.append(card)
    if len(selected) < 4:
        selected.extend(cards[: 4 - len(selected)])
    return "".join(
        f"""
        <article>
          <span>{_safe(card.get("title"))}</span>
          <b>{_score(card.get("score"))}/10</b>
        </article>
        """
        for card in selected[:4]
    )


def _map_rows(cards: list[dict]) -> str:
    return "".join(
        f"""
        <div class="score-row">
          <span>{_safe(card.get("title"))}</span>
          <b>{_score(card.get("score"))}</b>
        </div>
        """
        for card in cards
    )


def _radar_svg(cards: list[dict]) -> str:
    size = 220
    center = size / 2
    radius = 72
    levels = []
    for level in range(1, 5):
        r = radius * level / 4
        points = _radar_points(len(cards), r, center)
        levels.append(f'<polygon points="{points}" />')
    spokes = []
    labels = []
    values = []
    for index, card in enumerate(cards):
        angle = -math.pi / 2 + 2 * math.pi * index / len(cards)
        outer_x = center + math.cos(angle) * radius
        outer_y = center + math.sin(angle) * radius
        spokes.append(f'<line x1="{center}" y1="{center}" x2="{outer_x:.2f}" y2="{outer_y:.2f}" />')

        value_r = radius * _score(card.get("score")) / 10
        values.append(f"{center + math.cos(angle) * value_r:.2f},{center + math.sin(angle) * value_r:.2f}")

        label_r = radius + 23
        label_x = center + math.cos(angle) * label_r
        label_y = center + math.sin(angle) * label_r
        anchor = "middle"
        if math.cos(angle) > .35:
            anchor = "end"
        elif math.cos(angle) < -.35:
            anchor = "start"
        labels.append(
            f"""
            <text x="{label_x:.2f}" y="{label_y:.2f}" text-anchor="{anchor}" dominant-baseline="middle">
              {_safe(_radar_label(card.get("title")))}
            </text>
            """
        )
    value_points = " ".join(values)
    dots = "".join(
        f'<circle cx="{point.split(",")[0]}" cy="{point.split(",")[1]}" r="4.2" />'
        for point in values
    )
    return f"""
    <svg class="radar-svg" viewBox="0 0 {size} {size}">
      <g class="radar-grid">{"".join(levels)}{"".join(spokes)}</g>
      <polygon class="radar-area" points="{value_points}" />
      <polyline class="radar-line" points="{value_points} {values[0]}" />
      <g class="radar-dots">{dots}</g>
      <g class="radar-labels">{"".join(labels)}</g>
    </svg>
    """


def _radar_points(count: int, radius: float, center: float) -> str:
    return " ".join(
        f"{center + math.cos(-math.pi / 2 + 2 * math.pi * index / count) * radius:.2f},"
        f"{center + math.sin(-math.pi / 2 + 2 * math.pi * index / count) * radius:.2f}"
        for index in range(count)
    )


def _radar_label(title) -> str:
    mapping = {
        "Коммуникация": "Общение",
        "Долгосрочность": "Долгосрочн.",
    }
    text = str(title or "")
    return mapping.get(text, text)


def _value_bars(items, limit: int) -> str:
    if not isinstance(items, list):
        return ""
    return "".join(
        f"""
        <div class="syn-value">
          <div><span>{_safe(item.get("label"))}</span><b>{_score(item.get("value"))}/10</b></div>
          <i><em style="--fill:{_score(item.get("value")) * 10}%"></em></i>
        </div>
        """
        for item in items[:limit]
        if isinstance(item, dict)
    )


def _emotion_scales(items) -> str:
    if not isinstance(items, list):
        return ""
    return "".join(
        f"""
        <div class="emotion-col {'tension' if item.get("tone") == "tension" else ''}">
          <b>{_score(item.get("value"))}</b>
          <i><em style="--fill:{_score(item.get("value")) * 10}%"></em></i>
          <span>{_safe(item.get("label"))}</span>
        </div>
        """
        for item in items[:5]
        if isinstance(item, dict)
    )


def _list_items(items, limit: int = 4) -> str:
    if not isinstance(items, list):
        return ""
    return "".join(f"<li>{_safe(item)}</li>" for item in items[:limit])


def _love_items(items) -> str:
    if not isinstance(items, list):
        return ""
    return "".join(f"<span>{_safe(item)}</span>" for item in items[:4])


def _translator_rows(items) -> str:
    if not isinstance(items, list):
        return ""
    return "".join(
        f"""
        <div class="translator-row">
          <b>{_safe(item.get("from"))}</b>
          <i></i>
          <span>{_safe(item.get("to"))}</span>
        </div>
        """
        for item in items[:4]
        if isinstance(item, dict)
    )


def _trigger_cards(items) -> str:
    if not isinstance(items, list):
        return ""
    cards = []
    for item in items[:5]:
        if not isinstance(item, dict):
            continue
        level = min(_score(item.get("level"), 3), 5)
        dots = "".join("<i></i>" for _ in range(level))
        cards.append(
            f"""
            <article class="trigger-card">
              <header><h3>{_safe(item.get("title"))}</h3><span>{dots}</span></header>
              <p>{_safe(item.get("manifestation"))}</p>
              <strong>{_safe(item.get("action"))}</strong>
            </article>
            """
        )
    return "".join(cards)


def _pillars(items) -> str:
    if not isinstance(items, list):
        return ""
    return "".join(
        f"""
        <div class="pillar">
          <span>{_safe(item.get("label"))}</span>
          <b>{_score(item.get("value"))}</b>
        </div>
        """
        for item in items[:4]
        if isinstance(item, dict)
    )


def _resource_cards(items) -> str:
    if not isinstance(items, list):
        return ""
    return "".join(
        f"""
        <article class="resource-card">
          <h3>{_safe(item.get("title"))}</h3>
          <p>{_safe(item.get("text"))}</p>
        </article>
        """
        for item in items[:6]
        if isinstance(item, dict)
    )


def _risk_cards(items) -> str:
    if not isinstance(items, list):
        return ""
    return "".join(
        f"""
        <article class="risk-card" style="--level:{_risk_level(item.get("level")) * 10}%">
          <h3>{_safe(item.get("title"))}</h3>
          <small>{_safe(item.get("level"))}</small>
          <p>{_safe(item.get("text"))}</p>
        </article>
        """
        for item in items[:6]
        if isinstance(item, dict)
    )


def _risk_level(level) -> int:
    text = str(level or "").lower()
    if "выс" in text:
        return 9
    if "сред" in text:
        return 6
    if "низ" in text:
        return 3
    return _score(level, 5)


def _recommendations(items) -> str:
    if not isinstance(items, list):
        return ""
    return "".join(
        f"""
        <div class="rec-row">
          <b>{index}</b>
          <div><h3>{_safe(item.get("situation"))}</h3><p>{_safe(item.get("action"))}</p></div>
        </div>
        """
        for index, item in enumerate(items[:5], 1)
        if isinstance(item, dict)
    )
