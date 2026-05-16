"""AuctionNinja scraper using requests + BeautifulSoup."""
import re
import time
import logging
from datetime import datetime
from typing import Optional
import requests
from bs4 import BeautifulSoup
from .base import BaseScraper, NormalizedListing

logger = logging.getLogger("platapicker.scrapers.auctionninja")

BASE_URL = "https://www.auctionninja.com"
SEARCH_URL = f"{BASE_URL}/search"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


class AuctionNinjaScraper(BaseScraper):
    name = "auctionninja"

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.request_delay = self.config.get("request_delay_seconds", 2)
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def test_connection(self) -> tuple[bool, str]:
        try:
            resp = self.session.get(BASE_URL, timeout=10)
            if resp.status_code == 200:
                return True, f"AuctionNinja reachable (HTTP {resp.status_code})"
            return False, f"AuctionNinja returned HTTP {resp.status_code}"
        except Exception as e:
            return False, f"Connection failed: {e}"

    def fetch_raw_listings(self, keyword: str, location: str, radius_miles: int) -> list[dict]:
        raw_listings = []
        page = 1
        max_pages = 5

        while page <= max_pages:
            params = {
                "q": keyword,
                "page": page,
            }
            try:
                resp = self.session.get(SEARCH_URL, params=params, timeout=15)
                if resp.status_code != 200:
                    logger.warning(f"AuctionNinja search returned HTTP {resp.status_code} for '{keyword}'")
                    break

                soup = BeautifulSoup(resp.text, "html.parser")
                cards = self._extract_cards(soup)

                if not cards:
                    logger.info(f"No more cards found on page {page} for '{keyword}'")
                    break

                raw_listings.extend(cards)

                # Check for next page
                next_link = soup.find("a", rel="next")
                if not next_link:
                    break

                page += 1
                time.sleep(self.request_delay)

            except Exception as e:
                logger.error(f"AuctionNinja fetch error on page {page}: {e}")
                break

        logger.info(f"AuctionNinja: {len(raw_listings)} raw cards for '{keyword}'")
        return raw_listings

    def _extract_cards(self, soup: BeautifulSoup) -> list[dict]:
        """Extract raw card data from search results page."""
        cards = []

        # Try multiple selector patterns (site may change layout)
        selectors = [
            "div.auction-item",
            "div.listing-card",
            "article.auction",
            "div[class*='auction']",
            "div[class*='lot']",
        ]

        items = []
        for selector in selectors:
            items = soup.select(selector)
            if items:
                break

        if not items:
            # Fallback: look for any card-like elements with price info
            items = soup.find_all("div", attrs={"data-auction-id": True})

        for item in items:
            card = self._parse_card_element(item)
            if card:
                cards.append(card)

        return cards

    def _parse_card_element(self, element) -> Optional[dict]:
        """Parse a single search result card element."""
        try:
            title_el = (
                element.find("h2") or element.find("h3") or
                element.find(class_=re.compile(r"title|name|item-title", re.I))
            )
            title = title_el.get_text(strip=True) if title_el else None
            if not title:
                return None

            link_el = element.find("a", href=True)
            url = None
            if link_el:
                href = link_el["href"]
                url = href if href.startswith("http") else f"{BASE_URL}{href}"

            price_el = element.find(class_=re.compile(r"price|bid|amount", re.I))
            price = None
            if price_el:
                price_text = price_el.get_text(strip=True)
                price = self._extract_price(price_text)

            img_el = element.find("img")
            image_url = img_el.get("src") or img_el.get("data-src") if img_el else None

            location_el = element.find(class_=re.compile(r"location|city|zip", re.I))
            location = location_el.get_text(strip=True) if location_el else None

            end_time_el = element.find(class_=re.compile(r"end|closing|time|date", re.I))
            end_time = end_time_el.get_text(strip=True) if end_time_el else None

            listing_id = (
                element.get("data-auction-id") or
                element.get("data-id") or
                element.get("id") or
                (url.split("/")[-1] if url else None)
            )

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
            logger.debug(f"Failed to parse card element: {e}")
            return None

    def _extract_price(self, text: str) -> Optional[float]:
        match = re.search(r"\$?([\d,]+\.?\d*)", text.replace(",", ""))
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError:
                return None
        return None

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
