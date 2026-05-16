"""Fuzzy title matching for GameCube pricing table."""
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional
from thefuzz import fuzz, process

MATCH_THRESHOLD = 60  # minimum fuzz score to consider a match

COMMON_WORDS_TO_STRIP = [
    "the", "a", "an", "nintendo", "gamecube", "gc", "game", "games",
    "disc", "complete", "cib", "loose", "box", "manual", "with", "in",
    "and", "or", "only", "included", "bundle", "lot", "set", "for", "of",
]


@dataclass
class TitleMatch:
    raw_text: str
    matched_title: Optional[str]
    gamecube_price: Optional[object]  # GameCubePrice ORM object
    confidence: float
    fuzz_score: int = 0


def normalize_title(text: str) -> str:
    """Lowercase, remove punctuation, strip common filler words."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    words = [w for w in text.split() if w not in COMMON_WORDS_TO_STRIP]
    return " ".join(words)


def extract_game_candidates(text: str) -> list[str]:
    """
    Extract likely game title fragments from listing text.
    Splits on common delimiters and returns candidate strings.
    """
    text = re.sub(r"\n+", " ", text)
    # Split on commas, semicolons, bullets, pipe
    parts = re.split(r"[,;\|\•\-\*]|\band\b", text, flags=re.IGNORECASE)
    candidates = []
    for part in parts:
        part = part.strip()
        if 3 <= len(part) <= 80:  # ignore too-short or too-long fragments
            candidates.append(part)
    return candidates


def match_titles_in_text(
    text: str,
    gamecube_prices: list,
    aliases: Optional[list] = None,
) -> tuple[list[TitleMatch], list[str]]:
    """
    Given listing text and a list of GameCubePrice objects, return:
    - matched: list of TitleMatch
    - unmatched: list of raw candidate strings that could not be matched
    """
    if not gamecube_prices:
        return [], []

    # Build lookup: normalized_title -> GameCubePrice
    price_map: dict[str, object] = {}
    for gp in gamecube_prices:
        key = normalize_title(gp.title)
        price_map[key] = gp
        for alias in (gp.aliases or []):
            alias_key = normalize_title(alias)
            price_map[alias_key] = gp

    # Apply watchlist-level aliases
    alias_map: dict[str, str] = {}
    if aliases:
        for a in aliases:
            if isinstance(a, dict):
                alias_map[normalize_title(a.get("alias", ""))] = normalize_title(a.get("target", ""))

    all_keys = list(price_map.keys())

    candidates = extract_game_candidates(text)
    matched: list[TitleMatch] = []
    unmatched: list[str] = []
    matched_prices_seen: set = set()

    for candidate in candidates:
        norm = normalize_title(candidate)

        # Check alias map first
        if norm in alias_map:
            norm = alias_map[norm]

        # Exact match
        if norm in price_map:
            gp = price_map[norm]
            if id(gp) not in matched_prices_seen:
                matched_prices_seen.add(id(gp))
                matched.append(TitleMatch(
                    raw_text=candidate,
                    matched_title=gp.title,
                    gamecube_price=gp,
                    confidence=1.0,
                    fuzz_score=100,
                ))
            continue

        # Fuzzy match
        if len(norm) < 4:
            continue  # too short to fuzz reliably

        best_match, score = process.extractOne(norm, all_keys, scorer=fuzz.token_sort_ratio) or (None, 0)

        if best_match and score >= MATCH_THRESHOLD:
            gp = price_map[best_match]
            confidence = score / 100.0
            if confidence < 0.75:
                unmatched.append(candidate)  # low confidence — flag for manual review
            elif id(gp) not in matched_prices_seen:
                matched_prices_seen.add(id(gp))
                matched.append(TitleMatch(
                    raw_text=candidate,
                    matched_title=gp.title,
                    gamecube_price=gp,
                    confidence=confidence,
                    fuzz_score=score,
                ))
        else:
            # Only flag as unmatched if it looks like a game title (not generic words)
            if len(norm.split()) >= 2:
                unmatched.append(candidate)

    return matched, unmatched
