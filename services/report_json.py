"""Helpers for structured report JSON returned by Claude."""

from __future__ import annotations

import json
import re
from typing import Any

from services.report_templates import solar_report_template, synastry_report_template


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


def normalize_solar_report(report: dict[str, Any]) -> dict[str, Any]:
    return _merge_template(report, solar_report_template())


def normalize_synastry_report(
    report: dict[str, Any],
    first_name: str = "",
    partner_name: str = "",
) -> dict[str, Any]:
    return _merge_template(report, synastry_report_template(first_name, partner_name))
