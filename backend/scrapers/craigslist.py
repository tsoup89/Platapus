"""
Craigslist scraper using requests + BeautifulSoup.
Tries the JSON endpoint first; falls back to HTML parsing.
Optionally uses Playwright if both HTTP approaches are blocked.
"""
import json
import logging
import random
import re
import time
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, NormalizedListing
from backend.services.paths import get_screenshots_dir

logger = logging.getLogger("platapicker.scrapers.craigslist")

BASE_URL = "https://craigslist.org"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Maximum number of pages to fetch per keyword (120 results per page)
MAX_PAGES = 5
RESULTS_PER_PAGE = 120

# Mapping of common "City, ST" location strings to Craigslist city subdomains
CITY_SUBDOMAIN_MAP: dict[str, str] = {
    # Major metros
    "new york, ny": "newyork",
    "new york city, ny": "newyork",
    "nyc": "newyork",
    "los angeles, ca": "losangeles",
    "la, ca": "losangeles",
    "chicago, il": "chicago",
    "houston, tx": "houston",
    "phoenix, az": "phoenix",
    "philadelphia, pa": "philadelphia",
    "san antonio, tx": "sanantonio",
    "san diego, ca": "sandiego",
    "dallas, tx": "dallas",
    "san jose, ca": "sfbay",
    "austin, tx": "austin",
    "jacksonville, fl": "jacksonville",
    "fort worth, tx": "dallas",
    "columbus, oh": "columbus",
    "charlotte, nc": "charlotte",
    "indianapolis, in": "indianapolis",
    "san francisco, ca": "sfbay",
    "sf, ca": "sfbay",
    "seattle, wa": "seattle",
    "denver, co": "denver",
    "washington, dc": "washingtondc",
    "dc": "washingtondc",
    "nashville, tn": "nashville",
    "oklahoma city, ok": "oklahomacity",
    "el paso, tx": "elpaso",
    "boston, ma": "boston",
    "portland, or": "portland",
    "las vegas, nv": "lasvegas",
    "louisville, ky": "louisville",
    "baltimore, md": "baltimore",
    "milwaukee, wi": "milwaukee",
    "albuquerque, nm": "albuquerque",
    "tucson, az": "tucson",
    "fresno, ca": "fresno",
    "mesa, az": "phoenix",
    "sacramento, ca": "sacramento",
    "atlanta, ga": "atlanta",
    "kansas city, mo": "kansascity",
    "omaha, ne": "omaha",
    "cleveland, oh": "cleveland",
    "raleigh, nc": "raleigh",
    "virginia beach, va": "norfolk",
    "miami, fl": "miami",
    "minneapolis, mn": "minneapolis",
    "tampa, fl": "tampa",
    "new orleans, la": "neworleans",
    "detroit, mi": "detroit",
    "pittsburgh, pa": "pittsburgh",
    "richmond, va": "richmond",
    "orlando, fl": "orlando",
    "salt lake city, ut": "saltlakecity",
}


def _location_to_subdomain(location: str) -> str:
    """
    Convert a human-readable location string to a Craigslist city subdomain.
    Falls back to a simple slug of the first component before the comma.
    """
    normalized = location.strip().lower()
    if normalized in CITY_SUBDOMAIN_MAP:
        return CITY_SUBDOMAIN_MAP[normalized]

    # Try prefix match (e.g. "New York" without state)
    for key, subdomain in CITY_SUBDOMAIN_MAP.items():
        if normalized.startswith(key.split(",")[0]):
            return subdomain

    # Generic fallback: strip spaces from the part before the comma
    city_part = normalized.split(",")[0].strip()
    slug = re.sub(r"[^a-z0-9]", "", city_part)
    logger.warning(
        f"Craigslist: unknown location '{location}', guessing subdomain '{slug}'"
    )
    return slug


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


def _parse_date(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str[:19], fmt[:len(date_str[:19])])
        except ValueError:
            continue
    return None


