"""Generic deal scoring engine for all watchlist categories."""
from dataclasses import dataclass, field
from typing import Optional
import re


DEAL_THRESHOLDS = {
    "STEAL": 0.45,
    "GREAT": 0.55,
    "GOOD": 0.65,
    "FAIR": 0.75,
}

CONDITION_KEYWORDS_NEGATIVE = [
    "broken", "parts only", "for parts", "cracked", "damaged", "not working",
    "as-is", "as is", "faulty", "defective", "scratched", "worn", "faded",
]

CONDITION_KEYWORDS_POSITIVE = [
    "mint", "like new", "excellent", "perfect", "pristine", "flawless",
    "barely used", "lightly used",
]


@dataclass
class DealResult:
    rating: str = "PASS"
    score: float = 0.0
    estimated_value: Optional[float] = None
    conservative_value: Optional[float] = None
    target_buy_price: Optional[float] = None
    estimated_profit: Optional[float] = None
    profit_margin: Optional[float] = None
    confidence: float = 0.0
    reasons: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def _rating_from_ratio(price: float, conservative_value: float, thresholds: dict) -> str:
    if conservative_value <= 0:
        return "PASS"
    ratio = price / conservative_value
    if ratio <= thresholds.get("STEAL", 0.45):
        return "STEAL"
    if ratio <= thresholds.get("GREAT", 0.55):
        return "GREAT"
    if ratio <= thresholds.get("GOOD", 0.65):
        return "GOOD"
    if ratio <= thresholds.get("FAIR", 0.75):
        return "FAIR"
    return "PASS"


def score_listing(
    title: str,
    description: str,
    price: float,
    watchlist_keywords: list[str],
    watchlist_brands: list[str],
    watchlist_negative_keywords: list[str],
    estimated_value: Optional[float] = None,
    conservative_value: Optional[float] = None,
    thresholds: Optional[dict] = None,
    platform_fee_pct: float = 0.13,
    target_profit_margin: float = 0.30,
) -> DealResult:
    result = DealResult()
    thresholds = thresholds or DEAL_THRESHOLDS

    text = f"{title} {description}".lower()

    # --- Negative keyword check ---
    neg_hits = [kw for kw in watchlist_negative_keywords if kw.lower() in text]
    if neg_hits:
        result.warnings.append(f"Negative keyword(s) matched: {', '.join(neg_hits)}")
        result.rating = "PASS"
        result.score = 0
        return result

    # --- Brand match ---
    matched_brands = [b for b in watchlist_brands if b.lower() in text]
    if matched_brands:
        result.reasons.append(f"Brand match: {', '.join(matched_brands)}")
        result.confidence += 0.3

    # --- Keyword match ---
    kw_hits = [kw for kw in watchlist_keywords if kw.lower() in text]
    if kw_hits:
        result.reasons.append(f"Keyword match: {', '.join(kw_hits[:3])}")
        result.confidence += min(len(kw_hits) * 0.1, 0.4)

    # --- Condition signals ---
    bad_condition = any(kw in text for kw in CONDITION_KEYWORDS_NEGATIVE)
    good_condition = any(kw in text for kw in CONDITION_KEYWORDS_POSITIVE)
    if bad_condition:
        result.warnings.append("Condition keywords suggest damage or parts-only listing.")
        result.confidence -= 0.2
    if good_condition:
        result.reasons.append("Condition described as excellent/like-new.")
        result.confidence += 0.1

    result.confidence = max(0.0, min(1.0, result.confidence))

    # --- Value-based scoring ---
    if estimated_value and conservative_value and price and price > 0:
        result.estimated_value = estimated_value
        result.conservative_value = conservative_value

        sell_price_estimate = conservative_value * (1 - platform_fee_pct)
        result.target_buy_price = sell_price_estimate * (1 - target_profit_margin)

        ratio = price / conservative_value
        pct = int(ratio * 100)
        result.reasons.append(f"Price is {pct}% of conservative value (${conservative_value:,.0f})")

        result.estimated_profit = sell_price_estimate - price
        if sell_price_estimate > 0:
            result.profit_margin = result.estimated_profit / sell_price_estimate

        result.rating = _rating_from_ratio(price, conservative_value, thresholds)

        # Score 0-100
        score_ratio = max(0, 1 - ratio)
        result.score = round(min(score_ratio * 100, 100), 1)
    else:
        # No pricing data — can only flag if keywords/brands match
        if matched_brands or kw_hits:
            result.rating = "FAIR"
            result.score = 30
            result.warnings.append("No pricing data available — score based on keyword/brand match only.")
        else:
            result.rating = "PASS"
            result.score = 0

    return result
