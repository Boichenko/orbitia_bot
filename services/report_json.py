"""Helpers for structured report JSON returned by Claude."""

from __future__ import annotations

import json
import re
from typing import Any

from services.report_templates import (
    natal_report_template,
    solar_report_template,
    synastry_report_template,
)


def parse_report_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1).strip()

    if not cleaned.startswith("{"):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start : end + 1]

    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Claude returned JSON, but the root is not an object")
    return data


def structured_report_to_teaser(report: dict[str, Any]) -> str:
    theme = report.get("main_theme") or {}
    title = str(theme.get("title") or "").strip()
    text = str(theme.get("text") or "").strip()
    if title and text:
        return f"{title}\n\n{text[:700]}"
    if text:
        return text[:800]
    final_formula = str(report.get("final_formula") or "").strip()
    if final_formula:
        return final_formula[:800]
    return "Разбор готов — основной текст смотри в приложенном файле ниже."


def _merge_template(report: Any, template: Any) -> Any:
    if isinstance(template, dict):
        source = report if isinstance(report, dict) else {}
        merged = {key: _merge_template(source.get(key), value) for key, value in template.items()}
        for key, value in source.items():
            if key not in merged:
                merged[key] = value
        return merged

    if isinstance(template, list):
        if not isinstance(report, list) or not report:
            return template
        if len(template) == 1:
            return [_merge_template(item, template[0]) for item in report]
        return [
            _merge_template(report[index], template[index])
            if index < len(report)
            else template[index]
            for index in range(max(len(report), len(template)))
        ]

    if report is None or report == "":
        return template
    return report


_SOLAR_CATEGORY_TEXT_BUDGETS = {
    "summary": 250,
    "main_takeaway": 620,
    "amplified": {"count": 5, "item_max": 120},
    "risks": {"count": 3, "item_max": 110},
    "actions": {"count": 4, "item_max": 120},
    "astro_basis": {"count": 4, "item_max": 120, "total_max": 460},
}


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _trim_text(value: Any, max_chars: int) -> str:
    """Keep generated copy inside a visual slot without cutting a word in half."""
    text = _clean_text(value)
    if len(text) <= max_chars:
        return text

    prefix = text[: max_chars + 1]
    sentence_end = max(prefix.rfind(". "), prefix.rfind("! "), prefix.rfind("? "), prefix.rfind("; "))
    if sentence_end >= max_chars // 2:
        return prefix[: sentence_end + 1].strip()

    word_end = prefix.rfind(" ")
    return prefix[:word_end].rstrip(" ,;:-") if word_end > 0 else prefix[:max_chars]


def _normalize_category_items(value: Any, *, count: int, item_max: int, total_max: int | None = None) -> list[str]:
    if not isinstance(value, list):
        return []

    result: list[str] = []
    total = 0
    for raw_item in value:
        if len(result) >= count:
            break
        item = _trim_text(raw_item, item_max)
        if not item:
            continue
        separator = 3 if result else 0  # visual separator: " · "
        if total_max is not None and total + separator + len(item) > total_max:
            item = _trim_text(item, max(0, total_max - total - separator))
        if item:
            result.append(item)
            total += separator + len(item)
    return result


def _normalize_solar_category(category: Any) -> Any:
    if not isinstance(category, dict):
        return category

    normalized = dict(category)
    normalized["summary"] = _trim_text(normalized.get("summary"), _SOLAR_CATEGORY_TEXT_BUDGETS["summary"])
    normalized["main_takeaway"] = _trim_text(
        normalized.get("main_takeaway"), _SOLAR_CATEGORY_TEXT_BUDGETS["main_takeaway"]
    )
    for field in ("amplified", "risks", "actions", "astro_basis"):
        config = _SOLAR_CATEGORY_TEXT_BUDGETS[field]
        normalized[field] = _normalize_category_items(
            normalized.get(field),
            count=config["count"],
            item_max=config["item_max"],
            total_max=config.get("total_max"),
        )
    return normalized


def normalize_solar_report(report: dict[str, Any]) -> dict[str, Any]:
    normalized = _merge_template(report, solar_report_template())
    categories = normalized.get("categories")
    if isinstance(categories, list):
        normalized["categories"] = [_normalize_solar_category(category) for category in categories]
    return normalized


def normalize_synastry_report(
    report: dict[str, Any],
    first_name: str = "",
    partner_name: str = "",
) -> dict[str, Any]:
    return _merge_template(report, synastry_report_template(first_name, partner_name))


def normalize_natal_report(report: dict[str, Any], person_name: str = "") -> dict[str, Any]:
    return _merge_template(report, natal_report_template(person_name))
