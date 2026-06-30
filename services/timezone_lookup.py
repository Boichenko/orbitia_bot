"""Определение IANA-таймзоны по координатам (для геокодированного города)."""

from timezonefinder import TimezoneFinder

_tf = TimezoneFinder()


def get_timezone(lat: float, lon: float):
    """Возвращает имя IANA-таймзоны, например 'Asia/Sakhalin', или None."""
    return _tf.timezone_at(lat=lat, lng=lon)
