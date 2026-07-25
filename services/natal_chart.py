"""Natal chart calculation based on Swiss Ephemeris."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from services import ephemeris as eph


def compute_natal_chart(
    *,
    birth_year: int,
    birth_month: int,
    birth_day: int,
    birth_hour: int,
    birth_minute: int,
    birth_tz: str,
    birth_lat: float,
    birth_lon: float,
    birth_place_label: str,
    house_system: str = "P",
    orb: float = 6.0,
) -> dict:
    jd = eph.local_datetime_to_jd_ut(
        birth_year, birth_month, birth_day, birth_hour, birth_minute, birth_tz
    )
    planets = eph.compute_planet_positions(jd)
    cusps, asc, mc, vertex = eph.compute_houses(jd, birth_lat, birth_lon, house_system)
    planets["PoF"] = eph.compute_part_of_fortune(asc, planets["Moon"], planets["Sun"])
    planets["Vertex"] = vertex

    planet_rows = [["Планета", "Положение", "Дом"]]
    for key in eph.PLANET_ORDER:
        if key not in planets:
            continue
        planet_rows.append(
            [
                eph.RU_NAMES[key],
                eph.lon_to_sign_str(planets[key]),
                str(eph.find_house_of_degree(planets[key], cusps)),
            ]
        )

    house_rows = [["Дом", "Куспид"]]
    for index, cusp in enumerate(cusps, 1):
        label = "1 Дом (ASC)" if index == 1 else "10 Дом (MC)" if index == 10 else f"{index} Дом"
        house_rows.append([label, eph.lon_to_sign_str(cusp)])

    aspect_rows = [["Планета", "Аспект", "Планета", "Орб"]]
    keys = [key for key in eph.PLANET_ORDER if key in planets]
    for left_index, left_key in enumerate(keys):
        for right_key in keys[left_index + 1 :]:
            diff = abs(planets[left_key] - planets[right_key]) % 360
            diff = min(diff, 360 - diff)
            for aspect_name, angle in eph.ASPECTS.items():
                delta = abs(diff - angle)
                if delta <= orb:
                    aspect_rows.append(
                        [
                            eph.RU_NAMES[left_key],
                            aspect_name,
                            eph.RU_NAMES[right_key],
                            f"{delta:.2f}",
                        ]
                    )

    local_dt = dt.datetime(
        birth_year,
        birth_month,
        birth_day,
        birth_hour,
        birth_minute,
        tzinfo=ZoneInfo(birth_tz),
    )
    return {
        "header": (
            f"Дата и время рождения: {local_dt:%d.%m.%Y %H:%M}\n"
            f"Место рождения: {birth_place_label}\n"
            f"Система домов: Плацидус"
        ),
        "angles": [
            ["Точка", "Положение"],
            ["Асцендент", eph.lon_to_sign_str(asc)],
            ["MC", eph.lon_to_sign_str(mc)],
        ],
        "planets": planet_rows,
        "houses": house_rows,
        "aspects": aspect_rows,
    }
