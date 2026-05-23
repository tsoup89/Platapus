"""
Claude AI listing analyzer.

Uses the Anthropic Python SDK to analyze listing photos and text,
returning a structured verdict before Discord alerts fire.

Fail-open design: any API error returns approved=True so no alerts are blocked.
"""
from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

import httpx

logger = logging.getLogger("platapicker.claude")

_SYSTEM_PROMPT = """\
You are an expert resale deal analyst. You will be given a marketplace listing \
(title, description, asking price, and optionally a photo). Your job is to:

1. Verify the item matches the watchlist search intent.
2. Identify any red flags (damage, missing parts, wrong item, suspicious price, \
seller description mismatch, incomplete lot, etc.).
3. Highlight genuine positives (great price for condition, rare find, complete set, \
low competition, etc.).
4. Give a clear approve / reject decision.

Always reply with ONLY a JSON object — no markdown fences, no prose. \
Use this exact schema:
{
  "approved": true | false,
  "confidence": 0.0-1.0,
  "summary": "one-sentence verdict",
  "flags": ["flag1", "flag2"],
  "positives": ["positive1", "positive2"],
  "photo_notes": "brief notes on what the photo shows, or empty string"
}"""


@dataclass
class ListingReview:
    approved: bool = True
    confidence: float = 0.0
    summary: str = ""
    flags: list[str] = field(default_factory=list)
    positives: list[str] = field(default_factory=list)
    photo_notes: str = ""
    model: str = ""
    error: Optional[str] = None


def _fetch_image_b64(url: str) -> Optional[tuple[str, str]]:
    """Download an image and return (base64_data, media_type), or None on failure."""
    try:
        resp = httpx.get(url, timeout=10, follow_redirects=True)
        if resp.status_code != 200:
            return None
        content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        if not content_type.startswith("image/"):
            content_type = "image/jpeg"
        b64 = base64.standard_b64encode(resp.content).decode("utf-8")
        return b64, content_type
    except Exception as e:
        logger.debug(f"Could not fetch image {url}: {e}")
        return None


def review_listing(
    *,
    title: str,
    description: str = "",
    price: Optional[float] = None,
    image_url: Optional[str] = None,
    keywords: Optional[list[str]] = None,
    category: Optional[str] = None,
    api_key: str,
    model: str = "claude-haiku-4-5",
) -> ListingReview:
    """
    Analyze a listing with Claude and return a ListingReview.

    Uses prompt caching on the system prompt to reduce cost on repeated calls.
    Fail-open: any exception returns approved=True so alerts are never blocked.
    """
    try:
        from anthropic import Anthropic  # lazy import — only needed when Claude enabled

        client = Anthropic(api_key=api_key)

        # ── Build user message content blocks ──────────────────────────
        content: list[dict] = []

        # Optional listing photo
        if image_url:
            img = _fetch_image_b64(image_url)
            if img:
                b64_data, media_type = img
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": b64_data,
                    },
                })

        # Listing text block
        parts = [f"**Title:** {title}"]
        if price is not None:
            parts.append(f"**Asking price:** ${price:,.2f}")
        if keywords:
            parts.append(f"**Search keywords:** {', '.join(keywords)}")
        if category:
            parts.append(f"**Category:** {category}")
        if description:
            # Truncate long descriptions to keep tokens reasonable
            parts.append(f"**Description:** {description[:800]}")

        content.append({"type": "text", "text": "\n".join(parts)})

        # ── Call Claude with cached system prompt ────────────────────────
        response = client.messages.create(
            model=model,
            max_tokens=512,
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": content}],
        )

        raw_text = response.content[0].text.strip()

        # Strip accidental markdown code fences
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[-1]
            raw_text = raw_text.rsplit("```", 1)[0].strip()

        data = json.loads(raw_text)
        return ListingReview(
            approved=bool(data.get("approved", True)),
            confidence=float(data.get("confidence", 0.0)),
            summary=str(data.get("summary", "")),
            flags=list(data.get("flags", [])),
            positives=list(data.get("positives", [])),
            photo_notes=str(data.get("photo_notes", "")),
            model=model,
            error=None,
        )

    except Exception as e:
        logger.warning(f"Claude review failed (fail-open): {e}")
        return ListingReview(
            approved=True,
            confidence=0.0,
            summary="Review unavailable",
            error=str(e),
            model=model,
        )
