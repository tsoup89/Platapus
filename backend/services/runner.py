"""
Orchestrates scraper runs: fetches listings, scores them, saves to DB,
and sends Discord alerts and Expo push notifications.
"""
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.database import SessionLocal
from backend.models.models import (
    Watchlist, Source, ScraperRun, Listing, DealScore, GameCubePrice, AppSetting,
    ListingPriceHistory, ClaudeReview,
)
from backend.services.market_value import get_market_value
from backend.scrapers.base import NormalizedListing
from backend.scrapers.mock_scraper import MockScraper
from backend.scrapers.auctionninja import AuctionNinjaScraper
from backend.scrapers.facebook import FacebookScraper
from backend.scrapers.craigslist import CraigslistScraper
from backend.scrapers.offerup import OfferUpScraper
from backend.scrapers.mercari import MercariScraper
from backend.scrapers.ebay import EbayScraper
from backend.scoring.deal_scorer import score_listing
from backend.scoring.gamecube_scorer import score_gamecube_listing
from backend.services import discord as discord_service
from backend.services import push_notifications as push_service
from backend.services.settings import get_all_settings

logger = logging.getLogger("platapicker.runner")

SCRAPER_REGISTRY = {
    "mock": MockScraper,
    "auctionninja": AuctionNinjaScraper,
    "facebook": FacebookScraper,
    "craigslist": CraigslistScraper,
    "offerup": OfferUpScraper,
    "mercari": MercariScraper,
    "ebay": EbayScraper,
}


def _get_scraper(source_name: str, config: dict):
    cls = SCRAPER_REGISTRY.get(source_name)
    if not cls:
        raise ValueError(f"Unknown scraper: {source_name}")
    return cls(config=config)


def _record_price_change(db: Session, existing: Listing, new_price: Optional[float]):
    """Record a ListingPriceHistory entry when price changes by more than $1."""
    old_price = existing.price
    if (
        new_price is not None
        and old_price is not None
        and abs(new_price - old_price) > 1.0
    ):
        logger.info(
            f"Price change detected: ${old_price:.2f} → ${new_price:.2f} for '{existing.title}'"
        )
        history = ListingPriceHistory(
            listing_id=existing.id,
            price=new_price,
            recorded_at=datetime.utcnow(),
        )
        db.add(history)
        existing.price = new_price


def _deduplicate(db: Session, listing: NormalizedListing, watchlist_id: int) -> Optional[Listing]:
    """Returns existing DB listing for this watchlist if duplicate, else None."""
    q = db.query(Listing).filter(Listing.watchlist_id == watchlist_id)

    if listing.source_listing_id:
        existing = q.filter(
            Listing.source == listing.source,
            Listing.source_listing_id == listing.source_listing_id,
        ).first()
        if existing:
            existing.last_seen_at = datetime.utcnow()
            _record_price_change(db, existing, listing.price)
            return existing

    # Fallback: URL match within this watchlist
    if listing.url:
        existing = q.filter(Listing.url == listing.url).first()
        if existing:
            existing.last_seen_at = datetime.utcnow()
            _record_price_change(db, existing, listing.price)
            return existing

    return None


def _save_listing(db: Session, listing: NormalizedListing, watchlist_id: int) -> Listing:
    row = Listing(
        source=listing.source,
        source_listing_id=listing.source_listing_id,
        watchlist_id=watchlist_id,
        title=listing.title,
        description=listing.description or "",
        price=listing.price,
        url=listing.url,
        image_url=listing.image_url,
        location=listing.location,
        distance_miles=listing.distance_miles,
        seller=listing.seller,
        posted_at=listing.posted_at,
    )
    row.raw_payload = listing.raw_payload
    db.add(row)
    db.flush()

    # Record initial price history entry
    if listing.price is not None:
        initial_history = ListingPriceHistory(
            listing_id=row.id,
            price=listing.price,
            recorded_at=datetime.utcnow(),
        )
        db.add(initial_history)

    return row


