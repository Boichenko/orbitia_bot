"""Скрейпинг расчета соляра с geocult.ru через headless-браузер."""

import asyncio
import logging
import re
from typing import Optional

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

# Ищем не текст (он есть и в старом комментарии на странице!), а саму
# таблицу с результатом — это надежный признак того, что расчет прошел.
RESULT_TABLE_SELECTOR = "table:has-text('Дома Соляра')"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def _classify_table(rows: list[list[str]]) -> Optional[str]:
    if not rows:
        return None
    header = " ".join(rows[0]).lower()
    if "дома соляра" in header and "позиция" in header:
        return "houses"
    if "планеты соляра" in header:
        return "planets"
    if header.startswith("дома") and "натальная" in header:
        return "house_comparison"
    if "аспекты" in header:
        return "aspects"
    return None


async def _attempt(url: str, timeout_ms: int) -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1366, "height": 768},
            locale="ru-RU",
        )
        page = await context.new_page()
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )

        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        logger.info("Страница загружена (domcontentloaded)")

        await page.wait_for_selector(RESULT_TABLE_SELECTOR, timeout=timeout_ms)
        logger.info("Таблица с результатом найдена в DOM")

        await page.wait_for_timeout(1000)

        toggles = page.get_by_text("Развернуть/Свернуть", exact=True)
        toggle_count = await toggles.count()
        for i in range(toggle_count):
            try:
                await toggles.nth(i).click()
                await page.wait_for_timeout(300)
            except Exception:
                pass

        await page.wait_for_timeout(800)

        body_text = await page.inner_text("body")
        raw_tables = await page.evaluate(
            """() => Array.from(document.querySelectorAll('table')).map(
                t => Array.from(t.rows).map(
                    r => Array.from(r.cells).map(c => c.innerText.trim())
                )
            )"""
        )

        await browser.close()

    header_match = re.search(
        r"Дата рождения:\s*\d{1,2}\s+\S+\s+\d{4}\s+года.*?Время наступления Соляра:.*?\)",
        body_text,
        re.DOTALL,
    )
    header = header_match.group(0).strip() if header_match else None

    result = {
        "header": header,
        "houses": None,
        "planets": None,
        "house_comparison": None,
        "aspects": None,
    }
    for table in raw_tables:
        kind = _classify_table(table)
        if kind and result[kind] is None:
            rows = [r for r in table if r and r[0] != "Развернуть/Свернуть"]
            result[kind] = rows

    return result


async def fetch_solar_chart(url: str, timeout_ms: int = 45000, retries: int = 2) -> dict:
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            logger.info("Попытка %s/%s, URL: %s", attempt, retries, url)
            return await _attempt(url, timeout_ms)
        except Exception as e:
            last_error = e
            logger.warning("Попытка %s не удалась: %s", attempt, e)
            if attempt < retries:
                await asyncio.sleep(5)
    raise last_error
