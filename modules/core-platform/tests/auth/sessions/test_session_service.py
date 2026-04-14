"""Tests for session management service — TDD.

Covers: create, validate, revoke, revoke-all, concurrent limit enforcement,
activity touch, idle timeout, and cleanup of expired sessions.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.auth._models import Base, Tenant, User
from src.auth.sessions.models import Session_ as SessionRow
from src.auth.sessions.service import (
    SessionExpiredError,
    SessionNotFoundError,
    SessionRevokedError,
    SessionService,
)
from shared.auth.passwords import hash_password


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    # Session_ uses the same Base
    SessionRow.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def SessionLocal(engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@pytest.fixture
def db(SessionLocal) -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def tenant(db: Session) -> Tenant:
    t = Tenant(name="Test", slug="test")
    db.add(t)
    db.commit()
    return t


@pytest.fixture
def user(db: Session, tenant: Tenant) -> User:
    u = User(
        tenant_id=tenant.id,
        email="user@test.com",
        display_name="Test User",
        password_hash=hash_password("pass123!"),
    )
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def svc() -> SessionService:
    return SessionService(
        session_timeout_minutes=15,
        max_concurrent_sessions=5,
    )


# ---------------------------------------------------------------------------
# create_session
# ---------------------------------------------------------------------------


def test_create_session_returns_row(db: Session, user: User, tenant: Tenant, svc: SessionService):
    token_hash = hashlib.sha256(b"jwt-abc").hexdigest()
    row = svc.create_session(
        db=db,
        user_id=user.id,
        tenant_id=tenant.id,
        token_hash=token_hash,
        device_info={"ip": "1.2.3.4", "user_agent": "test"},
    )
    assert row.id is not None
    assert row.user_id == user.id
    assert row.tenant_id == tenant.id
    assert row.token_hash == token_hash
    assert row.is_active is True
    assert row.device_info == {"ip": "1.2.3.4", "user_agent": "test"}
    assert row.expires_at > _now()


def test_create_session_persists(db: Session, user: User, tenant: Tenant, svc: SessionService):
    token_hash = hashlib.sha256(b"jwt-1").hexdigest()
    row = svc.create_session(db=db, user_id=user.id, tenant_id=tenant.id, token_hash=token_hash)
    db.expire_all()
    found = db.get(SessionRow, row.id)
    assert found is not None
    assert found.token_hash == token_hash


# ---------------------------------------------------------------------------
# validate_session
# ---------------------------------------------------------------------------


def test_validate_session_succeeds(db: Session, user: User, tenant: Tenant, svc: SessionService):
    token_hash = hashlib.sha256(b"jwt-ok").hexdigest()
    row = svc.create_session(db=db, user_id=user.id, tenant_id=tenant.id, token_hash=token_hash)
    result = svc.validate_session(db=db, session_id=row.id, tenant_id=tenant.id)
    assert result.id == row.id
    assert result.is_active is True


def test_validate_session_not_found_raises(db: Session, tenant: Tenant, svc: SessionService):
    with pytest.raises(SessionNotFoundError):
        svc.validate_session(db=db, session_id=uuid.uuid4(), tenant_id=tenant.id)


def test_validate_session_wrong_tenant_raises(db: Session, user: User, tenant: Tenant, svc: SessionService):
    token_hash = hashlib.sha256(b"jwt-wrong-tenant").hexdigest()
    row = svc.create_session(db=db, user_id=user.id, tenant_id=tenant.id, token_hash=token_hash)
    with pytest.raises(SessionNotFoundError):
        svc.validate_session(db=db, session_id=row.id, tenant_id=uuid.uuid4())


def test_validate_revoked_session_raises(db: Session, user: User, tenant: Tenant, svc: SessionService):
    token_hash = hashlib.sha256(b"jwt-revoked").hexdigest()
    row = svc.create_session(db=db, user_id=user.id, tenant_id=tenant.id, token_hash=token_hash)
    svc.revoke_session(db=db, session_id=row.id, tenant_id=tenant.id, reason="test")
    with pytest.raises(SessionRevokedError):
        svc.validate_session(db=db, session_id=row.id, tenant_id=tenant.id)


def test_validate_expired_session_raises(db: Session, user: User, tenant: Tenant, svc: SessionService):
    token_hash = hashlib.sha256(b"jwt-expired").hexdigest()
    row = svc.create_session(db=db, user_id=user.id, tenant_id=tenant.id, token_hash=token_hash)
    # Force expire
    row.expires_at = _now() - timedelta(seconds=1)
    db.commit()
    with pytest.raises(SessionExpiredError):
        svc.validate_session(db=db, session_id=row.id, tenant_id=tenant.id)


def test_validate_idle_timeout_raises(db: Session, user: User, tenant: Tenant):
    """Session within expiry window but idle beyond timeout should raise."""
    svc = SessionService(session_timeout_minutes=15, max_concurrent_sessions=5)
    token_hash = hashlib.sha256(b"jwt-idle").hexdigest()
    row = svc.create_session(db=db, user_id=user.id, tenant_id=tenant.id, token_hash=token_hash)
    # Set last_activity to 20 minutes ago
    row.last_activity_at = _now() - timedelta(minutes=20)
    db.commit()
    with pytest.raises(SessionExpiredError, match="idle"):
        svc.validate_session(db=db, session_id=row.id, tenant_id=tenant.id)


# ---------------------------------------------------------------------------
# revoke_session
# ---------------------------------------------------------------------------


def test_revoke_session_sets_inactive(db: Session, user: User, tenant: Tenant, svc: SessionService):
    token_hash = hashlib.sha256(b"jwt-rev").hexdigest()
    row = svc.create_session(db=db, user_id=user.id, tenant_id=tenant.id, token_hash=token_hash)
    svc.revoke_session(db=db, session_id=row.id, tenant_id=tenant.id, reason="logout")
    db.expire_all()
    updated = db.get(SessionRow, row.id)
    assert updated.is_active is False
    assert updated.revoked_at is not None
    assert updated.revoked_reason == "logout"


def test_revoke_nonexistent_session_raises(db: Session, tenant: Tenant, svc: SessionService):
    with pytest.raises(SessionNotFoundError):
        svc.revoke_session(db=db, session_id=uuid.uuid4(), tenant_id=tenant.id, reason="test")


# ---------------------------------------------------------------------------
# revoke_all_user_sessions
# ---------------------------------------------------------------------------


def test_revoke_all_user_sessions(db: Session, user: User, tenant: Tenant, svc: SessionService):
    for i in range(3):
        svc.create_session(
            db=db,
            user_id=user.id,
            tenant_id=tenant.id,
            token_hash=hashlib.sha256(f"jwt-{i}".encode()).hexdigest(),
        )
    count = svc.revoke_all_user_sessions(
        db=db, user_id=user.id, tenant_id=tenant.id, reason="force_logout",
    )
    assert count == 3
    active = svc.list_active_sessions(db=db, user_id=user.id, tenant_id=tenant.id)
    assert len(active) == 0


# ---------------------------------------------------------------------------
# concurrent session limit
# ---------------------------------------------------------------------------


def test_concurrent_limit_evicts_oldest(db: Session, user: User, tenant: Tenant):
    svc = SessionService(session_timeout_minutes=15, max_concurrent_sessions=2)
    s1 = svc.create_session(
        db=db, user_id=user.id, tenant_id=tenant.id,
        token_hash=hashlib.sha256(b"jwt-1").hexdigest(),
    )
    _s2 = svc.create_session(
        db=db, user_id=user.id, tenant_id=tenant.id,
        token_hash=hashlib.sha256(b"jwt-2").hexdigest(),
    )
    # Third session should evict the oldest (s1)
    _s3 = svc.create_session(
        db=db, user_id=user.id, tenant_id=tenant.id,
        token_hash=hashlib.sha256(b"jwt-3").hexdigest(),
    )
    db.expire_all()
    evicted = db.get(SessionRow, s1.id)
    assert evicted.is_active is False
    assert evicted.revoked_reason == "concurrent_limit_exceeded"

    active = svc.list_active_sessions(db=db, user_id=user.id, tenant_id=tenant.id)
    assert len(active) == 2


# ---------------------------------------------------------------------------
# touch_activity
# ---------------------------------------------------------------------------


def test_touch_activity_updates_last_activity(db: Session, user: User, tenant: Tenant, svc: SessionService):
    token_hash = hashlib.sha256(b"jwt-touch").hexdigest()
    row = svc.create_session(db=db, user_id=user.id, tenant_id=tenant.id, token_hash=token_hash)
    before_touch = _now()
    import time
    time.sleep(0.01)
    svc.touch_activity(db=db, session_id=row.id, tenant_id=tenant.id)
    db.expire_all()
    updated = db.get(SessionRow, row.id)
    # Compare as naive timestamps since SQLite drops tzinfo on round-trip
    assert updated.last_activity_at.replace(tzinfo=None) >= before_touch.replace(tzinfo=None)


# ---------------------------------------------------------------------------
# list_active_sessions
# ---------------------------------------------------------------------------


def test_list_active_sessions_only_returns_active(db: Session, user: User, tenant: Tenant, svc: SessionService):
    s1 = svc.create_session(
        db=db, user_id=user.id, tenant_id=tenant.id,
        token_hash=hashlib.sha256(b"jwt-a1").hexdigest(),
    )
    _s2 = svc.create_session(
        db=db, user_id=user.id, tenant_id=tenant.id,
        token_hash=hashlib.sha256(b"jwt-a2").hexdigest(),
    )
    svc.revoke_session(db=db, session_id=s1.id, tenant_id=tenant.id, reason="test")
    active = svc.list_active_sessions(db=db, user_id=user.id, tenant_id=tenant.id)
    assert len(active) == 1


# ---------------------------------------------------------------------------
# cleanup_expired
# ---------------------------------------------------------------------------


def test_cleanup_expired_deactivates_old_sessions(db: Session, user: User, tenant: Tenant, svc: SessionService):
    row = svc.create_session(
        db=db, user_id=user.id, tenant_id=tenant.id,
        token_hash=hashlib.sha256(b"jwt-exp").hexdigest(),
    )
    row.expires_at = _now() - timedelta(hours=1)
    db.commit()

    count = svc.cleanup_expired(db=db)
    assert count == 1
    db.expire_all()
    updated = db.get(SessionRow, row.id)
    assert updated.is_active is False
    assert updated.revoked_reason == "expired"


def test_cleanup_expired_skips_active_sessions(db: Session, user: User, tenant: Tenant, svc: SessionService):
    _row = svc.create_session(
        db=db, user_id=user.id, tenant_id=tenant.id,
        token_hash=hashlib.sha256(b"jwt-not-exp").hexdigest(),
    )
    count = svc.cleanup_expired(db=db)
    assert count == 0


# ---------------------------------------------------------------------------
# tenant isolation
# ---------------------------------------------------------------------------


def test_list_sessions_tenant_isolation(db: Session, tenant: Tenant, svc: SessionService):
    """Sessions from one tenant must not appear in another tenant's listing."""
    other_tenant = Tenant(name="Other", slug="other")
    db.add(other_tenant)
    db.commit()

    u1 = User(
        tenant_id=tenant.id, email="u1@t1.com",
        display_name="U1", password_hash=hash_password("p1!"),
    )
    u2 = User(
        tenant_id=other_tenant.id, email="u2@t2.com",
        display_name="U2", password_hash=hash_password("p2!"),
    )
    db.add_all([u1, u2])
    db.commit()

    svc.create_session(
        db=db, user_id=u1.id, tenant_id=tenant.id,
        token_hash=hashlib.sha256(b"t1-jwt").hexdigest(),
    )
    svc.create_session(
        db=db, user_id=u2.id, tenant_id=other_tenant.id,
        token_hash=hashlib.sha256(b"t2-jwt").hexdigest(),
    )

    t1_sessions = svc.list_active_sessions(db=db, user_id=u1.id, tenant_id=tenant.id)
    t2_sessions = svc.list_active_sessions(db=db, user_id=u2.id, tenant_id=other_tenant.id)
    assert len(t1_sessions) == 1
    assert len(t2_sessions) == 1
    assert t1_sessions[0].tenant_id != t2_sessions[0].tenant_id
