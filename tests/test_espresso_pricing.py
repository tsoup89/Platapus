"""Tests for espresso price matching and the accessory filter."""
from unittest.mock import MagicMock

from backend.scoring.espresso_pricing import match_espresso_price


def make_row(match_key, used_price, aliases=None):
    row = MagicMock()
    row.match_key = match_key
    row.used_price = used_price
    row.aliases = aliases or []
    return row


PRICES = [
    make_row("breville barista express", 380),
    make_row("la marzocco linea mini", 3200),
    make_row("delonghi", 90, aliases=["de longhi"]),
]


class TestMachineMatching:
    def test_specific_model_matches(self):
        price, row = match_espresso_price("Breville Barista Express BES870XL", PRICES)
        assert price == 380

    def test_most_specific_row_wins(self):
        price, row = match_espresso_price("DeLonghi La Marzocco Linea Mini", PRICES)
        assert price == 3200

    def test_alias_matches(self):
        price, row = match_espresso_price("De'Longhi espresso machine", PRICES)
        assert price == 90

    def test_no_match(self):
        price, row = match_espresso_price("Gaggia Classic Pro", PRICES)
        assert price is None and row is None


class TestAccessoryFilter:
    def test_portafilter_rejected(self):
        price, row = match_espresso_price(
            "Portafilter for Breville Barista Express", PRICES
        )
        assert price is None

    def test_for_parts_rejected(self):
        price, row = match_espresso_price(
            "La Marzocco Linea Mini for parts not working", PRICES
        )
        assert price is None

    def test_trailing_part_rejected(self):
        # Regression: the old "part " term (with trailing space) missed
        # "part" at the end of the title.
        price, row = match_espresso_price(
            "Breville Barista Express replacement part", PRICES
        )
        assert price is None

    def test_descaling_prefix_still_matches(self):
        price, row = match_espresso_price(
            "Descaling kit for Breville Barista Express", PRICES
        )
        assert price is None

    def test_substring_inside_word_does_not_reject(self):
        # "counterparts" contains "parts"; "knobby" contains "knob" —
        # whole-word matching must not treat these as accessory listings.
        price, row = match_espresso_price(
            "Breville Barista Express outperforms its counterparts", PRICES
        )
        assert price == 380
