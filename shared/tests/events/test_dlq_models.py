"""Tests for EventDLQEntry and ProcessedEvent ORM models and migration."""

from __future__ import annotations

import importlib.util
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.db.models.events import EventDLQEntry, ProcessedEvent


def _load_migration():
    """Load the 0003 migration module by file path (bypasses dash in folder name)."""
    # shared/tests/events/ → parents[3] is the worktree root
    versions_dir = (
        Path(__file__).resolve().parents[3]
        / "modules"
        / "core-platform"
        / "alembic"
        / "versions"
    )
    migration_path = versions_dir / "0003_event_bus_reliability.py"
    spec = importlib.util.spec_from_file_location("migration_0003", migration_path)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


# ---------------------------------------------------------------------------
# ORM round-trip tests
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_session(pg_engine):
    """Create event tables and return a test session; drop on teardown."""
    from shared.db.base import Base
    from shared.db.models import events as _events_module  # noqa: F401 — register models

    async with pg_engine.begin() as conn:
        await conn.execute(sa.text("CREATE SCHEMA IF NOT EXISTS core"))
    async with pg_engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[EventDLQEntry.__table__, ProcessedEvent.__table__],
        )

    session_factory = async_sessionmaker(pg_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with pg_engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.drop_all,
            tables=[ProcessedEvent.__table__, EventDLQEntry.__table__],
        )


@pytest.mark.postgres
async def test_event_dlq_entry_round_trip(db_session: AsyncSession):
    """Insert and retrieve an EventDLQEntry, verifying all fields persist."""
    entry_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    event_id = uuid.uuid4()
    now = datetime.now(UTC)

    entry = EventDLQEntry(
        id=entry_id,
        event_id=event_id,
        tenant_id=tenant_id,
        event_type="payment.generated",
        envelope={"event_type": "payment.generated", "payload": {}},
        failure_reason="downstream timeout",
        attempt_count=3,
        first_failed_at=now,
        last_failed_at=now,
        dlq_topic="payment.generated",
        status="queued",
    )
    db_session.add(entry)
    await db_session.flush()

    result = await db_session.get(EventDLQEntry, entry_id)
    assert result is not None
    assert result.event_id == event_id
    assert result.tenant_id == tenant_id
    assert result.event_type == "payment.generated"
    assert result.failure_reason == "downstream timeout"
    assert result.attempt_count == 3
    assert result.dlq_topic == "payment.generated"
    assert result.status == "queued"
    assert result.replayed_at is None


@pytest.mark.postgres
async def test_event_dlq_entry_replayed_at_nullable(db_session: AsyncSession):
    """replayed_at should be nullable."""
    entry = EventDLQEntry(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        event_type="batch.created",
        envelope={},
        failure_reason="test",
        attempt_count=1,
        first_failed_at=datetime.now(UTC),
        last_failed_at=datetime.now(UTC),
        dlq_topic="batch.created",
        status="dropped",
        replayed_at=None,
    )
    db_session.add(entry)
    await db_session.flush()
    result = await db_session.get(EventDLQEntry, entry.id)
    assert result is not None
    assert result.replayed_at is None


@pytest.mark.postgres
async def test_processed_event_round_trip(db_session: AsyncSession):
    """Insert and retrieve a ProcessedEvent."""
    pe = ProcessedEvent(
        idempotency_key="payment_batch:abc-123",
        consumer_name="billing-service",
    )
    db_session.add(pe)
    await db_session.flush()

    result = await db_session.get(
        ProcessedEvent,
        {"idempotency_key": "payment_batch:abc-123", "consumer_name": "billing-service"},
    )
    assert result is not None
    assert result.idempotency_key == "payment_batch:abc-123"
    assert result.consumer_name == "billing-service"
    assert result.processed_at is not None


@pytest.mark.postgres
async def test_processed_event_composite_pk_allows_same_key_different_consumer(
    db_session: AsyncSession,
):
    """Same idempotency_key + different consumer_name must not conflict."""
    pe_a = ProcessedEvent(idempotency_key="shared-key", consumer_name="consumer-A")
    pe_b = ProcessedEvent(idempotency_key="shared-key", consumer_name="consumer-B")
    db_session.add(pe_a)
    db_session.add(pe_b)
    await db_session.flush()

    result_a = await db_session.get(
        ProcessedEvent, {"idempotency_key": "shared-key", "consumer_name": "consumer-A"}
    )
    result_b = await db_session.get(
        ProcessedEvent, {"idempotency_key": "shared-key", "consumer_name": "consumer-B"}
    )
    assert result_a is not None
    assert result_b is not None


@pytest.mark.postgres
async def test_event_dlq_entry_envelope_is_jsonb(db_session: AsyncSession):
    """Envelope stored as JSONB should support nested dict retrieval."""
    payload = {"event_id": str(uuid.uuid4()), "payload": {"amount": "99.99"}}
    entry = EventDLQEntry(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        event_type="invoice.generated",
        envelope=payload,
        failure_reason="schema error",
        attempt_count=1,
        first_failed_at=datetime.now(UTC),
        last_failed_at=datetime.now(UTC),
        dlq_topic="invoice.generated",
        status="queued",
    )
    db_session.add(entry)
    await db_session.flush()
    await db_session.refresh(entry)
    assert entry.envelope["payload"]["amount"] == "99.99"


# ---------------------------------------------------------------------------
# Migration tests
# ---------------------------------------------------------------------------


@pytest.mark.postgres
async def test_migration_upgrade_creates_tables(pg_engine):
    """Running upgrade() creates event_dlq and processed_events tables."""
    migration = _load_migration()

    async with pg_engine.begin() as conn:
        await conn.execute(sa.text("CREATE SCHEMA IF NOT EXISTS core"))
        await conn.run_sync(migration.upgrade)

    async with pg_engine.connect() as conn:
        result = await conn.execute(
            sa.text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'core' AND table_name IN ('event_dlq','processed_events') "
                "ORDER BY table_name"
            )
        )
        tables = [row[0] for row in result.fetchall()]

    assert "event_dlq" in tables, f"event_dlq not found, got: {tables}"
    assert "processed_events" in tables, f"processed_events not found, got: {tables}"

    # Cleanup
    async with pg_engine.begin() as conn:
        await conn.run_sync(migration.downgrade)


@pytest.mark.postgres
async def test_migration_downgrade_drops_tables(pg_engine):
    """downgrade() removes both tables."""
    migration = _load_migration()

    async with pg_engine.begin() as conn:
        await conn.execute(sa.text("CREATE SCHEMA IF NOT EXISTS core"))
        await conn.run_sync(migration.upgrade)

    async with pg_engine.begin() as conn:
        await conn.run_sync(migration.downgrade)

    async with pg_engine.connect() as conn:
        result = await conn.execute(
            sa.text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'core' AND table_name IN ('event_dlq','processed_events')"
            )
        )
        tables = [row[0] for row in result.fetchall()]

    assert tables == [], f"Expected empty, got: {tables}"