def _score_listing(db: Session, listing: Listing, watchlist: Watchlist, settings: dict):
    thresholds = settings.get("deal_thresholds", {
        "STEAL": 0.45, "GREAT": 0.55, "GOOD": 0.65, "FAIR": 0.75
    })

    if watchlist.category == "gamecube":
        gc_prices = db.query(GameCubePrice).all()
        aliases = watchlist.aliases
        result = score_gamecube_listing(
            title=listing.title,
            description=listing.description or "",
            price=listing.price or 0,
            gamecube_prices=gc_prices,
            platform_fee_pct=settings.get("gamecube_platform_fee_pct", 0.13),
            bundle_discount=settings.get("gamecube_bundle_discount", 0.85),
            low_demand_discount=settings.get("gamecube_low_demand_discount", 0.60),
            thresholds=thresholds,
            aliases=aliases,
        )
        score_row = DealScore(
            listing_id=listing.id,
            rating=result.rating,
            score=result.score,
            estimated_value=result.estimated_value,
            conservative_value=result.conservative_value,
            target_buy_price=result.target_buy_30pct,
            estimated_profit=result.estimated_profit,
            profit_margin=result.profit_margin,
            confidence=result.confidence,
        )
        score_row.reasons = result.reasons
        score_row.warnings = result.warnings
    else:
        # Fetch market value from eBay sold listings for non-gamecube watchlists
        market = get_market_value(
            keyword=listing.title,
            category=watchlist.category,
            db=db,
        )
        estimated_value = market.median_price if market and not market.error else None
        conservative_value = (
            round(market.median_price * 0.8, 2)
            if estimated_value is not None
            else None
        )

        result = score_listing(
            title=listing.title,
            description=listing.description or "",
            price=listing.price or 0,
            watchlist_keywords=watchlist.keywords,
            watchlist_brands=watchlist.brands,
            watchlist_negative_keywords=watchlist.negative_keywords,
            thresholds=thresholds,
            estimated_value=estimated_value,
            conservative_value=conservative_value,
        )
        score_row = DealScore(
            listing_id=listing.id,
            rating=result.rating,
            score=result.score,
            estimated_value=result.estimated_value,
            conservative_value=result.conservative_value,
            target_buy_price=result.target_buy_price,
            estimated_profit=result.estimated_profit,
            profit_margin=result.profit_margin,
            confidence=result.confidence,
        )
        score_row.reasons = result.reasons
        score_row.warnings = result.warnings

    db.add(score_row)
    return score_row


RATING_ORDER = ["STEAL", "GREAT", "GOOD", "FAIR", "PASS"]


def _should_alert(score: DealScore, watchlist: Watchlist) -> bool:
    if score.rating == "PASS":
        return False
    min_rating = watchlist.min_rating_to_alert or "GOOD"
    try:
        return RATING_ORDER.index(score.rating) <= RATING_ORDER.index(min_rating)
    except ValueError:
        return False


def _send_alert(listing: Listing, score: DealScore, watchlist: Watchlist, claude_review=None):
    if not watchlist.discord_webhook or not watchlist.discord_webhook.enabled:
        return False
    return discord_service.send_deal_alert(
        webhook_url=watchlist.discord_webhook.webhook_url,
        title=listing.title,
        price=listing.price or 0,
        rating=score.rating,
        estimated_value=score.estimated_value,
        conservative_value=score.conservative_value,
        target_buy_price=score.target_buy_price,
        estimated_profit=score.estimated_profit,
        source=listing.source,
        watchlist_name=watchlist.name,
        url=listing.url or "",
        location=listing.location,
        reasons=score.reasons,
        warnings=score.warnings,
        image_url=listing.image_url,
        claude_summary=claude_review.summary if claude_review else None,
        claude_flags=claude_review.flags if claude_review else None,
        claude_positives=claude_review.positives if claude_review else None,
    )


def run_scraper_for_watchlist(
    source_name: Optional[str] = None,
    watchlist_id: Optional[int] = None,
):
    """Main runner — called from background tasks or CLI."""
    db = SessionLocal()
    try:
        settings = get_all_settings(db)
        watchlists = db.query(Watchlist).filter(Watchlist.enabled == True).all()
        sources = db.query(Source).filter(Source.enabled == True).all()

        if watchlist_id:
            watchlists = [w for w in watchlists if w.id == watchlist_id]
        if source_name:
            sources = [s for s in sources if s.name == source_name]

        for watchlist in watchlists:
            enabled_sources = watchlist.sources_enabled or [s.name for s in sources]
            for source in sources:
                if source.name not in enabled_sources:
                    continue
                _run_one(db, source, watchlist, settings)
    finally:
        db.close()


