"""Расчет синастрии: две натальные карты, взаимные аспекты и наложения домов."""

import datetime as dt
from zoneinfo import ZoneInfo

from services import ephemeris as eph


def _person_chart(
    *,
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    tz: str,
    lat: float,
    lon: float,
    place_label: str,
    house_system: str,
) -> dict:
    jd = eph.local_datetime_to_jd_ut(year, month, day, hour, minute, tz)
    planets = eph.compute_planet_positions(jd)
    cusps, asc, mc, vertex = eph.compute_houses(jd, lat, lon, house_system)
    planets["PoF"] = eph.compute_part_of_fortune(asc, planets["Moon"], planets["Sun"])
    planets["Vertex"] = vertex
    local_dt = dt.datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(tz))

    return {
        "local_dt": local_dt,
        "place_label": place_label,
        "planets": planets,
        "cusps": cusps,
        "asc": asc,
        "mc": mc,
    }


def _format_person_header(label: str, chart: dict) -> str:
    local_dt = chart["local_dt"]
    offset_h = local_dt.utcoffset().total_seconds() / 3600
    return (
        f"{label}: {local_dt.day:02d}.{local_dt.month:02d}.{local_dt.year} "
        f"в {local_dt.hour:02d}:{local_dt.minute:02d} (GMT {offset_h:+.0f})\n"
        f"Место рождения: {chart['place_label']}\n"
        f"ASC: {eph.lon_to_sign_str(chart['asc'])}; MC: {eph.lon_to_sign_str(chart['mc'])}"
    )


def _planet_rows(title: str, chart: dict) -> list[list[str]]:
    rows = [[title, "Долгота", "Дом"]]
    for key in eph.PLANET_ORDER:
        if key not in chart["planets"]:
            continue
        lon = chart["planets"][key]
        rows.append(
            [
                eph.RU_NAMES[key],
                eph.lon_to_sign_str(lon),
                str(eph.find_house_of_degree(lon, chart["cusps"])),
            ]
        )
    return rows


def _overlay_rows(title: str, source_chart: dict, target_chart: dict) -> list[list[str]]:
    rows = [[title, "Долгота", "В доме партнера"]]
    for key in eph.PLANET_ORDER:
        if key not in source_chart["planets"]:
            continue
        lon = source_chart["planets"][key]
        rows.append(
            [
                eph.RU_NAMES[key],
                eph.lon_to_sign_str(lon),
                str(eph.find_house_of_degree(lon, target_chart["cusps"])),
            ]
        )
    return rows


def _aspect_rows(first_chart: dict, second_chart: dict, orb: float) -> list[list[str]]:
    rows = [["Планета первого человека", "Аспект", "Планета партнера", "Орб"]]
    for first_key in eph.PLANET_ORDER:
        if first_key not in first_chart["planets"]:
            continue
        first_lon = first_chart["planets"][first_key]
        for second_key in eph.PLANET_ORDER:
            if second_key not in second_chart["planets"]:
                continue
            second_lon = second_chart["planets"][second_key]
            diff = abs(first_lon - second_lon) % 360
            if diff > 180:
                diff = 360 - diff
            for aspect_name, angle in eph.ASPECTS.items():
                delta = abs(diff - angle)
                if delta <= orb:
                    rows.append(
                        [
                            eph.RU_NAMES[first_key],
                            aspect_name,
                            eph.RU_NAMES[second_key],
                            f"{delta:.2f}",
                        ]
                    )
    return rows


def compute_synastry(
    *,
    first_name: str,
    first_year: int,
    first_month: int,
    first_day: int,
    first_hour: int,
    first_minute: int,
    first_tz: str,
    first_lat: float,
    first_lon: float,
    first_place_label: str,
    partner_name: str,
    partner_year: int,
    partner_month: int,
    partner_day: int,
    partner_hour: int,
    partner_minute: int,
    partner_tz: str,
    partner_lat: float,
    partner_lon: float,
    partner_place_label: str,
    house_system: str = "P",
    orb: float = 3.0,
) -> dict:
    first_chart = _person_chart(
        year=first_year,
        month=first_month,
        day=first_day,
        hour=first_hour,
        minute=first_minute,
        tz=first_tz,
        lat=first_lat,
        lon=first_lon,
        place_label=first_place_label,
        house_system=house_system,
    )
    partner_chart = _person_chart(
        year=partner_year,
        month=partner_month,
        day=partner_day,
        hour=partner_hour,
        minute=partner_minute,
        tz=partner_tz,
        lat=partner_lat,
        lon=partner_lon,
        place_label=partner_place_label,
        house_system=house_system,
    )

    first_label = first_name or "Первый человек"
    partner_label = partner_name or "Партнер"
    header = (
        f"{_format_person_header(first_label, first_chart)}\n\n"
        f"{_format_person_header(partner_label, partner_chart)}\n\n"
        f"Система расчета домов: {'Плацидус' if house_system == 'P' else house_system}"
    )

    return {
        "header": header,
        "first_planets": _planet_rows(f"Планеты: {first_label}", first_chart),
        "partner_planets": _planet_rows(f"Планеты: {partner_label}", partner_chart),
        "first_in_partner_houses": _overlay_rows(
            f"Планеты {first_label} в домах {partner_label}", first_chart, partner_chart
        ),
        "partner_in_first_houses": _overlay_rows(
            f"Планеты {partner_label} в домах {first_label}", partner_chart, first_chart
        ),
        "aspects": _aspect_rows(first_chart, partner_chart, orb),
    }
