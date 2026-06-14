"""
Weekly review — a once-a-week health + deal-flow digest posted to Discord.

Runs locally inside the always-on backend (the DB, Ollama and the 127.0.0.1 API all
live on this machine, so a cloud agent couldn't reach them). Covers four areas the
user asked for:
  1. Pricing pipeline health  — eBay/Ollama up, comp-cache freshness, maker-checker
     disagreement rate.
  2. Deal flow & alerts        — listings scraped, alerts fired, STEAL/GREAT counts,
     leads, and watchlists that went silent.
  3. Tuning suggestions        — concrete, actionable nudges (tolerance too tight,
     watchlists missing a webhook, etc.).
  4. Scraper / source errors   — run failures and last-error messages from the week.

Read-only against the DB except for nothing — it never writes. Fail-soft: any
section that errors is reported as such rather than aborting the whole review.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.database import SessionLocal
from backend.models.models import (
    Watchlist, Source, ScraperRun, Listing, DealScore, MarketValueCache,
    DiscordWebhook,
)
from backend.services.settings import get_setting, get_all_settings
from backend.services import discord as discord_service

logger = logging.getLogger("platapicker.weekly_review")

WINDOW_DAYS = 7


def _pricing_health(db: Session, settings: dict, since: datetime) -> dict:
    from backend.services.local_llm_pricing import ollama_status

    ollama = ollama_status(settings)

    ebay = db.query(Source).filter(Source.name == "ebay").first()
    ebay_info = None
    if ebay:
        ebay_info = {
            "enabled": ebay.enabled,
            "status": ebay.status,
            "last_success_at": ebay.last_success_at.isoformat() if ebay.last_success_at else None,
        }

    now = datetime.utcnow()
    cache = {}
    for src in ("ebay_sold", "ebay", "local_llm"):
        rows = db.query(MarketValueCache).filter(MarketValueCache.source == src).all()
        if rows:
            cache[src] = {
                "total": len(rows),
                "fresh": sum(1 for r in rows if r.expires_at and r.expires_at > now),
            }

    # Maker-checker disagreement rate over the window: of the AI-priced scores this
    # week, what share got flagged needs_review (i.e. valued at the checker's low).
    mc_scores = (
        db.query(DealScore)
        .join(Listing, DealScore.listing_id == Listing.id)
        .filter(Listing.first_seen_at >= since,
                DealScore.value_source == "maker_checker")
        .all()
    )
    mc_total = len(mc_scores)
    mc_review = 0
    for s in mc_scores:
        pb = getattr(s, "pricing_breakdown", None)
        if pb and pb.get("needs_review"):
            mc_review += 1

    return {
        "ollama": ollama,
        "ebay": ebay_info,
        "cache": cache,
        "maker_checker_priced": mc_total,
        "maker_checker_needs_review": mc_review,
        "maker_checker_disagree_pct": round(100 * mc_review / mc_total) if mc_total else None,
    }


def _deal_flow(db: Session, since: datetime) -> dict:
    new_listings = db.query(Listing).filter(Listing.first_seen_at >= since).count()
    alerts_sent = db.query(Listing).filter(
        Listing.first_seen_at >= since, Listing.alert_sent == True
    ).count()

    scores = (
        db.query(DealScore)
        .join(Listing, DealScore.listing_id == Listing.id)
        .filter(Listing.first_seen_at >= since)
        .all()
    )
    ratings = {"STEAL": 0, "GREAT": 0, "GOOD": 0, "FAIR": 0, "PASS": 0}
    leads = 0
    for s in scores:
        if s.rating in ratings:
            ratings[s.rating] += 1
        if getattr(s, "is_lead", False):
            leads += 1

    # Per-watchlist scraped totals this week, to spot ones that went silent.
    per_wl = []
    for wl in db.query(Watchlist).filter(Watchlist.enabled == True).all():
        runs = (
            db.query(ScraperRun)
            .filter(ScraperRun.watchlist_id == wl.id, ScraperRun.started_at >= since)
            .all()
        )
        raw = sum(r.raw_count or 0 for r in runs)
        alerts = sum(r.alert_count or 0 for r in runs)
        per_wl.append({"name": wl.name, "runs": len(runs), "raw": raw, "alerts": alerts})

    silent = [w["name"] for w in per_wl if w["runs"] > 0 and w["raw"] == 0]

    return {
        "new_listings": new_listings,
        "alerts_sent": alerts_sent,
        "ratings": ratings,
        "leads": leads,
        "per_watchlist": sorted(per_wl, key=lambda w: w["raw"], reverse=True),
        "silent_watchlists": silent,
    }


def _source_errors(db: Session, since: datetime) -> dict:
    failed_runs = (
        db.query(ScraperRun)
        .filter(ScraperRun.started_at >= since,
                ScraperRun.status.in_(["failed", "partial"]))
        .all()
    )
    by_source = {}
    for r in failed_runs:
        by_source.setdefault(r.source_name, {"count": 0, "last_error": None})
        by_source[r.source_name]["count"] += 1
        if r.error_message:
            by_source[r.source_name]["last_error"] = r.error_message[:160]

    unhealthy = []
    for src in db.query(Source).filter(Source.enabled == True).all():
        if src.status and src.status != "healthy":
            unhealthy.append({"name": src.name, "status": src.status,
                              "last_error": (src.last_error or "")[:160]})

    return {"failed_by_source": by_source, "unhealthy_sources": unhealthy}


def _tuning_suggestions(db: Session, settings: dict, health: dict, flow: dict) -> list:
    tips = []

    # Tolerance too tight → most premium items flagged review (coder becomes ceiling).
    pct = health.get("maker_checker_disagree_pct")
    if pct is not None and pct >= 60 and health.get("maker_checker_priced", 0) >= 5:
        tol = settings.get("local_llm_agreement_tolerance", 0.25)
        tips.append(
            f"{pct}% of AI-priced items were flagged needs-review this week — the "
            f"checker is low-balling and becoming the price ceiling. Consider raising "
            f"`local_llm_agreement_tolerance` (now {tol}) to be more lenient."
        )

    # Enabled watchlists with no webhook → they scrape but never alert.
    no_wh = [wl.name for wl in db.query(Watchlist).filter(
        Watchlist.enabled == True, Watchlist.discord_webhook_id.is_(None)
    ).all()]
    if no_wh:
        tips.append(
            f"{len(no_wh)} enabled watchlist(s) have no Discord webhook → they scrape "
            f"but send no alerts: {', '.join(no_wh[:6])}{'…' if len(no_wh) > 6 else ''}."
        )

    # Silent watchlists (ran but returned nothing).
    if flow.get("silent_watchlists"):
        tips.append(
            "Returned 0 listings all week (possible scraper breakage): "
            + ", ".join(flow["silent_watchlists"][:6]) + "."
        )

    # eBay stale / blocked.
    ebay = health.get("ebay")
    if ebay and ebay.get("enabled") and ebay.get("status") not in (None, "healthy"):
        tips.append(f"eBay source is '{ebay['status']}' — comps may be unreliable; "
                    f"the AI gap-fill is carrying more of the pricing.")

    # Ollama / models missing.
    o = health.get("ollama", {})
    if not o.get("reachable"):
        tips.append("Ollama was unreachable at review time — AI pricing is down; "
                    "only eBay/table comps are working.")
    elif not o.get("maker_present") or not o.get("checker_present"):
        tips.append("A configured qwen model isn't pulled in Ollama — maker-checker "
                    "is running single-model (no cross-check).")

    if not tips:
        tips.append("No tuning issues detected this week. 🎯")
    return tips


def generate_weekly_review(db: Optional[Session] = None) -> dict:
    """Build the structured weekly-review payload. Read-only; fail-soft per section."""
    own = db is None
    db = db or SessionLocal()
    try:
        settings = get_all_settings(db)
        since = datetime.utcnow() - timedelta(days=WINDOW_DAYS)
        review = {"generated_at": datetime.utcnow().isoformat(), "window_days": WINDOW_DAYS}
        try:
            review["health"] = _pricing_health(db, settings, since)
        except Exception as e:
            review["health"] = {"error": str(e)}
        try:
            review["flow"] = _deal_flow(db, since)
        except Exception as e:
            review["flow"] = {"error": str(e)}
        try:
            review["errors"] = _source_errors(db, since)
        except Exception as e:
            review["errors"] = {"error": str(e)}
        try:
            review["tuning"] = _tuning_suggestions(
                db, settings, review.get("health", {}), review.get("flow", {})
            )
        except Exception as e:
            review["tuning"] = [f"(tuning analysis failed: {e})"]
        return review
    finally:
        if own:
            db.close()


def run_weekly_review(db: Optional[Session] = None) -> dict:
    """Generate the review and post it to the configured Discord webhook.

    Returns {posted: bool, webhook_id, review, ...}. Never raises."""
    own = db is None
    db = db or SessionLocal()
    try:
        review = generate_weekly_review(db)
        wh_id = get_setting(db, "weekly_review_discord_webhook_id")
        if not wh_id:
            logger.warning("Weekly review: no webhook configured; not posting.")
            return {"posted": False, "reason": "no webhook configured", "review": review}
        wh = db.query(DiscordWebhook).filter(
            DiscordWebhook.id == wh_id, DiscordWebhook.enabled == True
        ).first()
        if not wh:
            logger.warning("Weekly review: webhook %s not found/disabled.", wh_id)
            return {"posted": False, "reason": "webhook not found", "review": review}
        ok = discord_service.send_weekly_review(wh.webhook_url, review)
        logger.info("Weekly review posted to webhook %s: %s", wh_id, ok)
        return {"posted": ok, "webhook_id": wh_id, "review": review}
    except Exception as e:
        logger.error("Weekly review failed: %s", e, exc_info=True)
        return {"posted": False, "reason": str(e)}
    finally:
        if own:
            db.close()
