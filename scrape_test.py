import asyncio
from playwright.async_api import async_playwright

# Вставь сюда свою полную реальную ссылку (с уже посчитанными данными)
URL = "https://geocult.ru/solyarnyiy-goroskop-onlayn?fn=%D0%90%D0%BD%D0%BD%D0%B0&fd=25&fm=10&fy=1992&fh=4&fmn=0&c1=%D0%A5%D0%BE%D0%BB%D0%BC%D1%81%D0%BA%2C+%D0%A0%D0%BE%D1%81%D1%81%D0%B8%D1%8F&ttz=12&tz=Asia%2FSakhalin&tm=12&lt=47.0473&ln=142.050&tp=113&c1p2=%D0%9C%D0%B8%D0%BD%D1%81%D0%BA%2C+%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D1%8C&lt2=53.9000&ln2=27.5666&hs=P&fy2=2022&tms=3&sb=1"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)  # даём JS время на расчет
        text = await page.inner_text("body")
        print(text)
        await browser.close()


asyncio.run(main())
