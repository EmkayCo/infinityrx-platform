"""
tests/test_load_sam_wave8.py — Wave 8 extract-mode tests.

Focus: the NEW machinery (submit → poll → download, state file, mode
resolution, retry on 429/202). Wave 7 tests for _flatten_v4_record and
_upsert_row remain in tests/test_sam_exclusions.py and are not duplicated.

Tests use responses-style mocking on requests.get. We patch the db
connection to avoid requiring a live postgres.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import scripts.load_sam as loader


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_state(tmp_path, monkeypatch):
    """Redirect state file to a tmp path so tests don't clobber real state."""
    cache_dir = tmp_path / "sam_exclusions"
    state_file = cache_dir / ".last_run"
    monkeypatch.setattr(loader, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(loader, "STATE_FILE", state_file)
    return state_file


@pytest.fixture
def mock_db(monkeypatch):
    """Stub out get_db_connection + _upsert_row. Tracks upsert calls."""
    upserts: list[dict] = []

    class FakeCursor:
        def __init__(self): self._row = None
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, q, *args): self._row = self._preset
        def fetchone(self): return self._row
        _preset = None

    class FakeConn:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def cursor(self): return FakeCursor()
        def commit(self): pass

    def fake_get_conn():
        return FakeConn()

    def fake_upsert(conn, flat):
        upserts.append(flat)

    monkeypatch.setattr(loader, "get_db_connection", fake_get_conn)
    monkeypatch.setattr(loader, "_upsert_row", fake_upsert)
    return upserts


def _response(status: int, body=None, headers=None):
    """Build a fake requests.Response."""
    r = MagicMock()
    r.status_code = status
    r.headers = headers or {}
    if body is not None:
        r.json.return_value = body
        r.content = json.dumps(body).encode()
    else:
        r.json.side_effect = json.JSONDecodeError("x", "", 0)
        r.content = b""
    r.raise_for_status = MagicMock()
    return r


# ---------------------------------------------------------------------------
# _extract_token: handles both documented response shapes
# ---------------------------------------------------------------------------


def test_extract_token_from_direct_field():
    assert loader._extract_token({"token": "ABC123"}) == "ABC123"


def test_extract_token_from_url_string():
    body = {
        "message": (
            "Extract File will be available for download with url: "
            "https://api.sam.gov/entity-information/v4/download-exclusions"
            "?api_key=REPLACE_WITH_API_KEY&token=XYZ789 in some time."
        )
    }
    assert loader._extract_token(body) == "XYZ789"


def test_extract_token_missing_returns_none():
    assert loader._extract_token({"foo": "bar"}) is None


# ---------------------------------------------------------------------------
# _parse_retry_after: both formats per RFC 7231
# ---------------------------------------------------------------------------


def test_retry_after_seconds_integer():
    assert loader._parse_retry_after("120") == 120


def test_retry_after_http_date(monkeypatch):
    # Freeze utcnow at 2026-04-16 00:00:00.
    class FrozenDT(datetime):
        @classmethod
        def utcnow(cls):
            return datetime(2026, 4, 16, 0, 0, 0)
    monkeypatch.setattr(loader, "datetime", FrozenDT)
    result = loader._parse_retry_after("Fri, 17 Apr 2026 00:00:00 GMT")
    assert result == 86400  # 24h


def test_retry_after_empty_returns_none():
    assert loader._parse_retry_after("") is None


# ---------------------------------------------------------------------------
# _is_not_ready: distinguish real payloads from "still generating" envelopes
# ---------------------------------------------------------------------------


def test_not_ready_detects_generation_message():
    assert loader._is_not_ready({"message": "File is not generated yet. Please try again later."})


def test_not_ready_rejects_real_payload():
    assert not loader._is_not_ready({"totalRecords": 167240, "excludedEntity": []})


# ---------------------------------------------------------------------------
# _iter_records: handles both extract shapes
# ---------------------------------------------------------------------------


def test_iter_records_direct_shape():
    payload = {"excludedEntity": [{"a": 1}, {"a": 2}]}
    assert list(loader._iter_records(payload)) == [{"a": 1}, {"a": 2}]


def test_iter_records_nested_results_shape():
    payload = {"results": [{"excludedEntity": [{"a": 1}]}, {"excludedEntity": [{"a": 2}]}]}
    assert list(loader._iter_records(payload)) == [{"a": 1}, {"a": 2}]


def test_iter_records_unknown_shape_raises():
    with pytest.raises(RuntimeError, match="no excludedEntity key"):
        list(loader._iter_records({"foo": "bar"}))


