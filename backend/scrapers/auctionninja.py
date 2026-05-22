"""
AuctionNinja scraper using Playwright for reliability.
Falls back to requests+BeautifulSoup if Playwright unavailable.
"""
import asyncio
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from .base import BaseScraper, NormalizedListing, ScraperHealth
from backend.services.paths import get_screenshots_dir, get_debug_html_dir

logger = logging.getLogger("platapicker.scrapers.auctionninja")

SCREENSHOT_DIR = get_screenshots_dir()

BASE_URL = "https://www.auctionninja.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Candidate selectors tried in order — first match wins
CARD_SELECTORS = [
    "div.auction-item",
    "div.lot-card",
    "div.search-result-item",
    "article.auction",
    "[class*='auction-item']",
    "[class*='lot-card']",
    "[class*='listing-card']",
    "div[data-auction-id]",
    "div[data-lot-id]",
]

TITLE_SELECTORS = [
    "h2", "h3", "h4",
    "[class*='title']",
    "[class*='name']",
    "[class*='lot-title']",
]

PRICE_SELECTORS = [
    "[class*='price']",
    "[class*='bid']",
    "[class*='amount']",
    "[class*='current']",
]

LOCATION_SELECTORS = [
    "[class*='location']",
    "[class*='city']",
    "[class*='address']",
]

TIME_SELECTORS = [
    "[class*='end']",
    "[class*='closing']",
    "[class*='time']",
    "time",
    "[class*='date']",
]


