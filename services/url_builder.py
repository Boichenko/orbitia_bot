"""
Собирает URL для расчета соляра на geocult.ru из уже известных данных
(дата/время рождения, координаты места рождения и места соляра).

ttz, tm, tp, tms пока не включены (их назначение не до конца понятно).
sb=1 добавлен как тест гипотезы — похоже, это флаг "расчет отправлен",
без которого JS на странице не парсит параметры из URL вообще.
"""

from datetime import date
from typing import Optional
from urllib.parse import urlencode

BASE_URL = "https://geocult.ru/solyarnyiy-goroskop-onlayn"

HOUSE_SYSTEM_PLACIDUS = "P"


def compute_solar_cycle_year(
    birth_day: int, birth_month: int, today: Optional[date] = None
) -> int:
    today = today or date.today()
    this_year_birthday = date(today.year, birth_month, birth_day)
    if today >= this_year_birthday:
        return today.year
    return today.year - 1


def build_solar_url(
    *,
    first_name: str,
    birth_day: int,
    birth_month: int,
    birth_year: int,
    birth_hour: int,
    birth_minute: int,
    birth_place_label: str,
    birth_lat: float,
    birth_lon: float,
    birth_tz: str,
    solar_place_label: str,
    solar_lat: float,
    solar_lon: float,
    house_system: str = HOUSE_SYSTEM_PLACIDUS,
    solar_cycle_year: Optional[int] = None,
) -> str:
    if solar_cycle_year is None:
        solar_cycle_year = compute_solar_cycle_year(birth_day, birth_month)

    params = {
        "fn": first_name,
        "fd": birth_day,
        "fm": birth_month,
        "fy": birth_year,
        "fh": birth_hour,
        "fmn": birth_minute,
        "c1": birth_place_label,
        "tz": birth_tz,
        "lt": birth_lat,
        "ln": birth_lon,
        "c1p2": solar_place_label,
        "lt2": solar_lat,
        "ln2": solar_lon,
        "hs": house_system,
        "fy2": solar_cycle_year,
        "sb": 1,
    }
    return f"{BASE_URL}?{urlencode(params)}"
