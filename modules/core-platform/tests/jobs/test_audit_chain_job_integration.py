"""Integration tests for the H-07 daily audit chain verification job.

These tests exercise the full path:
  seed → Job row in DB → JobScheduler.tick_once() → handle_verify_audit_chain
  → events emitted → JobRun row recorded.

Uses the shim's in-memory SQLite DB (no Postgres required).
The verify_audit_chain_job handler accesses ``core_platform.audit_log`` via raw
SQL; in SQLite there are no schemas, so the SQL is intercepted via monkeypatching
to supply synthetic audit data.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from shared.events import event_types as et
from src._shim import db as db_shim
from src._shim import events as event_bus
from src.jobs.registry import default_registry
from src.jobs.scheduler import JobScheduler
from src.jobs.seed import ensure_audit_chain_job, AUDIT_CHAIN_VERIFY_JOB_TYPE
from src.models import Job, JobRun


# Note: _fresh_db autouse fixture is provided by tests/conftest.py — it sets up
# a fresh SQLite DB, calls create_all(), resets events, and tears down after each test.
# We do not redefine it here.

@pytest.fixture()
def session_factory():
    return db_shim.get_sessionmaker()


@pytest.fixture()
def audit_chain_job_row(session_factory):
    """Seed the audit.verify_chain Job row and return its id."""
    with session_factory() as session:
        ensure_audit_chain_job(session)

    with session_factory() as session:
        from sqlalchemy import select
        job = session.execute(
            select(Job).where(Job.job_type == AUDIT_CHAIN_VERIFY_JOB_TYPE)
        ).scalar_one()
        return job.id


def _make_db_session(tenant_ids: list[str], rows_per_tenant: dict) -> MagicMock:
    """Build a mock DB session for the handler's audit_log queries."""
    db = MagicMock()

    def _execute(stmt, params=None):
        result = MagicMock()
        if params is not None and "tenant_id" in params:
            tid = params["tenant_id"]
            result.fetchall.return_value = rows_per_tenant.get(tid, [])
        else:
            result.fetchall.return_value = [(t,) for t in tenant_ids]
        return result

    db.execute.side_effect = _execute
    return db


def _mock_sessionmaker(tenant_ids: list[str], rows_per_tenant: dict) -> MagicMock:
    """Return a mock sessionmaker suitable for patching db_shim.get_sessionmaker.

    The handler does:
        SessionLocal = db_shim.get_sessionmaker()   # → mock_sm
        with SessionLocal() as db:                   # → mock_sm() → ctx_mgr
    """
    db_session = _make_db_session(tenant_ids, rows_per_tenant)
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db_session)
    ctx.__exit__ = MagicMock(return_value=False)

    session_factory = MagicMock()
    session_factory.return_value = ctx
    return session_factory


class TestAuditChainJobIntegration:
    """Full scheduler → handler → event path with seeded Job row."""

    async def test_scheduler_dispatches_due_audit_chain_job_clean(
        self, session_factory, audit_chain_job_row
    ) -> None:
        """Scheduler dispatches the job; clean chain produces audit.chain_verified."""
        # Back-date next_run_at so the scheduler considers the job due
        with session_factory() as session:
            job = session.get(Job, audit_chain_job_row)
            job.next_run_at = datetime.now(timezone.utc) - timedelta(seconds=5)
            session.commit()

        with patch("src.jobs.verify_audit_chain_job.db_shim.get_sessionmaker") as mock_get_db:
            # No tenants with audit entries → clean run
            mock_get_db.return_value = _mock_sessionmaker([], {})

            scheduler = JobScheduler(session_factory, default_registry, tick_seconds=0.01)
            dispatched = await scheduler.tick_once()

        assert dispatched >= 1  # at least the audit chain job was dispatched

        # Verify JobRun was recorded
        with session_factory() as session:
            from sqlalchemy import select
            run = session.execute(
                select(JobRun).where(JobRun.job_id == audit_chain_job_row)
            ).scalar_one_or_none()
            assert run is not None
            assert run.status == "succeeded"

        # Verify event emitted
        verified_events = [e for e in event_bus.published_events() if e.topic == et.AUDIT_CHAIN_VERIFIED]
        assert len(verified_events) == 1

    async def test_scheduler_dispatches_due_audit_chain_job_broken(
        self, session_factory, audit_chain_job_row
    ) -> None:
        """Scheduler dispatches the job; broken chain produces audit.chain_broken CRITICAL."""
        tenant_id = str(uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
        ts = datetime.now(timezone.utc)
        tampered_hash = "f" * 64

        rows = {
            tenant_id: [(42, uuid.UUID(tenant_id), "login", None, None, ts, "0" * 64, tampered_hash)]
        }

        with session_factory() as session:
            job = session.get(Job, audit_chain_job_row)
            job.next_run_at = datetime.now(timezone.utc) - timedelta(seconds=5)
            session.commit()

        with patch("src.jobs.verify_audit_chain_job.db_shim.get_sessionmaker") as mock_get_db:
            mock_get_db.return_value = _mock_sessionmaker([tenant_id], rows)

            scheduler = JobScheduler(session_factory, default_registry, tick_seconds=0.01)
            await scheduler.tick_once()

        # Job run should be recorded as succeeded (handler itself succeeded; it
        # returned a dict — the integrity violation is in the payload, not an exception)
        with session_factory() as session:
            from sqlalchemy import select
            run = session.execute(
                select(JobRun).where(JobRun.job_id == audit_chain_job_row)
            ).scalar_one_or_none()
            assert run is not None
            assert run.status == "succeeded"
            assert run.result["status"] == "failed"  # handler result shows failure

        # Verify CRITICAL event emitted with hash metadata only (no audit content)
        broken_events = [e for e in event_bus.published_events() if e.topic == et.AUDIT_CHAIN_BROKEN]
        assert len(broken_events) == 1
        assert broken_events[0].payload["tenant_id"] == tenant_id
        assert broken_events[0].payload["entry_id"] == 42
        # Severity implied by event type — not in payload
        assert "severity" not in broken_events[0].payload
        # Action/entity content excluded from payload (PHI-adjacent)
        assert "action" not in broken_events[0].payload
        assert "message" not in broken_events[0].payload
        assert "entity_name" not in broken_events[0].payload

    async def test_seed_is_idempotent_across_restarts(self, session_factory) -> None:
        """Calling ensure_audit_chain_job twice creates exactly one Job row."""
        with session_factory() as session:
            r1 = ensure_audit_chain_job(session)
        with session_factory() as session:
            r2 = ensure_audit_chain_job(session)

        assert r1 is True
        assert r2 is False

        with session_factory() as session:
            from sqlalchemy import select
            rows = session.execute(
                select(Job).where(Job.job_type == AUDIT_CHAIN_VERIFY_JOB_TYPE)
            ).scalars().all()
            assert len(rows) == 1

    async def test_handler_registered_under_audit_verify_chain(self) -> None:
        """The @job_handler decorator registers under the expected key."""
        # Importing api.py triggers the side-effect import of verify_audit_chain_job
        import src.api  # noqa: F401
        handler = default_registry.get(AUDIT_CHAIN_VERIFY_JOB_TYPE)
        assert callable(handler)