def _run_one(db: Session, source: Source, watchlist: Watchlist, settings: dict):
    logger.info(f"▶ Running {source.name} for watchlist '{watchlist.name}'")
    run = ScraperRun(
        source_name=source.name,
        watchlist_id=watchlist.id,
        started_at=datetime.utcnow(),
        status="running",
    )
    db.add(run)
    db.flush()

    try:
        scraper = _get_scraper(source.name, source.config)

        keywords = watchlist.keywords or []
        location = (watchlist.locations or ["New York, NY"])[0]
        radius = watchlist.radius_miles or 50

        all_raw = []
        for keyword in keywords[:5]:
            raw, health = scraper.run(keyword, location, radius)
            all_raw.extend(raw)
            run.raw_count += health.raw_count

        seen: set = set()
        new_listings = []
        for item in all_raw:
            key = item.source_listing_id or item.url or item.title
            if key in seen:
                continue
            seen.add(key)
            existing = _deduplicate(db, item, watchlist.id)
            if existing:
                run.duplicate_count += 1
                continue
            row = _save_listing(db, item, watchlist.id)
            new_listings.append(row)
            run.parsed_count += 1

        alert_count = 0
        qualifying: list[tuple] = []  # (listing, score)
        for listing in new_listings:
            score = _score_listing(db, listing, watchlist, settings)
            db.flush()
            if not listing.ignored and _should_alert(score, watchlist):
                qualifying.append((listing, score))

        # ── Claude review gate ────────────────────────────────────────────
        claude_enabled = settings.get("claude_enabled", False)
        claude_api_key = settings.get("claude_api_key", "")
        qualifying_with_review: list[tuple] = []  # (listing, score, review_or_none)

        if claude_enabled and claude_api_key:
            from backend.services.claude_analyzer import review_listing
            claude_model = settings.get("claude_model", "claude-haiku-4-5")
            for listing, score in qualifying:
                review = review_listing(
                    title=listing.title,
                    description=listing.description or "",
                    price=listing.price,
                    image_url=listing.image_url,
                    keywords=watchlist.keywords,
                    category=watchlist.category,
                    api_key=claude_api_key,
                    model=claude_model,
                )
                # Save review row
                cr = ClaudeReview(
                    listing_id=listing.id,
                    approved=review.approved,
                    confidence=review.confidence,
                    summary=review.summary,
                    model=review.model,
                    error=review.error,
                    photo_notes=review.photo_notes,
                )
                cr.flags = review.flags
                cr.positives = review.positives
                db.add(cr)
                db.flush()
                if review.approved:
                    qualifying_with_review.append((listing, score, review))
                else:
                    logger.info(
                        f"🤖 Claude rejected '{listing.title}': {review.summary}"
                    )
        else:
            qualifying_with_review = [(l, s, None) for l, s in qualifying]

        batch_threshold = settings.get("alert_batch_threshold", 3)

        if len(qualifying_with_review) > batch_threshold:
            # Send one batch alert
            if watchlist.discord_webhook and watchlist.discord_webhook.enabled:
                deals = []
                for listing, score, review in qualifying_with_review:
                    deal = {
                        "title": listing.title,
                        "price": listing.price,
                        "rating": score.rating,
                        "conservative_value": score.conservative_value,
                        "target_buy_price": score.target_buy_price,
                        "estimated_profit": score.estimated_profit,
                        "url": listing.url or "",
                        "reasons": score.reasons or [],
                    }
                    if review:
                        deal["claude_summary"] = review.summary
                    deals.append(deal)
                run_summary = {
                    "raw_count": run.raw_count,
                    "parsed_count": run.parsed_count,
                    "duplicate_count": run.duplicate_count,
                }
                ok = discord_service.send_batch_alert(
                    webhook_url=watchlist.discord_webhook.webhook_url,
                    watchlist_name=watchlist.name,
                    deals=deals,
                    run_summary=run_summary,
                )
                if ok:
                    for listing, _, __ in qualifying_with_review:
                        listing.alert_sent = True
                        listing.alert_sent_at = datetime.utcnow()
                    alert_count = len(qualifying_with_review)
        else:
            # Send individual alerts
            for listing, score, review in qualifying_with_review:
                ok = _send_alert(listing, score, watchlist, claude_review=review)
                if ok:
                    listing.alert_sent = True
                    listing.alert_sent_at = datetime.utcnow()
                    alert_count += 1

        # Send Expo push notifications for every qualifying deal (alongside Discord).
        # Use qualifying_with_review so push respects the Claude review gate, matching Discord.
        push_token = settings.get("expo_push_token")
        if push_token and qualifying_with_review:
            for listing, score, review in qualifying_with_review:
                push_service.send_deal_push(
                    token=push_token,
                    title=listing.title,
                    price=listing.price or 0,
                    rating=score.rating,
                    listing_id=listing.id,
                    source=listing.source,
                    estimated_profit=score.estimated_profit,
                )

        run.alert_count = alert_count

        # ── Auto-outreach ─────────────────────────────────────────────────────
        # If watchlist has auto_outreach_enabled and the listing is from FB
        # Marketplace, send an automated message to the seller.
        if watchlist.auto_outreach_enabled:
            from backend.services.outreach import send_outreach, _check_rate_limit
            for listing, score, review in qualifying_with_review:
                if not listing.url or "facebook.com" not in listing.url:
                    continue
                if listing.outreach_status in ("SENT", "QUEUED"):
                    continue

                allowed, reason = _check_rate_limit()
                if not allowed:
                    logger.info(f"Outreach rate limited ({reason}) — skipping remaining")
                    break

                template = watchlist.outreach_message_template or ""
                listing.outreach_status = "QUEUED"
                db.flush()

                result = send_outreach(listing.url, listing.title, template)
                if result.success:
                    listing.outreach_status = "SENT"
                    listing.outreach_sent_at = datetime.utcnow()
                    logger.info(f"✉ Outreach sent to seller for '{listing.title}'")
                else:
                    listing.outreach_status = "FAILED"
                    logger.warning(
                        f"Outreach failed for '{listing.title}': {result.error}"
                    )

        run.status = "success"
        run.ended_at = datetime.utcnow()

        source.last_run_at = datetime.utcnow()
        source.last_success_at = datetime.utcnow()
        source.status = "healthy"

        db.commit()
        logger.info(
            f"✅ {source.name}/{watchlist.name}: "
            f"{run.raw_count} raw, {run.parsed_count} new, "
            f"{run.duplicate_count} dupes, {alert_count} alerts"
        )

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        run.ended_at = datetime.utcnow()
        source.last_run_at = datetime.utcnow()
        source.status = "failed"
        source.last_error = str(e)
        db.commit()
        logger.error(f"❌ {source.name}/{watchlist.name} failed: {e}", exc_info=True)