# ---------------------------------------------------------------------------
# State file: read/write roundtrip, graceful missing-file handling
# ---------------------------------------------------------------------------


def test_state_roundtrip(tmp_state):
    assert loader._read_state() is None  # absent
    loader._write_state(date(2026, 4, 15))
    assert loader._read_state() == date(2026, 4, 15)


def test_state_corrupt_file_returns_none(tmp_state):
    tmp_state.parent.mkdir(parents=True, exist_ok=True)
    tmp_state.write_text("not-a-date")
    assert loader._read_state() is None


# ---------------------------------------------------------------------------
# Mode resolution
# ---------------------------------------------------------------------------


def test_resolve_mode_explicit_wins(mock_db):
    assert loader._resolve_mode("seed") == "seed"
    assert loader._resolve_mode("delta") == "delta"
    assert loader._resolve_mode("backfill") == "backfill"


def test_resolve_mode_auto_empty_table_picks_seed(monkeypatch):
    monkeypatch.setattr(loader, "_table_is_empty", lambda: True)
    assert loader._resolve_mode(None) == "seed"


def test_resolve_mode_auto_populated_table_picks_delta(monkeypatch):
    monkeypatch.setattr(loader, "_table_is_empty", lambda: False)
    assert loader._resolve_mode(None) == "delta"


def test_resolve_since_seed_is_none():
    assert loader._resolve_since("seed", None) is None
    # Even if --since was passed, seed ignores it (full load is unconditional).
    assert loader._resolve_since("seed", date(2026, 1, 1)) is None


def test_resolve_since_backfill_requires_explicit_since():
    with pytest.raises(SystemExit, match="backfill requires --since"):
        loader._resolve_since("backfill", None)


def test_resolve_since_delta_without_state_errors(tmp_state):
    # State file absent → delta can't run.
    with pytest.raises(SystemExit, match="no state file"):
        loader._resolve_since("delta", None)


def test_resolve_since_delta_uses_state_minus_one_day(tmp_state):
    loader._write_state(date(2026, 4, 15))
    # One-day backoff absorbs late-arriving same-day updates.
    assert loader._resolve_since("delta", None) == date(2026, 4, 14)


def test_resolve_since_delta_cli_override_wins(tmp_state):
    loader._write_state(date(2026, 4, 15))
    assert loader._resolve_since("delta", date(2026, 1, 1)) == date(2026, 1, 1)


# ---------------------------------------------------------------------------
# Polling: retries on 202 and on 200-envelope "still generating"
# ---------------------------------------------------------------------------


def test_poll_download_retries_on_202(monkeypatch):
    real_payload = {"totalRecords": 1, "excludedEntity": [{"entityName": "Acme"}]}
    responses = [
        _response(202),
        _response(202),
        _response(200, real_payload),
    ]
    call_count = {"n": 0}

    def fake_get(url, params, timeout, accept_202=False):
        r = responses[call_count["n"]]
        call_count["n"] += 1
        return r

    monkeypatch.setattr(loader, "_get_with_retry", fake_get)
    monkeypatch.setattr(loader.time, "sleep", lambda s: None)

    result = loader._poll_download("KEY", "TOKEN")
    assert result == real_payload
    assert call_count["n"] == 3


def test_poll_download_retries_on_200_not_ready_envelope(monkeypatch):
    not_ready = {"message": "File is not generated yet. Please try again later."}
    real = {"totalRecords": 0, "excludedEntity": []}
    responses = [_response(200, not_ready), _response(200, real)]
    calls = iter(responses)

    monkeypatch.setattr(
        loader, "_get_with_retry",
        lambda *a, **kw: next(calls),
    )
    monkeypatch.setattr(loader.time, "sleep", lambda s: None)

    assert loader._poll_download("KEY", "TOKEN") == real


def test_poll_download_times_out(monkeypatch):
    # Always 202 → should eventually raise TimeoutError.
    monkeypatch.setattr(loader, "_get_with_retry", lambda *a, **kw: _response(202))
    monkeypatch.setattr(loader.time, "sleep", lambda s: None)
    monkeypatch.setattr(loader, "POLL_MAX_ATTEMPTS", 3)

    with pytest.raises(TimeoutError, match="not ready after 3 polls"):
        loader._poll_download("KEY", "TOKEN")


# ---------------------------------------------------------------------------
# End-to-end load: full path with mocked HTTP, verifies max_update tracking
# ---------------------------------------------------------------------------


