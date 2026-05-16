"""
eBay sold-listings market value service.

Fetches completed/sold listings from eBay to estimate the fair market value
of a search term, with a DB cache to avoid hammering eBay on every scrape run.
"""
import logging
import re
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote_plus

from sqlalchemy.orm import Session

from backend.models.models import MarketValueCache

logger = logging.getLogger("platapicker.market_value")

EBAY_SOLD_URL = (
    "https://www.ebay.com/sch/i.html?_nkw={keyword}&LH_Sold=1&LH_Complete=1&_sop=13"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


@dataclass
class MarketValueEstimate:
    keyword: str
    median_price: Optional[float]
    mean_price: Optional[float]
    min_price: Optional[float]
    max_price: Optional[float]
    sample_count: int
    source: str = "ebay_sold"
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    error: Optional[str] = None


def _parse_price(text: str) -> Optional[float]:
    """Extract the first dollar amount from a price string like '$12.99' or '$10.00 to $20.00'."""
    text = text.strip()
    match = re.search(r"\$?([\d,]+(?:\.\d+)?)", text.replace(",", ""))
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def _fetch_with_requests(url: str) -> Optional[str]:
    try:
        import requests
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            return resp.text
        logger.warning(f"eBay returned HTTP {resp.status_code}")
        return None
    except Exception as e:
        logger.warning(f"requests fetch failed: {e}")
        return None


def _fetch_with_playwright(url: str) -> Optional[str]:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=HEADERS["User-Agent"])
            page.goto(url, timeout=30000)
            page.wait_for_timeout(3000)
            html = page.content()
            browser.close()
            return html
    except Exception as e:
        logger.warning(f"playwright fetch failed: {e}")
        return None


def _parse_prices_from_html(html: str) -> list[float]:
    """Parse sold listing prices from eBay search results HTML."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error("BeautifulSoup4 not installed — cannot parse eBay HTML")
        return []

    soup = BeautifulSoup(html, "html.parser")
    prices: list[float] = []

    # eBay listing cards: li.s-item or div.s-item__wrapper
    items = soup.select("li.s-item")
    if not items:
        items = soup.select("div.s-item__wrapper")

    for item in items:
        # Skip the ghost "Shop on eBay" card that eBay injects
        title_el = item.select_one(".s-item__title")
        if title_el and "shop on ebay" in title_el.get_text(strip=True).lower():
            continue

        price_el = item.select_one(".s-item__price")
        if not price_el:
            continue

        price_text = price_el.get_text(strip=True)
        price = _parse_price(price_text)
        if price is not None and price > 0:
            prices.append(price)

    return prices


def _trim_outliers(prices: list[float], pct: float = 0.10) -> list[float]:
    """Drop the top and bottom `pct` fraction of prices."""
    if not prices:
        return prices
    prices_sorted = sorted(prices)
    n = len(prices_sorted)
    cut = int(n * pct)
    if cut == 0:
        return prices_sorted
    return prices_sorted[cut : n - cut] if n - cut > cut else prices_sorted


def _fetch_ebay_prices(keyword: str, use_playwright: bool = False) -> tuple[list[float], Optional[str]]:
    """Fetch and parse sold prices from eBay. Returns (prices, error_msg)."""
    url = EBAY_SOLD_URL.format(keyword=quote_plus(keyword))
    logger.info(f"Fetching eBay sold listings for '{keyword}': {url}")

    html = _fetch_with_requests(url)

    if not html and use_playwright:
        logger.info("requests blocked or failed — falling back to Playwright")
        html = _fetch_with_playwright(url)

    if not html:
        return [], "Failed to fetch eBay page (requests and Playwright both failed or disabled)"

    prices = _parse_prices_from_html(html)
    logger.info(f"Parsed {len(prices)} raw prices for '{keyword}'")
    return prices, None


def _cache_to_estimate(cache_row: MarketValueCache, keyword: str) -> MarketValueEstimate:
    return MarketValueEstimate(
        keyword=keyword,
        median_price=cache_row.median_price,
        mean_price=cache_row.mean_price,
        min_price=cache_row.min_price,
        max_price=cache_row.max_price,
        sample_count=cache_row.sample_count or 0,
        source=cache_row.source or "ebay_sold",
        fetched_at=cache_row.fetched_at or datetime.utcnow(),
    )


def get_market_value(
    keyword: str,
    category: str = None,
    db: Session = None,
    max_age_hours: int = 24,
    use_playwright: bool = False,
) -> MarketValueEstimate:
    """
    Estimate the market value for a keyword using eBay sold listings.

    1. Checks MarketValueCache for a fresh (non-expired) entry.
    2. On cache miss, fetches from eBay, trims outliers, computes stats.
    3. Stores result in cache with expires_at = now + max_age_hours.
    """
    now = datetime.utcnow()

    # --- Cache lookup ---
    if db is not None:
        q = db.query(MarketValueCache).filter(
            MarketValueCache.keyword == keyword,
            MarketValueCache.category == category,
        )
        cache_row = q.first()
        if cache_row and cache_row.expires_at and cache_row.expires_at > now:
            logger.info(f"Cache hit for '{keyword}' (category={category})")
            return _cache_to_estimate(cache_row, keyword)

    # --- Fetch from eBay ---
    raw_prices, error = _fetch_ebay_prices(keyword, use_playwright=use_playwright)

    if error or not raw_prices:
        estimate = MarketValueEstimate(
            keyword=keyword,
            median_price=None,
            mean_price=None,
            min_price=None,
            max_price=None,
            sample_count=0,
            error=error or "No sold listings found",
        )
        return estimate

    trimmed = _trim_outliers(raw_prices, pct=0.10)

    median_price = round(statistics.median(trimmed), 2) if trimmed else None
    mean_price = round(statistics.mean(trimmed), 2) if trimmed else None
    min_price = round(min(trimmed), 2) if trimmed else None
    max_price = round(max(trimmed), 2) if trimmed else None
    sample_count = len(trimmed)

    estimate = MarketValueEstimate(
        keyword=keyword,
        median_price=median_price,
        mean_price=mean_price,
        min_price=min_price,
        max_price=max_price,
        sample_count=sample_count,
        fetched_at=now,
    )

    # --- Store/update cache ---
    if db is not None:
        expires_at = now + timedelta(hours=max_age_hours)
        cache_row = db.query(MarketValueCache).filter(
            MarketValueCache.keyword == keyword,
            MarketValueCache.category == category,
        ).first()

        if cache_row:
            cache_row.median_price = median_price
            cache_row.mean_price = mean_price
            cache_row.min_price = min_price
            cache_row.max_price = max_price
            cache_row.sample_count = sample_count
            cache_row.fetched_at = now
            cache_row.expires_at = expires_at
        else:
            cache_row = MarketValueCache(
                keyword=keyword,
                category=category,
                median_price=median_price,
                mean_price=mean_price,
                min_price=min_price,
                max_price=max_price,
                sample_count=sample_count,
                fetched_at=now,
                expires_at=expires_at,
            )
            db.add(cache_row)

        try:
            db.flush()
        except Exception as e:
            logger.warning(f"Failed to cache market value for '{keyword}': {e}")

    logger.info(
        f"Market value for '{keyword}': median=${median_price}, "
        f"mean=${mean_price}, n={sample_count}"
    )
    return estimate
