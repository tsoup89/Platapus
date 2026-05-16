"""Mock scraper for testing and development."""
from datetime import datetime
from typing import Optional
from .base import BaseScraper, NormalizedListing

MOCK_LISTINGS = [
    {
        "id": "mock-001",
        "title": "Nintendo GameCube Bundle - Mario Kart Double Dash, Melee, Sunshine",
        "description": "Selling my GameCube bundle. Includes console, 2 controllers, memory card, and 3 games: Mario Kart Double Dash, Super Smash Bros Melee, Super Mario Sunshine. All working great.",
        "price": 180.0,
        "url": "https://mock.example.com/listing/001",
        "image_url": None,
        "location": "Brooklyn, NY",
        "seller": "mock_seller_1",
    },
    {
        "id": "mock-002",
        "title": "Rancilio Silvia Espresso Machine - Excellent Condition",
        "description": "Rancilio Silvia v6, purchased 2022. Barely used. Includes tamper and portafilter. Asking $350.",
        "price": 350.0,
        "url": "https://mock.example.com/listing/002",
        "image_url": None,
        "location": "Manhattan, NY",
        "seller": "mock_seller_2",
    },
    {
        "id": "mock-003",
        "title": "Brown Jordan Outdoor Patio Set - 6 Chairs + Table",
        "description": "Beautiful Brown Jordan patio set. Table and 6 chairs in excellent condition. Minor surface scratches. Originally $3,000.",
        "price": 600.0,
        "url": "https://mock.example.com/listing/003",
        "image_url": None,
        "location": "Queens, NY",
        "seller": "mock_seller_3",
    },
    {
        "id": "mock-004",
        "title": "GameCube games lot - Wind Waker, Mario Party 7, Madden 2003",
        "description": "Lot of GameCube games. Wind Waker complete with box and manual, Mario Party 7 disc only, Madden 2003 complete.",
        "price": 95.0,
        "url": "https://mock.example.com/listing/004",
        "image_url": None,
        "location": "Staten Island, NY",
        "seller": "mock_seller_4",
    },
    {
        "id": "mock-005",
        "title": "Profitec Pro 300 Dual Boiler Espresso Machine",
        "description": "Profitec Pro 300, 2021 model. Works perfectly. Selling because upgrading. $700.",
        "price": 700.0,
        "url": "https://mock.example.com/listing/005",
        "image_url": None,
        "location": "Hoboken, NJ",
        "seller": "mock_seller_5",
    },
]


class MockScraper(BaseScraper):
    name = "mock"

    def fetch_raw_listings(self, keyword: str, location: str, radius_miles: int) -> list[dict]:
        keyword_lower = keyword.lower()
        return [
            item for item in MOCK_LISTINGS
            if keyword_lower in item["title"].lower() or keyword_lower in item["description"].lower()
        ] or MOCK_LISTINGS[:2]

    def parse_listing(self, raw: dict) -> Optional[NormalizedListing]:
        return NormalizedListing(
            source=self.name,
            source_listing_id=raw.get("id"),
            title=raw["title"],
            description=raw.get("description", ""),
            price=raw.get("price"),
            url=raw.get("url"),
            image_url=raw.get("image_url"),
            location=raw.get("location"),
            seller=raw.get("seller"),
            scraped_at=datetime.utcnow(),
            raw_payload=raw,
        )

    def test_connection(self) -> tuple[bool, str]:
        return True, "Mock scraper always available"
