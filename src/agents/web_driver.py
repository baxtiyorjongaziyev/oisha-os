"""
Oisha Web Driver — Playwright asosida brauzer avtomatizatsiyasi.

Oisha-OS tizimi uchun veb-brauzer orqali har qanday saytni
inson kabi boshqarish imkoniyatini beradi.
"""
import asyncio
import logging
from typing import Optional, List, Dict, Any
from playwright.async_api import async_playwright, Page, BrowserContext, Browser

logger = logging.getLogger(__name__)


class OishaWebDriver:
    """Playwright asosidagi brauzer avtomatizatsiya driveri."""

    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._playwright = None

    # ── Lifecycle ──────────────────────────────────────────

    async def start(self, headless: bool = False):
        """Brauzerni ishga tushirish."""
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(headless=headless)
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        self.page = await self.context.new_page()
        logger.info("[WebDriver] Started successfully.")

    async def stop(self):
        """Brauzerni to'xtatish va resurslarni tozalash."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()
        self.page = None
        self.context = None
        self.browser = None
        logger.info("[WebDriver] Stopped.")

    def _ensure_page(self):
        """Page mavjudligini tekshirish."""
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")

    # ── Navigation ─────────────────────────────────────────

    async def goto(self, url: str, wait_until: str = "networkidle"):
        """Saytga o'tish."""
        self._ensure_page()
        logger.info(f"[WebDriver] Navigating to {url}")
        await self.page.goto(url, wait_until=wait_until)

    async def go_back(self):
        """Orqaga qaytish."""
        self._ensure_page()
        await self.page.go_back()

    async def go_forward(self):
        """Oldinga o'tish."""
        self._ensure_page()
        await self.page.go_forward()

    async def reload(self):
        """Sahifani qayta yuklash."""
        self._ensure_page()
        await self.page.reload()

    async def get_url(self) -> str:
        """Hozirgi sahifa URL ni olish."""
        self._ensure_page()
        return self.page.url

    async def get_title(self) -> str:
        """Sahifa sarlavhasini olish."""
        self._ensure_page()
        return await self.page.title()

    # ── Screenshots & Content ──────────────────────────────

    async def take_screenshot(self, path: str = "web_screenshot.png", full_page: bool = True) -> str:
        """Sahifaning skrinshotini olish."""
        self._ensure_page()
        await self.page.screenshot(path=path, full_page=full_page)
        logger.info(f"[WebDriver] Screenshot saved to {path}")
        return path

    async def get_page_text(self) -> str:
        """Sahifadagi barcha matnni olish."""
        self._ensure_page()
        return await self.page.inner_text("body")

    async def get_page_html(self) -> str:
        """Sahifaning HTML kontentini olish."""
        self._ensure_page()
        return await self.page.content()

    async def get_text(self, selector: str) -> str:
        """Berilgan selector ichidagi matnni olish."""
        self._ensure_page()
        element = await self.page.query_selector(selector)
        if element:
            return await element.inner_text()
        return ""

    async def get_attribute(self, selector: str, attribute: str) -> Optional[str]:
        """Elementning ma'lum bir atributini olish."""
        self._ensure_page()
        element = await self.page.query_selector(selector)
        if element:
            return await element.get_attribute(attribute)
        return None

    # ── Interactions ────────────────────────────────────────

    async def click(self, selector: str, timeout: int = 5000):
        """Elementga bosish."""
        self._ensure_page()
        logger.info(f"[WebDriver] Clicking: {selector}")
        await self.page.click(selector, timeout=timeout)

    async def double_click(self, selector: str):
        """Elementga ikki marta bosish."""
        self._ensure_page()
        await self.page.dblclick(selector)

    async def right_click(self, selector: str):
        """Elementga o'ng tugma bilan bosish."""
        self._ensure_page()
        await self.page.click(selector, button="right")

    async def hover(self, selector: str):
        """Element ustiga kursorni olib borish."""
        self._ensure_page()
        await self.page.hover(selector)

    async def type_text(self, selector: str, text: str, clear_first: bool = True):
        """Inputga matn kiritish."""
        self._ensure_page()
        logger.info(f"[WebDriver] Typing into {selector}: {text[:30]}...")
        if clear_first:
            await self.page.fill(selector, text)
        else:
            await self.page.type(selector, text)

    async def press_key(self, key: str):
        """Klaviatura tugmasini bosish (Enter, Tab, Escape va h.k.)."""
        self._ensure_page()
        await self.page.keyboard.press(key)

    async def select_option(self, selector: str, value: str):
        """<select> elementidan variant tanlash."""
        self._ensure_page()
        await self.page.select_option(selector, value)

    async def check(self, selector: str):
        """Checkboxni belgilash."""
        self._ensure_page()
        await self.page.check(selector)

    async def uncheck(self, selector: str):
        """Checkboxdan belgini olib tashlash."""
        self._ensure_page()
        await self.page.uncheck(selector)

    async def upload_file(self, selector: str, file_path: str):
        """Fayl yuklash inputiga fayl qo'shish."""
        self._ensure_page()
        await self.page.set_input_files(selector, file_path)

    # ── Waiting & Assertions ───────────────────────────────

    async def wait_for_selector(self, selector: str, timeout: int = 10000, state: str = "visible"):
        """Element paydo bo'lishini kutish."""
        self._ensure_page()
        await self.page.wait_for_selector(selector, timeout=timeout, state=state)

    async def wait_for_navigation(self, timeout: int = 10000):
        """Sahifa o'tishini kutish."""
        self._ensure_page()
        await self.page.wait_for_load_state("networkidle", timeout=timeout)

    async def wait_for_url(self, url_pattern: str, timeout: int = 10000):
        """URL o'zgarishini kutish."""
        self._ensure_page()
        await self.page.wait_for_url(url_pattern, timeout=timeout)

    async def is_visible(self, selector: str) -> bool:
        """Element ko'rinadimi tekshirish."""
        self._ensure_page()
        return await self.page.is_visible(selector)

    async def is_enabled(self, selector: str) -> bool:
        """Element faolmi tekshirish."""
        self._ensure_page()
        return await self.page.is_enabled(selector)

    async def element_count(self, selector: str) -> int:
        """Selectorga mos elementlar sonini olish."""
        self._ensure_page()
        elements = await self.page.query_selector_all(selector)
        return len(elements)

    # ── Advanced: Multiple Pages / Tabs ────────────────────

    async def new_tab(self, url: Optional[str] = None) -> Page:
        """Yangi tab ochish."""
        self._ensure_page()
        page = await self.context.new_page()
        if url:
            await page.goto(url)
        self.page = page
        return page

    async def get_all_pages(self) -> List[Page]:
        """Barcha ochiq tablarni olish."""
        if not self.context:
            return []
        return self.context.pages

    async def switch_to_page(self, index: int):
        """Boshqa tabga o'tish."""
        pages = await self.get_all_pages()
        if 0 <= index < len(pages):
            self.page = pages[index]
            await self.page.bring_to_front()

    # ── JavaScript Execution ───────────────────────────────

    async def evaluate(self, expression: str) -> Any:
        """JavaScript kodini sahifada bajarish."""
        self._ensure_page()
        return await self.page.evaluate(expression)

    async def scroll_down(self, pixels: int = 500):
        """Sahifani pastga aylantirish."""
        self._ensure_page()
        await self.page.evaluate(f"window.scrollBy(0, {pixels})")

    async def scroll_to_bottom(self):
        """Sahifaning eng pastiga tushish."""
        self._ensure_page()
        await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

    async def scroll_to_element(self, selector: str):
        """Element ko'rinadigan joyga aylantirish."""
        self._ensure_page()
        element = await self.page.query_selector(selector)
        if element:
            await element.scroll_into_view_if_needed()

    # ── Cookies & Storage ──────────────────────────────────

    async def get_cookies(self) -> List[Dict]:
        """Barcha cookielarni olish."""
        if not self.context:
            return []
        return await self.context.cookies()

    async def set_cookies(self, cookies: List[Dict]):
        """Cookielarni o'rnatish."""
        if self.context:
            await self.context.add_cookies(cookies)

    async def clear_cookies(self):
        """Barcha cookielarni tozalash."""
        if self.context:
            await self.context.clear_cookies()

    # ── Table / List Data Extraction ───────────────────────

    async def extract_table_data(self, table_selector: str = "table") -> List[List[str]]:
        """HTML jadvaldan barcha ma'lumotlarni olish."""
        self._ensure_page()
        return await self.page.evaluate(f"""
            (() => {{
                const table = document.querySelector('{table_selector}');
                if (!table) return [];
                const rows = table.querySelectorAll('tr');
                return Array.from(rows).map(row => {{
                    const cells = row.querySelectorAll('td, th');
                    return Array.from(cells).map(cell => cell.innerText.trim());
                }});
            }})()
        """)

    async def extract_links(self, selector: str = "a") -> List[Dict[str, str]]:
        """Sahifadagi barcha havolalarni olish."""
        self._ensure_page()
        return await self.page.evaluate(f"""
            (() => {{
                const links = document.querySelectorAll('{selector}');
                return Array.from(links).map(a => ({{
                    text: a.innerText.trim(),
                    href: a.href
                }}));
            }})()
        """)


# Sinov uchun
async def main():
    driver = OishaWebDriver()
    await driver.start(headless=False)
    await driver.goto("https://google.com")
    title = await driver.get_title()
    print(f"Page title: {title}")
    await asyncio.sleep(2)
    await driver.take_screenshot("google.png")
    await driver.stop()


if __name__ == "__main__":
    asyncio.run(main())
