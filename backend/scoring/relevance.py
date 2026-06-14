"""Watchlist relevance matching.

Decides whether a listing is actually *about* what a watchlist is looking for,
independent of price. This is the gate that keeps unrelated items — e.g. the
perfume, jewelry, and bric-a-brac that show up alongside the real target in a
broad Craigslist "for sale" search or an AuctionNinja estate-auction listing —
from being scored and alerted on.

Matching is done on whole words / phrases rather than loose substrings, so that
short keywords like "ds" don't match "kids" and "wii" doesn't match an
unrelated substring. Multi-word keywords ("espresso machine") match when the
words appear consecutively, separated by any whitespace.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


def term_matches(term: str, text: str) -> bool:
    """True if ``term`` appears in ``text`` as a whole word or phrase.

    ``text`` is expected to be lowercased by the caller; we lowercase ``term``
    (and ``text`` defensively) so callers don't have to.
    """
    term = (term or "").strip().lower()
    if not term:
        return False
    words = term.split()
    pattern = r"\b" + r"\s+".join(re.escape(w) for w in words) + r"\b"
    return re.search(pattern, text.lower()) is not None


def find_matches(terms, text: str) -> list[str]:
    """Return the subset of ``terms`` that match ``text`` (whole-word)."""
    text = text.lower()
    return [t for t in (terms or []) if t and t.strip() and term_matches(t, text)]


@dataclass
class RelevanceResult:
    relevant: bool
    matched_terms: list = field(default_factory=list)
    negative_hits: list = field(default_factory=list)
    reason: str = ""


def check_relevance(
    title: str,
    description: str,
    keywords,
    brands,
    negative_keywords=None,
) -> RelevanceResult:
    """Decide whether a listing is on-topic for a watchlist.

    A listing is relevant when it does **not** hit a negative keyword **and**
    it matches at least one watchlist keyword or brand. If the watchlist has no
    keywords and no brands configured, there is nothing to match against, so we
    treat the listing as relevant rather than silently dropping everything.
    """
    text = f"{title or ''} {description or ''}".lower()

    neg_hits = find_matches(negative_keywords, text)
    if neg_hits:
        return RelevanceResult(
            relevant=False,
            negative_hits=neg_hits,
            reason=f"negative keyword(s) matched: {', '.join(neg_hits)}",
        )

    terms = [t for t in (list(keywords or []) + list(brands or [])) if t and t.strip()]
    if not terms:
        return RelevanceResult(
            relevant=True,
            reason="no keywords or brands configured — cannot assess relevance",
        )

    hits = find_matches(terms, text)
    if hits:
        return RelevanceResult(
            relevant=True,
            matched_terms=hits,
            reason=f"matched: {', '.join(hits[:5])}",
        )

    return RelevanceResult(
        relevant=False,
        reason="no watchlist keyword or brand found in title/description",
    )
