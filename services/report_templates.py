"""Structured JSON templates Claude fills for visual PDF reports."""

from __future__ import annotations

import json
from typing import Any


SOLAR_CATEGORY_KEYS = [
    "career",
    "money",
    "relationships",
    "home",
    "health",
    "communication",
    "inner",
]

SYNASTRY_MAP_KEYS = [
    "emotions",
    "chemistry",
    "communication",
    "sex",
    "longterm",
    "home",
    "risks",
]


def _dump_template(template: dict[str, Any]) -> str:
    return json.dumps(template, ensure_ascii=False, indent=2)


def solar_report_template() -> dict[str, Any]:
    return {
        "cover": {
            "title": "Соляр 2025–2026",
            "subtitle": "Персональный прогноз по сферам жизни",
            "period": "2025–2026",
            "place": "город",
            "overall_score": 8,
            "top_sphere": "Деньги",
        },
        "sphere_map": [
            {"key": "career", "title": "Карьера", "score": 8, "meaning": "одна короткая строка"},
            {"key": "money", "title": "Деньги", "score": 8, "meaning": "одна короткая строка"},
            {"key": "relationships", "title": "Отношения", "score": 8, "meaning": "одна короткая строка"},
            {"key": "home", "title": "Дом", "score": 8, "meaning": "одна короткая строка"},
            {"key": "health", "title": "Здоровье", "score": 8, "meaning": "одна короткая строка"},
            {"key": "communication", "title": "Общение", "score": 8, "meaning": "одна короткая строка"},
            {"key": "inner", "title": "Внутреннее", "score": 8, "meaning": "одна короткая строка"},
        ],
        "map_summary": (
            "короткий абзац анализа круга: какие 2–3 сферы самые сильные, "
            "где ниже балл и что это значит для года"
        ),
        "main_theme": {
            "title": "ёмкая формула года",
            "text": "1–2 коротких абзаца",
            "accents": ["акцент 1", "акцент 2", "акцент 3"],
            "additional_accents": [
                {"title": "дополнительный акцент 1", "text": "1 короткое предложение"},
                {"title": "дополнительный акцент 2", "text": "1 короткое предложение"},
                {"title": "дополнительный акцент 3", "text": "1 короткое предложение"},
            ],
        },
        "categories": [
            {
                "key": "career",
                "title": "Карьера и статус",
                "score": 8,
                "summary": "короткий вывод",
                "keywords": ["слово 1", "слово 2", "слово 3"],
                "amplified": ["3–4 пункта"],
                "manifestations": ["3–4 пункта"],
                "risks": ["2–3 пункта"],
                "actions": ["3–4 пункта"],
                "astro_basis": ["2–4 конкретных фактора из таблиц"],
            },
            {
                "key": "money",
                "title": "Деньги и ресурсы",
                "score": 8,
                "summary": "короткий вывод",
                "keywords": ["слово 1", "слово 2", "слово 3"],
                "amplified": ["3–4 пункта"],
                "manifestations": ["3–4 пункта"],
                "risks": ["2–3 пункта"],
                "actions": ["3–4 пункта"],
                "astro_basis": ["2–4 конкретных фактора из таблиц"],
            },
            {
                "key": "relationships",
                "title": "Отношения",
                "score": 8,
                "summary": "короткий вывод",
                "keywords": ["слово 1", "слово 2", "слово 3"],
                "amplified": ["3–4 пункта"],
                "manifestations": ["3–4 пункта"],
                "risks": ["2–3 пункта"],
                "actions": ["3–4 пункта"],
                "astro_basis": ["2–4 конкретных фактора из таблиц"],
            },
            {
                "key": "home",
                "title": "Дом и семья",
                "score": 8,
                "summary": "короткий вывод",
                "keywords": ["слово 1", "слово 2", "слово 3"],
                "amplified": ["3–4 пункта"],
                "manifestations": ["3–4 пункта"],
                "risks": ["2–3 пункта"],
                "actions": ["3–4 пункта"],
                "astro_basis": ["2–4 конкретных фактора из таблиц"],
            },
            {
                "key": "health",
                "title": "Здоровье и энергия",
                "score": 8,
                "summary": "короткий вывод",
                "keywords": ["слово 1", "слово 2", "слово 3"],
                "amplified": ["3–4 пункта"],
                "manifestations": ["3–4 пункта"],
                "risks": ["2–3 пункта"],
                "actions": ["3–4 пункта"],
                "astro_basis": ["2–4 конкретных фактора из таблиц"],
            },
            {
                "key": "communication",
                "title": "Общение и обучение",
                "score": 8,
                "summary": "короткий вывод",
                "keywords": ["слово 1", "слово 2", "слово 3"],
                "amplified": ["3–4 пункта"],
                "manifestations": ["3–4 пункта"],
                "risks": ["2–3 пункта"],
                "actions": ["3–4 пункта"],
                "astro_basis": ["2–4 конкретных фактора из таблиц"],
            },
            {
                "key": "inner",
                "title": "Внутреннее состояние",
                "score": 8,
                "summary": "короткий вывод",
                "keywords": ["слово 1", "слово 2", "слово 3"],
                "amplified": ["3–4 пункта"],
                "manifestations": ["3–4 пункта"],
                "risks": ["2–3 пункта"],
                "actions": ["3–4 пункта"],
                "astro_basis": ["2–4 конкретных фактора из таблиц"],
            },
        ],
        "risk_summary": [
            {"title": "Перегруз", "level": 7, "risk": "коротко", "support": "что поможет"},
            {"title": "Самообман", "level": 7, "risk": "коротко", "support": "что поможет"},
            {"title": "Молчание о желаниях", "level": 7, "risk": "коротко", "support": "что поможет"},
            {"title": "Расфокус", "level": 7, "risk": "коротко", "support": "что поможет"},
        ],
        "opportunities": [
            {"title": "Рост статуса", "text": "1 предложение"},
            {"title": "Деньги через ценность", "text": "1 предложение"},
            {"title": "Новые знания", "text": "1 предложение"},
            {"title": "Личная зрелость", "text": "1 предложение"},
        ],
        "plan": [
            {"step": 1, "action": "короткое действие"},
            {"step": 2, "action": "короткое действие"},
            {"step": 3, "action": "короткое действие"},
            {"step": 4, "action": "короткое действие"},
            {"step": 5, "action": "короткое действие"},
        ],
        "final_formula": "один финальный абзац",
    }


