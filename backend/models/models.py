import json
from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, String, Text, ForeignKey
)
from sqlalchemy.orm import relationship
from .database import Base


def now():
    return datetime.utcnow()


class Watchlist(Base):
    __tablename__ = "watchlists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    enabled = Column(Boolean, default=True)
    category = Column(String)
    keywords_json = Column(Text, default="[]")
    negative_keywords_json = Column(Text, default="[]")
    brands_json = Column(Text, default="[]")
    aliases_json = Column(Text, default="[]")
    locations_json = Column(Text, default="[]")
    radius_miles = Column(Integer, default=50)
    min_price = Column(Float, default=0)
    max_price = Column(Float, default=99999)
    sources_enabled_json = Column(Text, default="[]")
    run_frequency_minutes = Column(Integer, default=60)
    min_rating_to_alert = Column(String, default="GOOD")
    min_profit_margin = Column(Float, default=0.20)
    min_profit_dollars = Column(Float, default=50)
    discord_webhook_id = Column(Integer, ForeignKey("discord_webhooks.id"), nullable=True)
    notes = Column(Text, default="")
    # ── Automation ──────────────────────────────────────────────────────────
    auto_outreach_enabled = Column(Boolean, default=False)
    outreach_message_template = Column(Text, default="")  # empty = use default
    auto_list_on_buy = Column(Boolean, default=False)     # auto-list on FB after promote
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)

    listings = relationship("Listing", back_populates="watchlist")
    discord_webhook = relationship("DiscordWebhook", back_populates="watchlists")

    @property
    def keywords(self):
        return json.loads(self.keywords_json or "[]")

    @keywords.setter
    def keywords(self, value):
        self.keywords_json = json.dumps(value)

    @property
    def negative_keywords(self):
        return json.loads(self.negative_keywords_json or "[]")

    @negative_keywords.setter
    def negative_keywords(self, value):
        self.negative_keywords_json = json.dumps(value)

    @property
    def brands(self):
        return json.loads(self.brands_json or "[]")

    @brands.setter
    def brands(self, value):
        self.brands_json = json.dumps(value)

    @property
    def aliases(self):
        return json.loads(self.aliases_json or "[]")

    @aliases.setter
    def aliases(self, value):
        self.aliases_json = json.dumps(value)

    @property
    def locations(self):
        return json.loads(self.locations_json or "[]")

    @locations.setter
    def locations(self, value):
        self.locations_json = json.dumps(value)

    @property
    def sources_enabled(self):
        return json.loads(self.sources_enabled_json or "[]")

    @sources_enabled.setter
    def sources_enabled(self, value):
        self.sources_enabled_json = json.dumps(value)


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    enabled = Column(Boolean, default=True)
    type = Column(String)  # facebook, auctionninja, generic
    config_json = Column(Text, default="{}")
    last_run_at = Column(DateTime, nullable=True)
    last_success_at = Column(DateTime, nullable=True)
    status = Column(String, default="unknown")  # healthy, warning, failed, needs_login, possible_block
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)

    runs = relationship("ScraperRun", back_populates="source_rel")

    @property
    def config(self):
        return json.loads(self.config_json or "{}")

    @config.setter
    def config(self, value):
        self.config_json = json.dumps(value)


class ScraperRun(Base):
    __tablename__ = "scraper_runs"

    id = Column(Integer, primary_key=True, index=True)
    source_name = Column(String, ForeignKey("sources.name"), nullable=False)
    watchlist_id = Column(Integer, ForeignKey("watchlists.id"), nullable=True)
    started_at = Column(DateTime, default=now)
    ended_at = Column(DateTime, nullable=True)
    status = Column(String, default="running")  # running, success, failed, partial
    raw_count = Column(Integer, default=0)
    parsed_count = Column(Integer, default=0)
    filtered_count = Column(Integer, default=0)
    duplicate_count = Column(Integer, default=0)
    alert_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    debug_artifact_path = Column(String, nullable=True)

    source_rel = relationship("Source", back_populates="runs")
    watchlist = relationship("Watchlist")


