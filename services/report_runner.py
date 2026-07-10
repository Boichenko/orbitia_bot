from __future__ import annotations

import os
import re
import tempfile
import time
from dataclasses import dataclass
from typing import Optional

from services.claude_client import interpret_solar_chart
from services.prompt_builder import (
    build_solar_json_prompt,
    build_solar_prompt,
    build_synastry_json_prompt,
    build_synastry_prompt,
)
from services.report_file import extract_main_theme
from services.report_insights import build_solar_profile, build_synastry_profile
from services.report_json import (
    normalize_solar_report,
    normalize_synastry_report,
    parse_report_json,
    structured_report_to_teaser,
)
from services.report_pdf import markdown_to_pdf, structured_solar_to_pdf, structured_synastry_to_pdf
from services.solar_chart import compute_solar_return
from services.synastry_chart import compute_synastry
from services.timezone_lookup import get_timezone


@dataclass
class GeneratedReport:
    path: str
    filename: str
    teaser: str


def _parse_date(value: str) -> tuple[int, int, int]:
    day, month, year = (int(x) for x in value.split("."))
    return day, month, year


def _parse_time(value: Optional[str]) -> tuple[int, int]:
    if not value:
        return 12, 0
    hour, minute = (int(x) for x in value.split(":"))
    return hour, minute


def _safe_filename(value: str) -> str:
    safe = re.sub(r'[\\/:*?"<>|]', "", value).strip()
    return re.sub(r"\s+", " ", safe)


def _tmp_pdf_path(prefix: str) -> str:
    handle, path = tempfile.mkstemp(prefix=f"{prefix}_{int(time.time())}_", suffix=".pdf")
    os.close(handle)
    return path


async def generate_solar_report(data: dict) -> GeneratedReport:
    birth_place = data["birth_place"]
    solar_place = data["solar_place"]
    cycle_year = int(data["solar_cycle_year"])
    user_context: Optional[str] = data.get("user_context")

    day, month, year = _parse_date(data["birth_date"])
    hour, minute = _parse_time(data.get("birth_time"))

    birth_tz = get_timezone(birth_place["lat"], birth_place["lon"])
    solar_tz = get_timezone(solar_place["lat"], solar_place["lon"])

    chart_data = compute_solar_return(
        birth_year=year,
        birth_month=month,
        birth_day=day,
        birth_hour=hour,
        birth_minute=minute,
        birth_tz=birth_tz,
        birth_lat=birth_place["lat"],
        birth_lon=birth_place["lon"],
        birth_place_label=birth_place["label"],
        solar_lat=solar_place["lat"],
        solar_lon=solar_place["lon"],
        solar_place_label=solar_place["label"],
        solar_tz=solar_tz,
        solar_cycle_year=cycle_year,
    )

    prompt = build_solar_json_prompt(
        chart_data,
        person_name=data.get("person_name", ""),
        user_context=user_context,
    )

    report_json = None
    buffer, stop_reason = await interpret_solar_chart(prompt)
    try:
        report_json = normalize_solar_report(parse_report_json(buffer))
    except Exception:
        fallback_prompt = build_solar_prompt(
            chart_data,
            person_name=data.get("person_name", ""),
            user_context=user_context,
        )
        buffer, stop_reason = await interpret_solar_chart(fallback_prompt)

    cut_off_note = (
        "\n\n⚠️ Ответ получился длиннее лимита и мог быть обрезан."
        if stop_reason == "max_tokens"
        else ""
    )
    if report_json:
        teaser = structured_report_to_teaser(report_json)
    else:
        teaser = extract_main_theme(buffer) or "Разбор готов — основной текст в PDF-файле."
    teaser += cut_off_note

    output_path = _tmp_pdf_path("solar")
    if report_json:
        await structured_solar_to_pdf(report_json, output_path)
    else:
        visual_profile = build_solar_profile(
            chart_data,
            person_name=data.get("person_name", ""),
            cycle_year=cycle_year,
        )
        title = f"Соляр {data.get('person_name', '')}".strip()
        await markdown_to_pdf(title, buffer, output_path, visual_profile=visual_profile)

    name_part = _safe_filename(data.get("person_name", ""))
    display_name = f"{name_part} {data['birth_date']} {cycle_year}-{cycle_year + 1}".strip()
    return GeneratedReport(path=output_path, filename=f"{display_name}.pdf", teaser=teaser)


async def generate_synastry_report(data: dict) -> GeneratedReport:
    birth_place = data["birth_place"]
    partner_birth_place = data["partner_birth_place"]

    day, month, year = _parse_date(data["birth_date"])
    p_day, p_month, p_year = _parse_date(data["partner_birth_date"])
    hour, minute = _parse_time(data.get("birth_time"))
    p_hour, p_minute = _parse_time(data.get("partner_birth_time"))

    birth_tz = get_timezone(birth_place["lat"], birth_place["lon"])
    partner_tz = get_timezone(partner_birth_place["lat"], partner_birth_place["lon"])

    first_name = data.get("person_name", "")
    partner_name = data.get("partner_name", "")
    chart_data = compute_synastry(
        first_name=first_name,
        first_year=year,
        first_month=month,
        first_day=day,
        first_hour=hour,
        first_minute=minute,
        first_tz=birth_tz,
        first_lat=birth_place["lat"],
        first_lon=birth_place["lon"],
        first_place_label=birth_place["label"],
        partner_name=partner_name,
        partner_year=p_year,
        partner_month=p_month,
        partner_day=p_day,
        partner_hour=p_hour,
        partner_minute=p_minute,
        partner_tz=partner_tz,
        partner_lat=partner_birth_place["lat"],
        partner_lon=partner_birth_place["lon"],
        partner_place_label=partner_birth_place["label"],
    )

    prompt = build_synastry_json_prompt(chart_data, first_name=first_name, partner_name=partner_name)
    report_json = None
    buffer, stop_reason = await interpret_solar_chart(prompt)
    try:
        report_json = normalize_synastry_report(
            parse_report_json(buffer),
            first_name=first_name,
            partner_name=partner_name,
        )
    except Exception:
        fallback_prompt = build_synastry_prompt(
            chart_data,
            first_name=first_name,
            partner_name=partner_name,
        )
        buffer, stop_reason = await interpret_solar_chart(fallback_prompt)

    cut_off_note = (
        "\n\n⚠️ Ответ получился длиннее лимита и мог быть обрезан."
        if stop_reason == "max_tokens"
        else ""
    )
    if report_json:
        teaser = structured_report_to_teaser(
            {
                "main_theme": {
                    "title": (report_json.get("formula") or {}).get("phrase", ""),
                    "text": (report_json.get("formula") or {}).get("text", ""),
                },
                "final_formula": (report_json.get("final") or {}).get("text", ""),
            }
        )
    else:
        teaser = extract_main_theme(buffer) or "Разбор совместимости готов — основной текст в PDF."
    teaser += cut_off_note

    output_path = _tmp_pdf_path("synastry")
    if report_json:
        await structured_synastry_to_pdf(report_json, output_path)
    else:
        visual_profile = build_synastry_profile(
            chart_data,
            first_name=first_name,
            partner_name=partner_name,
        )
        title = f"Синастрия {first_name} и {partner_name}".strip()
        await markdown_to_pdf(title, buffer, output_path, visual_profile=visual_profile)

    safe_first = _safe_filename(first_name)
    safe_partner = _safe_filename(partner_name)
    display_name = f"Синастрия {safe_first} и {safe_partner}".strip()
    return GeneratedReport(path=output_path, filename=f"{display_name}.pdf", teaser=teaser)
