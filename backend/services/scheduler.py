"""
APScheduler-based background scheduler for automatic scraper runs.
Polls every 15 minutes (or the minimum watchlist interval, whichever is smaller)
and respects each watchlist's individual run_frequency_minutes setting.
"""
import logging
import math
from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.models.database import SessionLocal
from backend.models.models import Watchlist, Source, AppSetting, ScraperRun
from backend.services.settings import get_setting
from backend.services.runner import run_scraper_for_watchlist
from backend.services import discord as discord_service

logger = logging.getLogger("platapicker.scheduler")

_scheduler: Optional[BackgroundScheduler] = None

# Fallback polling interval when no watchlists define a frequency
_DEFAULT_POLL_MINUTES = 15


def _heartbeat_job():
    """Send a Discord heartbeat summarising last run results."""
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


def _get_min_interval(db) -> int:
    """
    Return the polling interval in minutes — the minimum of all enabled watchlist
    run_frequency_minutes values, with a floor of 15 minutes.
    """
    watchlists = db.query(Watchlist).filter(Watchlist.enabled == True).all()
    if not watchlists:
        return _DEFAULT_POLL_MINUTES
    frequencies = [
        wl.run_frequency_minutes
        for wl in watchlists
        if wl.run_frequency_minutes and wl.run_frequency_minutes > 0
    ]
    if not frequencies:
        return _DEFAULT_POLL_MINUTES
    return max(_DEFAULT_POLL_MINUTES, min(frequencies))


def _scrape_all_job():
    """
    Polling job: check each enabled watchlist and run only those that are due
    based on their individual run_frequency_minutes setting.
    """
    logger.info("Scheduler poll: checking watchlist run schedules...")
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        watchlists = db.query(Watchlist).filter(Watchlist.enabled == True).all()

        for wl in watchlists:
            frequency = wl.run_frequency_minutes or 60

            # Find the most recent ScraperRun for this watchlist
            last_run = (
                db.query(ScraperRun)
                .filter(ScraperRun.watchlist_id == wl.id)
                .order_by(ScraperRun.started_at.desc())
                .first()
            )

            if last_run and last_run.started_at:
                elapsed_minutes = (now - last_run.started_at).total_seconds() / 60
                if elapsed_minutes < frequency:
                    logger.info(
                        f"Watchlist '{wl.name}' not due yet "
                        f"(last run {elapsed_minutes:.0f}m ago, interval {frequency}m)"
                    )
                    continue
                logger.info(
                    f"Watchlist '{wl.name}' due "
                    f"(last run {elapsed_minutes:.0f}m ago, interval {frequency}m), running..."
                )
            else:
                logger.info(
                    f"Watchlist '{wl.name}' has never run, running now..."
                )

            try:
                run_scraper_for_watchlist(watchlist_id=wl.id)
            except Exception as e:
                logger.error(
                    f"Scrape failed for watchlist '{wl.name}': {e}", exc_info=True
                )

        if get_setting(db, "heartbeat_enabled"):
            _heartbeat_job()

    except Exception as e:
        logger.error(f"Scheduler poll failed: {e}", exc_info=True)
    finally:
        db.close()


def start_scheduler():
    global _scheduler

    db = SessionLocal()
    try:
        enabled = get_setting(db, "global_schedule_enabled")
        poll_interval = _get_min_interval(db)
    finally:
        db.close()

    if not enabled:
        logger.info(
            "Scheduler disabled in settings. "
            "Set global_schedule_enabled=true to enable."
        )
        return

    _scheduler = BackgroundScheduler(timezone="UTC")

    _scheduler.add_job(
        _scrape_all_job,
        trigger=IntervalTrigger(minutes=poll_interval),
        id="scrape_all",
        name="Poll watchlist schedules",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    _scheduler.start()
    logger.info(
        f"Scheduler started — polling every {poll_interval} minutes "
        "(each watchlist controls its own cadence)."
    )


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
    """Update the poll interval without restarting the app."""
    global _scheduler
    if not _scheduler or not _scheduler.running:
        return
    _scheduler.reschedule_job(
        "scrape_all",
        trigger=IntervalTrigger(minutes=interval_minutes),
    )
    logger.info(f"Scheduler poll rescheduled to every {interval_minutes} minutes.")
