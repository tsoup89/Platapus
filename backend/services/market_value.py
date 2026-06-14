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

# Words that appear in listing titles but don't help eBay find the right comp.
_FILLER_WORDS = {
    # Category / appliance nouns
    "coffee", "espresso", "machine", "maker", "grinder", "frother",
    "steam", "pump", "pod", "capsule", "drip", "filter", "press",
    "monitor", "display", "screen", "computer", "laptop", "gaming",
    "furniture", "outdoor", "patio", "speaker", "audio", "sound",
    "wireless", "bluetooth",
    # Descriptors / materials
    "stainless", "steel", "black", "white", "silver", "chrome",
    "matte", "glossy", "polished", "brushed", "color",
    # Condition words
    "used", "like", "new", "great", "good", "excellent", "mint",
    "condition", "works", "tested", "fully", "barely", "hardly",
    "lightly", "gently", "perfect", "clean",
    # Sale-ad filler
    "price", "sale", "reduced", "negotiable", "bundle", "set",
    "lot", "unit", "included", "comes", "free", "obo",
    # Prepositions / articles / conjunctions
    "and", "the", "in", "by", "with", "for", "or", "of", "a", "an",
    "la", "le", "el", "de", "from", "to", "at", "on", "plus", "just",
}


def extract_search_keyword(title: str, brands: Optional[list] = None) -> str:
    """
    Reduce a verbose Facebook listing title to a clean 'Brand Model' keyword
    suitable for eBay comp lookups.

    Strategy:
      1. Find the brand in the title (using the watchlist brands list as hints).
      2. Remove the brand text and any 'by' connector from the remaining title.
      3. Keep up to 3 non-filler words as the model name.
      4. Return 'Brand model1 model2 …' (or just the original title if no brand matched).
    """
    if not brands:
        return title

    title_lower = title.lower()
    found_brand = None

    # Try longest brand names first so "Nespresso Vertuo" beats "Nespresso"
    for brand in sorted(brands, key=len, reverse=True):
        if brand.lower() in title_lower:
            found_brand = brand
            break

    if not found_brand:
        return title

    # Remove the matched brand text from the title
    cleaned = re.sub(re.escape(found_brand), "", title, flags=re.IGNORECASE)
    # Drop "by" connectors that sometimes separate brand from model
    cleaned = re.sub(r"\bby\b", " ", cleaned, flags=re.IGNORECASE)

    model_words = []
    for word in cleaned.split():
        token = re.sub(r"[^\w]", "", word).lower()
        if not token or len(token) < 2:
            continue
        if token in _FILLER_WORDS:
            # Stop collecting once we have some model words and hit filler
            if model_words:
                break
            continue
        model_words.append(word.strip(",.!?-"))
        if len(model_words) >= 3:
            break

    if not model_words:
        return found_brand

    return f"{found_brand} {' '.join(model_words)}"


EBAY_SOLD_URL = (
    "https://www.ebay.com/sch/i.html?_nkw={keyword}&LH_Sold=1&LH_Complete=1&_sop=13"
)

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

# eBay blocks cold requests (HTTP 403). A persistent session that first "warms up"
# by visiting the homepage to collect cookies — then searches with a Referer and
# Sec-Fetch-Site=same-origin — gets through, mirroring the buy-side EbayScraper.
_session = None
_warmed_up = False


def _get_warm_session():
    global _session, _warmed_up
    import requests
    if _session is None:
        _session = requests.Session()
        _session.headers.update(HEADERS)
    if not _warmed_up:
        try:
            _session.headers["Sec-Fetch-Site"] = "none"
            _session.get("https://www.ebay.com/", timeout=10)
            _warmed_up = True
        except Exception as e:
            logger.warning(f"eBay warmup failed (non-fatal): {e}")
    return _session


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
        session = _get_warm_session()
        session.headers["Referer"] = "https://www.ebay.com/"
        session.headers["Sec-Fetch-Site"] = "same-origin"
        resp = session.get(url, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"eBay returned HTTP {resp.status_code}")
            return None
        # A 200 can still be eBay's bot-challenge interstitial — treat as a miss.
        if "pardon our interruption" in resp.text[:4000].lower():
            logger.warning("eBay served bot-challenge interstitial (rate-limited)")
            return None
        return resp.text
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

    # eBay's current layout: <li class="s-card" data-listingid> with
    # <span class="s-card__price">. Fall back to the legacy s-item markup.
    cards = [li for li in soup.find_all("li", class_="s-card") if li.get("data-listingid")]
    if cards:
        for card in cards:
            title_el = card.select_one("div.s-card__title, span.s-card__title")
            if title_el and title_el.get_text(strip=True).lower() in (
                "shop on ebay", "results matching fewer words"
            ):
                continue
            # A price range yields two spans — take the lower bound.
            card_prices = [
                _parse_price(el.get_text(strip=True))
                for el in card.select("span.s-card__price")
            ]
            card_prices = [p for p in card_prices if p is not None and p > 0]
            if card_prices:
                prices.append(min(card_prices))
        return prices

    # Legacy fallback
    items = soup.select("li.s-item") or soup.select("div.s-item__wrapper")
    for item in items:
        title_el = item.select_one(".s-item__title")
        if title_el and "shop on ebay" in title_el.get_text(strip=True).lower():
            continue
        price_el = item.select_one(".s-item__price")
        if not price_el:
            continue
        price = _parse_price(price_el.get_text(strip=True))
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
            db.rollback()
            logger.warning(f"Failed to cache market value for '{keyword}': {e}")

    logger.info(
        f"Market value for '{keyword}': median=${median_price}, "
        f"mean=${mean_price}, n={sample_count}"
    )
    return estimate
