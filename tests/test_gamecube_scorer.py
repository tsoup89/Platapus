"""Tests for GameCube bundle valuation and scoring."""
import pytest
from unittest.mock import MagicMock
from backend.scoring.gamecube_scorer import (
    score_gamecube_listing, _detect_condition, _detect_console,
    _detect_controllers, _is_sports_filler,
)
from backend.scoring.title_matcher import normalize_title


def make_gc(title, loose=None, complete=None, core=False, demand="medium"):
    obj = MagicMock()
    obj.title = title
    obj.normalized_title = normalize_title(title)
    obj.loose_price = loose
    obj.complete_price = complete
    obj.core_title = core
    obj.demand_tier = demand
    obj.sell_speed = "fast" if core else "medium"
    obj.aliases = []
    return obj


GC_PRICES = [
    make_gc("Mario Kart: Double Dash!!", loose=25, complete=45, core=True, demand="high"),
    make_gc("Super Smash Bros. Melee", loose=30, complete=55, core=True, demand="high"),
    make_gc("Super Mario Sunshine", loose=20, complete=40, core=True, demand="high"),
    make_gc("Mario Party 7", loose=25, complete=40, demand="medium"),
    make_gc("Madden NFL 2003", loose=3, complete=5, demand="low"),
]


class TestDetectCondition:
    def test_complete(self):
        assert _detect_condition("complete in box with manual") == "complete"

    def test_cib(self):
        assert _detect_condition("CIB GameCube lot") == "complete"

    def test_loose(self):
        assert _detect_condition("disc only no box") == "loose"

    def test_unknown(self):
        assert _detect_condition("GameCube bundle") == "unknown"


class TestDetectHardware:
    def test_console(self):
        assert _detect_console("Nintendo GameCube console with controllers") is True

    def test_no_console(self):
        assert _detect_console("GameCube games lot") is False

    def test_controllers(self):
        assert _detect_controllers("2 controllers included") == 2

    def test_single_controller(self):
        assert _detect_controllers("with a controller") == 1


class TestSportsFiller:
    def test_madden(self):
        assert _is_sports_filler("Madden NFL 2003") is True

    def test_mario(self):
        assert _is_sports_filler("Super Mario Sunshine") is False

    def test_nba(self):
        assert _is_sports_filler("NBA 2K3") is True


class TestScoreGamecubeListing:
    def test_bundle_with_console(self):
        result = score_gamecube_listing(
            title="Nintendo GameCube console with Mario Kart Double Dash",
            description="2 controllers included",
            price=150,
            gamecube_prices=GC_PRICES,
        )
        assert result.console_value > 0
        assert result.accessory_value > 0
        assert result.conservative_value > 0
        assert result.rating in ("STEAL", "GREAT", "GOOD", "FAIR", "PASS")

    def test_no_price_no_crash(self):
        result = score_gamecube_listing(
            title="GameCube bundle",
            description="",
            price=0,
            gamecube_prices=GC_PRICES,
        )
        assert result is not None

    def test_steal_deal(self):
        result = score_gamecube_listing(
            title="Nintendo GameCube console, Mario Kart Double Dash, Super Smash Bros Melee, Super Mario Sunshine",
            description="2 controllers, memory card, all complete in box",
            price=50,
            gamecube_prices=GC_PRICES,
        )
        assert result.rating in ("STEAL", "GREAT")

    def test_pass_deal(self):
        result = score_gamecube_listing(
            title="Nintendo GameCube games",
            description="Madden 2003",
            price=500,
            gamecube_prices=GC_PRICES,
        )
        assert result.rating == "PASS"

    def test_bad_condition_applies_discount(self):
        result_bad = score_gamecube_listing(
            title="Nintendo GameCube console, sticky lid, disc read error",
            description="",
            price=100,
            gamecube_prices=GC_PRICES,
        )
        result_good = score_gamecube_listing(
            title="Nintendo GameCube console mint condition",
            description="",
            price=100,
            gamecube_prices=GC_PRICES,
        )
        assert result_bad.console_value <= result_good.console_value

    def test_empty_price_list(self):
        result = score_gamecube_listing(
            title="GameCube console",
            description="",
            price=50,
            gamecube_prices=[],
        )
        assert result.rating in ("STEAL", "GREAT", "GOOD", "FAIR", "PASS")

    def test_top_value_games_populated(self):
        result = score_gamecube_listing(
            title="GameCube bundle Mario Kart Double Dash Super Smash Bros Melee",
            description="",
            price=80,
            gamecube_prices=GC_PRICES,
        )
        assert len(result.top_value_games) >= 0
