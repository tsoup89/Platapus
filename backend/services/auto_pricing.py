"""
Auto-pricing service for sell-side inventory items.

Aggregates eBay sold comps (from MarketValueCache) + live active listings
from eBay and Mercari to suggest a competitive sell price.

Usage:
    from backend.services.auto_pricing import suggest_price
    result = suggest_price(item, db)
"""
import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger("platapicker.auto_pricing")

# Condition multipliers — relative to GOOD (1.0 baseline)
CONDITION_MULTIPLIERS = {
    "NEW": 1.25,
    "LIKE_NEW": 1.10,
    "GOOD": 1.00,
    "FAIR": 0.80,
    "POOR": 0.60,
}

# Max live comps to pull per source
MAX_COMPS_PER_SOURCE = 20

# Confidence thresholds (based on total data points)
CONFIDENCE_HIGH = 15
CONFIDENCE_MED = 5


@dataclass
class Comp:
    source: str
    title: str
    price: float
    url: Optional[str]
    is_sold: bool  # True = sold listing, False = active listing


@dataclass
class PricingSuggestion:
    suggested_price: Optional[float]
    low_estimate: Optional[float]
    high_estimate: Optional[float]
    confidence: str  # "high" | "medium" | "low" | "none"
    comps: list[Comp]
    condition_applied: str
    keyword_used: str
    generated_at: datetime = field(default_factory=datetime.utcnow)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "suggested_price": self.suggested_price,
            "low_estimate": self.low_estimate,
            "high_estimate": self.high_estimate,
            "confidence": self.confidence,
            "condition_applied": self.condition_applied,
            "keyword_used": self.keyword_used,
            "generated_at": self.generated_at.isoformat(),
            "error": self.error,
            "comps": [
                {
                    "source": c.source,
                    "title": c.title,
                    "price": c.price,
                    "url": c.url,
                    "is_sold": c.is_sold,
                }
                for c in self.comps
            ],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PricingSuggestion":
        comps = [
            Comp(
                source=c["source"],
                title=c["title"],
                price=c["price"],
                url=c.get("url"),
                is_sold=c.get("is_sold", False),
            )
            for c in d.get("comps", [])
        ]
        return cls(
            suggested_price=d.get("suggested_price"),
            low_estimate=d.get("low_estimate"),
            high_estimate=d.get("high_estimate"),
            confidence=d.get("confidence", "none"),
            condition_applied=d.get("condition_applied", "GOOD"),
            keyword_used=d.get("keyword_used", ""),
            generated_at=datetime.fromisoformat(d["generated_at"]) if d.get("generated_at") else datetime.utcnow(),
            error=d.get("error"),
            comps=comps,
        )


def _confidence_label(n: int) -> str:
    if n >= CONFIDENCE_HIGH:
        return "high"
    if n >= CONFIDENCE_MED:
        return "medium"
    if n > 0:
        return "low"
    return "none"


def _fetch_ebay_sold_comps(keyword: str, db: Session) -> list[Comp]:
    """Pull eBay sold comps via market_value.py (uses cache)."""
    try:
        from backend.services.market_value import get_market_value
        estimate = get_market_value(keyword, db=db, max_age_hours=24, use_playwright=False)
        if estimate.error or estimate.median_price is None:
            logger.info(f"eBay sold cache miss for '{keyword}': {estimate.error}")
            return []

        # We don't have individual sold listings from market_value, only aggregates.
        # Synthesize representative comps from the range.
        comps = []
        if estimate.median_price:
            comps.append(Comp(
                source="ebay_sold",
                title=f"eBay sold median ({estimate.sample_count} listings)",
                price=estimate.median_price,
                url=f"https://www.ebay.com/sch/i.html?_nkw={keyword.replace(' ', '+')}&LH_Sold=1&LH_Complete=1",
                is_sold=True,
            ))
        if estimate.min_price and estimate.min_price != estimate.median_price:
            comps.append(Comp(
                source="ebay_sold",
                title=f"eBay sold low",
                price=estimate.min_price,
                url=None,
                is_sold=True,
            ))
        if estimate.max_price and estimate.max_price != estimate.median_price:
            comps.append(Comp(
                source="ebay_sold",
                title=f"eBay sold high",
                price=estimate.max_price,
                url=None,
                is_sold=True,
            ))
        return comps
    except Exception as e:
        logger.warning(f"eBay sold comp fetch failed: {e}")
        return []


def _fetch_ebay_active_comps(keyword: str) -> list[Comp]:
    """Fetch live active eBay listings — these indicate the competition ceiling."""
    try:
        from backend.scrapers.ebay import EbayScraper
        scraper = EbayScraper(config={"max_listings_per_run": MAX_COMPS_PER_SOURCE})
        listings, _ = scraper.run(keyword, location="", radius_miles=0)
        comps = []
        for lst in listings[:MAX_COMPS_PER_SOURCE]:
            if lst.price and lst.price > 0:
                comps.append(Comp(
                    source="ebay",
                    title=lst.title,
                    price=lst.price,
                    url=lst.url,
                    is_sold=False,
                ))
        logger.info(f"eBay active: got {len(comps)} comps for '{keyword}'")
        return comps
    except Exception as e:
        logger.warning(f"eBay active comp fetch failed: {e}")
        return []