class Listing(Base):
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False)
    source_listing_id = Column(String, nullable=True)
    watchlist_id = Column(Integer, ForeignKey("watchlists.id"), nullable=True)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    price = Column(Float, nullable=True)
    url = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    location = Column(String, nullable=True)
    distance_miles = Column(Float, nullable=True)
    seller = Column(String, nullable=True)
    posted_at = Column(DateTime, nullable=True)
    first_seen_at = Column(DateTime, default=now)
    last_seen_at = Column(DateTime, default=now, onupdate=now)
    raw_payload_json = Column(Text, default="{}")
    ignored = Column(Boolean, default=False)
    alert_sent = Column(Boolean, default=False)
    alert_sent_at = Column(DateTime, nullable=True)
    # ── Auto-outreach ───────────────────────────────────────────────────────
    outreach_status = Column(String, nullable=True)    # None | QUEUED | SENT | FAILED
    outreach_sent_at = Column(DateTime, nullable=True)

    watchlist = relationship("Watchlist", back_populates="listings")
    deal_score = relationship("DealScore", back_populates="listing", uselist=False)
    claude_review = relationship("ClaudeReview", back_populates="listing", uselist=False)
    price_history = relationship(
        "ListingPriceHistory",
        back_populates="listing",
        order_by="ListingPriceHistory.recorded_at",
    )

    @property
    def raw_payload(self):
        return json.loads(self.raw_payload_json or "{}")

    @raw_payload.setter
    def raw_payload(self, value):
        self.raw_payload_json = json.dumps(value, default=str)


class DealScore(Base):
    __tablename__ = "deal_scores"

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), unique=True)
    rating = Column(String)  # STEAL, GREAT, GOOD, FAIR, PASS
    score = Column(Float, default=0)
    estimated_value = Column(Float, nullable=True)
    conservative_value = Column(Float, nullable=True)
    target_buy_price = Column(Float, nullable=True)
    estimated_profit = Column(Float, nullable=True)
    profit_margin = Column(Float, nullable=True)
    confidence = Column(Float, default=0)
    reasons_json = Column(Text, default="[]")
    warnings_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=now)

    listing = relationship("Listing", back_populates="deal_score")

    @property
    def reasons(self):
        return json.loads(self.reasons_json or "[]")

    @reasons.setter
    def reasons(self, value):
        self.reasons_json = json.dumps(value)

    @property
    def warnings(self):
        return json.loads(self.warnings_json or "[]")

    @warnings.setter
    def warnings(self, value):
        self.warnings_json = json.dumps(value)


class DiscordWebhook(Base):
    __tablename__ = "discord_webhooks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    webhook_url = Column(String, nullable=False)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now)

    watchlists = relationship("Watchlist", back_populates="discord_webhook")


class GameCubePrice(Base):
    __tablename__ = "gamecube_prices"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    normalized_title = Column(String, nullable=False, index=True)
    loose_price = Column(Float, nullable=True)
    complete_price = Column(Float, nullable=True)
    new_price = Column(Float, nullable=True)
    graded_price = Column(Float, nullable=True)
    box_only_price = Column(Float, nullable=True)
    manual_only_price = Column(Float, nullable=True)
    demand_tier = Column(String, default="medium")  # high, medium, low
    sell_speed = Column(String, default="medium")   # fast, medium, slow
    core_title = Column(Boolean, default=False)
    aliases_json = Column(Text, default="[]")
    last_updated = Column(DateTime, default=now)

    title_mappings = relationship("TitleMapping", back_populates="gamecube_price")

    @property
    def aliases(self):
        return json.loads(self.aliases_json or "[]")

    @aliases.setter
    def aliases(self, value):
        self.aliases_json = json.dumps(value)


class TitleMapping(Base):
    __tablename__ = "title_mappings"

    id = Column(Integer, primary_key=True, index=True)
    raw_text = Column(String, nullable=False, unique=True)
    normalized_text = Column(String, nullable=False)
    mapped_gamecube_price_id = Column(Integer, ForeignKey("gamecube_prices.id"), nullable=True)
    confidence = Column(Float, default=0)
    user_confirmed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)

    gamecube_price = relationship("GameCubePrice", back_populates="title_mappings")


class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String, primary_key=True)
    value_json = Column(Text, default="null")

    @property
    def value(self):
        return json.loads(self.value_json or "null")

    @value.setter
    def value(self, val):
        self.value_json = json.dumps(val)


class ListingPriceHistory(Base):
    __tablename__ = "listing_price_history"

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False)
    price = Column(Float, nullable=True)
    recorded_at = Column(DateTime, default=now)

    listing = relationship("Listing", back_populates="price_history")


