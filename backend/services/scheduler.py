"""
APScheduler-based background scheduler for automatic scraper runs.
Reads run_frequency_minutes from each watchlist and schedules accordingly.
"""
import logging
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.models.database import SessionLocal
from backend.models.models import Watchlist, Source, AppSetting
from backend.services.settings import get_setting
from backend.services.runner import run_scraper_for_watchlist
from backend.services import discord as discord_service

logger = logging.getLogger("platapicker.scheduler")

_scheduler: Optional[BackgroundScheduler] = None


def _heartbeat_job():
    """Send a Discord heartbeat summarizing last run results."""
    db = SessionLocal()
    try:
        from backend.models.models import ScraperRun, DiscordWebhook
        heartbeat_wh_id = get_setting(db, "heartbeat_discord_webhook_id")
        if not heartbeat_wh_id:
            return

        wh = db.query(DiscordWebhook).filter(
            DiscordWebhook.id == heartbeat_wh_id,
            DiscordWebhook.enabled == True,
        ).first()
        if not wh:
            return

        sources = db.query(Source).all()
        summaries = []
        errors = []

        for src in sources:
            last_run = (
                db.query(ScraperRun)
                .filter(ScraperRun.source_name == src.name)
                .order_by(ScraperRun.started_at.desc())
                .first()
            )
            summary = {
                "name": src.name,
                "status": src.status,
                "raw_count": last_run.raw_count if last_run else 0,
                "parsed_count": last_run.parsed_count if last_run else 0,
                "alert_count": last_run.alert_count if last_run else 0,
            }
            if src.status in ("failed", "needs_login", "possible_block"):
                errors.append(f"{src.name}: {src.last_error or src.status}")
            summaries.append(summary)

        discord_service.send_heartbeat(wh.webhook_url, summaries, errors or None)
        logger.info("Heartbeat sent.")
    except Exception as e:
        logger.error(f"Heartbeat job failed: {e}")
    finally:
        db.close()


def _scrape_all_job():
    """Run all enabled scrapers across all enabled watchlists."""
    logger.info("Scheduled scrape run starting...")
    try:
        run_scraper_for_watchlist()
    except Exception as e:
        logger.error(f"Scheduled scrape failed: {e}", exc_info=True)

    db = SessionLocal()
    try:
        if get_setting(db, "heartbeat_enabled"):
            _heartbeat_job()
    finally:
        db.close()


def start_scheduler():
    global _scheduler

    db = SessionLocal()
    try:
        enabled = get_setting(db, "global_schedule_enabled")
        interval = get_setting(db, "global_schedule_interval_minutes") or 60
    finally:
        db.close()

    if not enabled:
        logger.info("Scheduler disabled in settings. Set global_schedule_enabled=true to enable.")
        return

    _scheduler = BackgroundScheduler(timezone="UTC")

    _scheduler.add_job(
        _scrape_all_job,
        trigger=IntervalTrigger(minutes=int(interval)),
        id="scrape_all",
        name="Run all scrapers",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    _scheduler.start()
    logger.info(f"Scheduler started — scrape every {interval} minutes.")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")


def get_scheduler_status() -> dict:
    if not _scheduler or not _scheduler.running:
        return {"running": False, "jobs": []}

    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
        })
    return {"running": True, "jobs": jobs}


def reschedule(interval_minutes: int):
    """Update scrape interval without restarting the app."""
    global _scheduler
    if not _scheduler or not _scheduler.running:
        return
    _scheduler.reschedule_job(
        "scrape_all",
        trigger=IntervalTrigger(minutes=interval_minutes),
    )
    logger.info(f"Scheduler rescheduled to every {interval_minutes} minutes.")