def synastry_report_template(first_name: str = "", partner_name: str = "") -> dict[str, Any]:
    first = first_name or "Первый партнёр"
    partner = partner_name or "Партнёр"
    title_first = first_name or "Анна"
    title_partner = partner_name or "Александр"
    return {
        "cover": {
            "title": f"Синастрия {title_first} и {title_partner}",
            "subtitle": "Разбор совместимости по любви, коммуникации, химии и долгосрочному потенциалу.",
            "overall_score": 8,
            "connection_type": "глубокая, трансформирующая",
            "main_resource": "магнитное притяжение",
            "main_risk": "разные языки любви",
            "score_words": ["притяжение", "глубина", "рост"],
        },
        "relationship_map": [
            {"key": "emotions", "title": "Эмоции", "score": 8, "meaning": "коротко"},
            {"key": "chemistry", "title": "Химия", "score": 10, "meaning": "коротко"},
            {"key": "communication", "title": "Коммуникация", "score": 5, "meaning": "коротко"},
            {"key": "sex", "title": "Секс", "score": 8, "meaning": "коротко"},
            {"key": "longterm", "title": "Долгосрочность", "score": 8, "meaning": "коротко"},
            {"key": "home", "title": "Быт", "score": 7, "meaning": "коротко"},
            {"key": "risks", "title": "Риски", "score": 7, "meaning": "коротко"},
        ],
        "formula": {
            "title": "Формула пары",
            "phrase": "ёмкая фраза о связи",
            "text": "3–4 строки пояснения",
            "indicators": [
                {"label": "Магнитизм", "value": 10},
                {"label": "Спокойствие", "value": 5},
                {"label": "Долгосрочность", "value": 8},
                {"label": "Простота", "value": 3},
                {"label": "Трансформация", "value": 10},
            ],
        },
        "emotions": {
            "summary": "короткий вывод",
            "support": ["2–3 пункта"],
            "mismatch": ["2–3 пункта"],
            "scales": [
                {"label": "Поддержка", "value": 9, "tone": "resource"},
                {"label": "Безопасность", "value": 8, "tone": "resource"},
                {"label": "Понимание", "value": 6, "tone": "resource"},
                {"label": "Интенсивность", "value": 9, "tone": "tension"},
                {"label": "Раздражение", "value": 7, "tone": "tension"},
            ],
        },
        "chemistry": {
            "score": 10,
            "label": "Сильное притяжение",
            "summary": "короткий вывод",
            "amplifies": ["2–3 пункта"],
            "dims": ["2–3 пункта"],
            "parameters": [
                {"label": "Физическое притяжение", "value": 10},
                {"label": "Сексуальная искра", "value": 9},
                {"label": "Синхронность инициативы", "value": 5},
                {"label": "Глубина привязанности", "value": 10},
            ],
        },
        "love_languages": {
            "first": {"name": first, "items": ["Свобода", "Искренность", "Смысл"]},
            "partner": {"name": partner, "items": ["Прямота", "Действие", "Устойчивость"]},
            "bridge": "переводить ожидания в слова",
            "summary": "короткий вывод",
        },
        "communication": {
            "summary": "короткий вывод",
            "rows": [
                {"from": "смыслы", "to": "факты"},
                {"from": "глубина", "to": "практика"},
                {"from": "эмоциональный подтекст", "to": "конкретика"},
                {"from": "свобода выражения", "to": "стабильность"},
            ],
        },
        "triggers": [
            {"title": "Критика / инициатива", "manifestation": "коротко", "action": "что делать", "level": 4},
            {"title": "Неясность мотивов", "manifestation": "коротко", "action": "что делать", "level": 3},
            {"title": "Интенсивность", "manifestation": "коротко", "action": "что делать", "level": 4},
            {"title": "Разный язык любви", "manifestation": "коротко", "action": "что делать", "level": 5},
            {"title": "Ревность и контроль", "manifestation": "коротко", "action": "что делать", "level": 3},
        ],
        "longterm": {
            "score": 8,
            "summary": "короткий вывод",
            "pillars": [
                {"label": "Обязательства", "value": 9},
                {"label": "Будущее", "value": 9},
                {"label": "Строить", "value": 8},
                {"label": "Кризисы", "value": 7},
            ],
            "weak_spot": "эмоциональная простота",
        },
        "influence": {
            "first_to_partner": {"title": f"{first} → {partner}", "items": ["3–4 пункта"]},
            "partner_to_first": {"title": f"{partner} → {first}", "items": ["3–4 пункта"]},
        },
        "resources": [
            {"title": "Физическая химия", "text": "1 короткое предложение"},
            {"title": "Долгосрочный фундамент", "text": "1 короткое предложение"},
            {"title": "Эмоциональная поддержка", "text": "1 короткое предложение"},
            {"title": "Развитие через отношения", "text": "1 короткое предложение"},
            {"title": "Совместное движение", "text": "1 короткое предложение"},
            {"title": "Ощущение судьбоносности", "text": "1 короткое предложение"},
        ],
        "risks": [
            {"title": "Давление и критика", "level": "высокий", "text": "коротко"},
            {"title": "Разный язык любви", "level": "высокий", "text": "коротко"},
            {"title": "Ревность и контроль", "level": "средний", "text": "коротко"},
            {"title": "Неясность мотивов", "level": "средний", "text": "коротко"},
            {"title": "Эмоциональное перенасыщение", "level": "высокий", "text": "коротко"},
            {"title": "Зависимость от интенсивности", "level": "средний", "text": "коротко"},
        ],
        "recommendations": [
            {"situation": "Он критикует", "action": "короткое действие"},
            {"situation": "Она чувствует неясность", "action": "короткое действие"},
            {"situation": "Пропадает близость", "action": "короткое действие"},
            {"situation": "Слишком много интенсивности", "action": "короткое действие"},
            {"situation": "Разные языки любви", "action": "короткое действие"},
        ],
        "final": {
            "title": "Итоговая формула",
            "text": "финальный абзац",
            "keeps": "что держит пару",
            "breaks": "что может ломать",
            "growth": "что помогает расти",
        },
    }


def solar_report_template_text() -> str:
    return _dump_template(solar_report_template())


def synastry_report_template_text(first_name: str = "", partner_name: str = "") -> str:
    return _dump_template(synastry_report_template(first_name, partner_name))
