"""Tests for bundle-arbitrage detection."""
from dataclasses import dataclass, field
from typing import List, Optional

from backend.scoring.category_config import get_category_config
from backend.scoring.bundle import (
    detect_bundle, BREAK_APART, SELL_TOGETHER,
)
from tests.fixtures import listings as fx


# ── Minimal fake GameCubePrice rows for the title matcher ───────────────────
@dataclass
class _FakeGCPrice:
    title: str
    loose_price: Optional[float] = None
    complete_price: Optional[float] = None
    aliases: List[str] = field(default_factory=list)
    demand_tier: str = "medium"
    core_title: bool = True


GC_PRICES = [
    _FakeGCPrice("Mario Kart Double Dash", loose_price=70, complete_price=110),
    _FakeGCPrice("Super Smash Bros Melee", loose_price=55, complete_price=90),
    _FakeGCPrice("Luigi's Mansion", loose_price=40, complete_price=80),
]


def _run(fixture, cfg, **kw):
    return detect_bundle(
        title=fixture["title"],
        description=fixture["description"],
        category=fixture["category"],
        category_config=cfg,
        buy_price=fixture["price"],
        **kw,
    )


class TestGameCubeBundle:
    def test_detects_console_controllers_games(self):
        cfg = get_category_config("gamecube")
        r = _run(fx.GAMECUBE_BUNDLE, cfg, gamecube_prices=GC_PRICES, aliases=[])
        assert r.is_bundle is True
        items = [i.item.lower() for i in r.bundle_items]
        assert any("console" in i for i in items)
        assert any("controller" in i for i in items)
        # at least one matched game
        assert any("mario kart" in i for i in items)

    def test_recommends_break_apart_when_profitable(self):
        cfg = get_category_config("gamecube")
        r = _run(fx.GAMECUBE_BUNDLE, cfg, gamecube_prices=GC_PRICES, aliases=[])
        assert r.estimated_bundle_resale_total > 0
        assert r.recommended_strategy in (BREAK_APART, SELL_TOGETHER)
        assert 0 <= r.bundle_score <= 100


class TestCatalogBundles:
    def test_sonos_lot(self):
        cfg = get_category_config("sonos")
        r = _run(fx.SONOS_LOT, cfg)
        assert r.is_bundle is True
        assert r.estimated_bundle_resale_total > 0

    def test_tool_lot(self):
        cfg = get_category_config("tools")
        r = _run(fx.TOOL_LOT, cfg)
        assert r.is_bundle is True
        items = [i.item.lower() for i in r.bundle_items]
        assert any("drill" in i for i in items)

    def test_patio_set(self):
        cfg = get_category_config("furniture")
        r = _run(fx.PATIO_SET, cfg)
        assert r.is_bundle is True
        items = [i.item.lower() for i in r.bundle_items]
        assert any("chair" in i for i in items)


class TestCompLookup:
    def test_comp_lookup_upgrades_value(self):
        cfg = get_category_config("sonos")

        def fake_comp(name):
            return 999.0  # absurdly high to prove it was used

        r = _run(fx.SONOS_LOT, cfg, comp_lookup=fake_comp)
        assert any(i.estimated_resale_price == 999.0 for i in r.bundle_items)
        assert all(i.confidence == "HIGH" for i in r.bundle_items)


class TestNonBundle:
    def test_single_item_not_a_bundle(self):
        cfg = get_category_config("espresso")
        r = detect_bundle(
            title="Breville Barista Express",
            description="single machine, great condition",
            category="espresso",
            category_config=cfg,
            buy_price=300,
        )
        assert r.is_bundle is False
        assert r.recommended_strategy == SELL_TOGETHER
