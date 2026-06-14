"""Tests for the shared get_with_retry helper in scrapers/base.py."""
import pytest
import requests

from backend.scrapers import base
from backend.scrapers.base import get_with_retry


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


class FakeSession:
    """Yields one outcome per .get() call — a response or an exception."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def get(self, url, timeout=None):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(base.time, "sleep", lambda s: None)


def test_success_first_attempt():
    session = FakeSession([FakeResponse(200)])
    resp = get_with_retry(session, "http://x")
    assert resp.status_code == 200
    assert session.calls == 1


def test_retries_on_429_then_succeeds():
    session = FakeSession([FakeResponse(429), FakeResponse(200)])
    resp = get_with_retry(session, "http://x")
    assert resp.status_code == 200
    assert session.calls == 2


def test_retries_on_5xx_then_succeeds():
    session = FakeSession([FakeResponse(503), FakeResponse(500), FakeResponse(200)])
    resp = get_with_retry(session, "http://x")
    assert resp.status_code == 200
    assert session.calls == 3


def test_returns_final_error_response_after_exhausting_retries():
    session = FakeSession([FakeResponse(500)] * 3)
    resp = get_with_retry(session, "http://x", max_attempts=3)
    assert resp.status_code == 500
    assert session.calls == 3


def test_fails_fast_on_permanent_4xx():
    session = FakeSession([FakeResponse(404)])
    resp = get_with_retry(session, "http://x")
    assert resp.status_code == 404
    assert session.calls == 1


def test_fails_fast_on_403():
    session = FakeSession([FakeResponse(403)])
    resp = get_with_retry(session, "http://x")
    assert resp.status_code == 403
    assert session.calls == 1


def test_retries_timeout_then_succeeds():
    session = FakeSession([requests.Timeout("slow"), requests.Timeout("slow"), FakeResponse(200)])
    resp = get_with_retry(session, "http://x")
    assert resp.status_code == 200
    assert session.calls == 3


def test_raises_after_all_network_failures():
    session = FakeSession([requests.ConnectionError("refused")] * 3)
    with pytest.raises(requests.ConnectionError):
        get_with_retry(session, "http://x", max_attempts=3)
    assert session.calls == 3


def test_respects_max_attempts():
    session = FakeSession([requests.Timeout("slow"), FakeResponse(200)])
    with pytest.raises(requests.Timeout):
        get_with_retry(session, "http://x", max_attempts=1)
    assert session.calls == 1