def test_load_end_to_end_tracks_max_update(monkeypatch, mock_db, tmp_state):
    # Two records: older and newer. max_update should be the newer one.
    payload = {
        "totalRecords": 2,
        "excludedEntity": [
            {
                "exclusionDetails": {"classificationType": "Individual",
                                      "exclusionType": "Ineligible (Proceedings Completed)",
                                      "exclusionProgram": "Reciprocal",
                                      "excludingAgencyCode": "HHS",
                                      "excludingAgencyName": "DEPT OF HEALTH"},
                "exclusionIdentification": {"entityName": "Old Record"},
                "exclusionActions": {"listOfActions": [{"updateDate": "01-15-2025",
                                                          "activateDate": "01-15-2025",
                                                          "recordStatus": "Active"}]},
                "exclusionPrimaryAddress": {"countryCode": "USA"},
                "exclusionOtherInformation": {"isFASCSAOrder": "No"},
            },
            {
                "exclusionDetails": {"classificationType": "Firm",
                                      "exclusionType": "Prohibition/Restriction",
                                      "exclusionProgram": "Procurement",
                                      "excludingAgencyCode": "DOD",
                                      "excludingAgencyName": "DEPT OF DEFENSE"},
                "exclusionIdentification": {"entityName": "New Record"},
                "exclusionActions": {"listOfActions": [{"updateDate": "03-09-2026",
                                                          "activateDate": "03-09-2026",
                                                          "recordStatus": "Active"}]},
                "exclusionPrimaryAddress": {"countryCode": "USA"},
                "exclusionOtherInformation": {"isFASCSAOrder": "No"},
            },
        ],
    }

    monkeypatch.setattr(loader, "_submit_extract", lambda k, s: "TOKEN123")
    monkeypatch.setattr(loader, "_poll_download", lambda k, t: payload)

    result = loader.load(mode="seed", since=None, api_key="KEY")

    assert result.records_seen == 2
    assert result.records_upserted == 2
    assert result.max_update_date == date(2026, 3, 9)
    assert len(mock_db) == 2


def test_load_continues_past_single_record_flatten_error(monkeypatch, mock_db, tmp_state):
    """One bad record shouldn't abort the whole load."""
    payload = {
        "excludedEntity": [
            {"garbage": "data"},  # will fail _flatten_v4_record
            {
                "exclusionDetails": {"classificationType": "Individual",
                                      "exclusionType": "Ineligible (Proceedings Completed)",
                                      "exclusionProgram": "Reciprocal",
                                      "excludingAgencyCode": "HHS",
                                      "excludingAgencyName": "DEPT OF HEALTH"},
                "exclusionIdentification": {"entityName": "Good Record"},
                "exclusionActions": {"listOfActions": [{"updateDate": "03-09-2026",
                                                          "activateDate": "03-09-2026",
                                                          "recordStatus": "Active"}]},
                "exclusionPrimaryAddress": {"countryCode": "USA"},
                "exclusionOtherInformation": {"isFASCSAOrder": "No"},
            },
        ],
    }
    monkeypatch.setattr(loader, "_submit_extract", lambda k, s: "T")
    monkeypatch.setattr(loader, "_poll_download", lambda k, t: payload)

    result = loader.load(mode="seed", since=None, api_key="KEY")
    assert result.records_seen == 2
    assert result.records_upserted == 1  # only the good one


# ---------------------------------------------------------------------------
# Submit: since=None → no updateDate param; since=date → MM/DD/YYYY range
# ---------------------------------------------------------------------------


def test_submit_extract_no_since_omits_updateDate(monkeypatch):
    captured: dict = {}

    def fake_get(url, params, timeout, accept_202=False):
        captured.update(params)
        return _response(200, {"token": "ABC"})

    monkeypatch.setattr(loader, "_get_with_retry", fake_get)
    loader._submit_extract("KEY", None)
    assert "updateDate" not in captured
    assert captured["format"] == "JSON"


def test_submit_extract_with_since_formats_range(monkeypatch):
    captured: dict = {}

    def fake_get(url, params, timeout, accept_202=False):
        captured.update(params)
        return _response(200, {"token": "ABC"})

    monkeypatch.setattr(loader, "_get_with_retry", fake_get)

    class FrozenDT(datetime):
        @classmethod
        def utcnow(cls):
            return datetime(2026, 4, 16, 12, 0, 0)
    monkeypatch.setattr(loader, "datetime", FrozenDT)

    loader._submit_extract("KEY", date(2026, 4, 10))
    assert captured["updateDate"] == "[04/10/2026,04/16/2026]"
