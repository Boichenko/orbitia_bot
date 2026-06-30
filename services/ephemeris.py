"""
Низкоуровневые обертки над pyswisseph: julian day, позиции планет,
дома, поиск момента соляра.

Хирон (swe.CHIRON) требует файла эфемерид астероидов (seas_18.se1),
который не входит в pip-пакет. Без него Хирон просто не считается
(тихо опускается из результата) — единственное ограничение без
дополнительной установки файла. См. README.

"Белая Луна (Селена)" сознательно не реализована — не нашли надежного
общепринятого астрономического определения, под которым подгонять
формулу не стали, чтобы не выдавать неверные цифры за точные.
"""

import datetime as dt
import os
from zoneinfo import ZoneInfo

import swisseph as swe

_EPHE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ephe")
if os.path.isdir(_EPHE_PATH):
    swe.set_ephe_path(_EPHE_PATH)
SIGN_NAMES = [
    "Овен", "Телец", "Близнецы", "Рак", "Лев", "Дева",
    "Весы", "Скорпион", "Стрелец", "Козерог", "Водолей", "Рыбы",
]

PLANET_CODES = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus": swe.VENUS,
    "Mars": swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO,
    "Chiron": swe.CHIRON,
    "Lilith": swe.MEAN_APOG,
}

RU_NAMES = {
    "Sun": "Солнце",
    "Moon": "Луна",
    "Mercury": "Меркурий",
    "Venus": "Венера",
    "Mars": "Марс",
    "Jupiter": "Юпитер",
    "Saturn": "Сатурн",
    "Uranus": "Уран",
    "Neptune": "Нептун",
    "Pluto": "Плутон",
    "Chiron": "Хирон",
    "Lilith": "Лилит (Черная Луна)",
    "TrueNode": "Восходящий узел",
    "SouthNode": "Нисходящий узел",
    "PoF": "Парс Фортуны",
    "Vertex": "Вертекс",
}

PLANET_ORDER = [
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
    "Uranus", "Neptune", "Pluto", "Chiron", "Lilith",
    "TrueNode", "SouthNode", "PoF", "Vertex",
]

ASPECTS = {
    "Соединение": 0,
    "Секстиль": 60,
    "Квадрат": 90,
    "Тригон": 120,
    "Квиконс": 150,
    "Оппозиция": 180,
}

DEFAULT_ORB = 1.0


def lon_to_sign_str(lon_deg: float) -> str:
    lon_deg = lon_deg % 360
    sign_idx = int(lon_deg // 30)
    rem = lon_deg - sign_idx * 30
    d = int(rem)
    minute_full = (rem - d) * 60
    m = int(minute_full)
    s = round((minute_full - m) * 60)
    if s == 60:
        s = 0
        m += 1
    if m == 60:
        m = 0
        d += 1
    return f"{SIGN_NAMES[sign_idx]} {d:02d}°{m:02d}'{s:02d}\""


def local_datetime_to_jd_ut(
    year: int, month: int, day: int, hour: int, minute: int, tz_name: str
) -> float:
    local_dt = dt.datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(tz_name))
    utc_dt = local_dt.astimezone(dt.timezone.utc)
    decimal_hour = utc_dt.hour + utc_dt.minute / 60 + utc_dt.second / 3600
    return swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, decimal_hour, swe.GREG_CAL)


def jd_to_utc_datetime(jd: float) -> dt.datetime:
    y, m, d, h = swe.revjul(jd, swe.GREG_CAL)
    base = dt.datetime(y, m, 1, tzinfo=dt.timezone.utc)
    return base + dt.timedelta(days=d - 1, hours=h)


def compute_planet_positions(jd_ut: float) -> dict:
    positions = {}
    for name, code in PLANET_CODES.items():
        try:
            positions[name] = swe.calc_ut(jd_ut, code)[0][0]
        except swe.Error:
            if name == "Chiron":
                continue
            raise

    true_node = swe.calc_ut(jd_ut, swe.TRUE_NODE)[0][0]
    positions["TrueNode"] = true_node
    positions["SouthNode"] = (true_node + 180) % 360

    return positions


def compute_houses(jd_ut: float, lat: float, lon: float, house_system: str = "P"):
    cusps, ascmc = swe.houses(jd_ut, lat, lon, house_system.encode())
    return list(cusps[:12]), ascmc[0], ascmc[1], ascmc[3]


def compute_part_of_fortune(asc: float, moon_lon: float, sun_lon: float) -> float:
    return (asc + moon_lon - sun_lon) % 360


def find_house_of_degree(lon_deg: float, cusps: list) -> int:
    lon_deg = lon_deg % 360
    for i in range(12):
        start = cusps[i] % 360
        end = cusps[(i + 1) % 12] % 360
        span = (end - start) % 360
        if span == 0:
            span = 360
        offset = (lon_deg - start) % 360
        if offset < span:
            return i + 1
    return 12


def find_solar_return_jd(natal_sun_lon: float, jd_guess: float, max_iter: int = 8) -> float:
    jd = jd_guess
    for _ in range(max_iter):
        sun_pos, sun_speed = swe.calc_ut(jd, swe.SUN)[0][0], swe.calc_ut(jd, swe.SUN)[0][3]
        diff = ((natal_sun_lon - sun_pos + 180) % 360) - 180
        if abs(diff) < 1e-6:
            break
        jd = jd + diff / sun_speed
    return jd
