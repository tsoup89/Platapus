"""Tests for the watchlist relevance gate."""
import pytest
from backend.scoring.relevance import term_matches, find_matches, check_relevance
from backend.scoring.deal_scorer import score_listing


KEYWORDS = ["espresso machine", "coffee grinder", "dual boiler"]
BRANDS = ["La Marzocco", "Profitec", "Rancilio"]
NEG = ["broken", "parts only", "nespresso"]


class TestTermMatches:
    def test_whole_word(self):
        assert term_matches("espresso", "vintage espresso machine") is True

    def test_phrase(self):
        assert term_matches("espresso machine", "great espresso machine here") is True

    def test_no_substring_false_positive(self):
        # "ds" should not match inside "kids"
        assert term_matches("ds", "kids toys for sale") is False

    def test_case_insensitive(self):
        assert term_matches("Rancilio", "rancilio silvia") is True

    def test_phrase_not_present(self):
        assert term_matches("espresso machine", "espresso beans and a machine gun") is False


class TestCheckRelevance:
    def test_perfume_is_off_topic(self):
        verdict = check_relevance(
            "Vintage Chanel No. 5 Perfume", "sealed bottle",
            KEYWORDS, BRANDS, NEG,
        )
        assert verdict.relevant is False
        assert "no watchlist keyword" in verdict.reason

    def test_keyword_match_is_relevant(self):
        verdict = check_relevance(
            "Rancilio espresso machine", "", KEYWORDS, BRANDS, NEG,
        )
        assert verdict.relevant is True
        assert verdict.matched_terms

    def test_negative_keyword_blocks(self):
        verdict = check_relevance(
            "Broken espresso machine for parts", "", KEYWORDS, BRANDS, NEG,
        )
        assert verdict.relevant is False
        assert verdict.negative_hits

    def test_no_keywords_configured_is_relevant(self):
        verdict = check_relevance("anything at all", "", [], [], [])
        assert verdict.relevant is True


class TestScoreListingRelevanceGate:
    def test_off_topic_with_value_is_pass(self):
        # Regression: an off-topic listing with a (mistakenly looked-up) market
        # value must NOT be rated a deal on price alone.
        result = score_listing(
            title="Chanel No. 5 Perfume",
            description="brand new in box",
            price=30,
            watchlist_keywords=KEYWORDS,
            watchlist_brands=BRANDS,
            watchlist_negative_keywords=NEG,
            estimated_value=100,
            conservative_value=80,
        )
        assert result.rating == "PASS"
        assert result.score == 0

    def test_on_topic_steal_still_alerts(self):
        result = score_listing(
            title="Rancilio Silvia espresso machine",
            description="like new",
            price=100,
            watchlist_keywords=KEYWORDS,
            watchlist_brands=BRANDS,
            watchlist_negative_keywords=NEG,
            estimated_value=500,
            conservative_value=400,
        )
        assert result.rating in ("STEAL", "GREAT")
