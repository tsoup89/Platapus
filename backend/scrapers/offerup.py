"""
OfferUp scraper using Playwright.
No login required — tries to extract __NEXT_DATA__ JSON first,
falls back to DOM parsing.
"""
import asyncio
import json
import logging
import random
import re
import urllib.parse
from datetime import datetime
from typing import Optional

from .base import BaseScraper, NormalizedListing, ScraperHealth, extract_price
from backend.services.paths import get_screenshots_dir

logger = logging.getLogger("platapicker.scrapers.offerup")

SCREENSHOT_DIR = get_screenshots_dir()

OFFERUP_BASE = "https://offerup.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

BLOCK_INDICATORS = [
    "access denied", "you have been blocked", "unusual traffic detected",
    "complete the captcha", "verify you are human"
]


_extract_price = extract_price


class OfferUpScraper(BaseScraper):
    name = "offerup"

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.min_delay = self.config.get("min_delay_seconds", 2)
        self.max_delay = self.config.get("max_delay_seconds", 5)
        self.max_listings_per_run = self.config.get("max_listings_per_run", 60)

    # ------------------------------------------------------------------ #
    # BaseScraper interface
    # ------------------------------------------------------------------ #

    def fetch_raw_listings(self, keyword: str, location: str, radius_miles: int) -> list[dict]:
        return asyncio.run(self._async_fetch(keyword, location, radius_miles))

    def parse_listing(self, raw: dict) -> Optional[NormalizedListing]:
        title = raw.get("title")
        if not title:
            return None
        # Skip sponsored/promoted placeholders and obvious spam prices
        if title.strip().lower() in ("promoted", "sponsored", "ad"):
            return None
        price_raw = raw.get("price")
        if isinstance(price_raw, float) and price_raw > 100_000:
            return None

        price_raw = raw.get("price")
        if isinstance(price_raw, (int, float)):
            price = float(price_raw)
        else:
            price = _extract_price(str(price_raw)) if price_raw else None

        return NormalizedListing(
            source=self.name,
            source_listing_id=str(raw["id"]) if raw.get("id") else None,
            title=title.strip(),
            description=raw.get("description", ""),
            price=price,
            url=raw.get("url"),
            image_url=raw.get("image_url"),
            location=raw.get("location"),
            scraped_at=datetime.utcnow(),
            raw_payload=raw,
        )

    def test_connection(self) -> tuple[bool, str]:
        return asyncio.run(self._async_test())

    async def _async_test(self) -> tuple[bool, str]:
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
                page = await browser.new_page()
                resp = await page.goto(OFFERUP_BASE, wait_until="domcontentloaded", timeout=15_000)
                await browser.close()
                if resp and resp.status < 400:
                    return True, f"offerup.com reachable (HTTP {resp.status})"
                return False, f"offerup.com returned HTTP {resp.status if resp else 'N/A'}"
        except Exception as e:
            return False, f"Connection failed: {e}"

    # ------------------------------------------------------------------ #
    # Core async fetch
    # ------------------------------------------------------------------ #

    async def _async_fetch(self, keyword: str, location: str, radius_miles: int) -> list[dict]:
        raw_listings: list[dict] = []
        playwright = None
        browser = None
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
                extra_http_headers={"Accept-Language": HEADERS["Accept-Language"]},
            )
            page = await context.new_page()

            search_url = self._build_search_url(keyword, location, radius_miles)
            logger.info(f"OfferUp: fetching '{keyword}' at {location} r={radius_miles}mi")

            # Intercept network responses to catch the listings API call
            api_data: list[dict] = []

            async def handle_response(response):
                if "/api/search" in response.url or "offerup.com/v1/listings" in response.url:
                    try:
                        body = await response.json()
                        items = (
                            body.get("data", {}).get("items")
                            or body.get("items")
                            or body.get("results")
                            or []
                        )
                        if items:
                            api_data.extend(items)
                            logger.debug(f"OfferUp: intercepted {len(items)} items from API")
                    except Exception:
                        pass

            page.on("response", handle_response)

            await page.goto(search_url, wait_until="networkidle", timeout=30_000)
            await asyncio.sleep(random.uniform(self.min_delay, self.max_delay))

            # Check for blocks — only on very explicit block pages
            content = (await page.content()).lower()
            if any(ind in content for ind in BLOCK_INDICATORS):
                logger.warning("OfferUp: possible block detected")
                await self._save_screenshot(page, "possible_block")
                return []

            # Wait for at least one listing link to appear
            try:
                await page.wait_for_selector("a[href*='/item/']", timeout=10_000)
            except Exception:
                logger.warning("OfferUp: no listing links found after wait")
                await self._save_screenshot(page, "no_listings")
                return []

            # Scroll to trigger lazy loading of remaining cards
            await self._human_scroll(page, times=5)
            await asyncio.sleep(1.0)

            # Try __NEXT_DATA__ JSON first
            listings_from_json = await self._extract_next_data(page)

            # If API intercept caught data, use that
            if api_data:
                logger.info(f"OfferUp: using {len(api_data)} items from intercepted API")
                raw_listings = [self._normalize_api_item(item) for item in api_data]
                raw_listings = [r for r in raw_listings if r]
            elif listings_from_json:
                logger.info(f"OfferUp: using {len(listings_from_json)} items from __NEXT_DATA__")
                raw_listings = listings_from_json
            else:
                logger.info("OfferUp: falling back to DOM parsing")
                raw_listings = await self._extract_dom_cards(page)

            raw_listings = raw_listings[: self.max_listings_per_run]
            logger.info(f"OfferUp: returning {len(raw_listings)} listings for '{keyword}'")

        except Exception as e:
            logger.error(f"OfferUp scraper failed: {e}", exc_info=True)
        finally:
            if browser:
                await browser.close()
            if playwright:
                await playwright.stop()

        return raw_listings

    # ------------------------------------------------------------------ #
    # URL builder
    # ------------------------------------------------------------------ #

    def _build_search_url(self, keyword: str, location: str, radius_miles: int) -> str:
        params = {
            "q": keyword,
            "location": location,
            "radius": str(radius_miles),
            "sort": "-price",  # cheapest first — good for deal hunting
        }
        return f"{OFFERUP_BASE}/search/?{urllib.parse.urlencode(params)}"

    # ------------------------------------------------------------------ #
    # Extraction strategies
    # ------------------------------------------------------------------ #

    async def _extract_next_data(self, page) -> list[dict]:
        """Try to pull listings from Next.js __NEXT_DATA__ embedded JSON."""
        try:
            next_data = await page.evaluate(
                "() => window.__NEXT_DATA__ ? JSON.stringify(window.__NEXT_DATA__) : null"
            )
            if not next_data:
                return []

            data = json.loads(next_data)
            # Walk common paths where OfferUp embeds search results
            props = data.get("props", {}).get("pageProps", {})
            candidates = (
                props.get("initialItems")
                or props.get("listings")
                or props.get("items")
                or props.get("searchResults", {}).get("items")
                or []
            )
            if not candidates:
                # Deeper search
                for key, val in props.items():
                    if isinstance(val, list) and val and isinstance(val[0], dict):
                        if val[0].get("title") or val[0].get("name"):
                            candidates = val
                            break

            results = []
            for item in candidates:
                parsed = self._normalize_api_item(item)
                if parsed:
                    results.append(parsed)
            return results
        except Exception as e:
            logger.debug(f"OfferUp __NEXT_DATA__ extraction failed: {e}")
            return []

    def _normalize_api_item(self, item: dict) -> Optional[dict]:
        """Normalize an API/JSON listing item to a flat dict."""
        try:
            item_id = (
                item.get("id")
                or item.get("listingId")
                or item.get("listing_id")
            )
            title = (
                item.get("title")
                or item.get("name")
                or item.get("listingTitle")
            )
            if not title:
                return None

            # Price — can be nested
            price = None
            price_raw = item.get("price") or item.get("listingPrice")
            if isinstance(price_raw, dict):
                price = _extract_price(
                    price_raw.get("amount") or price_raw.get("display")
                    or price_raw.get("value")
                )
            elif price_raw is not None:
                price = _extract_price(str(price_raw))

            # URL
            url = item.get("url") or item.get("itemUrl") or item.get("listingUrl")
            if not url and item_id:
                url = f"{OFFERUP_BASE}/item/detail/{item_id}/"

            # Image
            image_url = None
            photos = item.get("photos") or item.get("images") or []
            if photos and isinstance(photos[0], dict):
                image_url = photos[0].get("url") or photos[0].get("src")
            elif photos and isinstance(photos[0], str):
                image_url = photos[0]
            if not image_url:
                image_url = item.get("imageUrl") or item.get("thumbnailUrl") or item.get("image_url")

            # Location
            location = None
            loc = item.get("location") or item.get("itemLocation") or {}
            if isinstance(loc, dict):
                city = loc.get("city") or loc.get("cityName") or ""
                state = loc.get("state") or loc.get("stateAbbreviation") or ""
                location = f"{city}, {state}".strip(", ") or None
            elif isinstance(loc, str):
                location = loc

            return {
                "id": str(item_id) if item_id else None,
                "title": title,
                "price": price,
                "url": url,
                "image_url": image_url,
                "location": location,
                "source": "offerup",
                "scraped_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.debug(f"OfferUp item normalization failed: {e}")
            return None

    async def _extract_dom_cards(self, page) -> list[dict]:
        """DOM fallback — scrape listing cards directly."""
        results = []
        try:
            # OfferUp renders cards as <a> tags linking to /item/detail/{id}
            # Each <a> contains an image + text lines (title, price, location)
            card_elements = await page.query_selector_all("a[href*='/item/detail/']")

            if not card_elements:
                # Broader fallback for alternate URL formats
                card_elements = await page.query_selector_all("a[href*='/item/']")

            logger.info(f"OfferUp DOM: found {len(card_elements)} card elements")

            seen_urls: set = set()
            for el in card_elements:
                try:
                    card = await self._parse_dom_card(el)
                    if card and card.get("url") not in seen_urls:
                        seen_urls.add(card["url"])
                        results.append(card)
                except Exception as e:
                    logger.debug(f"OfferUp DOM card parse error: {e}")

        except Exception as e:
            logger.warning(f"OfferUp DOM extraction failed: {e}")
            await self._save_screenshot(page, "dom_error")

        if not results:
            logger.warning("OfferUp: zero DOM cards found — possible layout change or block")
            await self._save_screenshot(page, "zero_results")

        return results

    async def _parse_dom_card(self, el) -> Optional[dict]:
        """Parse a single listing card element."""
        href = await el.get_attribute("href")
        if not href:
            return None
        url = href if href.startswith("http") else f"{OFFERUP_BASE}{href}"

        # Extract listing ID from URL
        m = re.search(r"/item/(?:detail/)?(\d+)", url)
        listing_id = m.group(1) if m else None

        # Pull all text from the card
        raw_text = (await el.inner_text()).strip()
        lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]

        if not lines:
            return None

        # Price: first line starting with $
        price = None
        price_line_idx = None
        for i, ln in enumerate(lines):
            if ln.startswith("$"):
                price = _extract_price(ln)
                price_line_idx = i
                break

        # Title: first non-price, non-trivial line
        title = None
        for i, ln in enumerate(lines):
            if i == price_line_idx:
                continue
            if len(ln) < 3 or re.match(r"^\$", ln):
                continue
            title = ln
            break

        if not title or not url:
            return None

        # Location: last short non-price, non-title line
        location = None
        for ln in reversed(lines):
            if ln == title or (price_line_idx is not None and ln == lines[price_line_idx]):
                continue
            if 2 < len(ln) < 60 and not ln.startswith("$"):
                location = ln
                break

        # Image
        img_el = await el.query_selector("img")
        image_url = await img_el.get_attribute("src") if img_el else None

        return {
            "id": listing_id,
            "title": title,
            "price": price,
            "url": url,
            "image_url": image_url,
            "location": location,
            "source": "offerup",
            "scraped_at": datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    async def _human_scroll(self, page, times: int = 4):
        for _ in range(times):
            await page.evaluate("window.scrollBy(0, Math.random() * 400 + 200)")
            await asyncio.sleep(random.uniform(0.4, 1.0))

    async def _save_screenshot(self, page, label: str = "error") -> Optional[str]:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = str(SCREENSHOT_DIR / f"offerup_{label}_{ts}.png")
        try:
            await page.screenshot(path=path, full_page=True)
            logger.info(f"Screenshot saved: {path}")
            return path
        except Exception as e:
            logger.debug(f"Screenshot failed: {e}")
        return None
