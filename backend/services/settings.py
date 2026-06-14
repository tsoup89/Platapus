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
    "watchdog_enabled": True,
    "watchdog_grace_multiplier": 2,
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
    # Photo analysis (OCR / model recognition). Opt-in — costs Claude tokens.
    "photo_analysis_enabled": False,
    # Local-LLM (Ollama) maker-checker pricing knobs (writable + visible in Settings).
    "local_llm_pricing_enabled": True,
    "local_llm_base_url": "http://localhost:11434",
    "local_llm_model": "qwen3:30b",
    "local_llm_checker_enabled": True,
    "local_llm_checker_model": "qwen3-coder:30b",
    "local_llm_agreement_tolerance": 0.25,
    "local_llm_timeout_seconds": 60,
    # Weekly review — once-a-week health + deal-flow digest posted to Discord.
    "weekly_review_enabled": True,
    "weekly_review_discord_webhook_id": None,
    "weekly_review_day_of_week": "mon",   # APScheduler cron day_of_week
    "weekly_review_hour": 8,              # local hour (see timezone below)
    "weekly_review_timezone": "America/New_York",
}

# Keys writable via the generic POST /settings endpoint. Keys with dedicated
# endpoints (pipeline_queue, expo_push_token) are deliberately excluded.
ALLOWED_KEYS = set(DEFAULTS) | {
    "claude_enabled",
    "claude_api_key",
    "claude_model",
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
