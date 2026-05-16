"""Unit tests for the audit chain verification job (H-07 / HIPAA 2026).

Tests use a mock DB session to avoid requiring a real PostgreSQL connection.
The hash chain logic is verified with known-good and tampered entries.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from sqlalchemy import select as sa_select

from shared.events import event_types as et
from src._shim import db as db_shim
from src._shim import events as event_bus
from src.audit.hash_chain import GENESIS_HASH, compute_entry_hash
from src.jobs.seed import AUDIT_CHAIN_VERIFY_CRON, AUDIT_CHAIN_VERIFY_JOB_TYPE, ensure_audit_chain_job
from src.jobs.verify_audit_chain_job import _verify_tenant_chain, handle_verify_audit_chain
from src.models import Job


_TENANT_ID = str(uuid.UUID("11111111-1111-1111-1111-111111111111"))


def _now():
    return datetime.now(tz=timezone.utc)


def _make_row(
    row_id: int,
    tenant_id: str,
    action: str,
    previous_hash: str,
    entry_hash: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> tuple:
    """Build a fake DB row tuple matching the SELECT column order."""
    return (
        row_id,
        uuid.UUID(tenant_id),
        action,
        entity_type,
        entity_id,
        _now(),
        previous_hash,
        entry_hash,
    )


def _compute_hash(tenant_id: str, action: str, created_at: datetime, previous_hash: str) -> str:
    return compute_entry_hash(
        tenant_id=uuid.UUID(tenant_id),
        action=action,
        entity_type=None,
        entity_id=None,
        created_at=created_at,
        previous_hash=previous_hash,
    )


class TestVerifyTenantChainOk:
    """Valid chain — should report zero failures."""

    def test_empty_chain_reports_zero_entries(self) -> None:
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = []
        result = _verify_tenant_chain(db, tenant_id=_TENANT_ID, stop_on_first=False)
        assert result["entries_checked"] == 0
        assert result["failures"] == []

    def test_single_valid_genesis_entry(self) -> None:
        ts = _now()
        entry_hash = _compute_hash(_TENANT_ID, "login", ts, GENESIS_HASH)
        row = (1, uuid.UUID(_TENANT_ID), "login", None, None, ts, GENESIS_HASH, entry_hash)

        db = MagicMock()
        db.execute.return_value.fetchall.return_value = [row]
        result = _verify_tenant_chain(db, tenant_id=_TENANT_ID, stop_on_first=False)

        assert result["entries_checked"] == 1
        assert result["failures"] == []

    def test_two_valid_entries_chained(self) -> None:
        ts1 = _now()
        ts2 = _now()
        h1 = _compute_hash(_TENANT_ID, "login", ts1, GENESIS_HASH)
        h2 = _compute_hash(_TENANT_ID, "logout", ts2, h1)

        rows = [
            (1, uuid.UUID(_TENANT_ID), "login", None, None, ts1, GENESIS_HASH, h1),
            (2, uuid.UUID(_TENANT_ID), "logout", None, None, ts2, h1, h2),
        ]
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = rows
        result = _verify_tenant_chain(db, tenant_id=_TENANT_ID, stop_on_first=False)

        assert result["entries_checked"] == 2
        assert result["failures"] == []


class TestVerifyTenantChainTamperedEntries:
    """Tampered chain — should report failures without raising."""

    def test_single_tampered_entry_reports_failure(self) -> None:
        ts = _now()
        tampered_hash = "a" * 64  # not the correct SHA-256

        row = (1, uuid.UUID(_TENANT_ID), "login", None, None, ts, GENESIS_HASH, tampered_hash)
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = [row]
        result = _verify_tenant_chain(db, tenant_id=_TENANT_ID, stop_on_first=False)

        assert result["entries_checked"] == 1
        assert len(result["failures"]) == 1
        failure = result["failures"][0]
        assert failure["entry_id"] == 1
        assert failure["tenant_id"] == _TENANT_ID
        assert failure["stored_hash"] == tampered_hash

    def test_tampered_middle_entry_causes_failure_and_cascades(self) -> None:
        """Tampering row 2 breaks row 2 AND row 3 (cascade)."""
        ts1 = _now()
        ts2 = _now()
        ts3 = _now()
        h1 = _compute_hash(_TENANT_ID, "login", ts1, GENESIS_HASH)
        tampered_h2 = "b" * 64
        # Row 3 is built against the correct h2, but since h2 is tampered it will
        # also fail verification.
        h2_real = _compute_hash(_TENANT_ID, "update", ts2, h1)
        h3 = _compute_hash(_TENANT_ID, "logout", ts3, h2_real)

        rows = [
            (1, uuid.UUID(_TENANT_ID), "login", None, None, ts1, GENESIS_HASH, h1),
            (2, uuid.UUID(_TENANT_ID), "update", None, None, ts2, h1, tampered_h2),
            (3, uuid.UUID(_TENANT_ID), "logout", None, None, ts3, tampered_h2, h3),
        ]
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = rows
        result = _verify_tenant_chain(db, tenant_id=_TENANT_ID, stop_on_first=False)

        assert result["entries_checked"] == 3
        # Rows 2 and 3 should both fail (cascade from tampering row 2)
        assert len(result["failures"]) == 2
        assert result["failures"][0]["entry_id"] == 2
        assert result["failures"][1]["entry_id"] == 3

    def test_tampered_previous_hash_detected_even_if_entry_hash_recomputed(self) -> None:
        """Attack: attacker rewrites previous_hash AND recomputes a valid entry_hash.

        Without the prev_hash continuity check this row would pass — the
        recomputed entry_hash matches the stored entry_hash. The check that
        stored_prev_hash == tracked prev_hash catches it.
        """
        ts1 = _now()
        ts2 = _now()
        h1 = _compute_hash(_TENANT_ID, "login", ts1, GENESIS_HASH)
        # Attacker sets row 2's previous_hash to a different value ("evil") and
        # recomputes a valid entry_hash against that fake previous_hash.
        evil_prev = "e" * 64
        evil_h2 = _compute_hash(_TENANT_ID, "logout", ts2, evil_prev)

        rows = [
            (1, uuid.UUID(_TENANT_ID), "login", None, None, ts1, GENESIS_HASH, h1),
            # Row 2: entry_hash is self-consistent with evil_prev but breaks chain
            (2, uuid.UUID(_TENANT_ID), "logout", None, None, ts2, evil_prev, evil_h2),
        ]
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = rows
        result = _verify_tenant_chain(db, tenant_id=_TENANT_ID, stop_on_first=False)

        assert result["entries_checked"] == 2
        # Row 1 valid; row 2 caught by prev_hash continuity check
        assert len(result["failures"]) == 1
        assert result["failures"][0]["entry_id"] == 2

    def test_stop_on_first_failure_stops_early(self) -> None:
        ts1 = _now()
        ts2 = _now()
        tampered_h1 = "c" * 64
        h2 = "d" * 64

        rows = [
            (1, uuid.UUID(_TENANT_ID), "login", None, None, ts1, GENESIS_HASH, tampered_h1),
            (2, uuid.UUID(_TENANT_ID), "logout", None, None, ts2, tampered_h1, h2),
        ]
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = rows
        result = _verify_tenant_chain(db, tenant_id=_TENANT_ID, stop_on_first=True)

        # Only 1 failure reported — stopped after first broken link
        assert result["entries_checked"] == 1
        assert len(result["failures"]) == 1
        assert result["failures"][0]["entry_id"] == 1


class TestJobHandlerRegistered:
    """Verify the job handler is registered under the expected type."""

    def test_handler_registered(self) -> None:
        from src.jobs.registry import default_registry
        # Importing the module registers the handler via @job_handler decorator.
        import src.jobs.verify_audit_chain_job  # noqa: F401

        handler = default_registry.get("audit.verify_chain")
        assert callable(handler)


# ---------------------------------------------------------------------------
# Event emission tests (H-07 requirement)
# ---------------------------------------------------------------------------

@pytest.fixture()
def _clear_events():
    """Reset the shim event bus before and after every test.

    The conftest's _fresh_db autouse fixture also calls reset_events() at the
    start of each test, so this fixture is only needed in tests that explicitly
    request it for additional clarity/documentation.
    """
    event_bus.reset_events()
    yield
    event_bus.reset_events()


def _make_db_session_mock(tenant_ids: list[str], rows_per_tenant: dict[str, list]) -> MagicMock:
    """Build a mock DB session that returns tenant IDs then per-tenant rows."""
    db = MagicMock()

    def _side_effect(stmt, params=None):
        result = MagicMock()
        # The handler first queries DISTINCT tenant_ids (no params),
        # then queries per-tenant rows (params has tenant_id).
        if params is not None and "tenant_id" in params:
            tid = params["tenant_id"]
            result.fetchall.return_value = rows_per_tenant.get(tid, [])
        else:
            result.fetchall.return_value = [(t,) for t in tenant_ids]
        return result

    db.execute.side_effect = _side_effect
    return db


def _patch_sessionmaker(tenant_ids: list[str], rows_per_tenant: dict[str, list]):
    """Context manager that patches db_shim.get_sessionmaker to return a mock session.

    The handler calls:
        SessionLocal = db_shim.get_sessionmaker()   # returns the factory callable
        with SessionLocal() as db:                   # calls factory(), gets ctx mgr
    So we must: mock_get_sessionmaker.return_value.return_value = context_manager
    """
    db_session = _make_db_session_mock(tenant_ids, rows_per_tenant)

    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db_session)
    ctx.__exit__ = MagicMock(return_value=False)

    p = patch("src.jobs.verify_audit_chain_job.db_shim.get_sessionmaker")
    mock_get_sessionmaker = p.start()
    # get_sessionmaker() returns the SessionLocal factory; SessionLocal() returns ctx
    mock_get_sessionmaker.return_value.return_value = ctx
    return p, mock_get_sessionmaker


class TestHandlerEventEmission:
    """Handler emits correct events via the shim event bus."""

    async def test_clean_chain_emits_audit_chain_verified(self) -> None:
        ts = _now()
        h1 = _compute_hash(_TENANT_ID, "login", ts, GENESIS_HASH)
        rows = {
            _TENANT_ID: [(1, uuid.UUID(_TENANT_ID), "login", None, None, ts, GENESIS_HASH, h1)]
        }

        p, _ = _patch_sessionmaker([_TENANT_ID], rows)
        try:
            result = await handle_verify_audit_chain({})
        finally:
            p.stop()

        assert result["status"] == "ok"
        assert result["tenants_checked"] == 1
        assert result["failures"] == []

        events = event_bus.published_events()
        verified_events = [e for e in events if e.topic == et.AUDIT_CHAIN_VERIFIED]
        broken_events = [e for e in events if e.topic == et.AUDIT_CHAIN_BROKEN]
        assert len(verified_events) == 1
        assert len(broken_events) == 0
        assert verified_events[0].payload["tenants_checked"] == 1
        assert verified_events[0].payload["entries_checked"] == 1
        assert "duration_ms" in verified_events[0].payload

    async def test_broken_chain_emits_audit_chain_broken_critical(self) -> None:
        ts = _now()
        tampered_hash = "a" * 64

        rows = {
            _TENANT_ID: [(1, uuid.UUID(_TENANT_ID), "login", None, None, ts, GENESIS_HASH, tampered_hash)]
        }

        p, _ = _patch_sessionmaker([_TENANT_ID], rows)
        try:
            result = await handle_verify_audit_chain({})
        finally:
            p.stop()

        assert result["status"] == "failed"
        assert len(result["failures"]) == 1

        events = event_bus.published_events()
        broken_events = [e for e in events if e.topic == et.AUDIT_CHAIN_BROKEN]
        verified_events = [e for e in events if e.topic == et.AUDIT_CHAIN_VERIFIED]
        assert len(broken_events) == 1
        assert len(verified_events) == 0

        payload = broken_events[0].payload
        assert payload["tenant_id"] == _TENANT_ID
        assert payload["entry_id"] == 1
        assert payload["stored_hash"] == tampered_hash
        # Verify no audit entry CONTENT is leaked — only entry_id and hash fields
        assert "action" not in payload   # audit action is audit content — excluded
        assert "severity" not in payload  # severity implied by event type
        assert "message" not in payload
        assert "entity_name" not in payload
        assert "member" not in payload

    async def test_multiple_broken_entries_emit_one_event_each(self) -> None:
        ts1 = _now()
        ts2 = _now()
        tampered_h1 = "b" * 64
        tampered_h2 = "c" * 64

        rows = {
            _TENANT_ID: [
                (1, uuid.UUID(_TENANT_ID), "login", None, None, ts1, GENESIS_HASH, tampered_h1),
                (2, uuid.UUID(_TENANT_ID), "logout", None, None, ts2, tampered_h1, tampered_h2),
            ]
        }

        p, _ = _patch_sessionmaker([_TENANT_ID], rows)
        try:
            result = await handle_verify_audit_chain({})
        finally:
            p.stop()

        assert result["status"] == "failed"
        broken_events = [e for e in event_bus.published_events() if e.topic == et.AUDIT_CHAIN_BROKEN]
        assert len(broken_events) == 2

    async def test_tenant_scoped_call_only_checks_that_tenant(self) -> None:
        other_id = str(uuid.UUID("22222222-2222-2222-2222-222222222222"))
        ts = _now()
        h1 = _compute_hash(_TENANT_ID, "login", ts, GENESIS_HASH)

        rows = {
            _TENANT_ID: [(1, uuid.UUID(_TENANT_ID), "login", None, None, ts, GENESIS_HASH, h1)],
            other_id: [],
        }

        p, _ = _patch_sessionmaker([_TENANT_ID, other_id], rows)
        try:
            result = await handle_verify_audit_chain({"tenant_id": _TENANT_ID})
        finally:
            p.stop()

        # Only one tenant was checked (the scoped one; no DB call for DISTINCT made)
        assert result["tenants_checked"] == 1
        events = event_bus.published_events()
        verified = [e for e in events if e.topic == et.AUDIT_CHAIN_VERIFIED]
        assert len(verified) == 1

    async def test_result_includes_duration_ms(self) -> None:
        p, _ = _patch_sessionmaker([], {})
        try:
            result = await handle_verify_audit_chain({})
        finally:
            p.stop()

        assert "duration_ms" in result
        assert isinstance(result["duration_ms"], int)
        assert result["duration_ms"] >= 0


# ---------------------------------------------------------------------------
# Seed function tests (H-07 — Job row seeding)
# ---------------------------------------------------------------------------

class TestEnsureAuditChainJob:
    """ensure_audit_chain_job() is idempotent and creates the correct Job row."""

    def test_creates_job_row_when_absent(self) -> None:
        # conftest _fresh_db creates tables; DB is empty at test start
        SessionLocal = db_shim.get_sessionmaker()
        with SessionLocal() as session:
            existing = session.execute(
                sa_select(Job).where(Job.job_type == AUDIT_CHAIN_VERIFY_JOB_TYPE)
            ).scalar_one_or_none()
            assert existing is None

            created = ensure_audit_chain_job(session)

        assert created is True

        with SessionLocal() as session:
            job = session.execute(
                sa_select(Job).where(Job.job_type == AUDIT_CHAIN_VERIFY_JOB_TYPE)
            ).scalar_one()
            assert job.schedule == AUDIT_CHAIN_VERIFY_CRON
            assert job.status == "active"
            assert job.tenant_id is None  # platform-wide
            assert job.next_run_at is not None

    def test_idempotent_when_row_already_exists(self) -> None:
        SessionLocal = db_shim.get_sessionmaker()
        # Seed the row first
        with SessionLocal() as session:
            ensure_audit_chain_job(session)

        # Second call must return False (no new row)
        with SessionLocal() as session:
            created_again = ensure_audit_chain_job(session)

        assert created_again is False

        # Verify only one row exists
        with SessionLocal() as session:
            rows = session.execute(
                sa_select(Job).where(Job.job_type == AUDIT_CHAIN_VERIFY_JOB_TYPE)
            ).scalars().all()
            assert len(rows) == 1
