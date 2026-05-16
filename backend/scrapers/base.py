"""Base scraper interface that all scrapers must implement."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger("platapicker.scrapers")


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
