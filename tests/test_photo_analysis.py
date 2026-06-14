"""Tests for the pluggable photo-analysis pipeline (mocked — no network)."""
import sys
import types
import json

import pytest

from backend.scoring.category_config import get_category_config
from backend.services.photo_analysis import (
    PhotoAnalysis, NullPhotoAnalyzer, ClaudeVisionAnalyzer, get_photo_analyzer,
)


class TestNullProvider:
    def test_returns_empty(self):
        a = NullPhotoAnalyzer()
        result = a.analyze("http://example.com/x.jpg", category_config=get_category_config("espresso"))
        assert isinstance(result, PhotoAnalysis)
        assert result.is_empty
        assert result.image_confidence == "NONE"

    def test_ocr_empty(self):
        assert NullPhotoAnalyzer().ocr("http://x") == []


class TestFactory:
    def test_disabled_returns_null(self):
        assert isinstance(get_photo_analyzer({"photo_analysis_enabled": False}), NullPhotoAnalyzer)

    def test_enabled_without_key_returns_null(self):
        assert isinstance(
            get_photo_analyzer({"photo_analysis_enabled": True, "claude_api_key": ""}),
            NullPhotoAnalyzer,
        )

    def test_enabled_with_key_returns_claude(self):
        analyzer = get_photo_analyzer(
            {"photo_analysis_enabled": True, "claude_api_key": "sk-test"}
        )
        assert isinstance(analyzer, ClaudeVisionAnalyzer)


# ── Mock plumbing for ClaudeVisionAnalyzer ──────────────────────────────────
_FAKE_RESPONSE_JSON = {
    "ocr_text": ["BES878", "Breville"],
    "detected_brand": "Breville",
    "detected_model": "BES878",
    "detected_accessories": ["portafilter", "drip tray"],
    "detected_condition_issues": ["visible scratches"],
    "missing_parts_risk": "LOW",
    "image_confidence": "MEDIUM",
}


class _FakeContentBlock:
    def __init__(self, text):
        self.text = text


class _FakeMessages:
    def __init__(self, payload):
        self._payload = payload

    def create(self, **kwargs):
        resp = types.SimpleNamespace()
        resp.content = [_FakeContentBlock(json.dumps(self._payload))]
        return resp


class _FakeAnthropic:
    _payload = _FAKE_RESPONSE_JSON

    def __init__(self, *args, **kwargs):
        self.messages = _FakeMessages(self._payload)


@pytest.fixture
def mock_anthropic(monkeypatch):
    # Inject a fake `anthropic` module so `from anthropic import Anthropic` works.
    fake_mod = types.ModuleType("anthropic")
    fake_mod.Anthropic = _FakeAnthropic
    monkeypatch.setitem(sys.modules, "anthropic", fake_mod)
    # Stub the image fetch so no network call happens.
    monkeypatch.setattr(
        "backend.services.claude_analyzer._fetch_image_b64",
        lambda url: ("ZmFrZQ==", "image/jpeg"),
    )


class TestClaudeVisionProvider:
    def test_parses_fields(self, mock_anthropic):
        analyzer = ClaudeVisionAnalyzer(api_key="sk-test")
        result = analyzer.analyze(
            "http://example.com/x.jpg",
            category_config=get_category_config("espresso"),
        )
        assert result.detected_brand == "Breville"
        assert result.detected_model == "BES878"
        assert "BES878" in result.ocr_text
        assert result.image_confidence == "MEDIUM"
        assert result.error is None

    def test_no_image_url_returns_empty(self, mock_anthropic):
        analyzer = ClaudeVisionAnalyzer(api_key="sk-test")
        result = analyzer.analyze("", category_config=None)
        assert result.is_empty

    def test_failure_is_fail_open(self, monkeypatch):
        # Fake image fetch OK, but the SDK raises → should return empty, not raise.
        fake_mod = types.ModuleType("anthropic")

        class _Boom:
            def __init__(self, *a, **k):
                raise RuntimeError("boom")

        fake_mod.Anthropic = _Boom
        monkeypatch.setitem(sys.modules, "anthropic", fake_mod)
        monkeypatch.setattr(
            "backend.services.claude_analyzer._fetch_image_b64",
            lambda url: ("ZmFrZQ==", "image/jpeg"),
        )
        analyzer = ClaudeVisionAnalyzer(api_key="sk-test")
        result = analyzer.analyze("http://example.com/x.jpg")
        assert result.is_empty
        assert result.error is not None
