"""Tests for the Net Flip Score economics engine."""
from backend.scoring.category_config import get_category_config
from backend.scoring.net_flip import compute_net_flip


ESPRESSO = get_category_config("espresso")
FURNITURE = get_category_config("furniture")


class TestEconomics:
    def test_label_passthrough(self):
        r = compute_net_flip(
            deal_label="GREAT", buy_price=180, resale_price=375,
            category_config=ESPRESSO, comp_sample_count=12,
        )
        assert r.deal_label == "GREAT"

    def test_net_profit_math(self):
        # resale 400, fee 13% = 52, shipping 35, repair 10 (default, condition good),
        # tax 0, buy 150  →  net = 400-52-35-10-150 = 153
        r = compute_net_flip(
            deal_label="GREAT", buy_price=150, resale_price=400,
            category_config=ESPRESSO, comp_sample_count=20,
            condition_unknown=False, condition_poor=False,
        )
        assert round(r.estimated_net_profit, 2) == 153.0
        assert r.estimated_fees == 52.0
        assert r.estimated_shipping_cost == 35.0

    def test_roi_percent(self):
        r = compute_net_flip(
            deal_label="GREAT", buy_price=100, resale_price=300,
            category_config=ESPRESSO, comp_sample_count=20,
        )
        # net = 300 - 39 - 35 - 10 - 100 = 116 ; ROI = 116/100 = 116%
        assert round(r.estimated_roi_percent, 0) == 116.0

    def test_local_pickup_zero_shipping(self):
        r = compute_net_flip(
            deal_label="GOOD", buy_price=50, resale_price=200,
            category_config=FURNITURE, comp_sample_count=10,
        )
        assert r.estimated_shipping_cost == 0.0

    def test_tax_reduces_profit(self):
        no_tax = compute_net_flip(
            deal_label="GOOD", buy_price=200, resale_price=400,
            category_config=ESPRESSO, comp_sample_count=20, tax_rate=0.0,
        )
        taxed = compute_net_flip(
            deal_label="GOOD", buy_price=200, resale_price=400,
            category_config=ESPRESSO, comp_sample_count=20, tax_rate=0.10,
        )
        assert taxed.estimated_net_profit < no_tax.estimated_net_profit
        assert round(no_tax.estimated_net_profit - taxed.estimated_net_profit, 2) == 20.0


class TestConfidenceAndRisk:
    def test_thin_comps_low_confidence(self):
        r = compute_net_flip(
            deal_label="GOOD", buy_price=100, resale_price=300,
            category_config=ESPRESSO, comp_sample_count=1,
        )
        assert r.confidence == "LOW"
        assert any("comp" in s.lower() for s in r.score_reasons)

    def test_many_comps_high_confidence(self):
        r = compute_net_flip(
            deal_label="GOOD", buy_price=100, resale_price=300,
            category_config=ESPRESSO, comp_sample_count=15,
        )
        assert r.confidence == "HIGH"

    def test_poor_condition_raises_risk_and_repair(self):
        good = compute_net_flip(
            deal_label="GOOD", buy_price=100, resale_price=300,
            category_config=ESPRESSO, comp_sample_count=15, condition_poor=False,
        )
        poor = compute_net_flip(
            deal_label="GOOD", buy_price=100, resale_price=300,
            category_config=ESPRESSO, comp_sample_count=15, condition_poor=True,
        )
        assert poor.estimated_repair_cost > good.estimated_repair_cost
        assert poor.estimated_net_profit < good.estimated_net_profit

    def test_negative_profit_caps_score(self):
        r = compute_net_flip(
            deal_label="FAIR", buy_price=350, resale_price=380,
            category_config=ESPRESSO, comp_sample_count=15,
        )
        assert r.estimated_net_profit < 0
        assert r.net_flip_score <= 10

    def test_photo_missing_parts_adds_repair(self):
        base = compute_net_flip(
            deal_label="GOOD", buy_price=100, resale_price=300,
            category_config=ESPRESSO, comp_sample_count=15,
        )
        risky = compute_net_flip(
            deal_label="GOOD", buy_price=100, resale_price=300,
            category_config=ESPRESSO, comp_sample_count=15,
            photo_missing_parts_risk="HIGH",
        )
        assert risky.estimated_repair_cost > base.estimated_repair_cost


class TestScoreBounds:
    def test_no_pricing_returns_zero(self):
        r = compute_net_flip(
            deal_label="PASS", buy_price=None, resale_price=None,
            category_config=ESPRESSO,
        )
        assert r.net_flip_score == 0
        assert r.risk_level == "HIGH"

    def test_score_in_range(self):
        r = compute_net_flip(
            deal_label="STEAL", buy_price=50, resale_price=500,
            category_config=ESPRESSO, comp_sample_count=30,
        )
        assert 0 <= r.net_flip_score <= 100
