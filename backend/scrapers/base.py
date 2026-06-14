"""Base scraper interface that all scrapers must implement."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import logging
import random
import re
import time

import requests

logger = logging.getLogger("platapicker.scrapers")


def extract_price(val) -> Optional[float]:
    """Parse a price out of marketplace text (or pass a number through).

    Handles "$1,234.56", "1200", "$10.00 to $50.00" (returns the first/lower
    amount), int/float passthrough, and returns None when no number is found.
    Shared by all scrapers so price parsing behaves identically everywhere.
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace(",", "").replace("$", "").strip()
    m = re.search(r"\d+(?:\.\d+)?", s)
    if m:
        try:
            return float(m.group())
        except ValueError:
            pass
    return None


def get_with_retry(
    session: requests.Session,
    url: str,
    *,
    timeout: float = 15,
    max_attempts: int = 3,
    backoff_base: float = 2.0,
    log: Optional[logging.Logger] = None,
) -> requests.Response:
    """GET with exponential backoff on transient failures.

    Retries timeouts, connection errors, and HTTP 429/5xx with jittered
    exponential backoff. Other statuses (404, 403, etc.) are returned
    immediately for the caller to handle — they won't change on retry.

    Returns the final Response (which may still carry an error status after
    retries are exhausted). Raises the last network exception if every
    attempt failed before getting a response.
    """
    log = log or logger
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = session.get(url, timeout=timeout)
        except (requests.Timeout, requests.ConnectionError) as e:
            last_exc = e
            reason = f"{type(e).__name__}: {e}"
        else:
            if resp.status_code != 429 and resp.status_code < 500:
                return resp
            if attempt == max_attempts:
                return resp
            reason = f"HTTP {resp.status_code}"
        if attempt < max_attempts:
            delay = backoff_base * (2 ** (attempt - 1)) + random.uniform(0, 1)
            log.warning(
                f"Transient failure ({reason}) for {url} — "
                f"retrying in {delay:.1f}s (attempt {attempt}/{max_attempts})"
            )
            time.sleep(delay)
    raise last_exc


@dataclass
class NormalizedListing:
    source: str
    source_listing_id: Optional[str]
    title: str
    description: str = ""
    price: Optional[float] = None
    url: Optional[str] = None
    image_url: Optional[str] = None
    location: Optional[str] = None
    distance_miles: Optional[float] = None
    seller: Optional[str] = None
    posted_at: Optional[datetime] = None
    scraped_at: datetime = field(default_factory=datetime.utcnow)
    raw_payload: dict = field(default_factory=dict)


@dataclass
class ScraperHealth:
    name: str
    status: str = "unknown"
    last_run_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    raw_count: int = 0
    parsed_count: int = 0
    filtered_count: int = 0
    duplicate_count: int = 0
    alert_count: int = 0
    last_error: Optional[str] = None
    debug_artifact_path: Optional[str] = None
    extra: dict = field(default_factory=dict)


class BaseScraper(ABC):
    name: str = "base"

    def __init__(self, config: dict = None):
        self.config = config or {}
        self._logger = logging.getLogger(f"platapicker.scrapers.{self.name}")

    @abstractmethod
    def fetch_raw_listings(self, keyword: str, location: str, radius_miles: int) -> list[dict]:
        """Fetch raw listings from source. Return list of raw dicts."""
        ...

    @abstractmethod
    def parse_listing(self, raw: dict) -> Optional[NormalizedListing]:
        """Parse a single raw listing dict into a NormalizedListing."""
        ...

    def normalize_listing(self, raw: dict) -> Optional[NormalizedListing]:
        try:
            return self.parse_listing(raw)
        except Exception as e:
            self._logger.warning(f"Failed to parse listing: {e} | raw: {str(raw)[:200]}")
            return None

    def run(self, keyword: str, location: str, radius_miles: int) -> tuple[list[NormalizedListing], ScraperHealth]:
        health = ScraperHealth(name=self.name)
        listings = []
        try:
            raw_items = self.fetch_raw_listings(keyword, location, radius_miles)
            health.raw_count = len(raw_items)
            for raw in raw_items:
                listing = self.normalize_listing(raw)
                if listing:
                    listings.append(listing)
            health.parsed_count = len(listings)
            health.status = "healthy"
        except Exception as e:
            health.status = "failed"
            health.last_error = str(e)
            self._logger.error(f"Scraper {self.name} failed: {e}", exc_info=True)
        return listings, health

    def test_connection(self) -> tuple[bool, str]:
        """Quick connectivity check. Returns (ok, message)."""
        return True, "Not implemented"
