"""
tests/test_load_sam_wave8.py — Wave 8 extract-mode tests.

Focus: the NEW machinery (submit → poll → download, state file, mode
resolution, retry on 429/202). Wave 7 tests for _flatten_v4_record and
_upsert_row remain in tests/test_sam_exclusions.py and are not duplicated.

Tests use responses-style mocking on requests.get. We patch the db
connection to avoid requiring a live postgres.
"""

from __future__ import annotations

import gzip
import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock

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


# parse_retry_after tests moved to tests/test_common.py in Wave 9 when the
# retry helper was extracted to shared.data_ingestion.common.


# ---------------------------------------------------------------------------
# _iter_records: streams from a gzipped SAM v4 extract file
# ---------------------------------------------------------------------------


def _write_extract_gz(tmp_path: Path, payload: dict) -> Path:
    """Serialize *payload* to a gzipped JSON file the way SAM ships it."""
    p = tmp_path / "extract.json.gz"
    with gzip.open(p, "wb") as fh:
        fh.write(json.dumps(payload).encode("utf-8"))
    return p


def test_iter_records_streams_excluded_entity(tmp_path):
    payload = {"totalRecords": 2, "excludedEntity": [{"a": 1}, {"a": 2}]}
    path = _write_extract_gz(tmp_path, payload)
    assert list(loader._iter_records(path)) == [{"a": 1}, {"a": 2}]


def test_iter_records_empty_array(tmp_path):
    payload = {"totalRecords": 0, "excludedEntity": []}
    path = _write_extract_gz(tmp_path, payload)
    assert list(loader._iter_records(path)) == []


def test_iter_records_missing_key_yields_nothing(tmp_path):
    # ijson silently yields nothing when prefix doesn't match — documented
    # in shared.data_ingestion.common.stream_json_array. Callers must
    # assert the count post-consumption, which load() does via records_seen.
    payload = {"foo": "bar"}
    path = _write_extract_gz(tmp_path, payload)
    assert list(loader._iter_records(path)) == []


# State-file read/write/corrupt tests moved to tests/test_common.py
# (StateFile class coverage). The _resolve_since tests below still
# exercise the wrapper path through load_sam._read_state / _write_state.


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
# Polling: real v4 protocol — 400 while generating, 302→S3 → 200 gzip when ready
# ---------------------------------------------------------------------------


def _streaming_response(status: int, body_bytes: bytes = b""):
    """Fake requests.Response with iter_content + close.

    Matches what ``requests.get(..., stream=True, allow_redirects=True)``
    returns after any 302 has been transparently followed.
    """
    r = MagicMock()
    r.status_code = status
    r.headers = {}
    r.iter_content = MagicMock(return_value=iter([body_bytes]) if body_bytes else iter([]))
    r.raise_for_status = MagicMock()
    r.close = MagicMock()
    return r


def test_poll_download_retries_on_400_until_ready(monkeypatch, tmp_path):
    monkeypatch.setattr(loader, "CACHE_DIR", tmp_path)
    real_payload = {"totalRecords": 1, "excludedEntity": [{"entityName": "Acme"}]}
    gz_body = gzip.compress(json.dumps(real_payload).encode("utf-8"))
    responses = [
        _streaming_response(400),
        _streaming_response(400),
        _streaming_response(200, gz_body),
    ]
    calls = iter(responses)

    monkeypatch.setattr(loader.requests, "get", lambda *a, **kw: next(calls))
    monkeypatch.setattr(loader.time, "sleep", lambda s: None)

    path = loader._poll_download("KEY", "TOKEN")
    assert isinstance(path, Path)
    assert path.read_bytes() == gz_body


def test_poll_download_retries_on_202_for_safety(monkeypatch, tmp_path):
    """Older SAM docs claim 202 while generating; keep compat alongside 400."""
    monkeypatch.setattr(loader, "CACHE_DIR", tmp_path)
    gz_body = gzip.compress(b'{"excludedEntity": []}')
    responses = [_streaming_response(202), _streaming_response(200, gz_body)]
    calls = iter(responses)

    monkeypatch.setattr(loader.requests, "get", lambda *a, **kw: next(calls))
    monkeypatch.setattr(loader.time, "sleep", lambda s: None)

    path = loader._poll_download("KEY", "TOKEN")
    assert path.exists()


def test_poll_download_times_out(monkeypatch, tmp_path):
    monkeypatch.setattr(loader, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(loader.requests, "get", lambda *a, **kw: _streaming_response(400))
    monkeypatch.setattr(loader.time, "sleep", lambda s: None)
    monkeypatch.setattr(loader, "POLL_MAX_ATTEMPTS", 3)

    with pytest.raises(TimeoutError, match="not ready after 3 polls"):
        loader._poll_download("KEY", "TOKEN")


def test_poll_download_unexpected_status_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(loader, "CACHE_DIR", tmp_path)
    bad = _streaming_response(500)
    bad.raise_for_status.side_effect = RuntimeError("boom")
    monkeypatch.setattr(loader.requests, "get", lambda *a, **kw: bad)

    with pytest.raises(RuntimeError, match="boom"):
        loader._poll_download("KEY", "TOKEN")


# ---------------------------------------------------------------------------
# End-to-end load: full path with mocked HTTP, verifies max_update tracking
# ---------------------------------------------------------------------------


def test_load_end_to_end_tracks_max_update(monkeypatch, mock_db, tmp_state, tmp_path):
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
    extract_path = _write_extract_gz(tmp_path, payload)

    monkeypatch.setattr(loader, "_submit_extract", lambda k, s: "TOKEN123")
    monkeypatch.setattr(loader, "_poll_download", lambda k, t: extract_path)

    result = loader.load(mode="seed", since=None, api_key="KEY")

    assert result.records_seen == 2
    assert result.records_upserted == 2
    assert result.max_update_date == date(2026, 3, 9)
    assert len(mock_db) == 2


def test_load_continues_past_single_record_flatten_error(monkeypatch, mock_db, tmp_state, tmp_path):
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
    extract_path = _write_extract_gz(tmp_path, payload)
    monkeypatch.setattr(loader, "_submit_extract", lambda k, s: "T")
    monkeypatch.setattr(loader, "_poll_download", lambda k, t: extract_path)

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