def _fetch_mercari_comps(keyword: str) -> list[Comp]:
    """Fetch live Mercari listings for comp ceiling."""
    try:
        from backend.scrapers.mercari import MercariScraper
        scraper = MercariScraper(config={"max_listings_per_run": MAX_COMPS_PER_SOURCE})
        listings, health = scraper.run(keyword, location="", radius_miles=0)
        if health.status == "failed":
            logger.info(f"Mercari scraper failed for '{keyword}': {health.last_error}")
            return []
        comps = []
        for lst in listings[:MAX_COMPS_PER_SOURCE]:
            if lst.price and lst.price > 0:
                comps.append(Comp(
                    source="mercari",
                    title=lst.title,
                    price=lst.price,
                    url=lst.url,
                    is_sold=False,
                ))
        logger.info(f"Mercari: got {len(comps)} comps for '{keyword}'")
        return comps
    except Exception as e:
        logger.warning(f"Mercari comp fetch failed (non-fatal, may need login): {e}")
        return []


def _apply_condition_adjustment(price: float, condition: str) -> float:
    """Scale price based on item condition relative to GOOD baseline."""
    mult = CONDITION_MULTIPLIERS.get(condition, 1.0)
    return round(price * mult, 2)


def _build_suggestion_from_comps(
    all_comps: list[Comp],
    condition: str,
    keyword: str,
) -> PricingSuggestion:
    """
    From all comps, compute a suggested sell price.

    Strategy:
    - Sold comps are authoritative — they represent what buyers actually pay.
      Use the median sold price as the base.
    - Active comps set the current competition ceiling.
      If active median < sold median, buyers can easily find cheaper; drop our price.
    - Apply condition multiplier to the base.
    - Low = 10th percentile of sold comps (or active if no sold).
    - High = 75th percentile of active comps (what sellers are asking).
    """
    if not all_comps:
        return PricingSuggestion(
            suggested_price=None,
            low_estimate=None,
            high_estimate=None,
            confidence="none",
            comps=[],
            condition_applied=condition,
            keyword_used=keyword,
            error="No comparable listings found.",
        )

    sold = [c.price for c in all_comps if c.is_sold]
    active = [c.price for c in all_comps if not c.is_sold]

    # Filter out extreme outliers (> 5× median or < 1/5 median) before stats
    def _filter_outliers(prices: list[float]) -> list[float]:
        if not prices:
            return prices
        med = statistics.median(prices)
        return [p for p in prices if (med / 5 <= p <= med * 5)]

    sold = _filter_outliers(sorted(sold))
    active = _filter_outliers(sorted(active))

    # Base price: prefer sold median, fall back to active median
    if sold:
        base_price = statistics.median(sold)
    elif active:
        base_price = statistics.median(active)
    else:
        return PricingSuggestion(
            suggested_price=None,
            low_estimate=None,
            high_estimate=None,
            confidence="none",
            comps=all_comps,
            condition_applied=condition,
            keyword_used=keyword,
            error="Could not extract valid prices from comps.",
        )

    # If active comps exist and their median is meaningfully lower than sold,
    # the market has moved down — use active median instead
    if active and sold:
        active_med = statistics.median(active)
        if active_med < base_price * 0.85:
            base_price = active_med

    # Apply condition adjustment
    suggested = _apply_condition_adjustment(base_price, condition)

    # Low estimate: 10th percentile of whichever pool we have most data from
    price_pool = sold if sold else active
    n = len(price_pool)
    low_idx = max(0, int(n * 0.10) - 1)
    high_idx = min(n - 1, int(n * 0.75))

    low_raw = price_pool[low_idx] if price_pool else suggested * 0.80
    high_raw = price_pool[high_idx] if price_pool else suggested * 1.20

    low_est = _apply_condition_adjustment(low_raw, condition)
    high_est = _apply_condition_adjustment(high_raw, condition)

    # Confidence: based on total data points (each ebay_sold agg comp counts as 5 data points)
    total_points = len(active)
    for c in all_comps:
        if c.source == "ebay_sold" and c.is_sold:
            total_points += 5  # aggregated, count more

    conf = _confidence_label(total_points)

    return PricingSuggestion(
        suggested_price=round(suggested, 2),
        low_estimate=round(low_est, 2),
        high_estimate=round(high_est, 2),
        confidence=conf,
        comps=all_comps,
        condition_applied=condition,
        keyword_used=keyword,
    )


def suggest_price(
    title: str,
    condition: str,
    db: Optional[Session] = None,
    include_mercari: bool = True,
) -> PricingSuggestion:
    """
    Generate a price suggestion for an inventory item.

    Args:
        title: Item title used as the search keyword.
        condition: One of NEW/LIKE_NEW/GOOD/FAIR/POOR.
        db: SQLAlchemy session (for market value cache lookup).
        include_mercari: Whether to include Mercari active listings.

    Returns:
        PricingSuggestion with suggested_price, low/high estimates, and comps.
    """
    keyword = title.strip()
    logger.info(f"Generating price suggestion for '{keyword}' (condition={condition})")

    all_comps: list[Comp] = []

    # 1. eBay sold comps (from cache or fresh fetch)
    sold_comps = _fetch_ebay_sold_comps(keyword, db)
    all_comps.extend(sold_comps)

    # 2. eBay active comps (current competition)
    active_comps = _fetch_ebay_active_comps(keyword)
    all_comps.extend(active_comps)

    # 3. Mercari active comps (optional — may fail if not logged in)
    if include_mercari:
        mercari_comps = _fetch_mercari_comps(keyword)
        all_comps.extend(mercari_comps)

    suggestion = _build_suggestion_from_comps(all_comps, condition, keyword)
    logger.info(
        f"Price suggestion for '{keyword}': ${suggestion.suggested_price} "
        f"(confidence={suggestion.confidence}, n={len(all_comps)})"
    )
    return suggestion
