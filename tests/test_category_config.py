"""Tests for the per-category config loader."""
from backend.scoring.category_config import (
    get_category_config,
    canonical_category,
    CATEGORY_DEFAULTS,
)


class TestCanonicalCategory:
    def test_direct_key(self):
        assert canonical_category("espresso") == "espresso"

    def test_alias(self):
        assert canonical_category("Espresso Machines") == "espresso"
        assert canonical_category("ultrawide monitor") == "monitor"
        assert canonical_category("Outdoor Furniture") == "furniture"

    def test_unknown_returns_none(self):
        assert canonical_category("llamas") is None

    def test_none(self):
        assert canonical_category(None) is None


class TestGetCategoryConfig:
    def test_unknown_falls_back_to_defaults(self):
        cfg = get_category_config("llamas")
        assert cfg["_category"] is None
        assert cfg["platform_fee_pct"] == CATEGORY_DEFAULTS["platform_fee_pct"]

    def test_override_applies(self):
        cfg = get_category_config("Espresso Machines")
        assert cfg["_category"] == "espresso"
        assert cfg["default_shipping_cost"] == 35.0  # espresso override

    def test_dict_keys_are_merged_not_replaced(self):
        # Espresso adds 'expresso' but should still inherit the global 'game cube'.
        cfg = get_category_config("espresso")
        assert cfg["misspellings"]["expresso"] == "espresso"
        assert cfg["misspellings"]["game cube"] == "gamecube"

    def test_furniture_is_local_pickup(self):
        cfg = get_category_config("furniture")
        assert cfg["local_pickup"] is True
        assert cfg["platform_fee_pct"] == 0.0

    def test_known_models_present(self):
        cfg = get_category_config("sonos")
        assert "Sonos" in cfg["known_models"]
        assert "Arc" in cfg["known_models"]["Sonos"]
