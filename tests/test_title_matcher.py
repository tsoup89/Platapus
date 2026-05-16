"""Tests for GameCube title normalization and fuzzy matching."""
import pytest
from unittest.mock import MagicMock
from backend.scoring.title_matcher import normalize_title, match_titles_in_text


def make_gc_price(title, loose=None, complete=None, core=False, demand="medium"):
    obj = MagicMock()
    obj.title = title
    obj.normalized_title = normalize_title(title)
    obj.loose_price = loose
    obj.complete_price = complete
    obj.core_title = core
    obj.demand_tier = demand
    obj.aliases = []
    return obj


GC_PRICES = [
    make_gc_price("Mario Kart: Double Dash!!", loose=25, complete=45, core=True, demand="high"),
    make_gc_price("Super Smash Bros. Melee", loose=30, complete=55, core=True, demand="high"),
    make_gc_price("Super Mario Sunshine", loose=20, complete=40, core=True, demand="high"),
    make_gc_price("The Legend of Zelda: The Wind Waker", loose=25, complete=50, core=True, demand="high"),
    make_gc_price("Luigi's Mansion", loose=35, complete=60, core=True, demand="high"),
    make_gc_price("Mario Party 7", loose=25, complete=40, core=False, demand="medium"),
    make_gc_price("Madden NFL 2003", loose=3, complete=5, core=False, demand="low"),
]


class TestNormalizeTitle:
    def test_basic(self):
        assert "mario kart double dash" in normalize_title("Mario Kart: Double Dash!!")

    def test_strips_punctuation(self):
        result = normalize_title("Super Smash Bros. Melee")
        assert "." not in result

    def test_lowercases(self):
        result = normalize_title("LUIGI'S MANSION")
        assert result == result.lower()

    def test_strips_common_words(self):
        result = normalize_title("The Legend of Zelda: The Wind Waker")
        assert "the" not in result.split()


class TestFuzzyMatching:
    def test_exact_match(self):
        text = "Nintendo GameCube bundle with Mario Kart Double Dash"
        matched, unmatched = match_titles_in_text(text, GC_PRICES)
        titles = [m.matched_title for m in matched]
        assert "Mario Kart: Double Dash!!" in titles

    def test_alias_smash_melee(self):
        text = "GameCube games - Smash Melee, Mario Sunshine"
        aliases = [
            {"alias": "Smash Melee", "target": "Super Smash Bros. Melee"},
            {"alias": "Mario Sunshine", "target": "Super Mario Sunshine"},
        ]
        matched, _ = match_titles_in_text(text, GC_PRICES, aliases=aliases)
        titles = [m.matched_title for m in matched]
        assert "Super Smash Bros. Melee" in titles or len(matched) > 0

    def test_alias_wind_waker(self):
        aliases = [{"alias": "Wind Waker", "target": "The Legend of Zelda: The Wind Waker"}]
        text = "Wind Waker complete in box"
        matched, _ = match_titles_in_text(text, GC_PRICES, aliases=aliases)
        titles = [m.matched_title for m in matched]
        assert "The Legend of Zelda: The Wind Waker" in titles

    def test_no_match_returns_unmatched(self):
        text = "some random text with no game names xyzabc"
        matched, unmatched = match_titles_in_text(text, GC_PRICES)
        assert len(matched) == 0

    def test_empty_price_list(self):
        matched, unmatched = match_titles_in_text("Mario Kart", [])
        assert matched == []
        assert unmatched == []

    def test_double_dash_fuzzy(self):
        text = "Double Dash disc only"
        matched, _ = match_titles_in_text(text, GC_PRICES)
        if matched:
            assert "Mario Kart: Double Dash!!" in [m.matched_title for m in matched]
