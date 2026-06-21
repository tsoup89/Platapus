"""CLI entry point: python -m platapicker <command>"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import click
from dotenv import load_dotenv
load_dotenv()

from backend.models.database import init_db, SessionLocal
from backend.services.seed import seed_database
from backend.services import discord as discord_service


@click.group()
def cli():
    """🦆 Platapicker — deal monitoring control center."""
    pass


@cli.command("seed")
def cmd_seed():
    """Seed database with default watchlists and sources."""
    init_db()
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()


@cli.command("run")
@click.option("--source", default=None, help="Source to run (facebook, auctionninja, mock)")
@click.option("--watchlist", default=None, help="Watchlist name to run")
@click.option("--debug", is_flag=True, help="Enable debug mode")
def cmd_run(source, watchlist, debug):
    """Run scrapers."""
    from backend.services.runner import run_scraper_for_watchlist
    from backend.models.models import Watchlist

    init_db()
    db = SessionLocal()
    try:
        wl_id = None
        if watchlist:
            wl = db.query(Watchlist).filter(Watchlist.name.ilike(f"%{watchlist}%")).first()
            if wl:
                wl_id = wl.id
                click.echo(f"Running watchlist: {wl.name}")
            else:
                click.echo(f"❌ Watchlist '{watchlist}' not found.")
                return
    finally:
        db.close()

    click.echo(f"▶ Running scrapers... source={source or 'all'}")
    run_scraper_for_watchlist(source_name=source, watchlist_id=wl_id)
    click.echo("✅ Done.")


@cli.command("health")
def cmd_health():
    """Show scraper health status."""
    from backend.models.models import Source, ScraperRun

    init_db()
    db = SessionLocal()
    try:
        sources = db.query(Source).all()
        click.echo("\n🦆 Platapicker Scraper Health\n" + "─" * 40)
        for src in sources:
            status_icon = {
                "healthy": "✅",
                "failed": "❌",
                "needs_login": "🔑",
                "possible_block": "⚠️",
                "warning": "⚠️",
            }.get(src.status, "❓")
            last_run = src.last_run_at.strftime("%b %d %H:%M") if src.last_run_at else "Never"
            click.echo(f"{status_icon} {src.name:<20} Status: {src.status:<15} Last run: {last_run}")
            if src.last_error:
                click.echo(f"   Error: {src.last_error[:80]}")
        click.echo("")
    finally:
        db.close()


@cli.command("facebook-login")
def cmd_facebook_login():
    """Open browser for Facebook Marketplace login."""
    from backend.scrapers.facebook import FacebookScraper
    scraper = FacebookScraper()
    scraper.login()


@cli.command("facebook-status")
def cmd_facebook_status():
    """Show Facebook scraper session status."""
    from pathlib import Path
    session_file = Path("browser_sessions/facebook/session.json")
    if session_file.exists():
        size = session_file.stat().st_size
        click.echo(f"✅ Facebook session file found ({size} bytes)")
        click.echo("   Run a test scrape to verify the session is still valid.")
    else:
        click.echo("❌ No Facebook session found.")
        click.echo("   Run: python -m platapicker facebook-login")


@cli.command("test-discord")
@click.argument("webhook_url", required=False)
def cmd_test_discord(webhook_url):
    """Send a test message to a Discord webhook."""
    if not webhook_url:
        from backend.models.models import DiscordWebhook
        init_db()
        db = SessionLocal()
        try:
            wh = db.query(DiscordWebhook).filter(DiscordWebhook.enabled == True).first()
            if wh:
                webhook_url = wh.webhook_url
                click.echo(f"Using webhook: {wh.name}")
            else:
                click.echo("❌ No Discord webhooks configured. Pass URL as argument or add one in the dashboard.")
                return
        finally:
            db.close()

    ok = discord_service.send_test_message(webhook_url)
    if ok:
        click.echo("✅ Test message sent!")
    else:
        click.echo("❌ Failed to send test message. Check the webhook URL.")


@cli.command("import-gamecube-prices")
@click.argument("csv_path", default=None, required=False)
def cmd_import_gamecube(csv_path):
    """Import GameCube prices from a CSV file (defaults to the bundled sample)."""
    from backend.services.gamecube_prices import (
        import_prices_from_csv, DEFAULT_SAMPLE_CSV,
    )

    csv_path = csv_path or DEFAULT_SAMPLE_CSV

    init_db()
    db = SessionLocal()
    try:
        result = import_prices_from_csv(db, csv_path)
        click.echo(
            f"✅ Imported {result['imported']} new titles, "
            f"updated {result['updated']} existing."
        )
    except FileNotFoundError:
        click.echo(f"❌ File not found: {csv_path}")
    finally:
        db.close()


@cli.command("reset-duplicates")
def cmd_reset_duplicates():
    """Clear all listings from the duplicate cache."""
    from backend.models.models import Listing
    init_db()
    db = SessionLocal()
    try:
        count = db.query(Listing).count()
        if click.confirm(f"This will delete {count} listings. Continue?"):
            db.query(Listing).delete()
            db.commit()
            click.echo(f"✅ Cleared {count} listings.")
    finally:
        db.close()


@cli.command("heartbeat")
def cmd_heartbeat():
    """Send a Discord heartbeat with current scraper health."""
    from backend.services.scheduler import _heartbeat_job
    init_db()
    _heartbeat_job()
    click.echo("✅ Heartbeat sent (if webhook is configured).")


@cli.command("scheduler-status")
def cmd_scheduler_status():
    """Show current scheduler configuration."""
    init_db()
    db = SessionLocal()
    try:
        from backend.services.settings import get_setting
        enabled = get_setting(db, "global_schedule_enabled")
        interval = get_setting(db, "global_schedule_interval_minutes")
        click.echo(f"\n🦆 Platapicker Scheduler\n" + "─" * 40)
        click.echo(f"  Enabled:  {'Yes' if enabled else 'No (start server to activate)'}")
        click.echo(f"  Interval: every {interval} minutes")
        click.echo(f"\n  Note: scheduler runs inside the server process (python run.py)")
    finally:
        db.close()


if __name__ == "__main__":
    cli()
