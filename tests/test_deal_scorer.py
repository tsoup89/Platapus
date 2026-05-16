"""Tests for the generic deal scoring engine."""
import pytest
from backend.scoring.deal_scorer import score_listing, _rating_from_ratio, DEAL_THRESHOLDS


class TestRatingFromRatio:
    def test_steal(self):
        assert _rating_from_ratio(40, 100, DEAL_THRESHOLDS) == "STEAL"

    def test_great(self):
        assert _rating_from_ratio(50, 100, DEAL_THRESHOLDS) == "GREAT"

    def test_good(self):
        assert _rating_from_ratio(60, 100, DEAL_THRESHOLDS) == "GOOD"

    def test_fair(self):
        assert _rating_from_ratio(70, 100, DEAL_THRESHOLDS) == "FAIR"

    def test_pass(self):
        assert _rating_from_ratio(80, 100, DEAL_THRESHOLDS) == "PASS"

    def test_zero_value(self):
        assert _rating_from_ratio(50, 0, DEAL_THRESHOLDS) == "PASS"


class TestScoreListing:
    KEYWORDS = ["espresso machine", "dual boiler", "coffee grinder"]
    BRANDS = ["Profitec", "La Marzocco", "Rancilio"]
    NEG = ["broken", "parts only", "nespresso"]

    def test_negative_keyword_blocks(self):
        result = score_listing(
            title="Broken espresso machine for parts",
            description="",
            price=100,
            watchlist_keywords=self.KEYWORDS,
            watchlist_brands=self.BRANDS,
            watchlist_negative_keywords=self.NEG,
        )
        assert result.rating == "PASS"
        assert result.score == 0

    def test_brand_match_increases_confidence(self):
        result = score_listing(
            title="Profitec Pro 300",
            description="Works great",
            price=500,
            watchlist_keywords=self.KEYWORDS,
            watchlist_brands=self.BRANDS,
            watchlist_negative_keywords=self.NEG,
        )
        assert result.confidence > 0.2

    def test_steal_rating_with_value(self):
        result = score_listing(
            title="Rancilio Silvia espresso machine",
            description="Like new",
            price=100,
            watchlist_keywords=self.KEYWORDS,
            watchlist_brands=self.BRANDS,
            watchlist_negative_keywords=self.NEG,
            estimated_value=500,
            conservative_value=400,
        )
        assert result.rating in ("STEAL", "GREAT")

    def test_pass_with_high_price(self):
        result = score_listing(
            title="Espresso machine",
            description="",
            price=900,
            watchlist_keywords=self.KEYWORDS,
            watchlist_brands=self.BRANDS,
            watchlist_negative_keywords=self.NEG,
            estimated_value=500,
            conservative_value=400,
        )
        assert result.rating == "PASS"

    def test_profit_calculation(self):
        result = score_listing(
            title="Profitec espresso machine",
            description="",
            price=200,
            watchlist_keywords=self.KEYWORDS,
            watchlist_brands=self.BRANDS,
            watchlist_negative_keywords=[],
            estimated_value=500,
            conservative_value=400,
            platform_fee_pct=0.13,
        )
        assert result.estimated_profit is not None
        assert result.estimated_profit > 0

    def test_no_value_data_returns_fair_on_match(self):
        result = score_listing(
            title="La Marzocco espresso machine",
            description="",
            price=500,
            watchlist_keywords=self.KEYWORDS,
            watchlist_brands=self.BRANDS,
            watchlist_negative_keywords=[],
        )
        assert result.rating in ("FAIR", "GOOD", "GREAT", "STEAL")
