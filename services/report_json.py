"""Helpers for structured report JSON returned by Claude."""

from __future__ import annotations

import json
import re
from typing import Any


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
