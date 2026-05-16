import json
from sqlalchemy.orm import Session
from backend.models.models import AppSetting


DEFAULTS = {
    "facebook_slow_mode": True,
    "facebook_min_delay_seconds": 3,
    "facebook_max_delay_seconds": 8,
    "facebook_max_listings_per_run": 50,
    "facebook_max_searches_per_run": 5,
    "facebook_cooldown_minutes": 30,
    "global_schedule_enabled": True,
    "global_schedule_interval_minutes": 60,
    "heartbeat_enabled": False,
    "heartbeat_discord_webhook_id": None,
    "alert_on_scraper_failure": True,
    "gamecube_bundle_discount": 0.85,
    "gamecube_low_demand_discount": 0.60,
    "gamecube_platform_fee_pct": 0.13,
    "deal_thresholds": {
        "STEAL": 0.45,
        "GREAT": 0.55,
        "GOOD": 0.65,
        "FAIR": 0.75,
    },
    "alert_batch_threshold": 3,
}


def get_setting(db: Session, key: str):
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row is None:
        return DEFAULTS.get(key)
    return row.value


def set_setting(db: Session, key: str, value):
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row is None:
        row = AppSetting(key=key)
        db.add(row)
    row.value = value
    db.commit()


def get_all_settings(db: Session) -> dict:
    rows = db.query(AppSetting).all()
    result = dict(DEFAULTS)
    for row in rows:
        result[row.key] = row.value
    return result
