"""Pydantic schemas for API request/response validation."""
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, field_validator
import json


class WatchlistCreate(BaseModel):
    name: str
    enabled: bool = True
    category: Optional[str] = None
    keywords: list[str] = []
    negative_keywords: list[str] = []
    brands: list[str] = []
    aliases: list[Any] = []
    locations: list[str] = []
    radius_miles: int = 50
    min_price: float = 0
    max_price: float = 99999
    sources_enabled: list[str] = []
    run_frequency_minutes: int = 60
    min_rating_to_alert: str = "GOOD"
    min_profit_margin: float = 0.20
    min_profit_dollars: float = 50
    discord_webhook_id: Optional[int] = None
    notes: str = ""


class WatchlistUpdate(WatchlistCreate):
    pass


class WatchlistOut(BaseModel):
    id: int
    name: str
    enabled: bool
    category: Optional[str]
    keywords: list[str]
    negative_keywords: list[str]
    brands: list[str]
    aliases: list[Any]
    locations: list[str]
    radius_miles: int
    min_price: float
    max_price: float
    sources_enabled: list[str]
    run_frequency_minutes: int
    min_rating_to_alert: str
    min_profit_margin: float
    min_profit_dollars: float
    discord_webhook_id: Optional[int]
    notes: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_safe(cls, obj):
        return cls(
            id=obj.id,
            name=obj.name,
            enabled=obj.enabled,
            category=obj.category,
            keywords=obj.keywords,
            negative_keywords=obj.negative_keywords,
            brands=obj.brands,
            aliases=obj.aliases,
            locations=obj.locations,
            radius_miles=obj.radius_miles,
            min_price=obj.min_price,
            max_price=obj.max_price,
            sources_enabled=obj.sources_enabled,
            run_frequency_minutes=obj.run_frequency_minutes,
            min_rating_to_alert=obj.min_rating_to_alert,
            min_profit_margin=obj.min_profit_margin,
            min_profit_dollars=obj.min_profit_dollars,
            discord_webhook_id=obj.discord_webhook_id,
            notes=obj.notes or "",
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )


class DiscordWebhookCreate(BaseModel):
    name: str
    webhook_url: str
    enabled: bool = True


class DiscordWebhookOut(BaseModel):
    id: int
    name: str
    webhook_url: str
    enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SourceOut(BaseModel):
    id: int
    name: str
    enabled: bool
    type: Optional[str]
    status: str
    last_run_at: Optional[datetime]
    last_success_at: Optional[datetime]
    last_error: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScraperRunOut(BaseModel):
    id: int
    source_name: str
    watchlist_id: Optional[int]
    started_at: datetime
    ended_at: Optional[datetime]
    status: str
    raw_count: int
    parsed_count: int
    filtered_count: int
    duplicate_count: int
    alert_count: int
    error_message: Optional[str]
    debug_artifact_path: Optional[str]

    model_config = {"from_attributes": True}


class DealScoreOut(BaseModel):
    id: int
    listing_id: int
    rating: Optional[str]
    score: float
    estimated_value: Optional[float]
    conservative_value: Optional[float]
    target_buy_price: Optional[float]
    estimated_profit: Optional[float]
    profit_margin: Optional[float]
    confidence: float
    reasons: list[str]
    warnings: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_safe(cls, obj):
        return cls(
            id=obj.id,
            listing_id=obj.listing_id,
            rating=obj.rating,
            score=obj.score,
            estimated_value=obj.estimated_value,
            conservative_value=obj.conservative_value,
            target_buy_price=obj.target_buy_price,
            estimated_profit=obj.estimated_profit,
            profit_margin=obj.profit_margin,
            confidence=obj.confidence,
            reasons=obj.reasons,
            warnings=obj.warnings,
            created_at=obj.created_at,
        )


class ListingOut(BaseModel):
    id: int
    source: str
    source_listing_id: Optional[str]
    watchlist_id: Optional[int]
    title: str
    description: str
    price: Optional[float]
    url: Optional[str]
    image_url: Optional[str]
    location: Optional[str]
    seller: Optional[str]
    posted_at: Optional[datetime]
    first_seen_at: datetime
    last_seen_at: datetime
    ignored: bool
    alert_sent: bool
    alert_sent_at: Optional[datetime]
    deal_score: Optional[DealScoreOut]

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_safe(cls, obj):
        return cls(
            id=obj.id,
            source=obj.source,
            source_listing_id=obj.source_listing_id,
            watchlist_id=obj.watchlist_id,
            title=obj.title,
            description=obj.description or "",
            price=obj.price,
            url=obj.url,
            image_url=obj.image_url,
            location=obj.location,
            seller=obj.seller,
            posted_at=obj.posted_at,
            first_seen_at=obj.first_seen_at,
            last_seen_at=obj.last_seen_at,
            ignored=obj.ignored,
            alert_sent=obj.alert_sent,
            alert_sent_at=obj.alert_sent_at,
            deal_score=DealScoreOut.from_orm_safe(obj.deal_score) if obj.deal_score else None,
        )


class GameCubePriceOut(BaseModel):
    id: int
    title: str
    normalized_title: str
    loose_price: Optional[float]
    complete_price: Optional[float]
    new_price: Optional[float]
    graded_price: Optional[float]
    box_only_price: Optional[float]
    manual_only_price: Optional[float]
    demand_tier: str
    sell_speed: str
    core_title: bool
    aliases: list[str]
    last_updated: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_safe(cls, obj):
        return cls(
            id=obj.id,
            title=obj.title,
            normalized_title=obj.normalized_title,
            loose_price=obj.loose_price,
            complete_price=obj.complete_price,
            new_price=obj.new_price,
            graded_price=obj.graded_price,
            box_only_price=obj.box_only_price,
            manual_only_price=obj.manual_only_price,
            demand_tier=obj.demand_tier,
            sell_speed=obj.sell_speed,
            core_title=obj.core_title,
            aliases=obj.aliases,
            last_updated=obj.last_updated,
        )


class GameCubePriceUpdate(BaseModel):
    loose_price: Optional[float] = None
    complete_price: Optional[float] = None
    new_price: Optional[float] = None
    graded_price: Optional[float] = None
    demand_tier: Optional[str] = None
    sell_speed: Optional[str] = None
    core_title: Optional[bool] = None
    aliases: Optional[list[str]] = None


class TitleMappingOut(BaseModel):
    id: int
    raw_text: str
    normalized_text: str
    mapped_gamecube_price_id: Optional[int]
    confidence: float
    user_confirmed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class OverviewStats(BaseModel):
    scrapers_enabled: int
    watchlists_enabled: int
    last_run: Optional[datetime]
    alerts_today: int
    errors_today: int
    sources: list[SourceOut]
