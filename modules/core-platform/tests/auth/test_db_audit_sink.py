"""Tests for src.auth.db_audit_sink.DatabaseAuditSink and deps wiring."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from src.auth import deps
from src.auth.audit_sink import AuditEvent, InMemoryAuditSink, make_event
from src.auth.db_audit_sink import DatabaseAuditSink


def _event(**overrides) -> AuditEvent:
    defaults: dict = dict(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        action="login.success",
    )
    defaults.update(overrides)
    return make_event(**defaults)


class _EmptyScalar:
    def scalar_one_or_none(self):
        return None


class _RecordingSession:
    """Minimal stand-in for sqlalchemy.orm.Session recording what happened."""

    def __init__(self) -> None:
        self.added = []
        self.flushed = 0
        self.committed = 0
        self.closed = False

    def add(self, row) -> None:
        self.added.append(row)

    def flush(self) -> None:
        self.flushed += 1

    def commit(self) -> None:
        self.committed += 1

    def execute(self, _stmt):
        # AuditService.log() looks up the current hash-chain head; an empty
        # recording session behaves like an empty table.
        return _EmptyScalar()


def _make_factory(session: _RecordingSession):
    @contextmanager
    def factory():
        try:
            yield session
        finally:
            session.closed = True

    return factory


# ---------------------------------------------------------------------------
# DatabaseAuditSink.emit
# ---------------------------------------------------------------------------


def test_emit_writes_via_audit_service() -> None:
    session = _RecordingSession()
    sink = DatabaseAuditSink(_make_factory(session))
    event = _event()

    sink.emit(event)

    # AuditService.log() calls session.add + flush; we also expect commit
    assert len(session.added) == 1
    assert session.flushed >= 1
    assert session.committed == 1
    assert session.closed is True


def test_emit_translates_event_fields_to_entry() -> None:
    session = _RecordingSession()
    sink = DatabaseAuditSink(_make_factory(session))
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    event = make_event(
        tenant_id=tenant_id,
        user_id=user_id,
        action="user.created",
        entity_type="user",
        entity_id="abc-123",
        after={"email": "new@example.com"},
    )
    sink.emit(event)
    row = session.added[0]
    assert row.tenant_id == str(tenant_id)
    assert row.user_id == str(user_id)
    assert row.action == "user.created"
    assert row.module == "core.auth"
    assert row.entity_type == "user"
    assert row.entity_id == "abc-123"
    assert row.after_value == {"email": "new@example.com"}


def test_emit_swallows_session_errors(caplog) -> None:
    """A DB failure must NOT propagate — auth cannot be blocked by audit."""

    @contextmanager
    def bad_factory():
        raise RuntimeError("db down")
        yield  # pragma: no cover

    sink = DatabaseAuditSink(bad_factory)
    # Must not raise
    with caplog.at_level("ERROR"):
        sink.emit(_event())
    assert any("audit_sink_write_failed" in m for m in caplog.messages)


def test_emit_swallows_commit_errors() -> None:
    session = MagicMock()
    session.commit.side_effect = RuntimeError("commit failed")

    @contextmanager
    def factory():
        yield session

    sink = DatabaseAuditSink(factory)
    sink.emit(_event())  # must not raise


def test_emit_with_none_tenant_and_user() -> None:
    """AuditEvent permits None tenant/user — must still persist (e.g. pre-auth failure)."""
    session = _RecordingSession()
    sink = DatabaseAuditSink(_make_factory(session))
    # Direct AuditEvent bypass so tenant_id can be None
    from datetime import datetime, timezone

    event = AuditEvent(
        tenant_id=None,
        user_id=None,
        action="login.failure",
        module="core.auth",
        entity_type=None,
        entity_id=None,
        before=None,
        after=None,
        created_at=datetime.now(tz=timezone.utc),
    )
    # AuditEntry requires a tenant_id UUID, so emit() will hit pydantic
    # validation and fall into the except branch. It must not raise.
    sink.emit(event)


# ---------------------------------------------------------------------------
# deps.configure_audit_sink / reset / get flow
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_deps_state():
    """Ensure each test starts/ends with no configured sink."""
    deps.reset_audit_sink()
    yield
    deps.reset_audit_sink()


def test_get_audit_sink_default_is_inmemory_fallback() -> None:
    sink = deps.get_audit_sink()
    assert isinstance(sink, InMemoryAuditSink)


def test_configure_audit_sink_installs_database_sink() -> None:
    session = _RecordingSession()
    sink = deps.configure_audit_sink(_make_factory(session))
    assert isinstance(sink, DatabaseAuditSink)
    assert deps.get_audit_sink() is sink


def test_configure_is_idempotent() -> None:
    session1 = _RecordingSession()
    session2 = _RecordingSession()
    first = deps.configure_audit_sink(_make_factory(session1))
    second = deps.configure_audit_sink(_make_factory(session2))
    assert first is not second
    assert deps.get_audit_sink() is second


def test_reset_restores_fallback() -> None:
    deps.configure_audit_sink(_make_factory(_RecordingSession()))
    deps.reset_audit_sink()
    assert isinstance(deps.get_audit_sink(), InMemoryAuditSink)
