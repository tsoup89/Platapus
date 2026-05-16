"""Tests for watchlist keyword filtering logic."""
import pytest
from backend.scoring.deal_scorer import score_listing


ESPRESSO_KWS = ["espresso machine", "coffee grinder", "dual boiler"]
ESPRESSO_BRANDS = ["La Marzocco", "Profitec", "Rancilio", "Breville"]
ESPRESSO_NEG = ["broken", "parts only", "nespresso", "keurig", "pod"]


class TestNegativeKeywords:
    def test_nespresso_filtered(self):
        result = score_listing(
            title="Nespresso pod machine like new",
            description="",
            price=100,
            watchlist_keywords=ESPRESSO_KWS,
            watchlist_brands=ESPRESSO_BRANDS,
            watchlist_negative_keywords=ESPRESSO_NEG,
        )
        assert result.rating == "PASS"

    def test_broken_filtered(self):
        result = score_listing(
            title="La Marzocco espresso machine broken",
            description="for parts only",
            price=50,
            watchlist_keywords=ESPRESSO_KWS,
            watchlist_brands=ESPRESSO_BRANDS,
            watchlist_negative_keywords=ESPRESSO_NEG,
        )
        assert result.rating == "PASS"
        assert len(result.warnings) > 0

    def test_good_listing_passes(self):
        result = score_listing(
            title="Rancilio Silvia espresso machine",
            description="Excellent condition, barely used",
            price=300,
            watchlist_keywords=ESPRESSO_KWS,
            watchlist_brands=ESPRESSO_BRANDS,
            watchlist_negative_keywords=ESPRESSO_NEG,
        )
        assert result.rating != "PASS"

    def test_case_insensitive_negative(self):
        result = score_listing(
            title="Keurig Coffee Machine",
            description="",
            price=100,
            watchlist_keywords=ESPRESSO_KWS,
            watchlist_brands=ESPRESSO_BRANDS,
            watchlist_negative_keywords=ESPRESSO_NEG,
        )
        assert result.rating == "PASS"


OUTDOOR_KWS = ["patio set", "outdoor furniture", "teak table", "patio chairs"]
OUTDOOR_BRANDS = ["Brown Jordan", "Polywood", "Restoration Hardware", "Pottery Barn"]
OUTDOOR_NEG = ["dollhouse", "miniature", "cover only", "cushions only"]


class TestOutdoorFurnitureFiltering:
    def test_cushions_only_filtered(self):
        result = score_listing(
            title="Patio cushions only for sale",
            description="cushions only no furniture",
            price=50,
            watchlist_keywords=OUTDOOR_KWS,
            watchlist_brands=OUTDOOR_BRANDS,
            watchlist_negative_keywords=OUTDOOR_NEG,
        )
        assert result.rating == "PASS"

    def test_premium_brand_passes(self):
        result = score_listing(
            title="Brown Jordan Outdoor Patio Set",
            description="6 chairs and table excellent condition",
            price=600,
            watchlist_keywords=OUTDOOR_KWS,
            watchlist_brands=OUTDOOR_BRANDS,
            watchlist_negative_keywords=OUTDOOR_NEG,
        )
        assert result.confidence > 0.2

    def test_no_match_is_pass(self):
        result = score_listing(
            title="Random item for sale",
            description="completely unrelated",
            price=100,
            watchlist_keywords=OUTDOOR_KWS,
            watchlist_brands=OUTDOOR_BRANDS,
            watchlist_negative_keywords=OUTDOOR_NEG,
        )
        assert result.rating == "PASS"
