"""
Facebook Marketplace scraper using Playwright with persistent session,
slow mode, human-like delays, and comprehensive error detection.
"""
import asyncio
import json
import logging
import os
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from .base import BaseScraper, NormalizedListing, ScraperHealth
from backend.services.paths import get_screenshots_dir, get_browser_sessions_dir

logger = logging.getLogger("platapicker.scrapers.facebook")

SESSION_DIR = get_browser_sessions_dir() / "facebook"
SCREENSHOT_DIR = get_screenshots_dir()
SESSION_DIR.mkdir(parents=True, exist_ok=True)

FB_MARKETPLACE_URL = "https://www.facebook.com/marketplace"

LOGIN_INDICATORS = [
    "log in", "sign in", "create new account", "forgot password"
]
BLOCK_INDICATORS = [
    "you're temporarily blocked", "unusual activity", "access denied",
    "request blocked", "security check required"
]


def _random_delay(min_s: float, max_s: float):
    time.sleep(random.uniform(min_s, max_s))


class FacebookScraper(BaseScraper):
    name = "facebook"

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.slow_mode = self.config.get("slow_mode", True)
        self.min_delay = self.config.get("min_delay_seconds", 3)
        self.max_delay = self.config.get("max_delay_seconds", 8)
        self.max_listings_per_run = self.config.get("max_listings_per_run", 50)
        self.max_searches_per_run = self.config.get("max_searches_per_run", 5)
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._session_status = "unknown"
        self._last_screenshot = None

    # ------------------------------------------------------------------ #
    # Session management
    # ------------------------------------------------------------------ #

    async def _launch_browser(self, headless: bool = True):
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        storage_state = str(SESSION_DIR / "session.json")
        if os.path.exists(storage_state):
            self._context = await self._browser.new_context(
                storage_state=storage_state,
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
            )
        else:
            self._context = await self._browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
            )
        self._page = await self._context.new_page()

    async def _save_session(self):
        if self._context:
            await self._context.storage_state(path=str(SESSION_DIR / "session.json"))
            logger.info("Facebook session saved.")

    async def _close_browser(self):
        try:
            if self._page:
                await self._page.close()
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.debug(f"Browser close error: {e}")

    async def _save_screenshot(self, label: str = "error") -> Optional[str]:
        if self._page:
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            path = str(SCREENSHOT_DIR / f"fb_{label}_{ts}.png")
            try:
                await self._page.screenshot(path=path, full_page=True)
                logger.info(f"Screenshot saved: {path}")
                self._last_screenshot = path
                return path
            except Exception as e:
                logger.debug(f"Screenshot failed: {e}")
        return None

    async def _check_login_status(self) -> str:
        """Returns 'logged_in', 'needs_login', or 'possible_block'."""
        try:
            content = (await self._page.content()).lower()
            if any(ind in content for ind in BLOCK_INDICATORS):
                return "possible_block"
            if any(ind in content for ind in LOGIN_INDICATORS):
                return "needs_login"
            return "logged_in"
        except Exception:
            return "unknown"

    async def _human_scroll(self, times: int = 3):
        for _ in range(times):
            await self._page.evaluate("window.scrollBy(0, Math.random() * 300 + 200)")
            await asyncio.sleep(random.uniform(0.5, 1.5))

    # ------------------------------------------------------------------ #
    # Login (interactive — opens visible browser)
    # ------------------------------------------------------------------ #

    async def _auto_login(self) -> bool:
        """Attempt credential-based login using FACEBOOK_EMAIL / FACEBOOK_PASSWORD env vars.
        Returns True if login succeeded."""
        email = os.getenv("FACEBOOK_EMAIL", "").strip()
        password = os.getenv("FACEBOOK_PASSWORD", "").strip()
        if not email or not password:
            logger.warning("Facebook: auto-login skipped — FACEBOOK_EMAIL/FACEBOOK_PASSWORD not set in .env")
            return False

        logger.info("Facebook: attempting auto-login with credentials")
        try:
            await self._page.goto("https://www.facebook.com/login", wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(random.uniform(1.5, 3.0))

            await self._page.fill("input[name='email']", email)
            await asyncio.sleep(random.uniform(0.5, 1.2))
            await self._page.fill("input[name='pass']", password)
            await asyncio.sleep(random.uniform(0.5, 1.2))
            await self._page.click("button[name='login']")

            # Wait for redirect away from login page
            await self._page.wait_for_url(lambda url: "login" not in url, timeout=20_000)
            await asyncio.sleep(random.uniform(2.0, 4.0))

            status = await self._check_login_status()
            if status == "logged_in":
                await self._save_session()
                logger.info("Facebook: auto-login succeeded, session saved")
                return True
            else:
                logger.warning(f"Facebook: auto-login failed — status={status}")
                await self._save_screenshot("auto_login_failed")
                return False
        except Exception as e:
            logger.warning(f"Facebook: auto-login error: {e}")
            await self._save_screenshot("auto_login_error")
            return False

    async def interactive_login(self):
        """Open visible browser for user to log in manually."""
        print("\n🦆 Opening Facebook Marketplace in browser...")
        print("   Please log in to Facebook, then close the browser window.")
        print("   Your session will be saved for future runs.\n")
        await self._launch_browser(headless=False)
        await self._page.goto("https://www.facebook.com/login", wait_until="networkidle")
        print("Waiting for you to log in and close the browser...")
        try:
            await self._page.wait_for_url("**/marketplace**", timeout=120_000)
        except Exception:
            pass
        await self._save_session()
        await self._close_browser()
        print("✅ Login session saved. Facebook scraper ready.")

    def login(self):
        asyncio.run(self.interactive_login())

    # ------------------------------------------------------------------ #
    # Scraping
    # ------------------------------------------------------------------ #

    def fetch_raw_listings(self, keyword: str, location: str, radius_miles: int) -> list[dict]:
        return asyncio.run(self._async_fetch(keyword, location, radius_miles))

    async def _async_fetch(self, keyword: str, location: str, radius_miles: int) -> list[dict]:
        raw_listings = []
        try:
            await self._launch_browser(headless=True)

            search_url = self._build_search_url(keyword, location, radius_miles)
            logger.info(f"Facebook: fetching '{keyword}' at {location} r={radius_miles}mi")

            await self._page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)

            if self.slow_mode:
                await asyncio.sleep(random.uniform(self.min_delay, self.max_delay))

            status = await self._check_login_status()
            self._session_status = status

            if status == "needs_login":
                logger.warning("Facebook: session expired — attempting auto-login")
                await self._save_screenshot("needs_login")
                recovered = await self._auto_login()
                if not recovered:
                    return []
                # Re-navigate to the search after login
                await self._page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)
                if self.slow_mode:
                    await asyncio.sleep(random.uniform(self.min_delay, self.max_delay))
                status = await self._check_login_status()
                if status != "logged_in":
                    return []

            if status == "possible_block":
                logger.warning("Facebook: possible block/rate limit detected")
                await self._save_screenshot("possible_block")
                return []

            await self._human_scroll(5)

            cards = await self._extract_listing_cards()
            raw_listings = cards[: self.max_listings_per_run]

            logger.info(f"Facebook: found {len(cards)} cards, returning {len(raw_listings)}")

            await self._save_session()

        except Exception as e:
            logger.error(f"Facebook scraper failed: {e}", exc_info=True)
            await self._save_screenshot("error")
            self._session_status = "error"
        finally:
            await self._close_browser()

        return raw_listings

    def _build_search_url(self, keyword: str, location: str, radius_miles: int) -> str:
        import urllib.parse
        kw_enc = urllib.parse.quote(keyword)
        city = location.replace(", ", "-").replace(" ", "-").lower()
        return (
            f"https://www.facebook.com/marketplace/{city}/search"
            f"?query={kw_enc}&radius={radius_miles}"
        )

    async def _extract_listing_cards(self) -> list[dict]:
        """Extract listing cards from current page."""
        cards = []
        try:
            await self._page.wait_for_selector("div[data-testid='marketplace_feed_item']", timeout=8_000)
        except Exception:
            logger.debug("Marketplace feed item selector not found — trying alternates")

        card_elements = await self._page.query_selector_all(
            "div[data-testid='marketplace_feed_item'], "
            "div[aria-label*='Marketplace'] a[href*='/marketplace/item/'], "
            "a[href*='/marketplace/item/']"
        )

        seen_urls: set = set()
        for el in card_elements:
            try:
                card = await self._parse_card_element(el)
                if card and card.get("url") not in seen_urls:
                    seen_urls.add(card.get("url"))
                    cards.append(card)
            except Exception as e:
                logger.debug(f"Failed to parse card: {e}")

        if not cards:
            logger.warning("Facebook: zero listing cards found — possible layout change or block")
            await self._save_screenshot("zero_results")

        return cards

    async def _parse_card_element(self, el) -> Optional[dict]:
        try:
            # Get the link — the card element itself or a child
            href = await el.get_attribute("href")
            if not href:
                link = await el.query_selector("a[href*='/marketplace/item/']")
                href = await link.get_attribute("href") if link else None

            url = None
            if href:
                url = href if href.startswith("http") else f"https://www.facebook.com{href}"

            listing_id = None
            if url:
                m = re.search(r"/item/(\d+)", url)
                listing_id = m.group(1) if m else None

            # Image
            img_el = await el.query_selector("img")
            image_url = await img_el.get_attribute("src") if img_el else None

            # Pull all visible text lines from the card, then parse title/price/location
            raw_text = (await el.inner_text()).strip()
            lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]

            # Price is any line starting with $ or matching a currency pattern
            price = None
            price_line_idx = None
            for i, ln in enumerate(lines):
                extracted = self._extract_price(ln)
                if extracted is not None and ln.lstrip().startswith("$"):
                    price = extracted
                    price_line_idx = i
                    break

            # Title is the longest non-price, non-location line (usually the first substantive one)
            title = None
            for i, ln in enumerate(lines):
                if i == price_line_idx:
                    continue
                # Skip very short lines or lines that look like prices/distances
                if len(ln) < 3 or re.match(r"^\$[\d,]+", ln) or re.match(r"^\d+\s*(mi|km|miles)", ln, re.I):
                    continue
                title = ln
                break

            # Location is typically the last short line that isn't the title or price
            location = None
            for ln in reversed(lines):
                if ln == title or (price_line_idx is not None and ln == lines[price_line_idx]):
                    continue
                if 2 < len(ln) < 60 and not re.match(r"^\$", ln):
                    location = ln
                    break

            if not title or not url:
                return None

            return {
                "id": listing_id,
                "title": title.strip(),
                "price": price,
                "url": url,
                "image_url": image_url,
                "location": location,
                "source": "facebook",
                "scraped_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.debug(f"Card parse error: {e}")
            return None

    def _extract_price(self, text: str) -> Optional[float]:
        if not text:
            return None
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

    def get_session_status(self) -> str:
        return self._session_status

    def test_connection(self) -> tuple[bool, str]:
        session_file = SESSION_DIR / "session.json"
        if not session_file.exists():
            return False, "No saved session found. Run: python -m platapicker facebook-login"
        return True, "Session file found. Run a test scrape to verify login."
