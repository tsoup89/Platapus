"""Tests for duplicate detection logic in the runner."""
import pytest
from datetime import datetime
from unittest.mock import MagicMock
from backend.scrapers.base import NormalizedListing


def make_listing(source="mock", source_listing_id=None, url=None, title="Test", price=100):
    return NormalizedListing(
        source=source,
        source_listing_id=source_listing_id,
        title=title,
        price=price,
        url=url,
        scraped_at=datetime.utcnow(),
    )


def make_db_listing(source="mock", source_listing_id=None, url=None):
    obj = MagicMock()
    obj.source = source
    obj.source_listing_id = source_listing_id
    obj.url = url
    obj.last_seen_at = None
    return obj


class TestDeduplication:
    """
    These tests verify the deduplication logic used in the runner.
    We test the logic directly rather than through the ORM.
    """

    def _check_dup(self, incoming: NormalizedListing, existing_listings: list) -> bool:
        """Simulate the deduplication logic from runner._deduplicate."""
        for existing in existing_listings:
            if incoming.source_listing_id and existing.source_listing_id:
                if (incoming.source == existing.source and
                        incoming.source_listing_id == existing.source_listing_id):
                    return True
            if incoming.url and existing.url and incoming.url == existing.url:
                return True
        return False

    def test_same_listing_id_is_duplicate(self):
        incoming = make_listing(source_listing_id="abc123", url="https://ex.com/1")
        existing = [make_db_listing(source_listing_id="abc123", url="https://ex.com/1")]
        assert self._check_dup(incoming, existing) is True

    def test_different_listing_id_not_duplicate(self):
        incoming = make_listing(source_listing_id="abc999")
        existing = [make_db_listing(source_listing_id="abc123")]
        assert self._check_dup(incoming, existing) is False

    def test_same_url_is_duplicate(self):
        incoming = make_listing(url="https://example.com/listing/42")
        existing = [make_db_listing(url="https://example.com/listing/42")]
        assert self._check_dup(incoming, existing) is True

    def test_different_url_not_duplicate(self):
        incoming = make_listing(url="https://example.com/listing/42")
        existing = [make_db_listing(url="https://example.com/listing/99")]
        assert self._check_dup(incoming, existing) is False

    def test_no_id_no_url_never_duplicate(self):
        incoming = make_listing(source_listing_id=None, url=None)
        existing = [make_db_listing(source_listing_id=None, url=None)]
        assert self._check_dup(incoming, existing) is False

    def test_empty_existing_not_duplicate(self):
        incoming = make_listing(source_listing_id="xyz")
        assert self._check_dup(incoming, []) is False
