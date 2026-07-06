"""Lightweight report profiles for visual PDF summaries."""

from __future__ import annotations

from statistics import mean

PERSONAL_PLANETS = {"Солнце", "Луна", "Меркурий", "Венера", "Марс"}
BENEFIC_PLANETS = {"Венера", "Юпитер"}
TENSION_ASPECTS = {"Квадрат", "Оппозиция", "Квиконс"}
FLOW_ASPECTS = {"Соединение", "Секстиль", "Тригон"}
GOLD = "#d8ae55"
PURPLE = "#7c4fd6"


def _clamp_score(value: float) -> int:
    return max(1, min(10, round(value)))


def _score_label(score: int, high: str, mid: str, low: str) -> str:
    if score >= 8:
        return high
    if score >= 5:
        return mid
    return low


def _planet_house_counts(chart_data: dict) -> dict[str, float]:
    weights = {
        "Солнце": 3.0,
        "Луна": 2.5,
        "Асцендент": 2.5,
        "MC": 2.5,
        "Венера": 2.0,
        "Марс": 2.0,
        "Меркурий": 1.5,
        "Юпитер": 1.5,
        "Сатурн": 1.5,
    }
    counts: dict[str, float] = {}
    for row in (chart_data.get("planets") or [])[1:]:
        if len(row) < 3:
            continue
        planet, _, house = row[:3]
        counts[house] = counts.get(house, 0) + weights.get(planet, 1.0)
    return counts


def _aspect_intensity(chart_data: dict, planets: set[str] | None = None) -> float:
    total = 0.0
    for row in (chart_data.get("aspects") or [])[1:]:
        if len(row) < 4:
            continue
        first, aspect, second, orb_text = row[:4]
        if planets and first not in planets and second not in planets:
            continue
        try:
            orb = float(orb_text)
        except ValueError:
            continue
        weight = max(0.2, 1.2 - orb)
        if aspect in TENSION_ASPECTS:
            weight *= 1.2
        total += weight
    return total


def _solar_score(counts: dict[str, float], houses: list[str], bonus: float = 0) -> int:
    raw = sum(counts.get(house, 0) for house in houses) + bonus
    return _clamp_score(3 + raw * 1.15)


def build_solar_profile(chart_data: dict, person_name: str, cycle_year: int) -> dict:
    counts = _planet_house_counts(chart_data)
    tension = _aspect_intensity(chart_data)
    personal = _aspect_intensity(chart_data, PERSONAL_PLANETS)
    cards = [
        {
            "title": "Отношения",
            "score": _solar_score(counts, ["5", "7", "8"], personal * 0.45),
            "color": PURPLE,
            "note": "Любовь, союзы, близость и важные договорённости.",
        },
        {
            "title": "Карьера",
            "score": _solar_score(counts, ["6", "10"], counts.get("10", 0) * 0.5),
            "color": GOLD,
            "note": "Работа, статус, нагрузка и профессиональный вектор.",
        },
        {
            "title": "Деньги",
            "score": _solar_score(counts, ["2", "8"], counts.get("2", 0) * 0.35),
            "color": GOLD,
            "note": "Личные ресурсы, общие деньги и финансовая опора.",
        },
        {
            "title": "Дом и семья",
            "score": _solar_score(counts, ["4"], counts.get("4", 0) * 0.7),
            "color": PURPLE,
            "note": "Дом, семья, переезд, личная база и близкий круг.",
        },
        {
            "title": "Внутренний фон",
            "score": _solar_score(counts, ["8", "12"], tension * 0.5),
            "color": PURPLE,
            "note": "Глубина, восстановление, психика и личная перестройка.",
        },
        {
            "title": "Самореализация",
            "score": _solar_score(counts, ["1", "5", "9", "11"], counts.get("1", 0) * 0.4),
            "color": GOLD,
            "note": "Проявленность, творчество, обучение и движение к целям.",
        },
    ]
    avg = round(mean(card["score"] for card in cards), 1)
    top = max(cards, key=lambda card: card["score"])
    focus = f"Главный фокус - {top['title'].lower()} и связанные с ним решения."
    return {
        "kind": "solar",
        "eyebrow": "СОЛЯР",
        "hero_title": f"Соляр {person_name}".strip(),
        "hero_accent": "персональная карта года",
        "hero_description": "Визуальный профиль года по сферам: сначала быстрая сводка в визуальных карточках, дальше - живая расшифровка каждого акцента.",
        "meta": [
            ("ПЕРИОД", f"{cycle_year}-{cycle_year + 1}"),
            ("ТИП", "Соляр"),
        ],
        "section_title": "Карта года в цифрах",
        "subtitle": focus,
        "average": avg,
        "top_label": top["title"],
        "cards": cards,
        "focus_title": "На что опираться в этом году",
        "focus_items": [
            f"Главную ставку делать на сферу: {top['title'].lower()}.",
            "Сохранять внимание к телу и режиму, если год идёт через нагрузку.",
            "Фиксировать договорённости письменно там, где много ожиданий.",
            "Смотреть на напряжение как на подсказку, где пора менять стратегию.",
        ],
    }


