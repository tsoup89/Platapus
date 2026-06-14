"""Parsing tests for the requests-based scrapers (eBay, Craigslist).

These run against static HTML/dict fixtures — no network. They pin down the
current marketplace layouts so a silent parser regression shows up as a
test failure instead of an empty scrape.
"""
from backend.scrapers.ebay import EbayScraper, _extract_price as ebay_price
from backend.scrapers.craigslist import CraigslistScraper, _extract_price as cl_price


EBAY_HTML = """
<ul>
  <li class="s-card" data-listingid="123456789012">
    <div class="su-card-container__header">
      <a href="https://www.ebay.com/itm/123456789012?hash=item1&amp;_trkparms=abc"></a>
    </div>
    <div class="s-card__title">Nintendo GameCube Console Bundle<span class="clipped">Opens in a new window or tab</span></div>
    <div class="s-card__subtitle">Pre-Owned</div>
    <span class="s-card__price">$89.99</span>
    <div class="s-card__attribute-row">Free delivery</div>
    <div class="s-card__attribute-row">Located in Portland, OR</div>
    <img class="s-card__image" src="https://i.ebayimg.com/images/g/abc/s-l500.jpg" />
  </li>
  <li class="s-card" data-listingid="222222222222">
    <div class="s-card__title">Breville Barista Express</div>
    <span class="s-card__price">$240.00</span>
    <span class="s-card__price">$310.00</span>
    <div class="s-card__attribute-row">+$12.50 delivery</div>
  </li>
  <li class="s-card" data-listingid="333333333333">
    <div class="s-card__title">Shop on eBay</div>
    <span class="s-card__price">$20.00</span>
  </li>
  <li class="s-card">
    <div class="s-card__title">No listing id — ad slot</div>
  </li>
</ul>
"""


class TestEbayParsing:
    def setup_method(self):
        self.scraper = EbayScraper()

    def test_parses_valid_cards_and_skips_junk(self):
        items = self.scraper._parse_html(EBAY_HTML)
        # "Shop on eBay" placeholder and the id-less ad slot are dropped
        assert [i["id"] for i in items] == ["123456789012", "222222222222"]

    def test_full_card_fields(self):
        item = self.scraper._parse_html(EBAY_HTML)[0]
        assert item["title"] == "Nintendo GameCube Console Bundle"
        assert item["price"] == 89.99  # free delivery adds nothing
        assert item["url"] == "https://www.ebay.com/itm/123456789012"  # tracking stripped
        assert item["location"] == "Portland, OR"
        assert item["condition"] == "Pre-Owned"
        assert item["image_url"] == "https://i.ebayimg.com/images/g/abc/s-l500.jpg"

    def test_price_range_takes_lower_and_adds_shipping(self):
        item = self.scraper._parse_html(EBAY_HTML)[1]
        assert item["price"] == 252.50  # min(240, 310) + 12.50

    def test_layout_change_yields_empty_not_crash(self):
        items = self.scraper._parse_html("<div class='totally-new-layout'></div>")
        assert items == []

    def test_parse_listing_normalizes(self):
        raw = self.scraper._parse_html(EBAY_HTML)[0]
        listing = self.scraper.parse_listing(raw)
        assert listing.source == "ebay"
        assert listing.source_listing_id == "123456789012"
        assert listing.price == 89.99
        assert listing.raw_payload == raw


class TestEbayPriceExtraction:
    def test_plain(self):
        assert ebay_price("$89.99") == 89.99

    def test_thousands_separator(self):
        assert ebay_price("$1,234.56") == 1234.56

    def test_range_takes_first(self):
        assert ebay_price("$10.00 to $50.00") == 10.0

    def test_no_digits(self):
        assert ebay_price("Free") is None

    def test_none(self):
        assert ebay_price(None) is None


class TestCraigslistParsing:
    def setup_method(self):
        self.scraper = CraigslistScraper()

    def test_parse_listing_from_json_item(self):
        raw = {
            "id": 7700000001,
            "title": "GameCube with 2 controllers",
            "price": "$120",
            "url": "https://portland.craigslist.org/mlt/vgm/d/x/7700000001.html",
            "location": "SE Portland",
            "images": ["https://images.craigslist.org/abc_600x450.jpg"],
        }
        listing = self.scraper.parse_listing(raw)
        assert listing.source == "craigslist"
        assert listing.source_listing_id == "7700000001"
        assert listing.title == "GameCube with 2 controllers"
        assert listing.price == 120.0
        assert listing.image_url == "https://images.craigslist.org/abc_600x450.jpg"

    def test_numeric_price_passes_through(self):
        listing = self.scraper.parse_listing({"id": 1, "title": "x", "price": 75})
        assert listing.price == 75.0

    def test_missing_title_returns_none(self):
        assert self.scraper.parse_listing({"id": 1, "price": "$50"}) is None


class TestCraigslistPriceExtraction:
    def test_dollar_with_comma(self):
        assert cl_price("$1,200") == 1200.0

    def test_no_digits(self):
        assert cl_price("free") is None

    def test_empty(self):
        assert cl_price("") is None
