"""
AuctionNinja scraper.

AuctionNinja serves server-rendered HTML, so the primary path is a simple
requests + BeautifulSoup fetch of the marketplace search results page. A
Playwright fetch of the same URL is kept as a fallback in case requests is
ever blocked.

The public search form (name="srch_itemsfrm", action="search_mid.php") posts a
``keyword`` and JS-redirects to ``marketplace-items?keyword=…``. We hit that
results page directly. Each result is a ``div.iteam-result-box`` wrapping a
``div.hot-items-box-in`` with a ``.hot-items-title a`` and a ``.hot-items-bottoms p``
current-bid line; the numeric item id is the trailing ``-<id>.html`` in the URL.
"""
import asyncio
import logging
import random
import re
import time
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, NormalizedListing, get_with_retry
from backend.services.paths import get_screenshots_dir, get_debug_html_dir

logger = logging.getLogger("platapicker.scrapers.auctionninja")

SCREENSHOT_DIR = get_screenshots_dir()

BASE_URL = "https://www.auctionninja.com"
SEARCH_URL = f"{BASE_URL}/marketplace-items"

# Up to this many result pages per keyword (20 items per page).
MAX_PAGES = 3
RESULTS_PER_PAGE = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Results-grid card. Scoped under .iteam-result-box so we don't pick up the
# "hot items" sidebar widget, which shares the inner .hot-items-box-in markup.
CARD_SELECTOR = "div.iteam-result-box div.hot-items-box-in"


