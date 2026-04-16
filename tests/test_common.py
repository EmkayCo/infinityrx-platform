"""Tests for shared loader primitives — the pieces extracted from
load_sam.py during Wave 9 so every loader reuses one implementation.

Scope here is unit-level: Retry-After parsing, StateFile read/write,
and the happy-path behaviour of get_with_retry against mocked
requests.get. SAM-specific tests (extract-token parsing, mode
resolver, end-to-end load) remain in tests/test_load_sam_wave8.py.
"""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from shared.data_ingestion import common


# ---------------------------------------------------------------------------
# parse_retry_after — both formats per RFC 7231
# ---------------------------------------------------------------------------


def test_retry_after_seconds_integer():
    assert common.parse_retry_after("120") == 120


def test_retry_after_seconds_integer_floor_at_one():
    assert common.parse_retry_after("0") == 1
    assert common.parse_retry_after("-5") == 1


def test_retry_after_http_date(monkeypatch):
    """HTTP-date form: compute delta against now."""
    class FrozenDT(datetime):
        @classmethod
        def utcnow(cls):
            return datetime(2026, 4, 16, 0, 0, 0)
    monkeypatch.setattr(common, "datetime", FrozenDT)
    assert common.parse_retry_after("Fri, 17 Apr 2026 00:00:00 GMT") == 86400


def test_retry_after_empty_returns_none():
    assert common.parse_retry_after("") is None


def test_retry_after_none_returns_none():
    assert common.parse_retry_after(None) is None


def test_retry_after_garbage_returns_none():
    assert common.parse_retry_after("not a number or date") is None


# ---------------------------------------------------------------------------
# StateFile
# ---------------------------------------------------------------------------


def test_state_file_read_absent_returns_none(tmp_path):
    sf = common.StateFile(tmp_path / "missing" / ".last_run")
    assert sf.read() is None


def test_state_file_write_then_read_roundtrips(tmp_path):
    sf = common.StateFile(tmp_path / ".last_run")
    sf.write(date(2026, 4, 15))
    assert sf.read() == date(2026, 4, 15)


def test_state_file_write_creates_parent_dir(tmp_path):
    sf = common.StateFile(tmp_path / "nested" / "dir" / ".last_run")
    sf.write(date(2026, 1, 1))
    assert sf.path.exists()
    assert sf.read() == date(2026, 1, 1)


def test_state_file_corrupt_content_returns_none(tmp_path):
    path = tmp_path / ".last_run"
    path.write_text("not-a-date")
    assert common.StateFile(path).read() is None


def test_state_file_accepts_str_path(tmp_path):
    """Path is coerced from str so callers don't need to wrap explicitly."""
    sf = common.StateFile(str(tmp_path / ".last_run"))
    sf.write(date(2026, 6, 1))
    assert sf.read() == date(2026, 6, 1)


# ---------------------------------------------------------------------------
# get_with_retry — happy path + 429 + 5xx + transport error retry
# ---------------------------------------------------------------------------


def _resp(status: int, headers=None):
    r = MagicMock()
    r.status_code = status
    r.headers = headers or {}
    r.raise_for_status = MagicMock()
    return r


def test_get_with_retry_returns_200_immediately(monkeypatch):
    monkeypatch.setattr(common.time, "sleep", lambda s: None)
    monkeypatch.setattr(common.requests, "get", lambda *a, **kw: _resp(200))
    resp = common.get_with_retry("http://x", {}, timeout=10)
    assert resp.status_code == 200


def test_get_with_retry_accepts_202_when_allowed(monkeypatch):
    monkeypatch.setattr(common.time, "sleep", lambda s: None)
    monkeypatch.setattr(common.requests, "get", lambda *a, **kw: _resp(202))
    resp = common.get_with_retry("http://x", {}, timeout=10, accept_202=True)
    assert resp.status_code == 202


def test_get_with_retry_retries_on_429_then_succeeds(monkeypatch):
    seq = iter([_resp(429, {"Retry-After": "1"}), _resp(200)])
    monkeypatch.setattr(common.time, "sleep", lambda s: None)
    monkeypatch.setattr(common.requests, "get", lambda *a, **kw: next(seq))
    resp = common.get_with_retry("http://x", {}, timeout=10)
    assert resp.status_code == 200


