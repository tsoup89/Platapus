"""
Auto-outreach service: automatically message sellers on Facebook Marketplace.

When a GREAT deal is found and the watchlist has auto_outreach_enabled=True,
this service navigates to the listing and sends a pre-configured message to
the seller via Facebook Messenger — using the existing persistent FB session.

Rate limiting: max 15 messages/hour, min 60s between messages, to avoid
triggering Facebook's spam detection.
"""
import asyncio
import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from backend.services.paths import get_browser_sessions_dir, get_screenshots_dir

logger = logging.getLogger("platapicker.outreach")

SESSION_DIR = get_browser_sessions_dir() / "facebook"
SCREENSHOT_DIR = get_screenshots_dir()

DEFAULT_MESSAGE_TEMPLATE = (
    "Hi! Is {title} still available? I can pick it up today for cash. "
    "Please let me know — thanks!"
)

# Rate limiting state (in-process, resets on restart — good enough for a local app)
_outreach_timestamps: list[float] = []
MAX_PER_HOUR = 15
MIN_SECONDS_BETWEEN = 60

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)


@dataclass
class OutreachResult:
    success: bool
    error: Optional[str] = None
    screenshot_path: Optional[str] = None


def _check_rate_limit() -> tuple[bool, str]:
    """Returns (allowed, reason). Prunes timestamps older than 1 hour."""
    now = time.time()
    cutoff = now - 3600
    _outreach_timestamps[:] = [t for t in _outreach_timestamps if t > cutoff]

    if len(_outreach_timestamps) >= MAX_PER_HOUR:
        oldest = min(_outreach_timestamps)
        wait = int(3600 - (now - oldest))
        return False, f"Rate limit: {MAX_PER_HOUR}/hour reached. Try again in ~{wait//60}m."

    if _outreach_timestamps:
        since_last = now - max(_outreach_timestamps)
        if since_last < MIN_SECONDS_BETWEEN:
            wait = int(MIN_SECONDS_BETWEEN - since_last)
            return False, f"Too soon after last message. Wait {wait}s."

    return True, ""


async def _send_message_playwright(
    listing_url: str, message: str
) -> OutreachResult:
    from playwright.async_api import async_playwright, TimeoutError as PwTimeout

    session_file = SESSION_DIR / "session.json"
    if not session_file.exists():
        return OutreachResult(
            success=False,
            error="No Facebook session. Log in via Scraper Health first.",
        )

    screenshot_path: Optional[str] = None

    async def _screenshot(page, label: str) -> Optional[str]:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = str(SCREENSHOT_DIR / f"outreach_{label}_{ts}.png")
        try:
            await page.screenshot(path=path, full_page=False)
            return path
        except Exception:
            return None

    async def _delay(a=0.5, b=1.5):
        await asyncio.sleep(random.uniform(a, b))

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
            logger.info(f"Outreach: navigating to {listing_url}")
            await page.goto(listing_url, wait_until="domcontentloaded", timeout=30_000)
            await _delay(2, 4)

            # Check login status
            content = (await page.content()).lower()
            if any(x in content for x in ["log in", "sign in", "create new account"]):
                screenshot_path = await _screenshot(page, "login_wall")
                return OutreachResult(
                    success=False,
                    error="Facebook session expired. Re-login via Scraper Health.",
                    screenshot_path=screenshot_path,
                )

            # Check if listing is still available (not sold/removed)
            if any(x in content for x in ["this listing is no longer available", "sold"]):
                return OutreachResult(success=False, error="Listing is no longer available.")

            # Find and click the "Send message" / "Chat" button
            msg_selectors = [
                "[aria-label='Send message']",
                "div[aria-label='Message seller']",
                "a[aria-label='Chat with seller']",
                "[role='button']:has-text('Message')",
                "[role='button']:has-text('Send message')",
                "[role='link']:has-text('Message')",
            ]
            msg_clicked = False
            for sel in msg_selectors:
                try:
                    el = page.locator(sel).first
                    await el.wait_for(timeout=5_000)
                    await el.click()
                    await _delay(1.5, 3)
                    msg_clicked = True
                    logger.info(f"Outreach: opened message dialog via '{sel}'")
                    break
                except Exception:
                    continue

            if not msg_clicked:
                screenshot_path = await _screenshot(page, "no_message_button")
                return OutreachResult(
                    success=False,
                    error="Could not find Message button (listing may not support messaging).",
                    screenshot_path=screenshot_path,
                )

            # Type the message into the chat input
            input_selectors = [
                "[aria-label='Message']",
                "[aria-label='Type a message']",
                "[aria-label='Aa']",
                "div[contenteditable='true'][role='textbox']",
                "textarea[aria-label*='message' i]",
            ]
            typed = False
            for sel in input_selectors:
                try:
                    el = page.locator(sel).first
                    await el.wait_for(timeout=5_000)
                    await el.click()
                    await _delay(0.3, 0.7)
                    await el.type(message, delay=random.randint(30, 80))
                    await _delay(0.5, 1.0)
                    typed = True
                    logger.info(f"Outreach: message typed via '{sel}'")
                    break
                except Exception:
                    continue

            if not typed:
                screenshot_path = await _screenshot(page, "no_input")
                return OutreachResult(
                    success=False,
                    error="Could not find message input field.",
                    screenshot_path=screenshot_path,
                )

            # Send the message (press Enter or click Send button)
            try:
                send_btn = page.locator("[aria-label='Press enter to send']").first
                await send_btn.wait_for(timeout=3_000)
                await send_btn.click()
            except Exception:
                # Fall back to pressing Enter
                await page.keyboard.press("Enter")

            await _delay(2, 3)
            screenshot_path = await _screenshot(page, "sent")
            logger.info("Outreach: message sent successfully")
            return OutreachResult(success=True, screenshot_path=screenshot_path)

        except PwTimeout as e:
            screenshot_path = await _screenshot(page, "timeout")
            logger.error(f"Outreach: timeout: {e}")
            return OutreachResult(
                success=False,
                error="Timed out while trying to send message.",
                screenshot_path=screenshot_path,
            )
        except Exception as e:
            screenshot_path = await _screenshot(page, "error")
            logger.error(f"Outreach: error: {e}", exc_info=True)
            return OutreachResult(success=False, error=str(e), screenshot_path=screenshot_path)
        finally:
            await context.close()
            await browser.close()


def send_outreach(
    listing_url: str,
    listing_title: str,
    message_template: str = "",
) -> OutreachResult:
    """
    Send a message to a seller on Facebook Marketplace.

    Args:
        listing_url: Full URL of the FB Marketplace listing.
        listing_title: Item title (used to fill {title} in the template).
        message_template: Custom message. Uses DEFAULT_MESSAGE_TEMPLATE if empty.

    Returns:
        OutreachResult with success flag and optional error/screenshot.
    """
    # Rate limit check
    allowed, reason = _check_rate_limit()
    if not allowed:
        return OutreachResult(success=False, error=reason)

    # Only FB Marketplace supported for now
    if "facebook.com" not in listing_url:
        return OutreachResult(
            success=False,
            error=f"Auto-outreach only works for Facebook Marketplace listings. Got: {listing_url}",
        )

    template = message_template.strip() or DEFAULT_MESSAGE_TEMPLATE
    message = template.format(title=listing_title, url=listing_url)

    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            _send_message_playwright(listing_url, message)
        )
        loop.close()
    except Exception as e:
        logger.error(f"Outreach event loop error: {e}", exc_info=True)
        return OutreachResult(success=False, error=str(e))

    if result.success:
        _outreach_timestamps.append(time.time())

    return result
