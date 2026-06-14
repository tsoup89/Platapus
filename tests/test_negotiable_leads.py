"""Tests for negotiable / no-fixed-price lead handling.

Covers the rule that Craigslist/OfferUp "best offer", "$0", and missing-price
listings (a) are detected as negotiable, (b) always alert via _should_alert when
flagged as a lead, and (c) auctions are excluded (their bid is a real number).
"""
from types import SimpleNamespace

from backend.services.runner import _is_negotiable_price, _should_alert


class TestIsNegotiablePrice:
    def test_missing_price_is_negotiable(self):
        assert _is_negotiable_price("Patio dining set", None, None, "craigslist") is True

    def test_zero_price_is_negotiable(self):
        assert _is_negotiable_price("Patio set", "", 0, "craigslist") is True

    def test_best_offer_marker_is_negotiable_even_with_price(self):
        assert _is_negotiable_price("Weber grill - best offer", "", 200, "craigslist") is True
        assert _is_negotiable_price("Hanamint set OBO", "", 300, "offerup") is True

    def test_firm_price_no_marker_is_not_negotiable(self):
        assert _is_negotiable_price("Sonos Arc $350 firm", "", 350, "craigslist") is False

    def test_auction_is_never_negotiable(self):
        # A $1 opening bid is a real (rising) number handled by the end-time gate.
        assert _is_negotiable_price("Vintage lot", "", 1, "auctionninja") is False
        assert _is_negotiable_price("Lot no price", "", None, "auctionninja") is False


class TestShouldAlertLead:
    def _wl(self, min_rating="STEAL"):
        return SimpleNamespace(min_rating_to_alert=min_rating)

    def test_lead_alerts_even_when_rating_below_threshold(self):
        # Even with the strictest gate (STEAL-only) and a low rating, a lead alerts.
        score = SimpleNamespace(rating="FAIR", is_lead=True)
        assert _should_alert(score, self._wl(min_rating="STEAL")) is True

    def test_lead_alerts_even_when_rating_is_pass(self):
        score = SimpleNamespace(rating="PASS", is_lead=True)
        assert _should_alert(score, self._wl(min_rating="GOOD")) is True

    def test_non_lead_pass_does_not_alert(self):
        score = SimpleNamespace(rating="PASS", is_lead=False)
        assert _should_alert(score, self._wl(min_rating="GOOD")) is False

    def test_non_lead_respects_rating_gate(self):
        score = SimpleNamespace(rating="FAIR", is_lead=False)
        assert _should_alert(score, self._wl(min_rating="GOOD")) is False
        good = SimpleNamespace(rating="GOOD", is_lead=False)
        assert _should_alert(good, self._wl(min_rating="GOOD")) is True