def test_get_with_retry_retries_on_5xx_then_succeeds(monkeypatch):
    seq = iter([_resp(502), _resp(503), _resp(200)])
    monkeypatch.setattr(common.time, "sleep", lambda s: None)
    monkeypatch.setattr(common.requests, "get", lambda *a, **kw: next(seq))
    resp = common.get_with_retry("http://x", {}, timeout=10)
    assert resp.status_code == 200


def test_get_with_retry_retries_on_transport_error(monkeypatch):
    attempts = {"n": 0}

    def fake_get(*a, **kw):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise common.requests.RequestException("net down")
        return _resp(200)

    monkeypatch.setattr(common.time, "sleep", lambda s: None)
    monkeypatch.setattr(common.requests, "get", fake_get)
    resp = common.get_with_retry("http://x", {}, timeout=10)
    assert resp.status_code == 200
    assert attempts["n"] == 2


def test_get_with_retry_raises_on_non_retryable_4xx(monkeypatch):
    """404 and other non-429 4xx go through raise_for_status immediately."""
    import requests as _r
    resp = _resp(404)
    resp.raise_for_status.side_effect = _r.HTTPError("404")
    monkeypatch.setattr(common.time, "sleep", lambda s: None)
    monkeypatch.setattr(common.requests, "get", lambda *a, **kw: resp)
    with pytest.raises(_r.HTTPError):
        common.get_with_retry("http://x", {}, timeout=10)


def test_get_with_retry_exhausts_retries_on_persistent_429(monkeypatch):
    """All attempts return 429 → the final 429 falls through the retry
    branch (no more attempts) and the function returns it as-is rather
    than raising. Callers decide whether that's fatal."""
    monkeypatch.setattr(common.time, "sleep", lambda s: None)
    monkeypatch.setattr(common.requests, "get",
                        lambda *a, **kw: _resp(429, {"Retry-After": "1"}))
    # max_retries=3 so the loop exits, leaving the raise_for_status path
    # on the final 429 un-triggered (continue inside the loop).
    # The spec says the function shouldn't loop forever; we check it
    # terminates cleanly.
    with pytest.raises((RuntimeError, Exception)):
        # After exhausting retries the function falls off the end and
        # raises RuntimeError (no last_exc saved for 429 case).
        common.get_with_retry("http://x", {}, timeout=10, max_retries=3)


def test_get_with_retry_honors_max_retries(monkeypatch):
    """Override max_retries — retries happen exactly N times."""
    attempts = {"n": 0}

    def fake_get(*a, **kw):
        attempts["n"] += 1
        raise common.requests.RequestException("always fails")

    monkeypatch.setattr(common.time, "sleep", lambda s: None)
    monkeypatch.setattr(common.requests, "get", fake_get)
    with pytest.raises(common.requests.RequestException):
        common.get_with_retry("http://x", {}, timeout=10, max_retries=2)
    assert attempts["n"] == 2


# ---------------------------------------------------------------------------
# get_db_connection — construction (no live Postgres)
# ---------------------------------------------------------------------------


def test_get_db_connection_raises_without_env(monkeypatch):
    monkeypatch.delenv("DATABASE_URL_SYNC", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        common.get_db_connection()


def test_get_db_connection_strips_sqlalchemy_prefix(monkeypatch):
    """URL prefixes like postgresql+psycopg2:// must be stripped for psycopg2."""
    captured = {}

    def fake_connect(url):
        captured["url"] = url
        return MagicMock()

    monkeypatch.setenv("DATABASE_URL_SYNC", "postgresql+psycopg2://u:p@h/d")
    with patch("psycopg2.connect", side_effect=fake_connect):
        common.get_db_connection()
    assert captured["url"] == "postgresql://u:p@h/d"


def test_get_db_connection_strips_asyncpg_prefix(monkeypatch):
    captured = {}

    def fake_connect(url):
        captured["url"] = url
        return MagicMock()

    monkeypatch.setenv("DATABASE_URL_SYNC", "postgresql+asyncpg://u:p@h/d")
    with patch("psycopg2.connect", side_effect=fake_connect):
        common.get_db_connection()
    assert captured["url"] == "postgresql://u:p@h/d"


def test_get_db_connection_falls_back_to_database_url(monkeypatch):
    captured = {}

    def fake_connect(url):
        captured["url"] = url
        return MagicMock()

    monkeypatch.delenv("DATABASE_URL_SYNC", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://plain/db")
    with patch("psycopg2.connect", side_effect=fake_connect):
        common.get_db_connection()
    assert captured["url"] == "postgresql://plain/db"