def _extract_price(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    match = re.search(r"\$?([\d,]+\.?\d*)", text.replace(",", ""))
    if match:
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


class AuctionNinjaScraper(BaseScraper):
    name = "auctionninja"

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.request_delay = self.config.get("request_delay_seconds", 2)
        self._last_screenshot: Optional[str] = None
        self._session = requests.Session()
        self._session.headers.update(HEADERS)

    # ------------------------------------------------------------------
    # BaseScraper interface
    # ------------------------------------------------------------------

    def test_connection(self) -> tuple[bool, str]:
        try:
            resp = self._session.get(BASE_URL, timeout=15)
            if resp.status_code == 200:
                return True, f"AuctionNinja reachable (HTTP {resp.status_code})"
            return False, f"AuctionNinja returned HTTP {resp.status_code}"
        except Exception as e:
            return False, f"Connection failed: {e}"

    def fetch_raw_listings(self, keyword: str, location: str, radius_miles: int) -> list[dict]:
        results: list[dict] = []
        seen_urls: set = set()

        for page in range(1, MAX_PAGES + 1):
            page_items = self._fetch_page(keyword, page)

            # Page 1 failure → try the Playwright fallback once before giving up.
            if page_items is None:
                if page == 1:
                    logger.info("AuctionNinja: requests fetch failed, trying Playwright fallback")
                    page_items = self._fetch_page_playwright(keyword, page)
                if not page_items:
                    break

            new = 0
            for item in page_items:
                key = item.get("url") or item.get("id")
                if key and key in seen_urls:
                    continue
                if key:
                    seen_urls.add(key)
                results.append(item)
                new += 1

            # Stop when a page adds nothing new or returns a short (final) page.
            if new == 0 or len(page_items) < RESULTS_PER_PAGE:
                break

            if page < MAX_PAGES:
                time.sleep(random.uniform(self.request_delay, self.request_delay + 1))

        logger.info(f"AuctionNinja: returning {len(results)} listings for '{keyword}'")
        return results

    def _fetch_page(self, keyword: str, page: int) -> Optional[list[dict]]:
        """Fetch one results page via requests. None on failure, list on success."""
        params = {"keyword": keyword}
        if page > 1:
            params["Page"] = page
        try:
            resp = get_with_retry(
                self._session, self._build_url(keyword, page), timeout=20, log=logger
            )
            if resp.status_code != 200:
                logger.warning(f"AuctionNinja: HTTP {resp.status_code} for page {page}")
                return None
            soup = BeautifulSoup(resp.text, "html.parser")
            return self._parse_results(soup, keyword, page)
        except requests.exceptions.RequestException as e:
            logger.warning(f"AuctionNinja requests fetch failed: {e}")
            return None

    @staticmethod
    def _build_url(keyword: str, page: int) -> str:
        kw = requests.utils.quote(keyword)
        if page > 1:
            return f"{SEARCH_URL}?Page={page}&keyword={kw}"
        return f"{SEARCH_URL}?keyword={kw}"

    def _parse_results(self, soup: BeautifulSoup, keyword: str, page: int) -> list[dict]:
        cards = soup.select(CARD_SELECTOR)
        if not cards:
            logger.warning(
                f"AuctionNinja: no result cards for '{keyword}' (page {page}) — "
                "possible layout change or no results"
            )
            self._save_debug_html(str(soup)[:500_000], "no_cards")
            return []

        items: list[dict] = []
        for card in cards:
            try:
                item = self._parse_card(card)
                if item:
                    items.append(item)
            except Exception as e:
                logger.debug(f"AuctionNinja card parse error: {e}")

        logger.info(f"AuctionNinja: parsed {len(items)} of {len(cards)} cards (page {page})")
        return items

    def _parse_card(self, card) -> Optional[dict]:
        anchor = card.select_one(".hot-items-title a") or card.select_one("a[href*='/product/']")
        if not anchor:
            return None

        title = anchor.get_text(strip=True)
        href = anchor.get("href", "")
        url = href if href.startswith("http") else f"{BASE_URL}/{href.lstrip('/')}"

        if not title:
            return None

        m = re.search(r"-(\d+)\.html", url)
        listing_id = m.group(1) if m else None

        price_el = card.select_one(".hot-items-bottoms p") or card.select_one("[id^='CURBIDID']")
        price = _extract_price(price_el.get_text(strip=True)) if price_el else None

        time_el = card.select_one(".day-left")
        end_time = time_el.get_text(strip=True) if time_el else None

        img = card.select_one("img")
        image_url = None
        if img:
            image_url = img.get("src") or img.get("data-src")

        return {
            "id": listing_id,
            "title": title,
            "price": price,
            "url": url,
            "image_url": image_url,
            "location": None,
            "end_time": end_time,
            "source": "auctionninja",
        }

    # ------------------------------------------------------------------
    # Playwright fallback (same URL, only used if requests is blocked)
    # ------------------------------------------------------------------

    def _fetch_page_playwright(self, keyword: str, page: int) -> Optional[list[dict]]:
        try:
            return asyncio.run(self._async_playwright_fetch(keyword, page))
        except Exception as e:
            logger.warning(f"AuctionNinja Playwright fallback failed: {e}")
            return None

    async def _async_playwright_fetch(self, keyword: str, page: int) -> Optional[list[dict]]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.debug("Playwright not available, skipping AuctionNinja fallback")
            return None

        url = self._build_url(keyword, page)
        browser = None
        playwright = None
        try:
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            )
            context = await browser.new_context(
                user_agent=HEADERS["User-Agent"],
                viewport={"width": 1280, "height": 900},
            )
            page_obj = await context.new_page()
            resp = await page_obj.goto(url, wait_until="domcontentloaded", timeout=20_000)
            if not resp or resp.status >= 400:
                logger.warning(
                    f"AuctionNinja Playwright: HTTP {resp.status if resp else 'N/A'}"
                )
                await self._save_screenshot(page_obj, "http_error")
                return None
            await asyncio.sleep(self.request_delay)
            html = await page_obj.content()
            soup = BeautifulSoup(html, "html.parser")
            return self._parse_results(soup, keyword, page) or None
        finally:
            if browser:
                await browser.close()
            if playwright:
                await playwright.stop()

    async def _save_screenshot(self, page, label: str) -> Optional[str]:
        try:
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            path = str(SCREENSHOT_DIR / f"auctionninja_{label}_{ts}.png")
            await page.screenshot(path=path, full_page=True)
            self._last_screenshot = path
            logger.info(f"Screenshot saved: {path}")
            return path
        except Exception:
            return None

    def _save_debug_html(self, html: str, label: str):
        try:
            debug_dir = get_debug_html_dir()
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            fpath = debug_dir / f"auctionninja_{label}_{ts}.html"
            fpath.write_text(html, encoding="utf-8")
            logger.info(f"Debug HTML saved: {fpath}")
        except Exception:
            pass

    # ------------------------------------------------------------------

    def parse_listing(self, raw: dict) -> Optional[NormalizedListing]:
        if not raw.get("title"):
            return None
        return NormalizedListing(
            source=self.name,
            source_listing_id=raw.get("id"),
            title=raw["title"],
            description=raw.get("description", ""),
            price=raw.get("price"),
            url=raw.get("url"),
            image_url=raw.get("image_url"),
            location=raw.get("location"),
            scraped_at=datetime.utcnow(),
            raw_payload=raw,
        )