class CraigslistScraper(BaseScraper):
    name = "craigslist"

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.request_delay = self.config.get("request_delay_seconds", 2)
        self._session = requests.Session()
        self._session.headers.update(HEADERS)

    # ------------------------------------------------------------------
    # BaseScraper interface
    # ------------------------------------------------------------------

    def test_connection(self) -> tuple[bool, str]:
        try:
            resp = self._session.get(BASE_URL, timeout=10)
            if resp.status_code == 200:
                return True, f"craigslist.org reachable (HTTP {resp.status_code})"
            return False, f"craigslist.org returned HTTP {resp.status_code}"
        except Exception as e:
            return False, f"Connection failed: {e}"

    def fetch_raw_listings(
        self, keyword: str, location: str, radius_miles: int
    ) -> list[dict]:
        """Try JSON endpoint first; fall back to HTML parsing."""
        subdomain = _location_to_subdomain(location)
        results: list[dict] = []

        for page in range(MAX_PAGES):
            offset = page * RESULTS_PER_PAGE
            page_results = self._fetch_json_page(subdomain, keyword, offset)

            if page_results is None:
                # JSON endpoint failed — try HTML fallback (only for first page)
                if page == 0:
                    logger.info(
                        f"Craigslist: JSON endpoint failed for '{subdomain}', "
                        "falling back to HTML parsing"
                    )
                    page_results = self._fetch_html_page(subdomain, keyword, offset)
                    if page_results is None:
                        # Try Playwright as last resort
                        page_results = self._fetch_playwright_page(
                            subdomain, keyword, offset
                        )
                if not page_results:
                    break

            results.extend(page_results)

            if len(page_results) < RESULTS_PER_PAGE:
                # Last page — no point requesting another
                break

            if page < MAX_PAGES - 1:
                delay = random.uniform(self.request_delay, self.request_delay + 1)
                logger.debug(f"Craigslist: sleeping {delay:.1f}s before next page")
                time.sleep(delay)

        logger.info(
            f"Craigslist: fetched {len(results)} raw listings for "
            f"'{keyword}' in '{location}' (subdomain: {subdomain})"
        )
        return results

    def parse_listing(self, raw: dict) -> Optional[NormalizedListing]:
        title = raw.get("title") or raw.get("name")
        if not title:
            return None

        price_raw = raw.get("price")
        if isinstance(price_raw, (int, float)):
            price = float(price_raw)
        elif isinstance(price_raw, str):
            price = _extract_price(price_raw)
        else:
            price = None

        posted_at = _parse_date(raw.get("date") or raw.get("posted_at"))

        images = raw.get("images") or []
        image_url = images[0] if images else raw.get("image_url")

        return NormalizedListing(
            source=self.name,
            source_listing_id=str(raw["id"]) if raw.get("id") else None,
            title=title,
            description=raw.get("body") or raw.get("description") or "",
            price=price,
            url=raw.get("url"),
            image_url=image_url,
            location=raw.get("location"),
            posted_at=posted_at,
            scraped_at=datetime.utcnow(),
            raw_payload=raw,
        )

    # ------------------------------------------------------------------
    # JSON endpoint
    # ------------------------------------------------------------------

    def _fetch_json_page(
        self, subdomain: str, keyword: str, offset: int
    ) -> Optional[list[dict]]:
        """
        Fetch one page from the Craigslist JSON search endpoint.
        Returns list of raw dicts on success, None on failure.
        """
        url = (
            f"https://{subdomain}.craigslist.org/search/sss"
            f"?query={requests.utils.quote(keyword)}&format=json&start={offset}"
        )
        try:
            resp = self._session.get(url, timeout=15)
            if resp.status_code == 404:
                logger.error(
                    f"Craigslist: subdomain '{subdomain}' not found (HTTP 404). "
                    "Check the location mapping."
                )
                return None
            if resp.status_code == 403 or resp.status_code == 429:
                logger.warning(
                    f"Craigslist: blocked on JSON endpoint (HTTP {resp.status_code}) "
                    f"for subdomain '{subdomain}'"
                )
                return None
            if resp.status_code != 200:
                logger.warning(
                    f"Craigslist JSON: unexpected HTTP {resp.status_code} for '{url}'"
                )
                return None

            data = resp.json()
            items = data.get("items") or []
            logger.debug(
                f"Craigslist JSON: got {len(items)} items "
                f"(subdomain={subdomain}, offset={offset})"
            )
            return items

        except requests.exceptions.JSONDecodeError:
            logger.warning(
                f"Craigslist: JSON endpoint returned non-JSON for '{subdomain}'"
            )
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"Craigslist JSON request failed: {e}")
            return None

    # ------------------------------------------------------------------
    # HTML fallback
    # ------------------------------------------------------------------

    def _fetch_html_page(
        self, subdomain: str, keyword: str, offset: int
    ) -> Optional[list[dict]]:
        """
        Parse the HTML search results page using BeautifulSoup.
        Returns list of raw dicts on success, None on unrecoverable failure.
        """
        url = (
            f"https://{subdomain}.craigslist.org/search/sss"
            f"?query={requests.utils.quote(keyword)}&start={offset}"
        )
        try:
            resp = self._session.get(url, timeout=15)
            if resp.status_code == 404:
                logger.error(
                    f"Craigslist HTML: subdomain '{subdomain}' not found (HTTP 404)."
                )
                return None
            if resp.status_code not in (200, 301, 302):
                logger.warning(
                    f"Craigslist HTML: HTTP {resp.status_code} for '{url}'"
                )
                return None

            soup = BeautifulSoup(resp.text, "html.parser")
            return self._parse_html_listings(soup, subdomain)

        except requests.exceptions.RequestException as e:
            logger.warning(f"Craigslist HTML request failed: {e}")
            return None

    def _parse_html_listings(self, soup: BeautifulSoup, subdomain: str) -> list[dict]:
        """Extract listings from a parsed Craigslist search results page."""
        results: list[dict] = []

        # Try modern selector first, then legacy
        cards = soup.select("li.cl-static-search-result") or soup.select("li[data-pid]")

        if not cards:
            logger.warning(
                f"Craigslist HTML: no listing cards found for subdomain '{subdomain}'. "
                "The page layout may have changed."
            )
            return results

        for card in cards:
            try:
                item = self._parse_html_card(card, subdomain)
                if item:
                    results.append(item)
            except Exception as e:
                logger.debug(f"Craigslist HTML card parse error: {e}")

        logger.debug(
            f"Craigslist HTML: parsed {len(results)} listings from {len(cards)} cards"
        )
        return results

    def _parse_html_card(self, card, subdomain: str) -> Optional[dict]:
        """Extract data from a single Craigslist HTML listing card."""
        # Listing ID from data-pid attribute
        listing_id = card.get("data-pid") or card.get("id")

        # Title and URL
        anchor = card.select_one("a.cl-app-anchor") or card.select_one("a[href]")
        title = None
        url = None
        if anchor:
            title = anchor.get_text(strip=True) or anchor.get("title")
            href = anchor.get("href", "")
            if href:
                url = href if href.startswith("http") else f"https://{subdomain}.craigslist.org{href}"

        # Fallback title from text content
        if not title:
            title_el = card.select_one(".title") or card.select_one("[class*='title']")
            if title_el:
                title = title_el.get_text(strip=True)

        if not title:
            return None

        # Price
        price_el = card.select_one(".priceinfo") or card.select_one("[class*='price']")
        price_text = price_el.get_text(strip=True) if price_el else None
        price = _extract_price(price_text)

        # Location
        loc_el = (
            card.select_one(".location")
            or card.select_one("[class*='location']")
            or card.select_one(".hood")
        )
        location = loc_el.get_text(strip=True) if loc_el else None

        # Date
        time_el = card.select_one("time[datetime]")
        date_str = time_el.get("datetime") if time_el else None

        # Image
        img_el = card.select_one("img")
        image_url = None
        if img_el:
            image_url = img_el.get("src") or img_el.get("data-src")

        return {
            "id": listing_id,
            "title": title,
            "price": price,
            "url": url,
            "image_url": image_url,
            "location": location,
            "date": date_str,
            "_source": "html",
        }

    # ------------------------------------------------------------------
    # Playwright last-resort fallback
    # ------------------------------------------------------------------

    def _fetch_playwright_page(
        self, subdomain: str, keyword: str, offset: int
    ) -> Optional[list[dict]]:
        """Use Playwright to fetch the page if requests is blocked."""
        try:
            import asyncio
            return asyncio.run(self._async_playwright_fetch(subdomain, keyword, offset))
        except ImportError:
            logger.debug("Playwright not available, skipping Playwright fallback")
            return None
        except Exception as e:
            logger.warning(f"Craigslist Playwright fallback failed: {e}")
            return None

    async def _async_playwright_fetch(
        self, subdomain: str, keyword: str, offset: int
    ) -> Optional[list[dict]]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return None

        url = (
            f"https://{subdomain}.craigslist.org/search/sss"
            f"?query={requests.utils.quote(keyword)}&start={offset}"
        )
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
            page = await context.new_page()
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=20_000)

            if not resp or resp.status >= 400:
                logger.warning(
                    f"Craigslist Playwright: HTTP {resp.status if resp else 'N/A'} "
                    f"for subdomain '{subdomain}'"
                )
                return None

            import asyncio as _asyncio
            await _asyncio.sleep(self.request_delay)

            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            results = self._parse_html_listings(soup, subdomain)
            logger.info(
                f"Craigslist Playwright: got {len(results)} listings for '{keyword}'"
            )
            return results or None

        except Exception as e:
            logger.warning(f"Craigslist Playwright fetch error: {e}")
            return None
        finally:
            if browser:
                await browser.close()
            if playwright:
                await playwright.stop()
