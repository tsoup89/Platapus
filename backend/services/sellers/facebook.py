"""
Facebook Marketplace sell-side listing service.

Uses Playwright with the existing persistent FB session to automate
the create-listing flow at facebook.com/marketplace/create/item.

Fallback strategy (in order):
  1. Playwright headless — fills title/price/condition/description/photos
  2. On any failure — saves a debug screenshot, returns the create-listing
     URL so the user can finish manually in their real browser.
"""
import asyncio
import logging
import random
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.services.paths import get_browser_sessions_dir, get_screenshots_dir
from .base import BaseSeller, ListingDraft, ListingResult

logger = logging.getLogger("platapicker.sellers.facebook")

SESSION_DIR = get_browser_sessions_dir() / "facebook"
SCREENSHOT_DIR = get_screenshots_dir()

FB_CREATE_URL = "https://www.facebook.com/marketplace/create/item"
FB_FEES_LOCAL = 0.0        # local pickup: free
FB_FEES_SHIPPING = 0.05    # shipping: 5% (min $0.40)

# Human-readable condition labels for FB's dropdown
FB_CONDITIONS = {
    "NEW": "New",
    "LIKE_NEW": "Used - Like New",
    "GOOD": "Used - Good",
    "FAIR": "Used - Fair",
    "POOR": "Used - Poor",
}

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)


