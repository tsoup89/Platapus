"""
Pluggable photo-analysis pipeline (OCR + model/brand recognition).

The pipeline is provider-agnostic so the app can later swap in OpenAI, a local
OCR engine, etc. Two providers ship today:

* ``NullPhotoAnalyzer`` — default, returns an empty result (no network, no cost).
* ``ClaudeVisionAnalyzer`` — reuses the Claude-vision image plumbing already in
  ``claude_analyzer.py`` and the per-category ``known_models`` hints. **Fail-open:**
  any error returns an empty result and never raises, so the scrape pipeline is
  never blocked by photo analysis.

``get_photo_analyzer(settings)`` picks the provider based on the
``photo_analysis_enabled`` setting and the presence of a Claude API key.

Python 3.9 — Optional[...] / List[...], never ``X | None``.
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger("platapicker.photo")


@dataclass
class PhotoAnalysis:
    ocr_text: List[str] = field(default_factory=list)
    detected_brand: Optional[str] = None
    detected_model: Optional[str] = None
    detected_accessories: List[str] = field(default_factory=list)
    detected_condition_issues: List[str] = field(default_factory=list)
    missing_parts_risk: str = "UNKNOWN"   # LOW | MEDIUM | HIGH | UNKNOWN
    image_confidence: str = "NONE"        # NONE | LOW | MEDIUM | HIGH
    error: Optional[str] = None

    @property
    def is_empty(self) -> bool:
        return not (self.ocr_text or self.detected_brand or self.detected_model)

    def to_dict(self) -> dict:
        return {
            "ocr_text": self.ocr_text,
            "detected_brand": self.detected_brand,
            "detected_model": self.detected_model,
            "detected_accessories": self.detected_accessories,
            "detected_condition_issues": self.detected_condition_issues,
            "missing_parts_risk": self.missing_parts_risk,
            "image_confidence": self.image_confidence,
            "error": self.error,
        }


class PhotoAnalyzer(ABC):
    """Interface every photo-analysis provider implements."""

    @abstractmethod
    def analyze(self, image_url: str, *, category_config: Optional[dict] = None) -> PhotoAnalysis:
        ...

    def ocr(self, image_url: str) -> List[str]:
        """Text-only extraction. Default delegates to analyze()."""
        return self.analyze(image_url).ocr_text


class NullPhotoAnalyzer(PhotoAnalyzer):
    """Default no-op provider — returns an empty analysis."""

    def analyze(self, image_url: str, *, category_config: Optional[dict] = None) -> PhotoAnalysis:
        return PhotoAnalysis()

    def ocr(self, image_url: str) -> List[str]:
        return []


_VISION_SYSTEM_PROMPT = """\
You are a product-identification engine for a resale arbitrage tool. You are \
given ONE photo of an item for sale. Read any visible text (model/serial \
stickers, brand logos, screen text) and identify the product.

Reply with ONLY a JSON object — no markdown fences, no prose — using this schema:
{
  "ocr_text": ["raw strings you can read, e.g. 'BES878', 'Breville'"],
  "detected_brand": "brand or null",
  "detected_model": "specific model number/name or null",
  "detected_accessories": ["visible accessories, e.g. 'portafilter', 'drip tray'"],
  "detected_condition_issues": ["visible problems, e.g. 'scratches', 'rust', 'missing knob'"],
  "missing_parts_risk": "LOW | MEDIUM | HIGH",
  "image_confidence": "LOW | MEDIUM | HIGH"
}
Be conservative: only report a brand/model you can actually see. Use null when unsure."""


class ClaudeVisionAnalyzer(PhotoAnalyzer):
    """Claude-vision provider. Fail-open — never raises."""

    def __init__(self, api_key: str, model: str = "claude-haiku-4-5"):
        self.api_key = api_key
        self.model = model

    def analyze(self, image_url: str, *, category_config: Optional[dict] = None) -> PhotoAnalysis:
        if not image_url or not self.api_key:
            return PhotoAnalysis()
        try:
            # Reuse the proven image-fetch helper from the existing analyzer.
            from backend.services.claude_analyzer import _fetch_image_b64
            from anthropic import Anthropic

            img = _fetch_image_b64(image_url)
            if not img:
                return PhotoAnalysis(error="image fetch failed")
            b64_data, media_type = img

            # Seed the prompt with known models for this category to aid recognition.
            hint = ""
            if category_config:
                known = category_config.get("known_models", {})
                if known:
                    pairs = []
                    for brand, models in list(known.items())[:8]:
                        pairs.append(f"{brand}: {', '.join(models[:8])}")
                    hint = "\n\nKnown models to watch for:\n" + "\n".join(pairs)

            client = Anthropic(api_key=self.api_key)
            response = client.messages.create(
                model=self.model,
                max_tokens=512,
                system=[{
                    "type": "text",
                    "text": _VISION_SYSTEM_PROMPT + hint,
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": media_type, "data": b64_data},
                        },
                        {"type": "text", "text": "Identify this item and return the JSON."},
                    ],
                }],
            )

            if not response.content:
                raise ValueError("Claude returned an empty response")
            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            data = json.loads(raw)
            return PhotoAnalysis(
                ocr_text=list(data.get("ocr_text", []) or []),
                detected_brand=data.get("detected_brand") or None,
                detected_model=data.get("detected_model") or None,
                detected_accessories=list(data.get("detected_accessories", []) or []),
                detected_condition_issues=list(data.get("detected_condition_issues", []) or []),
                missing_parts_risk=str(data.get("missing_parts_risk", "UNKNOWN") or "UNKNOWN").upper(),
                image_confidence=str(data.get("image_confidence", "LOW") or "LOW").upper(),
                error=None,
            )
        except Exception as e:
            logger.warning(f"Photo analysis failed (fail-open): {e}")
            return PhotoAnalysis(error=str(e))


def get_photo_analyzer(settings: dict) -> PhotoAnalyzer:
    """
    Choose a provider from settings.

    Returns the Claude-vision provider only when ``photo_analysis_enabled`` is
    true and a Claude API key is present; otherwise the Null provider.
    """
    if settings.get("photo_analysis_enabled") and settings.get("claude_api_key"):
        return ClaudeVisionAnalyzer(
            api_key=settings.get("claude_api_key", ""),
            model=settings.get("claude_model", "claude-haiku-4-5"),
        )
    return NullPhotoAnalyzer()
