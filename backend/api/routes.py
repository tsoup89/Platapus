"""All FastAPI route handlers for Platapicker."""
import csv
import io
import json
import logging
from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session

from backend.models import get_db
from backend.models.models import (
    Watchlist, Source, ScraperRun, Listing, DealScore,
    DiscordWebhook, GameCubePrice, TitleMapping, AppSetting,
)
from backend.api.schemas import (
    WatchlistCreate, WatchlistUpdate, WatchlistOut,
    DiscordWebhookCreate, DiscordWebhookOut,
    SourceOut, ScraperRunOut,
    ListingOut, DealScoreOut,
    GameCubePriceOut, GameCubePriceUpdate, TitleMappingOut,
    OverviewStats,
)
from backend.services import discord as discord_service
from backend.services.settings import get_all_settings, set_setting
from backend.scoring.title_matcher import normalize_title
from backend.services.runner import run_scraper_for_watchlist
from backend.services import scheduler as scheduler_service

logger = logging.getLogger("platapicker.api")
router = APIRouter()


# ─────────────────────────────────────────────────────────────
# Overview / Health
# ─────────────────────────────────────────────────────────────

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
                  "min_profit_margin", "min_profit_dollars", "discord_webhook_id", "notes"]:
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
        title = row.get("Game") or row.get("Title") or row.get("game") or ""
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
    return {
        "ok": True,
        "imported": imported,
        "updated": updated,
        "errors": errors,
        "message": f"Imported {imported} new titles, updated {updated} existing.",
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
