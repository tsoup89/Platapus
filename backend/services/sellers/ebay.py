"""
eBay sell-side listing service — MVP manual-fallback flow.

Opens eBay's Quick Listing tool with the item title pre-filled as a keyword
so eBay auto-suggests a category and condition. Returns a structured draft
card the frontend shows for copy-paste.

When eBay dev keys are provisioned, swap create_listing() to POST to the
Inventory API → Offer API → publish endpoint; the interface stays the same.
"""
import logging
import urllib.parse

from .base import BaseSeller, ListingDraft, ListingResult

logger = logging.getLogger("platapicker.sellers.ebay")

# eBay condition IDs (for reference / future API use)
CONDITION_IDS = {
    "NEW": 1000,
    "LIKE_NEW": 1500,
    "GOOD": 3000,
    "FAIR": 5000,
    "POOR": 7000,
}

# eBay fee schedule (approximation — varies by category)
EBAY_FVF_RATE = 0.1325   # 13.25% final value fee


def estimate_ebay_fees(sale_price: float) -> float:
    return round(sale_price * EBAY_FVF_RATE, 2)


class EbaySeller(BaseSeller):
    platform = "ebay"

    def create_listing(self, draft: ListingDraft) -> ListingResult:
        """
        For MVP: build the action_url that opens eBay's AI-assisted listing
        tool with the title pre-filled. The user completes the listing in their
        browser; they can paste the description and price from the UI card.

        Once eBay dev keys are approved, replace the body of this method with
        real Sell API calls — the interface (and everything calling it) stays
        identical.
        """
        # eBay's "prelist suggest" opens their AI listing tool with keyword pre-fill
        keyword = urllib.parse.quote_plus(draft.title)
        action_url = (
            f"https://www.ebay.com/sl/prelist/suggest?keywords={keyword}"
        )

        logger.info(
            f"eBay (manual flow): draft created for '{draft.title}' @ ${draft.price}"
        )

        return ListingResult(
            success=True,
            action_url=action_url,
            extra={
                "flow": "manual",
                "estimated_fee": estimate_ebay_fees(draft.price),
                "condition_id": CONDITION_IDS.get(draft.condition, 3000),
            },
        )

    def remove_listing(self, platform_listing_id: str) -> bool:
        # Manual flow — user delists in eBay's interface
        logger.info(f"eBay: remove_listing called for {platform_listing_id} (manual)")
        return True
