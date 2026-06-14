"""
Mercari scraper using Playwright with persistent session.
Requires a Mercari account. Run `python -m platapicker mercari-login` once
to save a session, then scrapes headlessly using that session.
Ships nationwide — location/radius params are ignored.
"""
import asyncio
import json
import logging
import os
import random
import re
import urllib.parse
from datetime import datetime
from typing import Optional

from .base import BaseScraper, NormalizedListing, ScraperHealth, extract_price
from backend.services.paths import get_screenshots_dir, get_browser_sessions_dir

logger = logging.getLogger("platapicker.scrapers.mercari")

SCREENSHOT_DIR = get_screenshots_dir()
SESSION_DIR = get_browser_sessions_dir() / "mercari"
# Persistent Chrome profile — Cloudflare trusts browsers with real accumulated history
PROFILE_DIR = get_browser_sessions_dir() / "mercari_profile"
SESSION_DIR.mkdir(parents=True, exist_ok=True)
PROFILE_DIR.mkdir(parents=True, exist_ok=True)

MERCARI_BASE = "https://www.mercari.com"
LOGIN_URL = "https://www.mercari.com/login/"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

LOGIN_INDICATORS = ["log in", "sign in", "create account", "sign up to"]
BLOCK_INDICATORS = [
    "access denied", "you have been blocked",
    "complete the captcha", "verify you are human",
]

STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
window.chrome = {runtime: {}};
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
"""

# sortBy=3 → price ascending (cheapest first)
SORT_BY = 3


_extract_price = extract_price


class MercariScraper(BaseScraper):
    name = "mercari"

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.min_delay = self.config.get("min_delay_seconds", 2)
        self.max_delay = self.config.get("max_delay_seconds", 5)
        self.max_listings_per_run = self.config.get("max_listings_per_run", 60)
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._session_status = "unknown"

    # ------------------------------------------------------------------ #
    # Session management
    # ------------------------------------------------------------------ #

    async def _launch_browser(self, headless: bool = False):
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        # Mercari uses Cloudflare Bot Management which fingerprints headless mode.
        # For silent background runs: start minimized so no window appears on screen.
        # For login: headless=False with no minimization so user can interact.
        args = [
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--window-size=1280,900",
        ]
        if not headless:
            # Background run — minimize to Dock, don't steal focus
            args += ["--start-minimized", "--no-first-run", "--no-default-browser-check"]

        self._context = await self._playwright.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            args=args,
            user_agent=UA,
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        await self._context.add_init_script(STEALTH_SCRIPT)
        await self._context.route("**/*.{woff,woff2,ttf,otf,eot}", lambda r: r.abort())
        self._page = await self._context.new_page()

    async def _save_session(self):
        # Persistent context saves state automatically to PROFILE_DIR; nothing extra needed
        logger.info("Mercari persistent profile updated.")

    async def _close_browser(self):
        try:
            if self._page:
                await self._page.close()
            if self._context:
                await self._context.close()  # persistent context — no separate browser to close
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.debug(f"Browser close error: {e}")

    async def _save_screenshot(self, label: str = "error") -> Optional[str]:
        if self._page:
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            path = str(SCREENSHOT_DIR / f"mercari_{label}_{ts}.png")
            try:
                await self._page.screenshot(path=path, full_page=False, timeout=10_000)
                logger.info(f"Screenshot saved: {path}")
                return path
            except Exception as e:
                logger.debug(f"Screenshot failed: {e}")
        return None

    async def _check_login_status(self) -> str:
        try:
            content = (await self._page.content()).lower()
            if any(ind in content for ind in BLOCK_INDICATORS):
                return "possible_block"
            if any(ind in content for ind in LOGIN_INDICATORS):
                return "needs_login"
            return "logged_in"
        except Exception:
            return "unknown"

    # ------------------------------------------------------------------ #
    # Login
    # ------------------------------------------------------------------ #

    async def _auto_login(self) -> bool:
        email = os.getenv("MERCARI_EMAIL", "").strip()
        password = os.getenv("MERCARI_PASSWORD", "").strip()
        if not email or not password:
            logger.warning("Mercari: auto-login skipped — MERCARI_EMAIL/MERCARI_PASSWORD not set")
            return False
        logger.info("Mercari: attempting auto-login with credentials")
        try:
            await self._page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(random.uniform(1.5, 3.0))

            # Accept cookie consent if shown
            try:
                btn = await self._page.wait_for_selector('button:has-text("Got it")', timeout=3_000)
                await btn.click()
                await asyncio.sleep(0.5)
            except Exception:
                pass

            await self._page.fill("input[name='email'], input[type='email']", email)
            await asyncio.sleep(random.uniform(0.4, 0.9))
            await self._page.fill("input[name='password'], input[type='password']", password)
            await asyncio.sleep(random.uniform(0.4, 0.9))
            await self._page.click("button[type='submit']")

            await self._page.wait_for_url(
                lambda url: "login" not in url and "signin" not in url,
                timeout=20_000,
            )
            await asyncio.sleep(random.uniform(2.0, 3.5))

            status = await self._check_login_status()
            if status == "logged_in":
                await self._save_session()
                logger.info("Mercari: auto-login succeeded")
                return True
            else:
                logger.warning(f"Mercari: auto-login failed — status={status}")
                await self._save_screenshot("auto_login_failed")
                return False
        except Exception as e:
            logger.warning(f"Mercari: auto-login error: {e}")
            await self._save_screenshot("auto_login_error")
            return False

    async def interactive_login(self):
        print("\nOpening Mercari login page...")
        print("   Please log in, then close the browser window.")
        print("   Your session will be saved for future runs.\n")
        # Fully visible browser for interactive login — no minimization
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        self._context = await self._playwright.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--window-size=1280,900",
            ],
            user_agent=UA,
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        await self._context.add_init_script(STEALTH_SCRIPT)
        self._page = await self._context.new_page()
        await self._page.goto(LOGIN_URL, wait_until="domcontentloaded")
        print("Waiting for you to log in...")
        try:
            await self._page.wait_for_url(
                lambda url: "login" not in url and "signin" not in url,
                timeout=120_000,
            )
            await asyncio.sleep(2)
        except Exception:
            pass
        await self._close_browser()
        print("✅ Mercari login saved. Scraper will now run silently in the background.")

    def login(self):
        asyncio.run(self.interactive_login())

    def test_connection(self) -> tuple[bool, str]:
        # Profile dir exists if login was ever completed
        if not any(PROFILE_DIR.iterdir()) if PROFILE_DIR.exists() else True:
            return False, "No browser profile found. Run: python -m platapicker mercari-login"
        return True, "Browser profile found. Run a test scrape to verify login."

    # ------------------------------------------------------------------ #
    # BaseScraper interface
    # ------------------------------------------------------------------ #

    def fetch_raw_listings(self, keyword: str, location: str, radius_miles: int) -> list[dict]:
        return asyncio.run(self._async_fetch(keyword))

    def parse_listing(self, raw: dict) -> Optional[NormalizedListing]:
        title = raw.get("title") or raw.get("name")
        if not title:
            return None
        price = _extract_price(raw.get("price"))
        listing_id = str(raw["id"]) if raw.get("id") else None
        url = raw.get("url")
        if not url and listing_id:
            url = f"{MERCARI_BASE}/item/{listing_id}/"
        return NormalizedListing(
            source=self.name,
            source_listing_id=listing_id,
            title=title.strip(),
            description=raw.get("description", ""),
            price=price,
            url=url,
            image_url=raw.get("image_url"),
            location=raw.get("location"),
            scraped_at=datetime.utcnow(),
            raw_payload=raw,
        )

    # ------------------------------------------------------------------ #
    # Core async fetch
    # ------------------------------------------------------------------ #

    async def _async_fetch(self, keyword: str) -> list[dict]:
        raw_listings: list[dict] = []
        try:
            await self._launch_browser(headless=True)
            search_url = self._build_search_url(keyword)
            logger.info(f"Mercari: fetching '{keyword}'")

            # Intercept search API responses
            api_items: list[dict] = []

            async def handle_response(response):
                if "mercari.com" not in response.url:
                    return
                if any(p in response.url for p in ["entities:search", "/search", "/items"]):
                    try:
                        if "application/json" in (response.headers.get("content-type") or ""):
                            body = await response.json()
                            items = (
                                body.get("items")
                                or body.get("data", {}).get("items")
                                or []
                            )
                            if items:
                                api_items.extend(items)
                                logger.debug(f"Mercari: intercepted {len(items)} items")
                    except Exception:
                        pass

            self._page.on("response", handle_response)

            await self._page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)

            # Accept cookie consent
            try:
                btn = await self._page.wait_for_selector('button:has-text("Got it")', timeout=3_000)
                await btn.click()
            except Exception:
                pass

            await asyncio.sleep(random.uniform(self.min_delay, self.max_delay))

            # Check session status
            status = await self._check_login_status()
            self._session_status = status

            if status == "needs_login":
                logger.warning("Mercari: session expired — attempting auto-login")
                await self._save_screenshot("needs_login")
                recovered = await self._auto_login()
                if not recovered:
                    return []
                await self._page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)
                await asyncio.sleep(random.uniform(self.min_delay, self.max_delay))

            if status == "possible_block":
                logger.warning("Mercari: possible block detected")
                await self._save_screenshot("possible_block")
                return []

            # Wait for listings to appear
            try:
                await self._page.wait_for_selector("a[href*='/item/']", timeout=10_000)
            except Exception:
                # Check if page shows 0 results
                text = await self._page.evaluate("() => document.body.innerText")
                if "0 results" in text or "No results found" in text:
                    logger.warning(f"Mercari: 0 results for '{keyword}' — may need re-login")
                    await self._save_screenshot("zero_results")
                    return []

            await self._human_scroll(times=4)
            await asyncio.sleep(1.0)

            # Use intercepted API data if available
            if api_items:
                logger.info(f"Mercari: {len(api_items)} items from API intercept")
                for item in api_items:
                    parsed = self._normalize_api_item(item)
                    if parsed:
                        raw_listings.append(parsed)
            else:
                # Fall back to __NEXT_DATA__ then DOM
                from_json = await self._extract_next_data()
                if from_json:
                    logger.info(f"Mercari: {len(from_json)} items from __NEXT_DATA__")
                    raw_listings = from_json
                else:
                    logger.info("Mercari: falling back to DOM parsing")
                    raw_listings = await self._extract_dom_cards()

            raw_listings = raw_listings[: self.max_listings_per_run]
            logger.info(f"Mercari: returning {len(raw_listings)} listings for '{keyword}'")
            await self._save_session()

        except Exception as e:
            logger.error(f"Mercari scraper failed: {e}", exc_info=True)
            await self._save_screenshot("error")
            self._session_status = "error"
        finally:
            await self._close_browser()

        return raw_listings

    # ------------------------------------------------------------------ #
    # URL builder
    # ------------------------------------------------------------------ #

    def _build_search_url(self, keyword: str) -> str:
        params = {"keyword": keyword, "sortBy": SORT_BY, "status": "on_sale"}
        return f"{MERCARI_BASE}/search/?{urllib.parse.urlencode(params)}"

    # ------------------------------------------------------------------ #
    # Extraction strategies
    # ------------------------------------------------------------------ #

    def _normalize_api_item(self, item: dict) -> Optional[dict]:
        try:
            item_id = item.get("id") or item.get("itemId")
            title = item.get("name") or item.get("title")
            if not title:
                return None
            price = _extract_price(
                item.get("price")
                or item.get("sellingPrice")
                or (item.get("priceInfo") or {}).get("price")
            )
            url = item.get("url") or (f"{MERCARI_BASE}/item/{item_id}/" if item_id else None)
            image_url = None
            photos = item.get("photos") or item.get("thumbnails") or []
            if photos:
                p = photos[0]
                image_url = (p.get("url") or p.get("thumbnailUrl")) if isinstance(p, dict) else p
            image_url = image_url or item.get("thumbnailUrl") or item.get("imageUrl")
            seller = item.get("seller") or {}
            location = (seller.get("location") or seller.get("country")) if isinstance(seller, dict) else None
            return {
                "id": str(item_id) if item_id else None,
                "title": title,
                "price": price,
                "url": url,
                "image_url": image_url,
                "location": location,
                "source": "mercari",
                "scraped_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.debug(f"Mercari item normalization failed: {e}")
            return None

    async def _extract_next_data(self) -> list[dict]:
        try:
            raw = await self._page.evaluate(
                "() => window.__NEXT_DATA__ ? JSON.stringify(window.__NEXT_DATA__) : null"
            )
            if not raw:
                return []
            data = json.loads(raw)
            props = data.get("props", {}).get("pageProps", {})
            candidates = (
                props.get("items")
                or props.get("searchResult", {}).get("items")
                or props.get("initialItems")
                or []
            )
            if not candidates:
                for val in props.values():
                    if isinstance(val, list) and val and isinstance(val[0], dict):
                        if val[0].get("name") or val[0].get("title"):
                            candidates = val
                            break
            return [r for r in (self._normalize_api_item(i) for i in candidates) if r]
        except Exception as e:
            logger.debug(f"Mercari __NEXT_DATA__ extraction failed: {e}")
            return []

    async def _extract_dom_cards(self) -> list[dict]:
        results = []
        try:
            card_elements = await self._page.query_selector_all("a[href*='/item/']")
            logger.info(f"Mercari DOM: found {len(card_elements)} card elements")
            seen_urls: set = set()
            for el in card_elements:
                try:
                    card = await self._parse_dom_card(el)
                    if card and card.get("url") not in seen_urls:
                        seen_urls.add(card["url"])
                        results.append(card)
                except Exception as e:
                    logger.debug(f"Mercari DOM card parse error: {e}")
        except Exception as e:
            logger.warning(f"Mercari DOM extraction failed: {e}")
        if not results:
            logger.warning("Mercari: zero DOM cards found")
            await self._save_screenshot("zero_dom")
        return results

    async def _parse_dom_card(self, el) -> Optional[dict]:
        href = await el.get_attribute("href")
        if not href:
            return None
        url = href if href.startswith("http") else f"{MERCARI_BASE}{href}"
        m = re.search(r"/item/([a-zA-Z0-9]+)", url)
        listing_id = m.group(1) if m else None
        raw_text = (await el.inner_text()).strip()
        lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
        if not lines:
            return None
        price, price_idx = None, None
        for i, ln in enumerate(lines):
            if ln.startswith("$"):
                price = _extract_price(ln)
                price_idx = i
                break
        title = None
        for i, ln in enumerate(lines):
            if i == price_idx or len(ln) < 3 or ln.startswith("$"):
                continue
            title = ln
            break
        if not title:
            return None
        img_el = await el.query_selector("img")
        image_url = await img_el.get_attribute("src") if img_el else None
        return {
            "id": listing_id,
            "title": title,
            "price": price,
            "url": url,
            "image_url": image_url,
            "location": None,
            "source": "mercari",
            "scraped_at": datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    async def _human_scroll(self, times: int = 4):
        for _ in range(times):
            await self._page.evaluate("window.scrollBy(0, Math.random() * 400 + 200)")
            await asyncio.sleep(random.uniform(0.4, 1.0))
