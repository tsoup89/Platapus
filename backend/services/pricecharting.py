"""PriceCharting price sync service for GameCube titles."""
import logging
import time
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote_plus

from sqlalchemy.orm import Session

logger = logging.getLogger("platapicker.pricecharting")

SEARCH_URL = "https://www.pricecharting.com/search-products?q={query}&type=videogames"
GAME_URL = "https://www.pricecharting.com/game/gamecube/{slug}"


def _fetch_html(url: str) -> Optional[str]:
    """Fetch page HTML using requests, with Playwright fallback if blocked."""
    try:
        import requests

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            return resp.text
        logger.warning(f"PriceCharting HTTP {resp.status_code} for {url}")
        # Fall through to Playwright on non-200
    except Exception as e:
        logger.warning(f"requests failed for {url}: {e}")

    # Playwright fallback
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=20000)
            page.wait_for_load_state("networkidle", timeout=10000)
            html = page.content()
            browser.close()
            return html
    except Exception as e:
        logger.error(f"Playwright fallback failed for {url}: {e}")
        return None


def _parse_price(soup, td_id: str) -> Optional[float]:
    """Extract a price value from a td#<id> span.price element."""
    try:
        from bs4 import BeautifulSoup  # noqa: F401 — imported for type checking

        td = soup.find("td", id=td_id)
        if not td:
            return None
        span = td.find("span", class_="price") or td.find("span")
        if not span:
            return None
        text = span.get_text(strip=True).replace("$", "").replace(",", "")
        return float(text)
    except (ValueError, AttributeError):
        return None


def fetch_pricecharting_prices(title: str) -> Optional[dict]:
    """
    Search PriceCharting for a GameCube title and return prices.

    Returns: {loose, complete, new, graded} or None on failure.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error("beautifulsoup4 is not installed — cannot parse PriceCharting")
        return None

    search_url = SEARCH_URL.format(query=quote_plus(title))
    html = _fetch_html(search_url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    # Find the first search result link for gamecube
    game_link = None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/game/gamecube/" in href:
            game_link = href
            break

    if not game_link:
        logger.info(f"No GameCube result found on PriceCharting for: {title!r}")
        return None

    # Make sure we have an absolute URL
    if game_link.startswith("/"):
        game_link = "https://www.pricecharting.com" + game_link

    game_html = _fetch_html(game_link)
    if not game_html:
        return None

    game_soup = BeautifulSoup(game_html, "html.parser")

    prices = {
        "loose": _parse_price(game_soup, "used_price"),
        "complete": _parse_price(game_soup, "complete_price"),
        "new": _parse_price(game_soup, "new_price"),
        "graded": _parse_price(game_soup, "graded_price"),
    }

    if all(v is None for v in prices.values()):
        logger.warning(f"All prices were None for {title!r} at {game_link}")
        return None

    logger.info(f"PriceCharting prices for {title!r}: {prices}")
    return prices


def sync_gamecube_prices(
    db: Session,
    max_titles: int = 50,
    delay_seconds: float = 3.0,
    only_stale_hours: int = 48,
) -> dict:
    """
    Sync GameCube prices from PriceCharting.

    1. Queries GameCubePrice entries not updated in only_stale_hours.
    2. Fetches prices from PriceCharting for each (up to max_titles).
    3. Updates the GameCubePrice record.
    4. Waits delay_seconds between requests.

    Returns: {synced: N, failed: N, skipped: N}
    """
    from backend.models.models import GameCubePrice

    stale_cutoff = datetime.utcnow() - timedelta(hours=only_stale_hours)

    entries = (
        db.query(GameCubePrice)
        .filter(
            (GameCubePrice.last_updated == None)  # noqa: E711
            | (GameCubePrice.last_updated < stale_cutoff)
        )
        .order_by(GameCubePrice.last_updated.asc().nullsfirst())
        .limit(max_titles)
        .all()
    )

    synced = 0
    failed = 0
    skipped = 0

    logger.info(f"PriceCharting sync: {len(entries)} stale entries to process")

    for i, entry in enumerate(entries):
        if i > 0:
            time.sleep(delay_seconds)

        prices = fetch_pricecharting_prices(entry.title)
        if prices is None:
            logger.warning(f"Failed to fetch prices for: {entry.title!r}")
            failed += 1
            continue

        if prices.get("loose") is not None:
            entry.loose_price = prices["loose"]
        if prices.get("complete") is not None:
            entry.complete_price = prices["complete"]
        if prices.get("new") is not None:
            entry.new_price = prices["new"]
        if prices.get("graded") is not None:
            entry.graded_price = prices["graded"]

        entry.last_updated = datetime.utcnow()
        db.commit()
        synced += 1
        logger.info(f"[{i+1}/{len(entries)}] Synced: {entry.title!r}")

    return {"synced": synced, "failed": failed, "skipped": skipped}
