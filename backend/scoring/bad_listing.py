"""
"Bad Listing, Good Item" detector.

Some of the best flips are listings where the seller doesn't understand what
they have: misspelled brands, generic one-word titles, urgency/cleanout
language, bundles, or a valuable model that's only visible in the photo. This
module turns those signals into a structured undervaluation score so the
pipeline can surface them even when the ratio-based label is mediocre.

Pure-text by default; photo signals (from ``services.photo_analysis``) are
additive and optional.

Python 3.9 — Optional[...] / List[...], never ``X | None``.
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional

from rapidfuzz import fuzz


@dataclass
class BadListingResult:
    bad_listing_good_item: bool = False
    undervaluation_score: int = 0
    detected_signals: List[str] = field(default_factory=list)
    suggested_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "bad_listing_good_item": self.bad_listing_good_item,
            "undervaluation_score": self.undervaluation_score,
            "detected_signals": self.detected_signals,
            "suggested_reason": self.suggested_reason,
        }


# Fuzzy threshold for treating a title token as a misspelled brand.
_FUZZY_BRAND_THRESHOLD = 82


def _tokens(text: str) -> List[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def detect_bad_listing(
    *,
    title: str,
    description: str = "",
    brands: Optional[List[str]] = None,
    category_config: Optional[dict] = None,
    photo_analysis=None,   # services.photo_analysis.PhotoAnalysis or None
) -> BadListingResult:
    """Analyse a listing for under-description / hidden-value signals."""
    cfg = category_config or {}
    brands = brands or []
    result = BadListingResult()

    title_l = (title or "").lower().strip()
    desc_l = (description or "").lower().strip()
    text = f"{title_l} {desc_l}".strip()
    title_tokens = _tokens(title_l)

    score = 0

    # ── 1. Misspelled brand (explicit map) ────────────────────────────────────
    misspellings = cfg.get("misspellings", {})
    for wrong, right in misspellings.items():
        if wrong in text and right not in title_l:
            result.detected_signals.append(
                f"Misspelled term '{wrong}' (likely '{right}')"
            )
            score += 22
            break

    # ── 2. Misspelled brand (fuzzy against watchlist brands) ──────────────────
    if brands and not any("Misspelled" in s for s in result.detected_signals):
        for token in title_tokens:
            if len(token) < 4:
                continue
            for brand in brands:
                bl = brand.lower()
                if token == bl or token in bl or bl in token:
                    continue  # exact / substring → correctly spelled
                if fuzz.ratio(token, bl) >= _FUZZY_BRAND_THRESHOLD:
                    result.detected_signals.append(
                        f"Possible misspelling of brand '{brand}' (saw '{token}')"
                    )
                    score += 18
                    break
            else:
                continue
            break

    # ── 3. Generic title ──────────────────────────────────────────────────────
    generic_terms = cfg.get("generic_title_terms", [])
    generic_hits = [t for t in generic_terms if t in title_l]
    # Also flag extremely short titles (1-2 meaningful words → likely generic).
    if generic_hits:
        result.detected_signals.append(
            f"Generic listing title ({', '.join(generic_hits[:2])})"
        )
        score += 16
    elif len(title_tokens) <= 2 and not any(b.lower() in title_l for b in brands):
        result.detected_signals.append("Very short / generic title with no brand")
        score += 14

    # ── 4. Urgency language ───────────────────────────────────────────────────
    urgency_hits = [p for p in cfg.get("urgency_phrases", []) if p in text]
    if urgency_hits:
        result.detected_signals.append(
            f"Urgency language detected ({urgency_hits[0]})"
        )
        score += 18

    # ── 5. Bundle language ────────────────────────────────────────────────────
    bundle_hits = [b for b in cfg.get("bundle_terms", []) if b in text]
    if bundle_hits:
        result.detected_signals.append(
            f"Bundle language detected ({bundle_hits[0]})"
        )
        score += 12

    # ── 6. Weak description ───────────────────────────────────────────────────
    if len(desc_l) < 15:
        result.detected_signals.append("Weak/empty description")
        score += 8

    # ── 7. Photo reveals value the title hides ────────────────────────────────
    if photo_analysis is not None:
        p_brand = getattr(photo_analysis, "detected_brand", None)
        p_model = getattr(photo_analysis, "detected_model", None)
        if p_brand and p_brand.lower() not in text:
            result.detected_signals.append(
                f"Valuable brand visible in photo but not in title ({p_brand})"
            )
            score += 20
        if p_model and p_model.lower() not in text:
            result.detected_signals.append(
                f"Model number visible in photo but not in title ({p_model})"
            )
            score += 20

    # ── Finalise ──────────────────────────────────────────────────────────────
    result.undervaluation_score = max(0, min(100, score))
    # "Good item" requires both an undervaluation signal AND a hint of real value
    # (a known brand somewhere, a photo-detected brand/model, or strong signals).
    has_value_hint = bool(
        any(b.lower() in text for b in brands)
        or (photo_analysis is not None and getattr(photo_analysis, "detected_brand", None))
        or any("photo" in s.lower() for s in result.detected_signals)
    )
    result.bad_listing_good_item = bool(
        result.undervaluation_score >= 30 and (has_value_hint or result.undervaluation_score >= 50)
    )

    if result.bad_listing_good_item:
        result.suggested_reason = (
            "Seller may be under-describing a valuable item — "
            + "; ".join(result.detected_signals[:3])
        )
    elif result.detected_signals:
        result.suggested_reason = "Minor under-description signals — " + result.detected_signals[0]

    return result
