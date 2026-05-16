"""Seed default watchlists, sources, and initial app settings."""
import json
from sqlalchemy.orm import Session
from backend.models.models import Watchlist, Source, AppSetting, DiscordWebhook


def seed_database(db: Session):
    _seed_sources(db)
    _seed_watchlists(db)
    _seed_settings(db)
    db.commit()
    print("✅ Database seeded with default watchlists and sources.")


def _seed_sources(db: Session):
    existing = {s.name for s in db.query(Source).all()}

    sources = [
        Source(
            name="facebook",
            enabled=True,
            type="facebook",
            status="unknown",
            config_json=json.dumps({
                "slow_mode": True,
                "min_delay_seconds": 3,
                "max_delay_seconds": 8,
                "max_listings_per_run": 50,
                "max_searches_per_run": 5,
                "cooldown_minutes": 30,
            }),
        ),
        Source(
            name="auctionninja",
            enabled=True,
            type="auctionninja",
            status="unknown",
            config_json=json.dumps({
                "base_url": "https://www.auctionninja.com",
                "request_delay_seconds": 2,
            }),
        ),
    ]

    for source in sources:
        if source.name not in existing:
            db.add(source)


def _seed_watchlists(db: Session):
    existing = {w.name for w in db.query(Watchlist).all()}

    watchlists = [
        Watchlist(
            name="Espresso Machines",
            enabled=True,
            category="espresso",
            keywords_json=json.dumps([
                "espresso machine", "espresso grinder", "coffee grinder",
                "dual boiler", "prosumer espresso", "commercial espresso machine",
                "home espresso",
            ]),
            negative_keywords_json=json.dumps([
                "toy", "broken", "parts only", "pod", "nespresso", "keurig",
                "automatic only",
            ]),
            brands_json=json.dumps([
                "La Marzocco", "Profitec", "ECM", "Rocket", "Lelit",
                "Rancilio", "Breville", "Ascaso", "Mazzer", "Eureka",
                "Niche", "Weber",
            ]),
            aliases_json=json.dumps([]),
            locations_json=json.dumps(["New York, NY"]),
            radius_miles=75,
            min_price=50,
            max_price=5000,
            sources_enabled_json=json.dumps(["facebook", "auctionninja"]),
            run_frequency_minutes=60,
            min_rating_to_alert="GOOD",
            min_profit_margin=0.20,
            min_profit_dollars=50,
            notes="Focus on prosumer machines. Ignore pod machines and broken units.",
        ),
        Watchlist(
            name="GameCube",
            enabled=True,
            category="gamecube",
            keywords_json=json.dumps([
                "GameCube", "Nintendo GameCube", "GameCube bundle",
                "GameCube games", "GameCube console",
                "Mario Kart Double Dash", "Smash Melee", "Mario Party",
                "Zelda GameCube",
            ]),
            negative_keywords_json=json.dumps([
                "wii", "wii u", "switch", "ds", "gba", "game boy",
            ]),
            brands_json=json.dumps(["Nintendo"]),
            aliases_json=json.dumps([
                {"alias": "Double Dash", "target": "Mario Kart: Double Dash!!"},
                {"alias": "Smash Melee", "target": "Super Smash Bros. Melee"},
                {"alias": "Melee", "target": "Super Smash Bros. Melee"},
                {"alias": "Mario Sunshine", "target": "Super Mario Sunshine"},
                {"alias": "Wind Waker", "target": "The Legend of Zelda: The Wind Waker"},
                {"alias": "Luigi Mansion", "target": "Luigi's Mansion"},
                {"alias": "Pikmin 2", "target": "Pikmin 2"},
            ]),
            locations_json=json.dumps(["New York, NY"]),
            radius_miles=100,
            min_price=20,
            max_price=1000,
            sources_enabled_json=json.dumps(["facebook", "auctionninja"]),
            run_frequency_minutes=60,
            min_rating_to_alert="GOOD",
            min_profit_margin=0.25,
            min_profit_dollars=30,
            notes="Use GameCube pricing table for bundle valuation. Flag unmatched titles for manual review.",
        ),
        Watchlist(
            name="Outdoor Furniture",
            enabled=True,
            category="outdoor_furniture",
            keywords_json=json.dumps([
                "patio set", "outdoor furniture", "teak table", "outdoor dining",
                "patio chairs", "Adirondack", "outdoor sectional",
                "wicker patio", "patio sofa", "outdoor table",
            ]),
            negative_keywords_json=json.dumps([
                "dollhouse", "miniature", "cover only", "cushions only",
                "broken", "kids",
            ]),
            brands_json=json.dumps([
                "Brown Jordan", "Kingsley Bate", "Polywood", "Gloster",
                "Tropitone", "Lloyd Flanders", "Woodard", "Frontgate",
                "Restoration Hardware", "Pottery Barn", "West Elm",
                "Teak Warehouse",
            ]),
            aliases_json=json.dumps([]),
            locations_json=json.dumps(["New York, NY"]),
            radius_miles=75,
            min_price=50,
            max_price=10000,
            sources_enabled_json=json.dumps(["facebook", "auctionninja"]),
            run_frequency_minutes=90,
            min_rating_to_alert="GOOD",
            min_profit_margin=0.25,
            min_profit_dollars=100,
            notes="Prioritize premium brands. Penalize missing pieces or cushion-only listings.",
        ),
    ]

    for wl in watchlists:
        if wl.name not in existing:
            db.add(wl)


def _seed_settings(db: Session):
    existing = {s.key for s in db.query(AppSetting).all()}

    defaults = {
        "facebook_slow_mode": True,
        "facebook_min_delay_seconds": 3,
        "facebook_max_delay_seconds": 8,
        "facebook_max_listings_per_run": 50,
        "facebook_max_searches_per_run": 5,
        "facebook_cooldown_minutes": 30,
        "global_schedule_enabled": False,
        "global_schedule_interval_minutes": 60,
        "heartbeat_enabled": False,
        "heartbeat_discord_webhook_id": None,
        "alert_on_scraper_failure": True,
        "gamecube_bundle_discount": 0.85,
        "gamecube_low_demand_discount": 0.60,
        "gamecube_platform_fee_pct": 0.13,
        "deal_thresholds": {"STEAL": 0.45, "GREAT": 0.55, "GOOD": 0.65, "FAIR": 0.75},
    }

    for key, val in defaults.items():
        if key not in existing:
            db.add(AppSetting(key=key, value_json=json.dumps(val)))
