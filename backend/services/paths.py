"""
Centralized path resolver for all data directories.

When running as a packaged Mac app, Electron sets PLATAPICKER_DATA_DIR to
  ~/Library/Application Support/Platapicker/
In development (or when run directly), it defaults to the project root so
existing behaviour is unchanged.
"""
import os
from pathlib import Path


def get_data_dir() -> Path:
    """Root data directory — all mutable files live here."""
    env = os.getenv("PLATAPICKER_DATA_DIR")
    if env:
        p = Path(env)
        p.mkdir(parents=True, exist_ok=True)
        return p
    return Path(".")


def get_screenshots_dir() -> Path:
    p = get_data_dir() / "screenshots"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_browser_sessions_dir() -> Path:
    p = get_data_dir() / "browser_sessions"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_debug_html_dir() -> Path:
    p = get_data_dir() / "debug_html"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_logs_dir() -> Path:
    p = get_data_dir() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_inventory_photos_dir() -> Path:
    p = get_data_dir() / "inventory_photos"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_inventory_item_photos_dir(item_id: int) -> Path:
    p = get_inventory_photos_dir() / str(item_id)
    p.mkdir(parents=True, exist_ok=True)
    return p