def _synastry_aspect_score(chart_data: dict, include: set[str], tension: bool | None = None) -> int:
    total = 0.0
    for row in (chart_data.get("aspects") or [])[1:]:
        if len(row) < 4:
            continue
        first, aspect, second, orb_text = row[:4]
        if first not in include and second not in include:
            continue
        if tension is True and aspect not in TENSION_ASPECTS:
            continue
        if tension is False and aspect not in FLOW_ASPECTS:
            continue
        try:
            orb = float(orb_text)
        except ValueError:
            continue
        total += max(0.2, 3.2 - orb)
    return _clamp_score(3 + total * 0.8)


def build_synastry_profile(chart_data: dict, first_name: str, partner_name: str) -> dict:
    cards = [
        {
            "title": "Эмоциональная связь",
            "score": _synastry_aspect_score(chart_data, {"Луна", "Венера", "Солнце"}, False),
            "color": PURPLE,
            "note": "Тепло, отклик, забота и способность чувствовать друг друга.",
        },
        {
            "title": "Химия",
            "score": _synastry_aspect_score(chart_data, {"Венера", "Марс", "Плутон", "Солнце"}),
            "color": GOLD,
            "note": "Притяжение, энергия контакта и телесная вовлечённость.",
        },
        {
            "title": "Коммуникация",
            "score": _synastry_aspect_score(chart_data, {"Меркурий", "Луна", "Солнце"}, False),
            "color": PURPLE,
            "note": "Разговоры, понимание, формулировки и бытовые договорённости.",
        },
        {
            "title": "Бытовая совместимость",
            "score": _synastry_aspect_score(chart_data, {"Луна", "Сатурн", "Венера"}, None),
            "color": GOLD,
            "note": "Ритмы дня, привычки, забота и ощущение общей базы.",
        },
        {
            "title": "Долгосрочность",
            "score": _synastry_aspect_score(chart_data, {"Сатурн", "Юпитер", "Солнце", "Луна"}),
            "color": PURPLE,
            "note": "Потенциал устойчивости, роста и связи со временем.",
        },
        {
            "title": "Зоны напряжения",
            "score": _synastry_aspect_score(chart_data, {"Марс", "Сатурн", "Плутон", "Луна"}, True),
            "color": GOLD,
            "note": "Интенсивность, триггеры и места, где нужна честность.",
        },
    ]
    avg = round(mean(card["score"] for card in cards), 1)
    top = max(cards, key=lambda card: card["score"])
    return {
        "kind": "synastry",
        "eyebrow": "ПАРА",
        "hero_title": f"Синастрия {first_name}".strip(),
        "hero_accent": f"и {partner_name}".strip(),
        "hero_description": "Визуальный профиль пары: сначала быстрая сводка по сферам совместимости, дальше - полная расшифровка динамики отношений.",
        "meta": [
            ("ПАРА", f"{first_name} + {partner_name}".strip(" +")),
            ("ТИП", "Синастрия"),
        ],
        "section_title": "Профиль совместимости",
        "subtitle": f"Главная активная сфера пары - {top['title'].lower()}.",
        "average": avg,
        "top_label": top["title"],
        "cards": cards,
        "focus_title": "На что опираться в паре",
        "focus_items": [
            f"Главный ресурс связи - {top['title'].lower()}.",
            "Обсуждать напряжение до того, как оно накапливается.",
            "Разделять эмоции, факты и ожидания в сложных разговорах.",
            "Поддерживать ритуалы близости и регулярные договорённости.",
        ],
    }