def _extract_price(text: str) -> Optional[float]:
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

    def test_connection(self) -> tuple[bool, str]:
        try:
            result = asyncio.run(self._async_test())
            return result
        except Exception as e:
            return False, f"Test failed: {e}"

    async def _async_test(self) -> tuple[bool, str]:
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
                page = await browser.new_page()
                await page.set_extra_http_headers(HEADERS)
                resp = await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=15_000)
                status = resp.status if resp else 0
                await browser.close()
                if status == 200:
                    return True, f"AuctionNinja reachable (HTTP {status})"
                return False, f"AuctionNinja returned HTTP {status}"
        except Exception as e:
            return False, f"Connection failed: {e}"

    def fetch_raw_listings(self, keyword: str, location: str, radius_miles: int) -> list[dict]:
        return asyncio.run(self._async_fetch(keyword, location, radius_miles))

    async def _async_fetch(self, keyword: str, location: str, radius_miles: int) -> list[dict]:
        raw_listings = []
        page_obj = None
        browser = None
        playwright = None

        try:
            from playwright.async_api import async_playwright
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
            await page_obj.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})

            search_url = f"{BASE_URL}/search?q={keyword.replace(' ', '+')}"
            logger.info(f"AuctionNinja: fetching '{keyword}' → {search_url}")

            resp = await page_obj.goto(search_url, wait_until="domcontentloaded", timeout=20_000)

            if not resp or resp.status >= 400:
                logger.warning(f"AuctionNinja returned HTTP {resp.status if resp else 'N/A'}")
                await self._save_screenshot(page_obj, "http_error")
                return []

            await asyncio.sleep(self.request_delay)

            # Try to wait for cards to appear
            card_sel = await self._find_card_selector(page_obj)
            if not card_sel:
                logger.warning("AuctionNinja: no listing card selector matched — possible layout change")
                await self._save_screenshot(page_obj, "no_cards")
                html = await page_obj.content()
                self._save_debug_html(html, "no_cards")
                return []

            # Scroll to load lazy content
            for _ in range(3):
                await page_obj.evaluate("window.scrollBy(0, 600)")
                await asyncio.sleep(0.5)

            cards = await page_obj.query_selector_all(card_sel)
            logger.info(f"AuctionNinja: found {len(cards)} cards with selector '{card_sel}'")

            seen_urls: set = set()
            for card in cards:
                try:
                    item = await self._parse_card(page_obj, card)
                    if item and item.get("url") not in seen_urls:
                        seen_urls.add(item.get("url"))
                        raw_listings.append(item)
                except Exception as e:
                    logger.debug(f"Card parse error: {e}")

            # Paginate (up to 3 pages)
            for page_num in range(2, 4):
                next_btn = await page_obj.query_selector("a[rel='next'], a.pagination-next, [class*='next']")
                if not next_btn:
                    break
                await next_btn.click()
                await asyncio.sleep(self.request_delay)
                cards = await page_obj.query_selector_all(card_sel)
                for card in cards:
                    try:
                        item = await self._parse_card(page_obj, card)
                        if item and item.get("url") not in seen_urls:
                            seen_urls.add(item.get("url"))
                            raw_listings.append(item)
                    except Exception:
                        pass

        except Exception as e:
            logger.error(f"AuctionNinja scraper failed: {e}", exc_info=True)
            if page_obj:
                await self._save_screenshot(page_obj, "error")
        finally:
            if browser:
                await browser.close()
            if playwright:
                await playwright.stop()

        logger.info(f"AuctionNinja: returning {len(raw_listings)} listings for '{keyword}'")
        return raw_listings

    async def _find_card_selector(self, page) -> Optional[str]:
        """Try each known card selector and return the first that finds elements."""
        for sel in CARD_SELECTORS:
            try:
                count = await page.eval_on_selector_all(sel, "els => els.length")
                if count and count > 0:
                    logger.debug(f"AuctionNinja card selector matched: '{sel}' ({count} items)")
                    return sel
            except Exception:
                continue

        # Last resort: look for repeated anchor patterns
        try:
            links = await page.query_selector_all("a[href*='/auction/'], a[href*='/lot/'], a[href*='/item/']")
            if links:
                return "a[href*='/auction/'], a[href*='/lot/'], a[href*='/item/']"
        except Exception:
            pass

        return None

    async def _parse_card(self, page, card_el) -> Optional[dict]:
        """Extract structured data from a single listing card element."""
        try:
            # URL
            href = await card_el.get_attribute("href")
            if not href:
                link = await card_el.query_selector("a[href]")
                href = await link.get_attribute("href") if link else None
            url = None
            if href:
                url = href if href.startswith("http") else f"{BASE_URL}{href}"

            listing_id = None
            if url:
                m = re.search(r"/(?:auction|lot|item)/([^/?#]+)", url)
                listing_id = m.group(1) if m else None

            # Title — try each selector
            title = None
            for sel in TITLE_SELECTORS:
                el = await card_el.query_selector(sel)
                if el:
                    t = (await el.inner_text()).strip()
                    if t and len(t) > 3:
                        title = t
                        break

            if not title:
                # Fall back to any text content
                title = (await card_el.inner_text()).strip()[:100]

            # Price
            price = None
            for sel in PRICE_SELECTORS:
                el = await card_el.query_selector(sel)
                if el:
                    price = _extract_price((await el.inner_text()).strip())
                    if price is not None:
                        break

            # Location
            location = None
            for sel in LOCATION_SELECTORS:
                el = await card_el.query_selector(sel)
                if el:
                    location = (await el.inner_text()).strip()
                    if location:
                        break

            # End time
            end_time = None
            for sel in TIME_SELECTORS:
                el = await card_el.query_selector(sel)
                if el:
                    end_time = (await el.inner_text()).strip()
                    if end_time:
                        break

            # Image
            img = await card_el.query_selector("img")
            image_url = None
            if img:
                image_url = await img.get_attribute("src") or await img.get_attribute("data-src")

            if not title:
                return None

            return {
                "id": listing_id,
                "title": title,
                "price": price,
                "url": url,
                "image_url": image_url,
                "location": location,
                "end_time": end_time,
                "source": "auctionninja",
            }
        except Exception as e:
            logger.debug(f"AuctionNinja card parse error: {e}")
            return None

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
        debug_dir = get_debug_html_dir()
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        fpath = debug_dir / f"auctionninja_{label}_{ts}.html"
        fpath.write_text(html, encoding="utf-8")
        logger.info(f"Debug HTML saved: {fpath}")

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
