"""
Бесплатный поиск городов через Nominatim (OpenStreetMap).
У сервиса жёсткое требование: не больше 1 запроса в секунду и
обязательный User-Agent с контактом — иначе банят по IP.
Для личного бота с низкой нагрузкой этого более чем достаточно.
"""

import httpx

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Поставь сюда свой реальный контакт (email или ссылку на бота) —
# это требование политики использования Nominatim, не формальность.
USER_AGENT = "hanna.boychenko@gmail.com"


async def search_city(query: str, limit: int = 5) -> list[dict]:
    """Возвращает список найденных городов: label, lat, lon, raw display_name."""
    params = {
        "q": query,
        "format": "json",
        "addressdetails": 1,
        "limit": limit,
        "accept-language": "ru",
    }
    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(NOMINATIM_URL, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    results = []
    seen_labels = set()
    for item in data:
        address = item.get("address", {})
        city = (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("municipality")
            or item.get("display_name", "").split(",")[0]
        )
        country = address.get("country", "")
        region = address.get("state", "")
        label_parts = [p for p in (city, region, country) if p]
        label = ", ".join(dict.fromkeys(label_parts))  # без дублей подряд

        if label in seen_labels:
            continue
        seen_labels.add(label)

        results.append(
            {
                "label": label,
                "display_name": item.get("display_name", label),
                "lat": float(item["lat"]),
                "lon": float(item["lon"]),
            }
        )
    return results