async def _run_listing(draft: ListingDraft) -> ListingResult:
    """Async Playwright implementation of the FB create-listing flow."""
    from playwright.async_api import async_playwright, TimeoutError as PwTimeout

    session_file = SESSION_DIR / "session.json"
    screenshot_path: Optional[str] = None

    async def _screenshot(page, label: str) -> Optional[str]:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = str(SCREENSHOT_DIR / f"fb_sell_{label}_{ts}.png")
        try:
            await page.screenshot(path=path, full_page=True)
            return path
        except Exception:
            return None

    async def _human_delay(min_s=0.4, max_s=1.2):
        await asyncio.sleep(random.uniform(min_s, max_s))

    if not session_file.exists():
        return ListingResult(
            success=False,
            action_url=FB_CREATE_URL,
            error_message=(
                "No Facebook session found. "
                "Log in via the Scraper Health page first, then retry."
            ),
        )

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            storage_state=str(session_file),
            user_agent=UA,
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()

        try:
            # ── Navigate to create-listing page ──────────────────────────
            logger.info("FB seller: navigating to create-listing page")
            await page.goto(FB_CREATE_URL, wait_until="domcontentloaded", timeout=30_000)
            await _human_delay(2, 4)

            # Check for login wall
            content = (await page.content()).lower()
            if any(x in content for x in ["log in", "sign in", "create new account"]):
                screenshot_path = await _screenshot(page, "login_wall")
                return ListingResult(
                    success=False,
                    action_url=FB_CREATE_URL,
                    screenshot_path=screenshot_path,
                    error_message=(
                        "Facebook session has expired. "
                        "Re-login via Scraper Health and retry."
                    ),
                )

            # ── Photos ────────────────────────────────────────────────────
            if draft.photo_paths:
                logger.info(f"FB seller: uploading {len(draft.photo_paths)} photos")
                try:
                    file_input = page.locator("input[type='file']").first
                    await file_input.set_input_files(
                        [str(p) for p in draft.photo_paths[:10]]
                    )
                    await _human_delay(2, 4)
                except Exception as e:
                    # Marketplace requires at least one photo, so continuing
                    # would only fail later at Publish with a confusing error.
                    logger.error(f"FB seller: photo upload failed: {e}")
                    screenshot_path = await _screenshot(page, "photo_upload_failed")
                    return ListingResult(
                        success=False,
                        action_url=FB_CREATE_URL,
                        screenshot_path=screenshot_path,
                        error_message=(
                            "Photo upload failed — Facebook Marketplace requires "
                            "at least one photo. Complete the listing manually."
                        ),
                    )

            # ── Title ─────────────────────────────────────────────────────
            logger.info("FB seller: filling title")
            title_selectors = [
                "[aria-label='Title']",
                "input[placeholder*='selling']",
                "input[placeholder*='title' i]",
                "label:has-text('Title') + div input",
            ]
            title_filled = False
            for sel in title_selectors:
                try:
                    el = page.locator(sel).first
                    await el.wait_for(timeout=5_000)
                    await el.click()
                    await _human_delay()
                    await el.fill(draft.title[:80])
                    await _human_delay()
                    title_filled = True
                    break
                except Exception:
                    continue

            if not title_filled:
                screenshot_path = await _screenshot(page, "title_not_found")
                return ListingResult(
                    success=False,
                    action_url=FB_CREATE_URL,
                    screenshot_path=screenshot_path,
                    error_message=(
                        "Could not locate the Title field "
                        "(Facebook may have changed their layout). "
                        "Complete the listing manually."
                    ),
                )

            # ── Price ─────────────────────────────────────────────────────
            logger.info("FB seller: filling price")
            price_selectors = [
                "[aria-label='Price']",
                "input[placeholder='Price']",
                "input[placeholder*='price' i]",
                "label:has-text('Price') + div input",
            ]
            for sel in price_selectors:
                try:
                    el = page.locator(sel).first
                    await el.wait_for(timeout=4_000)
                    await el.click()
                    await _human_delay()
                    # Keep cents — int() would silently turn $29.99 into $29
                    price_str = f"{draft.price:.2f}".rstrip("0").rstrip(".")
                    await el.fill(price_str)
                    await _human_delay()
                    break
                except Exception:
                    continue

            # ── Condition ─────────────────────────────────────────────────
            logger.info("FB seller: selecting condition")
            fb_condition = FB_CONDITIONS.get(draft.condition, "Used - Good")
            try:
                # FB condition is usually a combobox / listbox
                cond_selectors = [
                    "[aria-label='Condition']",
                    "div[role='combobox']:has-text('Condition')",
                    "label:has-text('Condition') ~ div [role='combobox']",
                ]
                for sel in cond_selectors:
                    try:
                        el = page.locator(sel).first
                        await el.wait_for(timeout=3_000)
                        await el.click()
                        await _human_delay()
                        # Look for the option in the opened dropdown
                        option = page.locator(f"[role='option']:has-text('{fb_condition}')").first
                        await option.wait_for(timeout=3_000)
                        await option.click()
                        await _human_delay()
                        break
                    except Exception:
                        continue
            except Exception as e:
                logger.warning(f"FB seller: condition select failed (non-fatal): {e}")

            # ── Description ───────────────────────────────────────────────
            if draft.description:
                logger.info("FB seller: filling description")
                desc_selectors = [
                    "[aria-label='Description']",
                    "textarea[placeholder*='Describe' i]",
                    "textarea[placeholder*='description' i]",
                    "label:has-text('Description') + div textarea",
                ]
                for sel in desc_selectors:
                    try:
                        el = page.locator(sel).first
                        await el.wait_for(timeout=3_000)
                        await el.click()
                        await _human_delay()
                        await el.fill(draft.description[:2000])
                        await _human_delay()
                        break
                    except Exception:
                        continue

            # ── Next button ───────────────────────────────────────────────
            logger.info("FB seller: clicking Next")
            next_selectors = [
                "div[aria-label='Next']",
                "button:has-text('Next')",
                "[role='button']:has-text('Next')",
            ]
            next_clicked = False
            for sel in next_selectors:
                try:
                    el = page.locator(sel).first
                    await el.wait_for(timeout=5_000)
                    await el.click()
                    await _human_delay(2, 4)
                    next_clicked = True
                    break
                except Exception:
                    continue

            if not next_clicked:
                screenshot_path = await _screenshot(page, "next_not_found")
                return ListingResult(
                    success=False,
                    action_url=FB_CREATE_URL,
                    screenshot_path=screenshot_path,
                    error_message=(
                        "Could not find the Next button "
                        "(form partially filled — Facebook may have changed layout). "
                        "Complete the listing manually."
                    ),
                )

            # ── Publish button ────────────────────────────────────────────
            logger.info("FB seller: clicking Publish / List item")
            await _human_delay(1, 2)
            publish_selectors = [
                "[aria-label='Publish']",
                "div[aria-label='List item']",
                "button:has-text('Publish')",
                "[role='button']:has-text('Publish')",
                "[role='button']:has-text('List item')",
                "[role='button']:has-text('Post')",
            ]
            published = False
            for sel in publish_selectors:
                try:
                    el = page.locator(sel).first
                    await el.wait_for(timeout=6_000)
                    await el.click()
                    await _human_delay(3, 5)
                    published = True
                    break
                except Exception:
                    continue

            if not published:
                screenshot_path = await _screenshot(page, "publish_not_found")
                return ListingResult(
                    success=False,
                    action_url=FB_CREATE_URL,
                    screenshot_path=screenshot_path,
                    error_message=(
                        "Filled in all fields but could not click Publish "
                        "(Facebook may require additional steps). "
                        "Complete the listing manually."
                    ),
                )

            # ── Grab listing URL ──────────────────────────────────────────
            await _human_delay(2, 4)
            current_url = page.url
            listing_url: Optional[str] = None

            if "marketplace" in current_url and "item" in current_url:
                listing_url = current_url
            else:
                # Try to find a "View your listing" link on the confirmation page
                try:
                    view_link = page.locator("a[href*='/marketplace/item/']").first
                    href = await view_link.get_attribute("href", timeout=3_000)
                    if href:
                        listing_url = (
                            href if href.startswith("http")
                            else f"https://www.facebook.com{href}"
                        )
                except Exception:
                    pass

            screenshot_path = await _screenshot(page, "success")
            logger.info(f"FB seller: published successfully. URL={listing_url}")

            return ListingResult(
                success=True,
                platform_url=listing_url,
                screenshot_path=screenshot_path,
            )

        except PwTimeout as e:
            screenshot_path = await _screenshot(page, "timeout")
            logger.error(f"FB seller: Playwright timeout: {e}")
            return ListingResult(
                success=False,
                action_url=FB_CREATE_URL,
                screenshot_path=screenshot_path,
                error_message=f"Timed out during listing automation. Complete manually.",
            )

        except Exception as e:
            screenshot_path = await _screenshot(page, "error")
            logger.error(f"FB seller: unexpected error: {e}", exc_info=True)
            return ListingResult(
                success=False,
                action_url=FB_CREATE_URL,
                screenshot_path=screenshot_path,
                error_message=str(e),
            )

        finally:
            await context.close()
            await browser.close()


class FacebookSeller(BaseSeller):
    platform = "facebook"

    def create_listing(self, draft: ListingDraft) -> ListingResult:
        """Run the async Playwright flow synchronously (safe from a BackgroundTask thread)."""
        try:
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(_run_listing(draft))
            loop.close()
            return result
        except Exception as e:
            logger.error(f"FB seller: failed to run event loop: {e}", exc_info=True)
            return ListingResult(
                success=False,
                action_url=FB_CREATE_URL,
                error_message=str(e),
            )

    def remove_listing(self, platform_listing_id: str) -> bool:
        # No API for removal — user must delist manually
        logger.info(f"FB: remove_listing for {platform_listing_id} (manual)")
        return True
