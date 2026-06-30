import asyncio
import json
import re

from playwright.async_api import async_playwright

from services.geocoding import search_city
from services.timezone_lookup import get_timezone
from services.url_builder import build_solar_url

BIRTH_NAME = "Anna"
BIRTH_DAY, BIRTH_MONTH, BIRTH_YEAR = 25, 10, 1992
BIRTH_HOUR, BIRTH_MINUTE = 4, 0
BIRTH_CITY_QUERY = "Холмск, Россия"
SOLAR_CITY_QUERY = "Минск, Беларусь"
SOLAR_CYCLE_YEAR = 2022


async def scrape(url: str) -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # networkidle никогда не наступит на этой странице (виджет переводчика
        # и реклама постоянно дергают сеть) — ждем просто загрузки DOM.
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # Дожидаемся, когда JS реально досчитает и вставит результат.
        try:
            await page.wait_for_selector(
                "text=Время наступления Соляра", timeout=20000
            )
            print("Результат найден на странице.")
        except Exception as e:
            print(f"Не дождались результата за 20 сек: {e}")

        await page.wait_for_timeout(2000)

        toggles = page.get_by_text("Развернуть/Свернуть", exact=True)
        toggle_count = await toggles.count()
        print(f"Найдено переключателей: {toggle_count}")
        for i in range(toggle_count):
            try:
                await toggles.nth(i).click()
                await page.wait_for_timeout(400)
            except Exception:
                pass

        await page.wait_for_timeout(1000)
        body_text = await page.inner_text("body")

        tables = await page.evaluate(
            """() => Array.from(document.querySelectorAll('table')).map(
                t => Array.from(t.rows).map(
                    r => Array.from(r.cells).map(c => c.innerText.trim())
                )
            )"""
        )

        header_match = re.search(
            r"Дата рождения:.*?Время наступления Соляра:.*?\)",
            body_text,
            re.DOTALL,
        )
        header = header_match.group(0) if header_match else None

        await browser.close()
        return {"header": header, "tables": tables}


async def main():
    birth_candidates = await search_city(BIRTH_CITY_QUERY)
    solar_candidates = await search_city(SOLAR_CITY_QUERY)

    birth = birth_candidates[0]
    solar = solar_candidates[0]

    birth_tz = get_timezone(birth["lat"], birth["lon"])
    print("Определена таймзона рождения:", birth_tz)

    url = build_solar_url(
        first_name=BIRTH_NAME,
        birth_day=BIRTH_DAY,
        birth_month=BIRTH_MONTH,
        birth_year=BIRTH_YEAR,
        birth_hour=BIRTH_HOUR,
        birth_minute=BIRTH_MINUTE,
        birth_place_label=birth["label"],
        birth_lat=birth["lat"],
        birth_lon=birth["lon"],
        birth_tz=birth_tz,
        solar_place_label=solar["label"],
        solar_lat=solar["lat"],
        solar_lon=solar["lon"],
        solar_cycle_year=SOLAR_CYCLE_YEAR,
    )
    print("Сформированный URL:")
    print(url)

    data = await scrape(url)

    with open("pipeline_result.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(json.dumps(data, ensure_ascii=False, indent=2))


asyncio.run(main())
