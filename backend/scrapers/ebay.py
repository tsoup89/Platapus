"""
eBay active listings scraper.
Scrapes eBay search results for Buy It Now listings sorted by price.
No API key required. Optionally uses EBAY_APP_ID for higher reliability.
"""
import json
import logging
import random
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, NormalizedListing, ScraperHealth, extract_price, get_with_retry

logger = logging.getLogger("platapicker.scrapers.ebay")

EBAY_SEARCH = "https://www.ebay.com/sch/i.html"
ITEM_BASE = "https://www.ebay.com/itm"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Connection": "keep-alive",
}


# Price ranges like "$10.00 to $50.00" yield the first (lower) amount.
_extract_price = extract_price


class EbayScraper(BaseScraper):
    name = "ebay"

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.max_listings_per_run = self.config.get("max_listings_per_run", 60)
        self.request_delay = self.config.get("request_delay_seconds", 2)
        self._session = requests.Session()
        self._session.headers.update(HEADERS)
        self._warmed_up = False

    # ------------------------------------------------------------------ #
    # BaseScraper interface
    # ------------------------------------------------------------------ #

    def test_connection(self) -> tuple[bool, str]:
        try:
            resp = self._session.get("https://www.ebay.com", timeout=10)
            if resp.status_code == 200:
                return True, "ebay.com reachable"
            return False, f"ebay.com returned HTTP {resp.status_code}"
        except Exception as e:
            return False, f"Connection failed: {e}"

    def fetch_raw_listings(self, keyword: str, location: str, radius_miles: int) -> list[dict]:
        # eBay is nationwide — location/radius not used for filtering
        results = []
        page = 1
        per_page = 60

        while len(results) < self.max_listings_per_run:
            items = self._fetch_page(keyword, page, per_page)
            if not items:
                break
            results.extend(items)
            if len(items) < per_page:
                break
            page += 1
            if page > 3:
                break
            time.sleep(random.uniform(self.request_delay, self.request_delay + 1))

        logger.info(f"eBay: fetched {len(results)} listings for '{keyword}'")
        return results[: self.max_listings_per_run]

    def parse_listing(self, raw: dict) -> Optional[NormalizedListing]:
        title = raw.get("title")
        if not title:
            return None
        price = _extract_price(raw.get("price"))
        listing_id = str(raw["id"]) if raw.get("id") else None
        url = raw.get("url") or (f"{ITEM_BASE}/{listing_id}" if listing_id else None)
        posted_at = raw.get("posted_at")
        return NormalizedListing(
            source=self.name,
            source_listing_id=listing_id,
            title=title.strip(),
            description=raw.get("description", ""),
            price=price,
            url=url,
            image_url=raw.get("image_url"),
            location=raw.get("location"),
            posted_at=posted_at,
            scraped_at=datetime.utcnow(),
            raw_payload=raw,
        )

    # ------------------------------------------------------------------ #
    # Page fetching
    # ------------------------------------------------------------------ #

    def _build_url(self, keyword: str, page: int = 1, per_page: int = 60) -> str:
        params = {
            "_nkw": keyword,
            "LH_BIN": "1",        # Buy It Now only
            "_sop": "15",          # sort: price + shipping lowest first
            "_ipg": str(per_page),
            "_pgn": str(page),
            "LH_ItemCondition": "1000|1500|2000|2500|3000",  # new + used conditions
            "_sacat": "0",
        }
        return f"{EBAY_SEARCH}?{urllib.parse.urlencode(params)}"

    def _warmup(self):
        """Visit eBay homepage to get cookies before searching."""
        if self._warmed_up:
            return
        try:
            self._session.headers["Sec-Fetch-Site"] = "none"
            self._session.get("https://www.ebay.com/", timeout=10)
            self._warmed_up = True
            time.sleep(1)
        except Exception as e:
            logger.debug(f"eBay warmup failed (non-fatal): {e}")

    def _fetch_page(self, keyword: str, page: int, per_page: int) -> list[dict]:
        self._warmup()
        url = self._build_url(keyword, page, per_page)
        try:
            self._session.headers["Referer"] = "https://www.ebay.com/"
            self._session.headers["Sec-Fetch-Site"] = "same-origin"
            resp = get_with_retry(self._session, url, timeout=15, log=logger)
            if resp.status_code == 200:
                return self._parse_html(resp.text)
            logger.warning(f"eBay: HTTP {resp.status_code} for '{keyword}' page {page}")
            return []
        except requests.RequestException as e:
            logger.warning(f"eBay request failed: {e}")
            return []

    def _parse_html(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        results = []

        # eBay's new layout uses <li class="s-card"> with data-listingid attribute
        cards = [
            li for li in soup.find_all("li", class_="s-card")
            if li.get("data-listingid")
        ]

        for card in cards:
            try:
                item = self._parse_card(card)
                if item:
                    results.append(item)
            except Exception as e:
                logger.debug(f"eBay card parse error: {e}")

        logger.debug(f"eBay: parsed {len(results)} items from {len(cards)} cards")
        return results

    def _parse_card(self, card) -> Optional[dict]:
        listing_id = card.get("data-listingid")

        # Title
        title_el = card.select_one("div.s-card__title, span.s-card__title")
        if not title_el:
            return None
        # Remove any "Opens in a new window or tab" clipped text
        for clipped in title_el.find_all(class_="clipped"):
            clipped.decompose()
        title = title_el.get_text(strip=True)
        if not title or title.lower() in ("shop on ebay", "results matching fewer words"):
            return None

        # URL — prefer the header link
        link_el = card.select_one("div.su-card-container__header a, a.s-card__link")
        url = link_el.get("href", "") if link_el else ""
        url = url.split("?")[0] if url else ""  # strip tracking params

        if not url:
            url = f"{ITEM_BASE}/{listing_id}" if listing_id else None
        if not url:
            return None

        # Price — there may be two (range); take the lower
        price_els = card.select("span.s-card__price")
        if price_els:
            prices = [_extract_price(el.get_text(strip=True)) for el in price_els]
            prices = [p for p in prices if p is not None]
            price = min(prices) if prices else None
        else:
            price = None

        # Shipping — look through attribute rows for "Free delivery" or a $ amount
        shipping_cost = 0.0
        for row in card.select("div.s-card__attribute-row"):
            row_text = row.get_text(strip=True).lower()
            if "free" in row_text and ("deliver" in row_text or "shipping" in row_text):
                shipping_cost = 0.0
                break
            elif "$" in row_text and ("deliver" in row_text or "shipping" in row_text):
                shipping_cost = _extract_price(row_text) or 0.0
                break

        if price is not None:
            price = round(price + shipping_cost, 2)

        # Image
        img_el = card.select_one("img.s-card__image, img[src*='ebayimg']")
        image_url = None
        if img_el:
            image_url = (
                img_el.get("src")
                or img_el.get("data-defer-load")
                or img_el.get("data-src")
            )

        # Location — look for "Located in ..." row
        location = None
        for row in card.select("div.s-card__attribute-row"):
            row_text = row.get_text(strip=True)
            if row_text.lower().startswith("located in"):
                location = row_text.replace("Located in ", "").strip()
                break

        # Condition
        cond_el = card.select_one("div.s-card__subtitle")
        condition = cond_el.get_text(strip=True) if cond_el else None

        return {
            "id": listing_id,
            "title": title,
            "price": price,
            "url": url,
            "image_url": image_url,
            "location": location,
            "condition": condition,
            "source": "ebay",
            "scraped_at": datetime.utcnow().isoformat(),
        }
