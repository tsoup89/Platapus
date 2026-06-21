"""Tests that the GameCube price table is bootstrapped so the watchlist works.

Regression for the "GameCube not running" bug: with an empty gamecube_prices
table the watchlist matches zero games and rates every listing PASS, so it
silently never alerts.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models.database import Base
from backend.models.models import GameCubePrice, Watchlist
from backend.services.gamecube_prices import seed_prices_if_empty, DEFAULT_SAMPLE_CSV
from backend.scoring.gamecube_scorer import score_gamecube_listing


@pytest.fixture
def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    os.unlink(path)


def test_sample_csv_exists():
    assert os.path.exists(DEFAULT_SAMPLE_CSV)


def test_seed_prices_if_empty_populates_table(db):
    assert db.query(GameCubePrice).count() == 0
    result = seed_prices_if_empty(db)
    assert result["imported"] > 0
    assert db.query(GameCubePrice).count() == result["imported"]


def test_seed_prices_if_empty_is_idempotent(db):
    seed_prices_if_empty(db)
    count = db.query(GameCubePrice).count()
    again = seed_prices_if_empty(db)
    assert again["imported"] == 0
    assert db.query(GameCubePrice).count() == count


def test_seeded_prices_let_gamecube_match_and_rate(db):
    """The core regression: with seeded prices a cheap bundle is a real deal."""
    seed_prices_if_empty(db)
    prices = db.query(GameCubePrice).all()
    # Games-only lot (no hardware) so the empty-table case has zero value.
    title = (
        "GameCube games lot - Mario Kart Double Dash, Super Smash Bros Melee, "
        "Super Mario Sunshine, Luigi Mansion"
    )

    empty = score_gamecube_listing(title, "", 40.0, gamecube_prices=[])
    assert empty.rating == "PASS"
    assert len(empty.matched_games) == 0
    assert empty.estimated_value == 0

    seeded = score_gamecube_listing(title, "", 40.0, gamecube_prices=prices)
    assert len(seeded.matched_games) >= 3
    assert seeded.estimated_value > empty.estimated_value
    assert seeded.rating in ("STEAL", "GREAT", "GOOD")