class ClaudeReview(Base):
    __tablename__ = "claude_reviews"

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), unique=True, nullable=False)
    approved = Column(Boolean, default=True)
    confidence = Column(Float, default=0.0)
    summary = Column(Text, default="")
    flags_json = Column(Text, default="[]")
    positives_json = Column(Text, default="[]")
    photo_notes = Column(Text, default="")
    model = Column(String, default="")
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now)

    listing = relationship("Listing", back_populates="claude_review")

    @property
    def flags(self):
        return json.loads(self.flags_json or "[]")

    @flags.setter
    def flags(self, value):
        self.flags_json = json.dumps(value)

    @property
    def positives(self):
        return json.loads(self.positives_json or "[]")

    @positives.setter
    def positives(self, value):
        self.positives_json = json.dumps(value)


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    category = Column(String, nullable=True)
    condition = Column(String, default="GOOD")  # NEW, LIKE_NEW, GOOD, FAIR, POOR
    purchase_price = Column(Float, nullable=True)
    purchase_date = Column(DateTime, nullable=True)
    source_listing_id = Column(Integer, ForeignKey("listings.id"), nullable=True)
    notes = Column(Text, default="")
    status = Column(String, default="DRAFT")  # DRAFT, LISTED, SOLD, ARCHIVED
    listed_price = Column(Float, nullable=True)   # target sell price (filled via auto-pricing or manual)
    price_suggestion_json = Column(Text, nullable=True)  # cached auto-pricing result
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)

    source_listing = relationship("Listing", foreign_keys=[source_listing_id])
    photos = relationship(
        "InventoryPhoto",
        back_populates="item",
        order_by="InventoryPhoto.order_index",
        cascade="all, delete-orphan",
    )
    sell_listings = relationship(
        "SellListing",
        back_populates="item",
        order_by="SellListing.created_at",
        cascade="all, delete-orphan",
    )

    @property
    def price_suggestion(self):
        if not self.price_suggestion_json:
            return None
        return json.loads(self.price_suggestion_json)

    @price_suggestion.setter
    def price_suggestion(self, value):
        self.price_suggestion_json = json.dumps(value) if value is not None else None


class InventoryPhoto(Base):
    __tablename__ = "inventory_photos"

    id = Column(Integer, primary_key=True, index=True)
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"), nullable=False)
    file_path = Column(String, nullable=False)  # relative to inventory_photos dir
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime, default=now)

    item = relationship("InventoryItem", back_populates="photos")


class SellListing(Base):
    """A listing of an InventoryItem on a sell-side marketplace platform."""
    __tablename__ = "sell_listings"

    id = Column(Integer, primary_key=True, index=True)
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"), nullable=False)
    platform = Column(String, nullable=False)  # "ebay" | "facebook"
    platform_listing_id = Column(String, nullable=True)   # eBay item ID / FB listing ID
    platform_url = Column(String, nullable=True)          # URL of the live listing
    listed_price = Column(Float, nullable=True)
    # DRAFT → POSTING → POSTED | FAILED; also SOLD | REMOVED
    status = Column(String, default="DRAFT")
    listed_at = Column(DateTime, nullable=True)
    sold_at = Column(DateTime, nullable=True)
    removed_at = Column(DateTime, nullable=True)
    sale_price = Column(Float, nullable=True)
    platform_fees = Column(Float, nullable=True)
    shipping_cost = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    screenshot_path = Column(String, nullable=True)  # last screenshot (debug / failure)
    action_url = Column(String, nullable=True)        # manual-fallback URL for the frontend
    raw_metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)

    item = relationship("InventoryItem", back_populates="sell_listings")

    @property
    def raw_metadata(self):
        if not self.raw_metadata_json:
            return {}
        return json.loads(self.raw_metadata_json)

    @raw_metadata.setter
    def raw_metadata(self, value):
        self.raw_metadata_json = json.dumps(value) if value is not None else None


class MarketValueCache(Base):
    __tablename__ = "market_value_cache"

    id = Column(Integer, primary_key=True)
    keyword = Column(String, nullable=False, index=True)
    category = Column(String, nullable=True)
    median_price = Column(Float, nullable=True)
    mean_price = Column(Float, nullable=True)
    min_price = Column(Float, nullable=True)
    max_price = Column(Float, nullable=True)
    sample_count = Column(Integer, default=0)
    source = Column(String, default="ebay_sold")
    fetched_at = Column(DateTime, default=now)
    expires_at = Column(DateTime, nullable=True)
