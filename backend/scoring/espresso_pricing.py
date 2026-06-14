"""
Espresso price lookup — a manual price reference used in place of eBay sold
comps (eBay rate-limits the sold-listing scrape too aggressively to be reliable).

Each EspressoPrice row has a `match_key` (normalized "brand model"); a listing
matches a row when EVERY token of the key appears in the normalized title. Among
matching rows the most specific (most tokens) wins, so "Breville Barista Express"
beats the brand-only "Breville" fallback.
"""
import re
from typing import Optional, Tuple

# Listing words that never help identify the machine — stripped before matching.
_NOISE = {
    "espresso", "machine", "maker", "coffee", "automatic", "super", "semi",
    "with", "and", "the", "for", "stainless", "steel", "black", "white",
    "silver", "new", "used", "great", "condition", "barely", "like",
}

# If a title contains any of these, it's a PART/ACCESSORY, not a machine — pricing
# it at machine value produces absurd false STEALs (a $24 portafilter basket valued
# like a $3,200 La Marzocco). Such titles get no table price (fall back to keyword
# scoring, which won't flag them as deals).
_ACCESSORY_TERMS = [
    "oem", "replacement", "portafilter", "tamper", "basket", "kcup", "k cup",
    "carousel", "carosel", "capsule", "pod holder", "assembly", "gasket",
    "knob", "cleaning", "brush", "drip tray",
    "water tank", "pitcher", "frothing", "steam wand", "shower screen",
    "filter holder", "for parts", "spare", "part", "parts", "accessory",
    "accessories", "burr set", "fan assembly", "carafe", "blade", "smoking gun",
]

# Whole-word matching so substrings inside larger words (e.g. "counterparts",
# "knobby") don't trigger the filter; "descal" keeps prefix matching so it
# covers descaler/descaling/descaled.
_ACCESSORY_RE = re.compile(
    r"\b(?:descal\w*|" + "|".join(re.escape(t) for t in _ACCESSORY_TERMS) + r")\b"
)


def normalize(text: str) -> str:
    text = (text or "").lower()
    text = text.replace("’", "'")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _title_tokens(title: str) -> set:
    return {t for t in normalize(title).split() if t not in _NOISE}


def match_espresso_price(title: str, prices) -> Tuple[Optional[float], Optional[object]]:
    """Return (used_price, matched_row) for the most specific matching row, or
    (None, None). `prices` is an iterable of EspressoPrice rows (or any object
    exposing .match_key, .used_price, and optionally .aliases)."""
    norm = normalize(title)
    # Parts/accessories must not be priced like whole machines.
    if _ACCESSORY_RE.search(norm):
        return None, None

    tokens = _title_tokens(title)
    if not tokens:
        return None, None

    best = None
    best_specificity = 0
    for row in prices:
        # A row matches if every key-token is present in the title. Aliases let a
        # single row cover alternate spellings (e.g. "delonghi" / "de'longhi").
        candidates = [row.match_key] + list(getattr(row, "aliases", []) or [])
        for cand in candidates:
            key_tokens = [t for t in normalize(cand).split() if t]
            if not key_tokens:
                continue
            if all(kt in tokens for kt in key_tokens):
                specificity = len(key_tokens)
                if specificity > best_specificity:
                    best = row
                    best_specificity = specificity
                break

    if best is None:
        return None, None
    return best.used_price, best
