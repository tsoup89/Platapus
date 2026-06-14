"""Tests for the Bad-Listing / undervaluation detector."""
from dataclasses import dataclass
from typing import Optional

from backend.scoring.category_config import get_category_config
from backend.scoring.bad_listing import detect_bad_listing
from tests.fixtures import listings as fx


ESPRESSO = get_category_config("espresso")
SONOS = get_category_config("sonos")
GAMECUBE = get_category_config("gamecube")


@dataclass
class _FakePhoto:
    detected_brand: Optional[str] = None
    detected_model: Optional[str] = None
    is_empty: bool = False


def _run(fixture, cfg, **kw):
    return detect_bad_listing(
        title=fixture["title"],
        description=fixture["description"],
        brands=fixture["brands"],
        category_config=cfg,
        **kw,
    )


class TestMisspellings:
    def test_expresso(self):
        r = _run(fx.MISSPELLED_ESPRESSO, ESPRESSO)
        assert any("expresso" in s.lower() or "espresso" in s.lower() for s in r.detected_signals)

    def test_fuzzy_brand_breveille(self):
        r = detect_bad_listing(
            title="Breveille machine for sale",
            description="",
            brands=["Breville"],
            category_config=ESPRESSO,
        )
        assert any("misspell" in s.lower() or "breville" in s.lower() for s in r.detected_signals)

    def test_sonnos(self):
        r = detect_bad_listing(
            title="Sonnos speaker", description="", brands=["Sonos"],
            category_config=SONOS,
        )
        assert any("sonos" in s.lower() for s in r.detected_signals)

    def test_game_cube_spacing(self):
        r = detect_bad_listing(
            title="Nintendo Game Cube console", description="", brands=["Nintendo"],
            category_config=GAMECUBE,
        )
        assert any("gamecube" in s.lower() for s in r.detected_signals)


class TestGenericAndUrgency:
    def test_generic_title(self):
        r = _run(fx.GENERIC_TITLE, ESPRESSO)
        assert any("generic" in s.lower() or "short" in s.lower() for s in r.detected_signals)

    def test_urgency_language(self):
        r = detect_bad_listing(
            title="Breville espresso machine", description="must go, moving sale this weekend",
            brands=["Breville"], category_config=ESPRESSO,
        )
        assert any("urgency" in s.lower() for s in r.detected_signals)

    def test_bundle_language(self):
        r = detect_bad_listing(
            title="Espresso setup lot", description="everything pictured, garage cleanout",
            brands=["Breville"], category_config=ESPRESSO,
        )
        assert any("bundle" in s.lower() for s in r.detected_signals)


class TestPhotoSignals:
    def test_brand_in_photo_not_title(self):
        photo = _FakePhoto(detected_brand="Breville", detected_model="BES878")
        r = detect_bad_listing(
            title="coffee machine", description="works",
            brands=["Breville"], category_config=ESPRESSO,
            photo_analysis=photo,
        )
        assert any("photo" in s.lower() for s in r.detected_signals)
        assert r.bad_listing_good_item is True


class TestVerdict:
    def test_clean_listing_not_flagged(self):
        r = _run(fx.GOOD_ESPRESSO, ESPRESSO)
        assert r.bad_listing_good_item is False

    def test_under_described_flagged(self):
        r = _run(fx.MISSPELLED_ESPRESSO, ESPRESSO)
        assert r.bad_listing_good_item is True
        assert r.suggested_reason
        assert 0 <= r.undervaluation_score <= 100
