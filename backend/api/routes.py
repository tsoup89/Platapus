"""All FastAPI route handlers for Platapicker."""
import csv
import io
import json
import logging
from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.models import get_db
from backend.models.models import (
    Watchlist, Source, ScraperRun, Listing, DealScore,
    DiscordWebhook, GameCubePrice, TitleMapping, AppSetting,
    MarketValueCache, ClaudeReview,
    InventoryItem, InventoryPhoto, SellListing,
)
from backend.services.market_value import get_market_value
from backend.services.paths import (
    get_inventory_photos_dir, get_inventory_item_photos_dir,
)
from backend.api.schemas import (
    WatchlistCreate, WatchlistUpdate, WatchlistOut,
    DiscordWebhookCreate, DiscordWebhookOut,
    SourceOut, ScraperRunOut,
    ListingOut, DealScoreOut, ClaudeReviewOut,
    GameCubePriceOut, GameCubePriceUpdate, TitleMappingOut,
    OverviewStats,
    InventoryItemCreate, InventoryItemUpdate, InventoryItemOut,
    SellListingOut, CreateSellListingIn, MarkSoldIn, UpdateSellListingIn,
)
from backend.services import discord as discord_service
from backend.services.settings import get_all_settings, get_setting, set_setting
from backend.scoring.title_matcher import normalize_title
from backend.services.runner import run_scraper_for_watchlist
from backend.services import scheduler as scheduler_service

logger = logging.getLogger("platapicker.api")
router = APIRouter()


# ─────────────────────────────────────────────────────────────
# Overview / Health
# ─────────────────────────────────────────────────────────────

@router.get("/health")
@router.head("/health")
def health():
    return {"ok": True}


@router.get("/overview", response_model=OverviewStats)
def overview(db: Session = Depends(get_db)):
    sources = db.query(Source).all()
    watchlists = db.query(Watchlist).filter(Watchlist.enabled == True).all()

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    alerts_today = db.query(Listing).filter(
        Listing.alert_sent == True, Listing.alert_sent_at >= today_start
    ).count()

    errors_today = db.query(ScraperRun).filter(
        ScraperRun.status == "failed", ScraperRun.started_at >= today_start
    ).count()

    last_run = db.query(ScraperRun).order_by(ScraperRun.started_at.desc()).first()

    return OverviewStats(
        scrapers_enabled=sum(1 for s in sources if s.enabled),
        watchlists_enabled=len(watchlists),
        last_run=last_run.started_at if last_run else None,
        alerts_today=alerts_today,
        errors_today=errors_today,
        sources=[SourceOut.model_validate(s) for s in sources],
    )


# ─────────────────────────────────────────────────────────────
# Watchlists
# ─────────────────────────────────────────────────────────────

@router.get("/watchlists", response_model=list[WatchlistOut])
def list_watchlists(db: Session = Depends(get_db)):
    wls = db.query(Watchlist).order_by(Watchlist.name).all()
    return [WatchlistOut.from_orm_safe(w) for w in wls]


@router.post("/watchlists", response_model=WatchlistOut)
def create_watchlist(data: WatchlistCreate, db: Session = Depends(get_db)):
    wl = Watchlist(
        name=data.name,
        enabled=data.enabled,
        category=data.category,
        radius_miles=data.radius_miles,
        min_price=data.min_price,
        max_price=data.max_price,
        run_frequency_minutes=data.run_frequency_minutes,
        min_rating_to_alert=data.min_rating_to_alert,
        min_profit_margin=data.min_profit_margin,
        min_profit_dollars=data.min_profit_dollars,
        discord_webhook_id=data.discord_webhook_id,
        notes=data.notes,
        auto_outreach_enabled=data.auto_outreach_enabled,
        outreach_message_template=data.outreach_message_template,
        auto_list_on_buy=data.auto_list_on_buy,
    )
    wl.keywords = data.keywords
    wl.negative_keywords = data.negative_keywords
    wl.brands = data.brands
    wl.aliases = data.aliases
    wl.locations = data.locations
    wl.sources_enabled = data.sources_enabled
    db.add(wl)
    db.commit()
    db.refresh(wl)
    return WatchlistOut.from_orm_safe(wl)


@router.get("/watchlists/{watchlist_id}", response_model=WatchlistOut)
def get_watchlist(watchlist_id: int, db: Session = Depends(get_db)):
    wl = db.query(Watchlist).filter(Watchlist.id == watchlist_id).first()
    if not wl:
        raise HTTPException(404, "Watchlist not found")
    return WatchlistOut.from_orm_safe(wl)


@router.put("/watchlists/{watchlist_id}", response_model=WatchlistOut)
def update_watchlist(watchlist_id: int, data: WatchlistUpdate, db: Session = Depends(get_db)):
    wl = db.query(Watchlist).filter(Watchlist.id == watchlist_id).first()
    if not wl:
        raise HTTPException(404, "Watchlist not found")
    for field in ["name", "enabled", "category", "radius_miles", "min_price",
                  "max_price", "run_frequency_minutes", "min_rating_to_alert",
                  "min_profit_margin", "min_profit_dollars", "discord_webhook_id", "notes",
                  "auto_outreach_enabled", "outreach_message_template", "auto_list_on_buy"]:
        setattr(wl, field, getattr(data, field))
    wl.keywords = data.keywords
    wl.negative_keywords = data.negative_keywords
    wl.brands = data.brands
    wl.aliases = data.aliases
    wl.locations = data.locations
    wl.sources_enabled = data.sources_enabled
    wl.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(wl)
    return WatchlistOut.from_orm_safe(wl)


@router.delete("/watchlists/{watchlist_id}")
def delete_watchlist(watchlist_id: int, db: Session = Depends(get_db)):
    wl = db.query(Watchlist).filter(Watchlist.id == watchlist_id).first()
    if not wl:
        raise HTTPException(404, "Watchlist not found")
    db.delete(wl)
    db.commit()
    return {"ok": True}


@router.post("/watchlists/{watchlist_id}/toggle")
def toggle_watchlist(watchlist_id: int, db: Session = Depends(get_db)):
    wl = db.query(Watchlist).filter(Watchlist.id == watchlist_id).first()
    if not wl:
        raise HTTPException(404, "Watchlist not found")
    wl.enabled = not wl.enabled
    wl.updated_at = datetime.utcnow()
    db.commit()
    return {"enabled": wl.enabled}


# ─────────────────────────────────────────────────────────────
# Sources / Scraper Health
# ─────────────────────────────────────────────────────────────

@router.get("/sources", response_model=list[SourceOut])
def list_sources(db: Session = Depends(get_db)):
    return db.query(Source).all()


@router.post("/sources/{source_name}/toggle")
def toggle_source(source_name: str, db: Session = Depends(get_db)):
    src = db.query(Source).filter(Source.name == source_name).first()
    if not src:
        raise HTTPException(404, "Source not found")
    src.enabled = not src.enabled
    src.updated_at = datetime.utcnow()
    db.commit()
    return {"enabled": src.enabled}


@router.get("/sources/{source_name}/runs", response_model=list[ScraperRunOut])
def get_source_runs(source_name: str, limit: int = 20, db: Session = Depends(get_db)):
    runs = (
        db.query(ScraperRun)
        .filter(ScraperRun.source_name == source_name)
        .order_by(ScraperRun.started_at.desc())
        .limit(limit)
        .all()
    )
    return runs


