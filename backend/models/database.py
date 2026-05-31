import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./platapicker.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
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
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(__import__("sqlalchemy").text(sql))
                conn.commit()
            except Exception:
                # Column already exists — safe to ignore
                pass
