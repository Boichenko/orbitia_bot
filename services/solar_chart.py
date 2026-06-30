"""
Полный расчет соляра: натальная карта + момент возвращения Солнца +
релоцированные дома соляра (по месту, где встречается день рождения) +
аспекты.
"""

import datetime as dt
from zoneinfo import ZoneInfo

from services import ephemeris as eph

HOUSE_NAMES = {1: "1 Дом (AC)", 10: "10 Дом (МC)"}


def _house_label(n: int) -> str:
    return HOUSE_NAMES.get(n, f"{n} Дом")


def compute_solar_return(
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
    solar_lat: float,
    solar_lon: float,
    solar_place_label: str,
    solar_tz: str,
    solar_cycle_year: int,
    house_system: str = "P",
    orb: float = eph.DEFAULT_ORB,
) -> dict:
    jd_birth = eph.local_datetime_to_jd_ut(
        birth_year, birth_month, birth_day, birth_hour, birth_minute, birth_tz
    )
    natal_planets = eph.compute_planet_positions(jd_birth)
    natal_cusps, natal_asc, natal_mc, natal_vertex = eph.compute_houses(
        jd_birth, birth_lat, birth_lon, house_system
    )
    natal_planets["PoF"] = eph.compute_part_of_fortune(
        natal_asc, natal_planets["Moon"], natal_planets["Sun"]
    )
    natal_planets["Vertex"] = natal_vertex

    jd_guess = eph.local_datetime_to_jd_ut(
        solar_cycle_year, birth_month, birth_day, birth_hour, birth_minute, birth_tz
    )
    jd_solar = eph.find_solar_return_jd(natal_planets["Sun"], jd_guess)

    solar_planets = eph.compute_planet_positions(jd_solar)
    solar_cusps, solar_asc, solar_mc, solar_vertex = eph.compute_houses(
        jd_solar, solar_lat, solar_lon, house_system
    )
    solar_planets["PoF"] = eph.compute_part_of_fortune(
        solar_asc, solar_planets["Moon"], solar_planets["Sun"]
    )
    solar_planets["Vertex"] = solar_vertex

    houses_table = [["Дома Соляра", "Долгота", "Позиция Натального Дома"]]
    for i in range(12):
        cusp = solar_cusps[i]
        natal_house = eph.find_house_of_degree(cusp, natal_cusps)
        houses_table.append([_house_label(i + 1), eph.lon_to_sign_str(cusp), str(natal_house)])

    planets_table = [["Планеты Соляра", "Долгота", "Позиция Дома Соляра"]]
    for key in eph.PLANET_ORDER:
        if key not in solar_planets:
            continue
        lon = solar_planets[key]
        house = eph.find_house_of_degree(lon, solar_cusps)
        planets_table.append([eph.RU_NAMES[key], eph.lon_to_sign_str(lon), str(house)])

    comparison_table = [["Дома", "Натальная", "Соляр"]]
    for i in range(12):
        comparison_table.append(
            [
                _house_label(i + 1),
                eph.lon_to_sign_str(natal_cusps[i]),
                eph.lon_to_sign_str(solar_cusps[i]),
            ]
        )

    aspects_table = [["Солярные планеты", "Аспекты", "Натальные планеты", "Орб"]]
    for s_key in eph.PLANET_ORDER:
        if s_key not in solar_planets:
            continue
        s_lon = solar_planets[s_key]
        for n_key in eph.PLANET_ORDER:
            if n_key not in natal_planets:
                continue
            n_lon = natal_planets[n_key]
            diff = abs(s_lon - n_lon) % 360
            if diff > 180:
                diff = 360 - diff
            for aspect_name, angle in eph.ASPECTS.items():
                delta = abs(diff - angle)
                if delta <= orb:
                    aspects_table.append(
                        [eph.RU_NAMES[s_key], aspect_name, eph.RU_NAMES[n_key], f"{delta:.2f}"]
                    )

    birth_dt_local = dt.datetime(
        birth_year, birth_month, birth_day, birth_hour, birth_minute, tzinfo=ZoneInfo(birth_tz)
    )
    solar_dt_utc = eph.jd_to_utc_datetime(jd_solar)
    solar_dt_local = solar_dt_utc.astimezone(ZoneInfo(solar_tz))
    solar_offset_h = solar_dt_local.utcoffset().total_seconds() / 3600
    offset_str = f"{solar_offset_h:+.0f}"

    cycle_end_year = solar_cycle_year + 1

    months_ru = [
        "Января", "Февраля", "Марта", "Апреля", "Мая", "Июня",
        "Июля", "Августа", "Сентября", "Октября", "Ноября", "Декабря",
    ]

    header = (
        f"Дата рождения: {birth_dt_local.day} {months_ru[birth_dt_local.month - 1]} "
        f"{birth_dt_local.year} года в {birth_dt_local.hour}:{birth_dt_local.minute:02d}\n"
        f"Населенный пункт: {birth_place_label}\n\n"
        f"Место соляра: {solar_place_label}\n\n"
        f"Система расчета домов: {'Плацидус' if house_system == 'P' else house_system}\n\n"
        f"Год расчета: с {birth_dt_local.day} {months_ru[birth_dt_local.month - 1]} "
        f"{solar_cycle_year} по {birth_dt_local.day} {months_ru[birth_dt_local.month - 1]} "
        f"{cycle_end_year}\n\n"
        f"Время наступления Соляра: {solar_dt_local.day} {months_ru[solar_dt_local.month - 1]} "
        f"{solar_dt_local.year} в {solar_dt_local.hour}:{solar_dt_local.minute:02d} "
        f"(GMT {offset_str})"
    )

    return {
        "header": header,
        "houses": houses_table,
        "planets": planets_table,
        "house_comparison": comparison_table,
        "aspects": aspects_table,
    }