@router.post("/sources/{source_name}/run")
def trigger_source_run(
    source_name: str,
    background_tasks: BackgroundTasks,
    watchlist_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    src = db.query(Source).filter(Source.name == source_name).first()
    if not src:
        raise HTTPException(404, "Source not found")
    background_tasks.add_task(run_scraper_for_watchlist, source_name, watchlist_id)
    return {"message": f"Scraper '{source_name}' queued for run."}


@router.post("/run-all")
def run_all_scrapers(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    background_tasks.add_task(run_scraper_for_watchlist, None, None)
    return {"message": "All scrapers queued."}


@router.post("/sources/{source_name}/login")
def trigger_login(source_name: str, background_tasks: BackgroundTasks):
    """Open a browser window for the user to log into a browser-based scraper."""
    def _do_login():
        if source_name == "mercari":
            from backend.scrapers.mercari import MercariScraper
            MercariScraper().login()
        elif source_name == "facebook":
            from backend.scrapers.facebook import FacebookScraper
            FacebookScraper().login()
        else:
            raise ValueError(f"No login flow for: {source_name}")

    background_tasks.add_task(_do_login)
    return {"message": f"Opening {source_name} login window…"}


# ─────────────────────────────────────────────────────────────
# Scraper Runs
# ─────────────────────────────────────────────────────────────

@router.get("/runs", response_model=list[ScraperRunOut])
def list_runs(limit: int = 50, db: Session = Depends(get_db)):
    return (
        db.query(ScraperRun)
        .order_by(ScraperRun.started_at.desc())
        .limit(limit)
        .all()
    )


# ─────────────────────────────────────────────────────────────
# Listings
# ─────────────────────────────────────────────────────────────

@router.get("/listings", response_model=list[ListingOut])
def list_listings(
    watchlist_id: Optional[int] = None,
    source: Optional[str] = None,
    ignored: Optional[bool] = None,
    rating: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(Listing)
    if watchlist_id is not None:
        q = q.filter(Listing.watchlist_id == watchlist_id)
    if source:
        q = q.filter(Listing.source == source)
    if ignored is not None:
        q = q.filter(Listing.ignored == ignored)
    if rating:
        q = q.join(DealScore).filter(DealScore.rating == rating)
    listings = q.order_by(Listing.first_seen_at.desc()).offset(offset).limit(limit).all()
    return [ListingOut.from_orm_safe(l) for l in listings]


@router.post("/listings/{listing_id}/ignore")
def ignore_listing(listing_id: int, db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(404, "Listing not found")
    listing.ignored = True
    db.commit()
    return {"ok": True}


@router.post("/listings/{listing_id}/unignore")
def unignore_listing(listing_id: int, db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(404, "Listing not found")
    listing.ignored = False
    db.commit()
    return {"ok": True}


@router.post("/listings/{listing_id}/send-discord")
def manually_send_discord(listing_id: int, db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(404, "Listing not found")

    wl = listing.watchlist
    if not wl or not wl.discord_webhook:
        raise HTTPException(400, "No Discord webhook configured for this watchlist.")

    score = listing.deal_score
    ok = discord_service.send_deal_alert(
        webhook_url=wl.discord_webhook.webhook_url,
        title=listing.title,
        price=listing.price or 0,
        rating=score.rating if score else "UNKNOWN",
        estimated_value=score.estimated_value if score else None,
        conservative_value=score.conservative_value if score else None,
        target_buy_price=score.target_buy_price if score else None,
        estimated_profit=score.estimated_profit if score else None,
        source=listing.source,
        watchlist_name=wl.name,
        url=listing.url or "",
        location=listing.location,
        reasons=score.reasons if score else [],
        warnings=score.warnings if score else [],
        image_url=listing.image_url,
    )
    if ok:
        listing.alert_sent = True
        listing.alert_sent_at = datetime.utcnow()
        db.commit()
        return {"ok": True}
    raise HTTPException(500, "Failed to send Discord alert.")


@router.get("/listings/{listing_id}/raw")
def get_listing_raw(listing_id: int, db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(404, "Listing not found")
    return listing.raw_payload


@router.get("/listings/{listing_id}/claude-review", response_model=ClaudeReviewOut)
def get_claude_review(listing_id: int, db: Session = Depends(get_db)):
    review = db.query(ClaudeReview).filter(ClaudeReview.listing_id == listing_id).first()
    if not review:
        raise HTTPException(404, "No Claude review for this listing")
    return ClaudeReviewOut.from_orm_safe(review)


@router.post("/listings/{listing_id}/claude-review")
def trigger_claude_review(
    listing_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Queue an on-demand Claude review for a single listing."""
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(404, "Listing not found")

    settings = get_all_settings(db)
    api_key = settings.get("claude_api_key", "")
    if not api_key:
        raise HTTPException(400, "Claude API key not configured. Add it in Settings → Claude Review.")

    def _do_review():
        from backend.services.claude_analyzer import review_listing
        from backend.models.database import SessionLocal
        from datetime import datetime as _dt

        rdb = SessionLocal()
        try:
            lst = rdb.query(Listing).filter(Listing.id == listing_id).first()
            if not lst:
                return
            wl = lst.watchlist
            rev = review_listing(
                title=lst.title,
                description=lst.description or "",
                price=lst.price,
                image_url=lst.image_url,
                keywords=wl.keywords if wl else [],
                category=wl.category if wl else None,
                api_key=api_key,
                model=settings.get("claude_model", "claude-haiku-4-5"),
            )
            existing = rdb.query(ClaudeReview).filter(
                ClaudeReview.listing_id == listing_id
            ).first()
            if existing:
                existing.approved = rev.approved
                existing.confidence = rev.confidence
                existing.summary = rev.summary
                existing.model = rev.model
                existing.error = rev.error
                existing.photo_notes = rev.photo_notes
                existing.flags = rev.flags
                existing.positives = rev.positives
                existing.created_at = _dt.utcnow()
            else:
                cr = ClaudeReview(
                    listing_id=listing_id,
                    approved=rev.approved,
                    confidence=rev.confidence,
                    summary=rev.summary,
                    model=rev.model,
                    error=rev.error,
                    photo_notes=rev.photo_notes,
                )
                cr.flags = rev.flags
                cr.positives = rev.positives
                rdb.add(cr)
            rdb.commit()
        finally:
            rdb.close()

    background_tasks.add_task(_do_review)
    return {"message": "Claude review queued.", "listing_id": listing_id}


@router.post("/analyze-photo")
async def analyze_photo_endpoint(
    mode: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Analyze an uploaded photo with Claude to pre-fill inventory or watchlist form fields."""
    if mode not in ("inventory", "watchlist"):
        raise HTTPException(400, "mode must be 'inventory' or 'watchlist'")

    settings = get_all_settings(db)
    api_key = settings.get("claude_api_key", "")
    if not api_key:
        raise HTTPException(400, "Claude API key not configured. Add it in Settings → Claude Review.")

    content_type = file.content_type or "image/jpeg"
    if not content_type.startswith("image/"):
        raise HTTPException(400, "File must be an image.")

    image_bytes = await file.read()
    if len(image_bytes) > 15 * 1024 * 1024:
        raise HTTPException(400, "Image too large (max 15 MB).")

    try:
        from backend.services.claude_analyzer import analyze_photo
        result = analyze_photo(
            image_bytes=image_bytes,
            media_type=content_type,
            mode=mode,
            api_key=api_key,
            model=settings.get("claude_model", "claude-haiku-4-5"),
        )
        return result
    except Exception as e:
        logger.error(f"Photo analysis failed: {e}")
        raise HTTPException(500, f"Claude analysis failed: {str(e)}")


# ─────────────────────────────────────────────────────────────
# Discord Webhooks
# ─────────────────────────────────────────────────────────────

@router.get("/webhooks", response_model=list[DiscordWebhookOut])
def list_webhooks(db: Session = Depends(get_db)):
    return db.query(DiscordWebhook).all()


@router.post("/webhooks", response_model=DiscordWebhookOut)
def create_webhook(data: DiscordWebhookCreate, db: Session = Depends(get_db)):
    wh = DiscordWebhook(name=data.name, webhook_url=data.webhook_url, enabled=data.enabled)
    db.add(wh)
    db.commit()
    db.refresh(wh)
    return wh


@router.delete("/webhooks/{webhook_id}")
def delete_webhook(webhook_id: int, db: Session = Depends(get_db)):
    wh = db.query(DiscordWebhook).filter(DiscordWebhook.id == webhook_id).first()
    if not wh:
        raise HTTPException(404, "Webhook not found")
    db.delete(wh)
    db.commit()
    return {"ok": True}


@router.post("/webhooks/{webhook_id}/test")
def test_webhook(webhook_id: int, db: Session = Depends(get_db)):
    wh = db.query(DiscordWebhook).filter(DiscordWebhook.id == webhook_id).first()
    if not wh:
        raise HTTPException(404, "Webhook not found")
    ok = discord_service.send_test_message(wh.webhook_url)
    if ok:
        return {"ok": True, "message": "Test message sent!"}
    raise HTTPException(500, "Failed to send test message. Check the webhook URL.")


# ─────────────────────────────────────────────────────────────
# GameCube Pricing
# ─────────────────────────────────────────────────────────────

@router.get("/gamecube/prices", response_model=list[GameCubePriceOut])
def list_gamecube_prices(
    search: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(GameCubePrice)
    if search:
        q = q.filter(GameCubePrice.title.ilike(f"%{search}%"))
    prices = q.order_by(GameCubePrice.title).offset(offset).limit(limit).all()
    return [GameCubePriceOut.from_orm_safe(p) for p in prices]


@router.put("/gamecube/prices/{price_id}", response_model=GameCubePriceOut)
def update_gamecube_price(
    price_id: int, data: GameCubePriceUpdate, db: Session = Depends(get_db)
):
    gp = db.query(GameCubePrice).filter(GameCubePrice.id == price_id).first()
    if not gp:
        raise HTTPException(404, "Price entry not found")
    for field, value in data.model_dump(exclude_none=True).items():
        if field == "aliases":
            gp.aliases = value
        else:
            setattr(gp, field, value)
    gp.last_updated = datetime.utcnow()
    db.commit()
    db.refresh(gp)
    return GameCubePriceOut.from_orm_safe(gp)


@router.post("/gamecube/import")
async def import_gamecube_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "Please upload a CSV file.")

    contents = await file.read()
    text = contents.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    imported = 0
    updated = 0
    errors = []

    CORE_TITLES = [
        "mario kart", "super smash bros", "mario party", "super mario sunshine",
        "luigi's mansion", "legend of zelda", "metroid prime", "pikmin",
        "animal crossing", "f-zero", "paper mario", "resident evil 4",
        "tales of symphonia", "baten kaitos",
    ]

    for i, row in enumerate(reader):
        title = row.get("Game") or row.get("Title") or row.get("Name") or row.get("game") or ""
        title = title.strip()
        if not title:
            continue

        def safe_float(val):
            if not val or val.strip() in ("", "N/A", "-"):
                return None
            try:
                return float(val.replace("$", "").replace(",", "").strip())
            except ValueError:
                return None

        norm = normalize_title(title)
        existing = db.query(GameCubePrice).filter(
            GameCubePrice.normalized_title == norm
        ).first()

        is_core = any(ct in title.lower() for ct in CORE_TITLES)

        fields = {
            "loose_price": safe_float(row.get("Loose Price") or row.get("loose_price", "")),
            "complete_price": safe_float(row.get("Complete Price") or row.get("complete_price", "")),
            "new_price": safe_float(row.get("New Price") or row.get("new_price", "")),
            "graded_price": safe_float(row.get("Graded Price") or row.get("graded_price", "")),
            "box_only_price": safe_float(row.get("Box Only") or row.get("box_only_price", "")),
            "manual_only_price": safe_float(row.get("Manual Only") or row.get("manual_only_price", "")),
            "core_title": is_core,
            "last_updated": datetime.utcnow(),
        }

        if existing:
            for k, v in fields.items():
                if v is not None:
                    setattr(existing, k, v)
            updated += 1
        else:
            gp = GameCubePrice(
                title=title,
                normalized_title=norm,
                demand_tier="high" if is_core else "medium",
                sell_speed="fast" if is_core else "medium",
                **{k: v for k, v in fields.items() if k != "last_updated"},
                last_updated=datetime.utcnow(),
            )
            db.add(gp)
            imported += 1

    db.commit()

    # Auto-rescore existing GameCube listings with new prices
    from backend.services.settings import get_all_settings
    from backend.scoring.gamecube_scorer import score_gamecube_listing
    settings = get_all_settings(db)
    gc_wl = db.query(Watchlist).filter(Watchlist.category == "gamecube").first()
    rescored = 0
    if gc_wl:
        gc_prices_all = db.query(GameCubePrice).all()
        thresholds = settings.get("deal_thresholds", {"STEAL": 0.45, "GREAT": 0.55, "GOOD": 0.65, "FAIR": 0.75})
        for listing in db.query(Listing).filter(Listing.watchlist_id == gc_wl.id).all():
            result = score_gamecube_listing(
                title=listing.title,
                description=listing.description or "",
                price=listing.price or 0,
                gamecube_prices=gc_prices_all,
                platform_fee_pct=settings.get("gamecube_platform_fee_pct", 0.13),
                bundle_discount=settings.get("gamecube_bundle_discount", 0.85),
                low_demand_discount=settings.get("gamecube_low_demand_discount", 0.60),
                thresholds=thresholds,
                aliases=gc_wl.aliases,
            )
            existing_score = db.query(DealScore).filter(DealScore.listing_id == listing.id).first()  
            if existing_score:
                existing_score.rating = result.rating
                existing_score.score = result.score
                existing_score.estimated_value = result.estimated_value
                existing_score.conservative_value = result.conservative_value
                existing_score.target_buy_price = result.target_buy_30pct
                existing_score.estimated_profit = result.estimated_profit
                existing_score.profit_margin = result.profit_margin
                existing_score.confidence = result.confidence
                existing_score.reasons = result.reasons
                existing_score.warnings = result.warnings
                rescored += 1
        db.commit()

    return {
        "ok": True,
        "imported": imported,
        "updated": updated,
        "rescored": rescored,
        "errors": errors,
        "message": f"Imported {imported} new titles, updated {updated} existing. Re-scored {rescored} listings.",
    }


@router.get("/gamecube/unmatched", response_model=list[TitleMappingOut])
def get_unmatched_titles(db: Session = Depends(get_db)):
    return (
        db.query(TitleMapping)
        .filter(TitleMapping.mapped_gamecube_price_id == None, TitleMapping.user_confirmed == False)
        .order_by(TitleMapping.created_at.desc())
        .all()
    )


@router.post("/gamecube/mappings/{mapping_id}/confirm")
def confirm_title_mapping(
    mapping_id: int,
    gamecube_price_id: int,
    db: Session = Depends(get_db),
):
    mapping = db.query(TitleMapping).filter(TitleMapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(404, "Mapping not found")
    mapping.mapped_gamecube_price_id = gamecube_price_id
    mapping.user_confirmed = True
    db.commit()
    return {"ok": True}

@router.post("/gamecube/sync-pricecharting")
def sync_pricecharting(
    max_titles: int = 50,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """Queue a PriceCharting sync in the background and return immediately."""
    from backend.services.pricecharting import sync_gamecube_prices
    from backend.models.database import SessionLocal

    def _do_sync():
        sync_db = SessionLocal()
        try:
            sync_gamecube_prices(sync_db, max_titles=max_titles)
        finally:
            sync_db.close()

    if background_tasks:
        background_tasks.add_task(_do_sync)
        return {"ok": True, "message": f"PriceCharting sync queued for up to {max_titles} titles."}
    return {"ok": False, "message": "No background task context available."}


@router.get("/gamecube/sync-status")
def get_sync_status(db: Session = Depends(get_db)):
    """Return count of prices updated in last 48h and oldest price age."""
    from datetime import timedelta

    cutoff_48h = datetime.utcnow() - timedelta(hours=48)
    updated_recently = (
        db.query(GameCubePrice)
        .filter(GameCubePrice.last_updated >= cutoff_48h)
        .count()
    )
    total = db.query(GameCubePrice).count()
    oldest = (
        db.query(GameCubePrice)
        .order_by(GameCubePrice.last_updated.asc().nullsfirst())
        .first()
    )
    oldest_updated = oldest.last_updated.isoformat() if oldest and oldest.last_updated else None
    stale_count = (
        db.query(GameCubePrice)
        .filter(
            (GameCubePrice.last_updated == None)
            | (GameCubePrice.last_updated < cutoff_48h)
        )
        .count()
    )
    return {
        "total": total,
        "updated_last_48h": updated_recently,
        "stale_count": stale_count,
        "oldest_updated": oldest_updated,
    }


# ─────────────────────────────────────────────────────────────
# Settings
# ─────────────────────────────────────────────────────────────

@router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    return get_all_settings(db)


@router.post("/settings")
def update_settings(data: dict, db: Session = Depends(get_db)):
    for key, value in data.items():
        set_setting(db, key, value)

    # Reconcile the running scheduler with the new settings so toggling
    # global_schedule_enabled (or changing the interval) takes effect
    # immediately, without an app restart.
    if "global_schedule_enabled" in data or "global_schedule_interval_minutes" in data:
        scheduler_service.apply_settings()

    return {"ok": True}


# ─────────────────────────────────────────────────────────────
# Maintenance
# ─────────────────────────────────────────────────────────────

@router.post("/maintenance/clear-duplicates")
def clear_duplicates(db: Session = Depends(get_db)):
    count = db.query(Listing).count()
    db.query(Listing).delete()
    db.commit()
    return {"ok": True, "message": f"Cleared {count} listings from duplicate cache."}


@router.post("/maintenance/reset-alerts")
def reset_alerts(db: Session = Depends(get_db)):
    db.query(Listing).update({"alert_sent": False, "alert_sent_at": None})
    db.commit()
    return {"ok": True, "message": "All alert sent flags reset."}


@router.post("/maintenance/rescore-gamecube")
def rescore_gamecube(db: Session = Depends(get_db)):
    """Re-score all GameCube watchlist listings after a pricing CSV update."""
    from backend.services.settings import get_all_settings
    settings = get_all_settings(db)

    wl = db.query(Watchlist).filter(Watchlist.category == "gamecube").first()
    if not wl:
        raise HTTPException(404, "No GameCube watchlist found.")

    listings = db.query(Listing).filter(Listing.watchlist_id == wl.id).all()
    if not listings:
        return {"ok": True, "rescored": 0, "message": "No GameCube listings to rescore."}

    from backend.scoring.gamecube_scorer import score_gamecube_listing
    from backend.models.models import GameCubePrice

    gc_prices = db.query(GameCubePrice).all()
    thresholds = settings.get("deal_thresholds", {
        "STEAL": 0.45, "GREAT": 0.55, "GOOD": 0.65, "FAIR": 0.75
    })

    rescored = 0
    for listing in listings:
        result = score_gamecube_listing(
            title=listing.title,
            description=listing.description or "",
            price=listing.price or 0,
            gamecube_prices=gc_prices,
            platform_fee_pct=settings.get("gamecube_platform_fee_pct", 0.13),
            bundle_discount=settings.get("gamecube_bundle_discount", 0.85),
            low_demand_discount=settings.get("gamecube_low_demand_discount", 0.60),
            thresholds=thresholds,
            aliases=wl.aliases,
        )

        existing = db.query(DealScore).filter(DealScore.listing_id == listing.id).first()
        if existing:
            existing.rating = result.rating
            existing.score = result.score
            existing.estimated_value = result.estimated_value
            existing.conservative_value = result.conservative_value
            existing.target_buy_price = result.target_buy_30pct
            existing.estimated_profit = result.estimated_profit
            existing.profit_margin = result.profit_margin
            existing.confidence = result.confidence
            existing.reasons = result.reasons
            existing.warnings = result.warnings
            existing.created_at = datetime.utcnow()
        else:
            score_row = DealScore(listing_id=listing.id)
            score_row.rating = result.rating
            score_row.score = result.score
            score_row.estimated_value = result.estimated_value
            score_row.conservative_value = result.conservative_value
            score_row.target_buy_price = result.target_buy_30pct
            score_row.estimated_profit = result.estimated_profit
            score_row.profit_margin = result.profit_margin
            score_row.confidence = result.confidence
            score_row.reasons = result.reasons
            score_row.warnings = result.warnings
            db.add(score_row)
        rescored += 1

    db.commit()
    return {"ok": True, "rescored": rescored, "message": f"Re-scored {rescored} GameCube listings."}


# ─────────────────────────────────────────────────────────────
# Market Value
# ─────────────────────────────────────────────────────────────

@router.get("/market-value")
def get_market_value_estimate(
    keyword: str,
    category: Optional[str] = None,
    refresh: bool = False,
    db: Session = Depends(get_db),
):
    if refresh:
        db.query(MarketValueCache).filter(
            MarketValueCache.keyword == keyword,
            MarketValueCache.category == category,
        ).delete()
        db.flush()

    estimate = get_market_value(keyword=keyword, category=category, db=db)
    return {
        "keyword": estimate.keyword,
        "median_price": estimate.median_price,
        "mean_price": estimate.mean_price,
        "min_price": estimate.min_price,
        "max_price": estimate.max_price,
        "sample_count": estimate.sample_count,
        "source": estimate.source,
        "fetched_at": estimate.fetched_at.isoformat() if estimate.fetched_at else None,
        "error": estimate.error,
    }


@router.get("/market-value/cache")
def list_cached_values(db: Session = Depends(get_db)):
    rows = (
        db.query(MarketValueCache)
        .order_by(MarketValueCache.fetched_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "keyword": r.keyword,
            "category": r.category,
            "median_price": r.median_price,
            "mean_price": r.mean_price,
            "min_price": r.min_price,
            "max_price": r.max_price,
            "sample_count": r.sample_count,
            "source": r.source,
            "fetched_at": r.fetched_at.isoformat() if r.fetched_at else None,
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
        }
        for r in rows
    ]


@router.delete("/market-value/cache")
def clear_market_value_cache(db: Session = Depends(get_db)):
    count = db.query(MarketValueCache).count()
    db.query(MarketValueCache).delete()
    db.commit()
    return {"ok": True, "cleared": count}


# ─────────────────────────────────────────────────────────────
# Scheduler
# ─────────────────────────────────────────────────────────────

@router.get("/scheduler/status")
def scheduler_status():
    return scheduler_service.get_scheduler_status()


@router.post("/scheduler/run-now")
def scheduler_run_now(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_scraper_for_watchlist)
    return {"message": "Full scrape queued."}


@router.post("/scheduler/reschedule")
def scheduler_reschedule(interval_minutes: int, db: Session = Depends(get_db)):
    set_setting(db, "global_schedule_interval_minutes", interval_minutes)
    scheduler_service.reschedule(interval_minutes)
    return {"ok": True, "interval_minutes": interval_minutes}


# ─────────────────────────────────────────────────────────────
# Facebook-specific
# ─────────────────────────────────────────────────────────────

@router.get("/facebook/session-status")
def facebook_session_status():
    from pathlib import Path
    session_file = Path("browser_sessions/facebook/session.json")
    if session_file.exists():
        size = session_file.stat().st_size
        mtime = datetime.utcfromtimestamp(session_file.stat().st_mtime).isoformat()
        return {
            "has_session": True,
            "session_size_bytes": size,
            "last_modified": mtime,
            "message": "Session file found. Facebook scraper should be ready.",
        }
    return {
        "has_session": False,
        "message": "No session found. Run: python platapicker.py facebook-login",
    }


@router.post("/facebook/debug-scrape")
def facebook_debug_scrape(
    keyword: str = "GameCube",
    location: str = "New York, NY",
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """Run a single Facebook search and return raw card count — does not save listings."""
    def _debug():
        from backend.scrapers.facebook import FacebookScraper
        src = db.query(Source).filter(Source.name == "facebook").first()
        config = src.config if src else {}
        scraper = FacebookScraper(config=config)
        raw, health = scraper.run(keyword, location, 50)
        logger.info(
            f"[DEBUG] Facebook '{keyword}': {health.raw_count} raw cards, "
            f"{len(raw)} parsed, status={health.status}, error={health.last_error}"
        )

    if background_tasks:
        background_tasks.add_task(_debug)
        return {"message": f"Debug scrape for '{keyword}' queued — check logs."}
    return {"message": "No background task context available."}


# ─────────────────────────────────────────────────────────────
# Inventory (sell-side)
# ─────────────────────────────────────────────────────────────

ALLOWED_PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_PHOTO_BYTES = 15 * 1024 * 1024  # 15MB per photo


@router.get("/inventory", response_model=list[InventoryItemOut])
def list_inventory(
    status: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(InventoryItem)
    if status:
        q = q.filter(InventoryItem.status == status)
    items = q.order_by(InventoryItem.created_at.desc()).offset(offset).limit(limit).all()
    return [InventoryItemOut.from_orm_safe(i) for i in items]


@router.post("/inventory", response_model=InventoryItemOut)
def create_inventory_item(data: InventoryItemCreate, db: Session = Depends(get_db)):
    item = InventoryItem(
        title=data.title,
        description=data.description,
        category=data.category,
        condition=data.condition,
        purchase_price=data.purchase_price,
        purchase_date=data.purchase_date,
        source_listing_id=data.source_listing_id,
        notes=data.notes,
        status=data.status,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return InventoryItemOut.from_orm_safe(item)


@router.get("/inventory/{item_id}", response_model=InventoryItemOut)
def get_inventory_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Inventory item not found")
    return InventoryItemOut.from_orm_safe(item)


@router.patch("/inventory/{item_id}", response_model=InventoryItemOut)
def update_inventory_item(
    item_id: int, data: InventoryItemUpdate, db: Session = Depends(get_db)
):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Inventory item not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return InventoryItemOut.from_orm_safe(item)


@router.delete("/inventory/{item_id}")
def delete_inventory_item(item_id: int, db: Session = Depends(get_db)):
    import shutil
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Inventory item not found")
    # Remove photo files on disk
    photos_dir = get_inventory_photos_dir() / str(item_id)
    if photos_dir.exists():
        shutil.rmtree(photos_dir, ignore_errors=True)
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.post("/inventory/{item_id}/photos", response_model=InventoryItemOut)
async def upload_inventory_photos(
    item_id: int,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    import uuid as _uuid
    from pathlib import Path as _Path

    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Inventory item not found")

    photos_dir = get_inventory_item_photos_dir(item_id)
    existing_count = db.query(InventoryPhoto).filter(
        InventoryPhoto.inventory_item_id == item_id
    ).count()

    for idx, upload in enumerate(files):
        ext = _Path(upload.filename or "").suffix.lower() or ".jpg"
        if ext not in ALLOWED_PHOTO_EXT:
            raise HTTPException(400, f"Unsupported image type: {ext}")
        contents = await upload.read()
        if len(contents) > MAX_PHOTO_BYTES:
            raise HTTPException(400, f"Photo too large (max 15MB): {upload.filename}")
        filename = f"{_uuid.uuid4().hex}{ext}"
        (photos_dir / filename).write_bytes(contents)
        photo = InventoryPhoto(
            inventory_item_id=item_id,
            file_path=filename,
            order_index=existing_count + idx,
        )
        db.add(photo)

    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return InventoryItemOut.from_orm_safe(item)


@router.delete("/inventory/photos/{photo_id}")
def delete_inventory_photo(photo_id: int, db: Session = Depends(get_db)):
    photo = db.query(InventoryPhoto).filter(InventoryPhoto.id == photo_id).first()
    if not photo:
        raise HTTPException(404, "Photo not found")
    photo_path = get_inventory_photos_dir() / str(photo.inventory_item_id) / photo.file_path
    if photo_path.exists():
        try:
            photo_path.unlink()
        except OSError:
            pass
    db.delete(photo)
    db.commit()
    return {"ok": True}


@router.post("/inventory/photos/reorder")
def reorder_inventory_photos(data: dict, db: Session = Depends(get_db)):
    """Body: {photo_ids: [int, int, ...]} — sets order_index by position."""
    ids = data.get("photo_ids", [])
    if not isinstance(ids, list):
        raise HTTPException(400, "photo_ids must be a list")
    for idx, pid in enumerate(ids):
        photo = db.query(InventoryPhoto).filter(InventoryPhoto.id == pid).first()
        if photo:
            photo.order_index = idx
    db.commit()
    return {"ok": True}


@router.get("/inventory/photos/{item_id}/{filename}")
def serve_inventory_photo(item_id: int, filename: str):
    # Path-traversal guard
    if "/" in filename or ".." in filename or "\\" in filename:
        raise HTTPException(400, "Invalid filename")
    path = get_inventory_photos_dir() / str(item_id) / filename
    if not path.exists():
        raise HTTPException(404, "Photo not found")
    return FileResponse(str(path))


# ─────────────────────────────────────────────────────────────
# Inventory — price suggestions
# ─────────────────────────────────────────────────────────────

@router.post("/inventory/{item_id}/price-suggestion")
def trigger_price_suggestion(
    item_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Kick off an async price-suggestion job. Poll GET .../price-suggestion for results."""
    from backend.api.schemas import PriceSuggestionOut
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Inventory item not found")

    def _run_suggestion(iid: int, title: str, condition: str):
        from backend.models.database import SessionLocal
        from backend.services.auto_pricing import suggest_price
        bdb = SessionLocal()
        try:
            suggestion = suggest_price(title, condition, db=bdb)
            row = bdb.query(InventoryItem).filter(InventoryItem.id == iid).first()
            if row:
                row.price_suggestion = suggestion.to_dict()
                bdb.commit()
                logger.info(f"Price suggestion saved for item {iid}: ${suggestion.suggested_price}")
        except Exception as e:
            logger.error(f"Price suggestion failed for item {iid}: {e}", exc_info=True)
        finally:
            bdb.close()

    # Mark as pending right away so the frontend knows work is in progress
    pending = {
        "suggested_price": None,
        "low_estimate": None,
        "high_estimate": None,
        "confidence": "pending",
        "condition_applied": item.condition or "GOOD",
        "keyword_used": item.title,
        "generated_at": None,
        "error": None,
        "comps": [],
    }
    item.price_suggestion = pending
    db.commit()

    background_tasks.add_task(_run_suggestion, item_id, item.title, item.condition or "GOOD")
    return {"status": "started", "item_id": item_id}


@router.get("/inventory/{item_id}/price-suggestion")
def get_price_suggestion(item_id: int, db: Session = Depends(get_db)):
    """Return the cached price suggestion for an inventory item."""
    from backend.api.schemas import PriceSuggestionOut
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Inventory item not found")
    if not item.price_suggestion:
        return {"confidence": "none", "comps": [], "suggested_price": None,
                "low_estimate": None, "high_estimate": None,
                "condition_applied": item.condition or "GOOD",
                "keyword_used": item.title, "generated_at": None, "error": None}
    return item.price_suggestion


# ─────────────────────────────────────────────────────────────
# Sell listings — list items on eBay / Facebook
# ─────────────────────────────────────────────────────────────

PLATFORM_FEE_RATES = {
    "ebay": 0.1325,       # 13.25% FVF
    "facebook": 0.05,     # 5% for shipping (0% local pickup)
}


def _sell_listing_to_out(sl: SellListing) -> SellListingOut:
    return SellListingOut(
        id=sl.id,
        inventory_item_id=sl.inventory_item_id,
        platform=sl.platform,
        platform_listing_id=sl.platform_listing_id,
        platform_url=sl.platform_url,
        action_url=sl.action_url,
        listed_price=sl.listed_price,
        status=sl.status,
        listed_at=sl.listed_at,
        sold_at=sl.sold_at,
        removed_at=sl.removed_at,
        sale_price=sl.sale_price,
        platform_fees=sl.platform_fees,
        shipping_cost=sl.shipping_cost,
        error_message=sl.error_message,
        screenshot_path=sl.screenshot_path,
        created_at=sl.created_at,
        updated_at=sl.updated_at,
    )


@router.get("/inventory/{item_id}/sell-listings", response_model=list[SellListingOut])
def list_sell_listings_for_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Inventory item not found")
    return [_sell_listing_to_out(sl) for sl in item.sell_listings]


@router.post("/inventory/{item_id}/sell-listings", response_model=SellListingOut)
def create_sell_listing(
    item_id: int,
    data: CreateSellListingIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Initiate listing an inventory item on a platform.

    For eBay (manual flow): creates the record immediately with status DRAFT
    and returns an action_url the user opens in their browser.

    For Facebook (Playwright): creates the record as POSTING, then kicks off
    Playwright in the background. Poll GET .../sell-listings to see result.
    """
    platform = data.platform.lower()
    if platform not in ("ebay", "facebook"):
        raise HTTPException(400, "Platform must be 'ebay' or 'facebook'")

    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Inventory item not found")

    # Build initial record
    sl = SellListing(
        inventory_item_id=item_id,
        platform=platform,
        listed_price=data.listed_price,
        status="DRAFT" if platform == "ebay" else "POSTING",
        listed_at=datetime.utcnow() if platform == "facebook" else None,
    )
    db.add(sl)
    db.commit()
    db.refresh(sl)
    sl_id = sl.id

    if platform == "ebay":
        # eBay manual-fallback: generate action_url immediately
        from backend.services.sellers.ebay import EbaySeller
        from backend.services.sellers.base import ListingDraft
        draft = ListingDraft(
            title=item.title,
            description=item.description or "",
            price=data.listed_price,
            condition=item.condition or "GOOD",
            category=item.category,
            photo_paths=[],
        )
        result = EbaySeller().create_listing(draft)
        sl.action_url = result.action_url
        sl.status = "DRAFT"
        sl.raw_metadata = result.extra
        db.commit()
        db.refresh(sl)
        return _sell_listing_to_out(sl)

    # Facebook: run Playwright in background
    def _run_fb(iid: int, sell_listing_id: int, price: float):
        from backend.models.database import SessionLocal
        from backend.services.sellers.facebook import FacebookSeller
        from backend.services.sellers.base import ListingDraft
        from backend.services.paths import get_inventory_item_photos_dir
        bdb = SessionLocal()
        try:
            inv_item = bdb.query(InventoryItem).filter(InventoryItem.id == iid).first()
            if not inv_item:
                return

            # Collect photo paths
            photo_paths = []
            if inv_item.photos:
                photos_dir = get_inventory_item_photos_dir(iid)
                for p in inv_item.photos:
                    full = photos_dir.parent / str(iid) / p.file_path
                    if full.exists():
                        photo_paths.append(full)

            draft = ListingDraft(
                title=inv_item.title,
                description=inv_item.description or "",
                price=price,
                condition=inv_item.condition or "GOOD",
                category=inv_item.category,
                photo_paths=photo_paths,
            )

            result = FacebookSeller().create_listing(draft)

            row = bdb.query(SellListing).filter(SellListing.id == sell_listing_id).first()
            if not row:
                return

            if result.success:
                row.status = "POSTED"
                row.platform_url = result.platform_url
                row.listed_at = datetime.utcnow()
                # Update InventoryItem status to LISTED if not already sold
                if inv_item.status == "DRAFT":
                    inv_item.status = "LISTED"
            else:
                row.status = "FAILED"
                row.error_message = result.error_message
                row.action_url = result.action_url or "https://www.facebook.com/marketplace/create/item"
                row.screenshot_path = result.screenshot_path

            bdb.commit()
            logger.info(
                f"FB listing background task done for item {iid}: "
                f"success={result.success}"
            )
        except Exception as e:
            logger.error(f"FB listing background task failed: {e}", exc_info=True)
            try:
                row = bdb.query(SellListing).filter(SellListing.id == sell_listing_id).first()
                if row:
                    row.status = "FAILED"
                    row.error_message = str(e)
                    row.action_url = "https://www.facebook.com/marketplace/create/item"
                    bdb.commit()
            except Exception:
                pass
        finally:
            bdb.close()

    background_tasks.add_task(_run_fb, item_id, sl_id, data.listed_price)
    return _sell_listing_to_out(sl)


@router.get("/sell-listings/{sell_listing_id}", response_model=SellListingOut)
def get_sell_listing(sell_listing_id: int, db: Session = Depends(get_db)):
    sl = db.query(SellListing).filter(SellListing.id == sell_listing_id).first()
    if not sl:
        raise HTTPException(404, "Sell listing not found")
    return _sell_listing_to_out(sl)


@router.patch("/sell-listings/{sell_listing_id}", response_model=SellListingOut)
def update_sell_listing(
    sell_listing_id: int,
    data: UpdateSellListingIn,
    db: Session = Depends(get_db),
):
    """Update platform URL / listing ID after manual listing completion."""
    sl = db.query(SellListing).filter(SellListing.id == sell_listing_id).first()
    if not sl:
        raise HTTPException(404, "Sell listing not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(sl, field, value)
    if data.status == "POSTED" and not sl.listed_at:
        sl.listed_at = datetime.utcnow()
    sl.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(sl)
    return _sell_listing_to_out(sl)


@router.post("/sell-listings/{sell_listing_id}/mark-sold", response_model=SellListingOut)
def mark_sell_listing_sold(
    sell_listing_id: int,
    data: MarkSoldIn,
    db: Session = Depends(get_db),
):
    sl = db.query(SellListing).filter(SellListing.id == sell_listing_id).first()
    if not sl:
        raise HTTPException(404, "Sell listing not found")

    # Auto-calculate fees if not provided
    fees = data.platform_fees
    if fees is None:
        rate = PLATFORM_FEE_RATES.get(sl.platform, 0)
        fees = round(data.sale_price * rate, 2)

    sl.status = "SOLD"
    sl.sale_price = data.sale_price
    sl.platform_fees = fees
    sl.shipping_cost = data.shipping_cost or 0.0
    sl.sold_at = datetime.utcnow()
    if data.platform_listing_id:
        sl.platform_listing_id = data.platform_listing_id
    if data.platform_url:
        sl.platform_url = data.platform_url

    # Update inventory item status
    item = db.query(InventoryItem).filter(InventoryItem.id == sl.inventory_item_id).first()
    if item:
        item.status = "SOLD"
        item.updated_at = datetime.utcnow()

    sl.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(sl)
    return _sell_listing_to_out(sl)


@router.post("/sell-listings/{sell_listing_id}/remove", response_model=SellListingOut)
def remove_sell_listing(sell_listing_id: int, db: Session = Depends(get_db)):
    sl = db.query(SellListing).filter(SellListing.id == sell_listing_id).first()
    if not sl:
        raise HTTPException(404, "Sell listing not found")
    sl.status = "REMOVED"
    sl.removed_at = datetime.utcnow()
    sl.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(sl)
    return _sell_listing_to_out(sl)


@router.post("/listings/{listing_id}/promote-to-inventory", response_model=InventoryItemOut)
def promote_listing_to_inventory(
    listing_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Create an InventoryItem from a buy-side Listing.

    Copies title/price/source link. If the listing has an image_url, downloads it
    in the background as the first photo. The user is expected to add their own
    photos (of the item they actually received) afterward.
    """
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(404, "Listing not found")

    existing = db.query(InventoryItem).filter(
        InventoryItem.source_listing_id == listing_id
    ).first()
    if existing:
        return InventoryItemOut.from_orm_safe(existing)

    item = InventoryItem(
        title=listing.title,
        description=listing.description or "",
        category=listing.watchlist.category if listing.watchlist else None,
        condition="GOOD",
        purchase_price=listing.price,
        purchase_date=datetime.utcnow(),
        source_listing_id=listing_id,
        notes=f"Promoted from {listing.source} listing.",
        status="DRAFT",
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    image_url = listing.image_url
    if image_url:
        new_item_id = item.id

        def _download_image():
            import httpx
            import uuid as _uuid
            from pathlib import Path as _Path
            from backend.models.database import SessionLocal

            try:
                resp = httpx.get(image_url, timeout=15.0, follow_redirects=True)
                if resp.status_code != 200 or len(resp.content) > MAX_PHOTO_BYTES:
                    return
                ext = _Path(image_url.split("?")[0]).suffix.lower()
                if ext not in ALLOWED_PHOTO_EXT:
                    ext = ".jpg"
                filename = f"{_uuid.uuid4().hex}{ext}"
                photo_dir = get_inventory_item_photos_dir(new_item_id)
                (photo_dir / filename).write_bytes(resp.content)

                bdb = SessionLocal()
                try:
                    photo = InventoryPhoto(
                        inventory_item_id=new_item_id,
                        file_path=filename,
                        order_index=0,
                    )
                    bdb.add(photo)
                    bdb.commit()
                finally:
                    bdb.close()
            except Exception as e:
                logger.warning(f"Failed to download promoted listing image: {e}")

        background_tasks.add_task(_download_image)

    return InventoryItemOut.from_orm_safe(item)


# ─────────────────────────────────────────────────────────────
# Sell dashboard + profit analytics
# ─────────────────────────────────────────────────────────────

@router.get("/sell/dashboard")
def get_sell_dashboard(db: Session = Depends(get_db)):
    """
    KPI summary for the Sell Dashboard page.
    Returns counts, values, profit, and items needing attention.
    """
    from datetime import date, timedelta
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    stale_threshold = now - timedelta(days=30)

    # Active sell listings (DRAFT or POSTED)
    active = db.query(SellListing).filter(
        SellListing.status.in_(["DRAFT", "POSTED"])
    ).all()

    # Total listed value
    total_listed_value = sum(
        (sl.listed_price or 0) for sl in active
    )

    # Sold this month
    sold_this_month = db.query(SellListing).filter(
        SellListing.status == "SOLD",
        SellListing.sold_at >= month_start,
    ).all()

    revenue_this_month = sum(sl.sale_price or 0 for sl in sold_this_month)
    fees_this_month = sum(sl.platform_fees or 0 for sl in sold_this_month)
    shipping_this_month = sum(sl.shipping_cost or 0 for sl in sold_this_month)

    # Purchase costs for sold items this month
    sold_item_ids = [sl.inventory_item_id for sl in sold_this_month]
    purchase_costs = 0.0
    if sold_item_ids:
        inv_items = db.query(InventoryItem).filter(
            InventoryItem.id.in_(sold_item_ids)
        ).all()
        purchase_costs = sum(i.purchase_price or 0 for i in inv_items)

    profit_this_month = round(
        revenue_this_month - fees_this_month - shipping_this_month - purchase_costs, 2
    )

    # All-time totals
    all_sold = db.query(SellListing).filter(SellListing.status == "SOLD").all()
    all_revenue = sum(sl.sale_price or 0 for sl in all_sold)
    all_fees = sum(sl.platform_fees or 0 for sl in all_sold)
    all_shipping = sum(sl.shipping_cost or 0 for sl in all_sold)
    all_item_ids = [sl.inventory_item_id for sl in all_sold]
    all_purchase = 0.0
    if all_item_ids:
        inv = db.query(InventoryItem).filter(InventoryItem.id.in_(all_item_ids)).all()
        all_purchase = sum(i.purchase_price or 0 for i in inv)
    total_profit = round(all_revenue - all_fees - all_shipping - all_purchase, 2)

    # Inventory status counts
    inv_counts = {}
    for status in ("DRAFT", "LISTED", "SOLD", "ARCHIVED"):
        inv_counts[status.lower()] = db.query(InventoryItem).filter(
            InventoryItem.status == status
        ).count()

    # Needs attention
    attention = []

    # Failed listings
    failed = db.query(SellListing).filter(SellListing.status == "FAILED").all()
    for sl in failed:
        inv_item = db.query(InventoryItem).filter(InventoryItem.id == sl.inventory_item_id).first()
        attention.append({
            "type": "failed_listing",
            "inventory_item_id": sl.inventory_item_id,
            "sell_listing_id": sl.id,
            "title": inv_item.title if inv_item else "Unknown",
            "platform": sl.platform,
            "message": f"{sl.platform.title()} listing failed — {(sl.error_message or '')[:80]}",
        })

    # Stale listings (POSTED but no sale for >30 days)
    stale = db.query(SellListing).filter(
        SellListing.status == "POSTED",
        SellListing.listed_at <= stale_threshold,
    ).all()
    for sl in stale:
        inv_item = db.query(InventoryItem).filter(InventoryItem.id == sl.inventory_item_id).first()
        days = (now - sl.listed_at).days if sl.listed_at else "?"
        attention.append({
            "type": "stale_listing",
            "inventory_item_id": sl.inventory_item_id,
            "sell_listing_id": sl.id,
            "title": inv_item.title if inv_item else "Unknown",
            "platform": sl.platform,
            "message": f"Listed on {sl.platform.title()} for {days} days — consider a price drop",
        })

    # Recent activity (last 20 status changes)
    recent_listings = db.query(SellListing).order_by(
        SellListing.updated_at.desc()
    ).limit(20).all()
    activity = []
    for sl in recent_listings:
        inv_item = db.query(InventoryItem).filter(InventoryItem.id == sl.inventory_item_id).first()
        activity.append({
            "sell_listing_id": sl.id,
            "inventory_item_id": sl.inventory_item_id,
            "title": inv_item.title if inv_item else "Unknown",
            "platform": sl.platform,
            "status": sl.status,
            "listed_price": sl.listed_price,
            "sale_price": sl.sale_price,
            "updated_at": sl.updated_at.isoformat() if sl.updated_at else None,
        })

    return {
        "active_listings_count": len(active),
        "total_listed_value": round(total_listed_value, 2),
        "sold_this_month_count": len(sold_this_month),
        "revenue_this_month": round(revenue_this_month, 2),
        "profit_this_month": profit_this_month,
        "total_profit_alltime": total_profit,
        "total_sold_alltime": len(all_sold),
        "inventory": inv_counts,
        "attention": attention,
        "activity": activity,
    }


@router.get("/sell/profit")
def get_sell_profit(
    platform: Optional[str] = None,
    days: Optional[int] = None,   # e.g. 30, 90, 365 — None = all time
    db: Session = Depends(get_db),
):
    """
    Detailed profit breakdown for the Profit Tracker page.
    """
    query = db.query(SellListing).filter(SellListing.status == "SOLD")

    if platform:
        query = query.filter(SellListing.platform == platform.lower())

    if days:
        cutoff = datetime.utcnow() - __import__("datetime").timedelta(days=days)
        query = query.filter(SellListing.sold_at >= cutoff)

    sold = query.order_by(SellListing.sold_at.desc()).all()

    rows = []
    for sl in sold:
        inv_item = db.query(InventoryItem).filter(InventoryItem.id == sl.inventory_item_id).first()
        purchase_price = inv_item.purchase_price if inv_item else None
        sale_price = sl.sale_price or 0
        fees = sl.platform_fees or 0
        shipping = sl.shipping_cost or 0
        cost = purchase_price or 0
        net = round(sale_price - fees - shipping - cost, 2)
        roi = round((net / cost * 100), 1) if cost > 0 else None

        rows.append({
            "sell_listing_id": sl.id,
            "inventory_item_id": sl.inventory_item_id,
            "title": inv_item.title if inv_item else "Unknown",
            "category": inv_item.category if inv_item else None,
            "condition": inv_item.condition if inv_item else None,
            "platform": sl.platform,
            "platform_url": sl.platform_url,
            "purchase_price": purchase_price,
            "listed_price": sl.listed_price,
            "sale_price": sale_price,
            "platform_fees": fees,
            "shipping_cost": shipping,
            "net_profit": net,
            "roi_pct": roi,
            "sold_at": sl.sold_at.isoformat() if sl.sold_at else None,
            "source_listing_id": inv_item.source_listing_id if inv_item else None,
        })

    # Aggregates
    total_revenue = sum(r["sale_price"] for r in rows)
    total_fees = sum(r["platform_fees"] for r in rows)
    total_shipping = sum(r["shipping_cost"] for r in rows)
    total_cost = sum(r["purchase_price"] or 0 for r in rows)
    total_net = round(total_revenue - total_fees - total_shipping - total_cost, 2)

    # By platform
    by_platform = {}
    for r in rows:
        p = r["platform"]
        if p not in by_platform:
            by_platform[p] = {"count": 0, "revenue": 0, "fees": 0, "net": 0}
        by_platform[p]["count"] += 1
        by_platform[p]["revenue"] = round(by_platform[p]["revenue"] + r["sale_price"], 2)
        by_platform[p]["fees"] = round(by_platform[p]["fees"] + r["platform_fees"], 2)
        by_platform[p]["net"] = round(by_platform[p]["net"] + r["net_profit"], 2)

    # Monthly buckets (for chart)
    monthly = {}
    for r in rows:
        if not r["sold_at"]:
            continue
        month = r["sold_at"][:7]  # "YYYY-MM"
        if month not in monthly:
            monthly[month] = {"revenue": 0, "net": 0, "count": 0}
        monthly[month]["revenue"] = round(monthly[month]["revenue"] + r["sale_price"], 2)
        monthly[month]["net"] = round(monthly[month]["net"] + r["net_profit"], 2)
        monthly[month]["count"] += 1
    monthly_list = [{"month": k, **v} for k, v in sorted(monthly.items())]

    return {
        "rows": rows,
        "summary": {
            "count": len(rows),
            "total_revenue": round(total_revenue, 2),
            "total_fees": round(total_fees, 2),
            "total_shipping": round(total_shipping, 2),
            "total_cost": round(total_cost, 2),
            "total_net": total_net,
            "avg_roi_pct": round(
                sum(r["roi_pct"] for r in rows if r["roi_pct"] is not None)
                / max(1, sum(1 for r in rows if r["roi_pct"] is not None)), 1
            ) if rows else None,
        },
        "by_platform": by_platform,
        "monthly": monthly_list,
    }


# ─────────────────────────────────────────────────────────────
# Auto-outreach (manual trigger + full pipeline)
# ─────────────────────────────────────────────────────────────

@router.post("/listings/{listing_id}/send-outreach")
def send_listing_outreach(
    listing_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Manually trigger outreach for a specific listing.

    Works only for Facebook Marketplace listings. Runs in background so the
    endpoint returns immediately with the listing's updated outreach_status.
    """
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(404, "Listing not found")
    if not listing.url or "facebook.com" not in listing.url:
        raise HTTPException(400, "Auto-outreach only works for Facebook Marketplace listings")

    # Grab watchlist template before background task (avoids lazy-load issues)
    template = ""
    if listing.watchlist:
        template = listing.watchlist.outreach_message_template or ""

    listing.outreach_status = "QUEUED"
    db.commit()

    listing_url = listing.url
    listing_title = listing.title
    listing_id_val = listing.id

    def _do_outreach():
        from backend.services.outreach import send_outreach
        from backend.models.database import SessionLocal as _SL
        result = send_outreach(listing_url, listing_title, template)
        bdb = _SL()
        try:
            row = bdb.query(Listing).filter(Listing.id == listing_id_val).first()
            if row:
                if result.success:
                    row.outreach_status = "SENT"
                    row.outreach_sent_at = datetime.utcnow()
                else:
                    row.outreach_status = "FAILED"
                bdb.commit()
        finally:
            bdb.close()

    background_tasks.add_task(_do_outreach)
    return {"ok": True, "outreach_status": "QUEUED", "listing_id": listing_id}


@router.post("/listings/{listing_id}/full-pipeline")
def full_pipeline(
    listing_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Promote listing → inventory, trigger price suggestion, and (if watchlist has
    auto_list_on_buy) create a Facebook sell listing once pricing completes.

    Steps run in background — returns immediately with the new inventory item.
    """
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(404, "Listing not found")

    # Step 1: promote (idempotent)
    existing = db.query(InventoryItem).filter(
        InventoryItem.source_listing_id == listing_id
    ).first()
    if existing:
        item = existing
    else:
        item = InventoryItem(
            title=listing.title,
            description=listing.description or "",
            category=listing.watchlist.category if listing.watchlist else None,
            condition="GOOD",
            purchase_price=listing.price,
            purchase_date=datetime.utcnow(),
            source_listing_id=listing_id,
            notes=f"Auto-pipeline from {listing.source} listing.",
            status="DRAFT",
        )
        db.add(item)
        db.commit()
        db.refresh(item)

    item_id = item.id
    auto_list = listing.watchlist.auto_list_on_buy if listing.watchlist else False
    image_url = listing.image_url

    def _pipeline():
        import time as _time
        import httpx
        import uuid as _uuid
        from pathlib import Path as _Path
        from backend.models.database import SessionLocal as _SL
        from backend.services.auto_pricing import suggest_price as _suggest
        from backend.services.paths import get_inventory_item_photos_dir

        bdb = _SL()
        try:
            inv_item = bdb.query(InventoryItem).filter(InventoryItem.id == item_id).first()
            if not inv_item:
                return

            # Download image if needed
            if image_url and not inv_item.photos:
                try:
                    resp = httpx.get(image_url, timeout=15.0, follow_redirects=True)
                    if resp.status_code == 200 and len(resp.content) <= MAX_PHOTO_BYTES:
                        ext = _Path(image_url.split("?")[0]).suffix.lower()
                        if ext not in ALLOWED_PHOTO_EXT:
                            ext = ".jpg"
                        fname = f"{_uuid.uuid4().hex}{ext}"
                        photo_dir = get_inventory_item_photos_dir(item_id)
                        (photo_dir / fname).write_bytes(resp.content)
                        photo = InventoryPhoto(
                            inventory_item_id=item_id,
                            file_path=fname,
                            order_index=0,
                        )
                        bdb.add(photo)
                        bdb.commit()
                except Exception as e:
                    logger.warning(f"Pipeline: failed to download image: {e}")

            # Step 2: price suggestion
            bdb.refresh(inv_item)
            suggestion = _suggest(inv_item.title, inv_item.condition or "GOOD", bdb)
            inv_item.price_suggestion = suggestion.to_dict()
            if suggestion.suggested_price:
                inv_item.listed_price = suggestion.suggested_price
            bdb.commit()
            bdb.refresh(inv_item)

            # Step 3: auto-list on Facebook if enabled
            if auto_list and inv_item.listed_price:
                from backend.services.sellers.facebook import FacebookSeller
                from backend.services.sellers.base import ListingDraft

                photo_paths = [
                    str(get_inventory_item_photos_dir(item_id) / p.file_path)
                    for p in inv_item.photos
                ]
                draft = ListingDraft(
                    title=inv_item.title,
                    description=inv_item.description or "",
                    price=inv_item.listed_price,
                    condition=inv_item.condition or "GOOD",
                    category=inv_item.category or "",
                    photo_paths=photo_paths,
                )
                seller = FacebookSeller()
                result = seller.create_listing(draft)
                sl = SellListing(
                    inventory_item_id=item_id,
                    platform="facebook",
                    platform_listing_id=result.platform_listing_id,
                    platform_url=result.platform_url,
                    listed_price=inv_item.listed_price,
                    status="POSTED" if result.success else "FAILED",
                    listed_at=datetime.utcnow() if result.success else None,
                    error_message=result.error_message,
                    screenshot_path=result.screenshot_path,
                    action_url=result.action_url,
                )
                if result.extra:
                    sl.raw_metadata = result.extra
                bdb.add(sl)
                bdb.commit()

        except Exception as e:
            logger.error(f"Full pipeline error for item {item_id}: {e}", exc_info=True)
        finally:
            bdb.close()

    background_tasks.add_task(_pipeline)

    return {
        "ok": True,
        "inventory_item_id": item_id,
        "auto_list": auto_list,
        "message": "Pipeline started: pricing + listing in background",
    }


# ─────────────────────────────────────────────────────────────
# Source config
# ─────────────────────────────────────────────────────────────

@router.post("/sources/{source_name}/update-config")
def update_source_config(
    source_name: str,
    config: dict,
    db: Session = Depends(get_db),
):
    src = db.query(Source).filter(Source.name == source_name).first()
    if not src:
        raise HTTPException(404, "Source not found")
    existing = src.config
    existing.update(config)
    src.config = existing
    src.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "config": src.config}


# ─────────────────────────────────────────────────────────────
# Mobile — Pipeline Queue, Push Notifications & Connection
# Phone taps ⚡ → listing saved to queue → desktop polls & processes
# ─────────────────────────────────────────────────────────────

@router.post("/listings/{listing_id}/queue-pipeline")
def queue_for_pipeline(listing_id: int, db: Session = Depends(get_db)):
    """Queue a listing for desktop pipeline (price → inventory → FB Marketplace).
    Used by the mobile app, which can't run Playwright itself — the desktop polls
    GET /pipeline-queue and processes each entry. (Distinct from the desktop's
    /full-pipeline, which runs the pipeline directly.)"""
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(404, "Listing not found")
    queue: list[int] = get_setting(db, "pipeline_queue") or []
    if listing_id not in queue:
        queue.append(listing_id)
        set_setting(db, "pipeline_queue", queue)
    return {"ok": True, "queued": True, "queue_length": len(queue)}


@router.get("/pipeline-queue")
def get_pipeline_queue(db: Session = Depends(get_db)):
    """Desktop polls this to pick up listings queued from the mobile app."""
    queue: list[int] = get_setting(db, "pipeline_queue") or []
    listings = db.query(Listing).filter(Listing.id.in_(queue)).all() if queue else []
    return {
        "count": len(queue),
        "listing_ids": queue,
        "listings": [ListingOut.from_orm_safe(l) for l in listings],
    }


@router.delete("/pipeline-queue/{listing_id}")
def dequeue_pipeline(listing_id: int, db: Session = Depends(get_db)):
    """Desktop calls this after it finishes processing a queued listing."""
    queue: list[int] = get_setting(db, "pipeline_queue") or []
    set_setting(db, "pipeline_queue", [i for i in queue if i != listing_id])
    return {"ok": True}


@router.get("/connection-test")
def connection_test():
    """Phone pings this on first setup to verify it can reach the backend."""
    return {"ok": True, "service": "platapicker", "version": "1.0.0"}


class PushTokenIn(BaseModel):
    token: str


@router.post("/push-token")
def save_push_token(data: PushTokenIn, db: Session = Depends(get_db)):
    """Store the device's Expo push token so runner.py can send deal alerts."""
    set_setting(db, "expo_push_token", data.token)
    return {"ok": True}
