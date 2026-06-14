import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./platapicker.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30} if "sqlite" in DATABASE_URL else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models  # noqa: F401 — ensures models are registered
    Base.metadata.create_all(bind=engine)
    _run_migrations()


def _run_migrations():
    """Safe ALTER TABLE migrations for columns added after initial schema creation."""
    migrations = [
        "ALTER TABLE inventory_items ADD COLUMN listed_price REAL",
        # Watchlist automation fields
        "ALTER TABLE watchlists ADD COLUMN auto_outreach_enabled INTEGER DEFAULT 0",
        "ALTER TABLE watchlists ADD COLUMN outreach_message_template TEXT DEFAULT ''",
        "ALTER TABLE watchlists ADD COLUMN auto_list_on_buy INTEGER DEFAULT 0",
        # Listing outreach tracking
        "ALTER TABLE listings ADD COLUMN outreach_status TEXT",
        "ALTER TABLE listings ADD COLUMN outreach_sent_at DATETIME",
        # Per-watchlist scoring adjustments
        "ALTER TABLE watchlists ADD COLUMN estimated_shipping_cost REAL DEFAULT 0.0",
        "ALTER TABLE watchlists ADD COLUMN sales_tax_rate REAL DEFAULT 0.0",
        # Required-keyword relevance gate (any-of match on title/description)
        "ALTER TABLE watchlists ADD COLUMN required_keywords_json TEXT DEFAULT '[]'",
        # Net Flip Score + new signal detail on deal_scores
        "ALTER TABLE deal_scores ADD COLUMN net_flip_score REAL",
        "ALTER TABLE deal_scores ADD COLUMN estimated_roi_percent REAL",
        "ALTER TABLE deal_scores ADD COLUMN net_profit REAL",
        "ALTER TABLE deal_scores ADD COLUMN risk_level TEXT",
        "ALTER TABLE deal_scores ADD COLUMN confidence_label TEXT",
        "ALTER TABLE deal_scores ADD COLUMN net_flip_json TEXT",
        "ALTER TABLE deal_scores ADD COLUMN bad_listing_json TEXT",
        "ALTER TABLE deal_scores ADD COLUMN bundle_json TEXT",
        # Photo analysis on listings
        "ALTER TABLE listings ADD COLUMN detected_brand TEXT",
        "ALTER TABLE listings ADD COLUMN detected_model TEXT",
        "ALTER TABLE listings ADD COLUMN photo_analysis_json TEXT",
        # Maker-checker local-LLM pricing (added 2026-06-14)
        "ALTER TABLE deal_scores ADD COLUMN value_source TEXT",
        "ALTER TABLE deal_scores ADD COLUMN pricing_breakdown_json TEXT",
        "ALTER TABLE market_value_cache ADD COLUMN details_json TEXT",
        # Negotiable / no-fixed-price lead flag (added 2026-06-14)
        "ALTER TABLE deal_scores ADD COLUMN is_lead INTEGER DEFAULT 0",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(__import__("sqlalchemy").text(sql))
                conn.commit()
            except Exception:
                # Column already exists — safe to ignore
                pass
