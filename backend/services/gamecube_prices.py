"""Import and bootstrap GameCube pricing data.

The GameCube watchlist scores listings against the ``gamecube_prices`` table.
If that table is empty, every GameCube listing matches zero games, lands a
near-zero value, and is rated PASS — so the watchlist looks dead even though
the scraper ran. This module provides the importer used by both the CLI and
the seeder so a fresh install is populated automatically.
"""
import csv
import os
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from backend.models.models import GameCubePrice
from backend.scoring.title_matcher import normalize_title

logger = logging.getLogger("platapicker.gamecube_prices")

# repo_root/data/gamecube_prices_sample.csv
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_SAMPLE_CSV = os.path.join(_REPO_ROOT, "data", "gamecube_prices_sample.csv")

CORE_TITLES = [
    "mario kart", "super smash bros", "mario party", "super mario sunshine",
    "luigi's mansion", "legend of zelda", "metroid prime", "pikmin",
    "animal crossing", "f-zero", "paper mario", "resident evil 4",
]


def _safe_float(val):
    if not val or str(val).strip() in ("", "N/A", "-"):
        return None
    try:
        return float(str(val).replace("$", "").replace(",", "").strip())
    except ValueError:
        return None


def import_prices_from_csv(db: Session, csv_path: str) -> dict:
    """Import/update GameCube prices from a PriceCharting-style CSV.

    Returns ``{"imported": N, "updated": N}``. Raises ``FileNotFoundError``
    if ``csv_path`` does not exist.
    """
    imported = updated = 0
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = (row.get("Game") or row.get("Title") or "").strip()
            if not title:
                continue

            norm = normalize_title(title)
            is_core = any(ct in title.lower() for ct in CORE_TITLES)
            existing = (
                db.query(GameCubePrice)
                .filter(GameCubePrice.normalized_title == norm)
                .first()
            )

            if existing:
                existing.loose_price = _safe_float(row.get("Loose Price"))
                existing.complete_price = _safe_float(row.get("Complete Price"))
                existing.new_price = _safe_float(row.get("New Price"))
                existing.graded_price = _safe_float(row.get("Graded Price"))
                existing.box_only_price = _safe_float(row.get("Box Only"))
                existing.manual_only_price = _safe_float(row.get("Manual Only"))
                existing.last_updated = datetime.utcnow()
                updated += 1
            else:
                db.add(GameCubePrice(
                    title=title,
                    normalized_title=norm,
                    loose_price=_safe_float(row.get("Loose Price")),
                    complete_price=_safe_float(row.get("Complete Price")),
                    new_price=_safe_float(row.get("New Price")),
                    graded_price=_safe_float(row.get("Graded Price")),
                    box_only_price=_safe_float(row.get("Box Only")),
                    manual_only_price=_safe_float(row.get("Manual Only")),
                    demand_tier="high" if is_core else "medium",
                    sell_speed="fast" if is_core else "medium",
                    core_title=is_core,
                ))
                imported += 1

    db.commit()
    return {"imported": imported, "updated": updated}


def seed_prices_if_empty(db: Session, csv_path: str = DEFAULT_SAMPLE_CSV) -> dict:
    """Bootstrap the price table from the bundled sample CSV when it is empty.

    A no-op when prices already exist or the CSV is missing.
    """
    if db.query(GameCubePrice).count() > 0:
        return {"imported": 0, "updated": 0, "skipped": "already populated"}
    if not os.path.exists(csv_path):
        logger.warning(f"GameCube sample prices not found at {csv_path}; skipping seed.")
        return {"imported": 0, "updated": 0, "skipped": "csv missing"}

    result = import_prices_from_csv(db, csv_path)
    logger.info(f"Seeded {result['imported']} GameCube prices from sample CSV.")
    return result
