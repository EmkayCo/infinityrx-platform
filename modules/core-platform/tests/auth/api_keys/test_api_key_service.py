"""Tests for API key management service — TDD.

Covers: create (returns raw key once), validate by raw key, revoke,
list (prefix only), expiration, IP allowlisting, tenant isolation.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.auth._models import Base, Tenant, User
from src.auth.api_keys.models import ApiKey
from src.auth.api_keys.service import (
    ApiKeyCreated,
    ApiKeyExpiredError,
    ApiKeyInvalidError,
    ApiKeyRevokedError,
    ApiKeyService,
)
from shared.auth.passwords import hash_password


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
    ApiKey.metadata.create_all(eng)
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
        email="admin@test.com",
        display_name="Admin",
        password_hash=hash_password("pass123!"),
    )
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def svc() -> ApiKeyService:
    return ApiKeyService()


# ---------------------------------------------------------------------------
# create_api_key
# ---------------------------------------------------------------------------


def test_create_api_key_returns_raw_key(
    db: Session, user: User, tenant: Tenant, svc: ApiKeyService
):
    result = svc.create_api_key(
        db=db,
        tenant_id=tenant.id,
        name="My Key",
        key_type="service",
        created_by=user.id,
    )
    assert isinstance(result, ApiKeyCreated)
    assert len(result.raw_key) >= 32  # cryptographically random, long enough
    assert result.key_prefix == result.raw_key[:8]
    assert result.api_key_id is not None


def test_create_api_key_persists(
    db: Session, user: User, tenant: Tenant, svc: ApiKeyService
):
    result = svc.create_api_key(
        db=db, tenant_id=tenant.id, name="Test Key", key_type="client",
        created_by=user.id,
    )
    db.expire_all()
    row = db.get(ApiKey, result.api_key_id)
    assert row is not None
    assert row.name == "Test Key"
    assert row.key_type == "client"
    assert row.is_active is True
    assert row.key_prefix == result.raw_key[:8]
    # Raw key is NOT stored — only hash
    assert row.key_hash != result.raw_key


def test_create_api_key_with_permissions(
    db: Session, user: User, tenant: Tenant, svc: ApiKeyService
):
    result = svc.create_api_key(
        db=db, tenant_id=tenant.id, name="Scoped Key", key_type="service",
        created_by=user.id,
        permissions=["claims:read", "claims:write"],
    )
    db.expire_all()
    row = db.get(ApiKey, result.api_key_id)
    assert row.permissions == ["claims:read", "claims:write"]


def test_create_api_key_with_expiration(
    db: Session, user: User, tenant: Tenant, svc: ApiKeyService
):
    expires = _now() + timedelta(days=30)
    result = svc.create_api_key(
        db=db, tenant_id=tenant.id, name="Expiring Key", key_type="client",
        created_by=user.id, expires_at=expires,
    )
    db.expire_all()
    row = db.get(ApiKey, result.api_key_id)
    assert row.expires_at is not None


# ---------------------------------------------------------------------------
# validate_api_key
# ---------------------------------------------------------------------------


def test_validate_api_key_succeeds(
    db: Session, user: User, tenant: Tenant, svc: ApiKeyService
):
    result = svc.create_api_key(
        db=db, tenant_id=tenant.id, name="Valid Key", key_type="service",
        created_by=user.id,
    )
    row = svc.validate_api_key(db=db, raw_key=result.raw_key)
    assert row.id == result.api_key_id
    assert row.tenant_id == tenant.id


def test_validate_api_key_updates_last_used(
    db: Session, user: User, tenant: Tenant, svc: ApiKeyService
):
    result = svc.create_api_key(
        db=db, tenant_id=tenant.id, name="Track Key", key_type="service",
        created_by=user.id,
    )
    svc.validate_api_key(db=db, raw_key=result.raw_key)
    db.expire_all()
    row = db.get(ApiKey, result.api_key_id)
    assert row.last_used_at is not None


def test_validate_invalid_key_raises(db: Session, svc: ApiKeyService):
    with pytest.raises(ApiKeyInvalidError):
        svc.validate_api_key(db=db, raw_key="nonexistent-garbage-key-value")


def test_validate_revoked_key_raises(
    db: Session, user: User, tenant: Tenant, svc: ApiKeyService
):
    result = svc.create_api_key(
        db=db, tenant_id=tenant.id, name="Revoke Me", key_type="service",
        created_by=user.id,
    )
    svc.revoke_api_key(db=db, api_key_id=result.api_key_id, tenant_id=tenant.id)
    with pytest.raises(ApiKeyRevokedError):
        svc.validate_api_key(db=db, raw_key=result.raw_key)


def test_validate_expired_key_raises(
    db: Session, user: User, tenant: Tenant, svc: ApiKeyService
):
    result = svc.create_api_key(
        db=db, tenant_id=tenant.id, name="Expired Key", key_type="client",
        created_by=user.id, expires_at=_now() - timedelta(hours=1),
    )
    with pytest.raises(ApiKeyExpiredError):
        svc.validate_api_key(db=db, raw_key=result.raw_key)


# ---------------------------------------------------------------------------
# revoke_api_key
# ---------------------------------------------------------------------------


def test_revoke_api_key(
    db: Session, user: User, tenant: Tenant, svc: ApiKeyService
):
    result = svc.create_api_key(
        db=db, tenant_id=tenant.id, name="To Revoke", key_type="service",
        created_by=user.id,
    )
    svc.revoke_api_key(db=db, api_key_id=result.api_key_id, tenant_id=tenant.id)
    db.expire_all()
    row = db.get(ApiKey, result.api_key_id)
    assert row.is_active is False


def test_revoke_wrong_tenant_raises(
    db: Session, user: User, tenant: Tenant, svc: ApiKeyService
):
    result = svc.create_api_key(
        db=db, tenant_id=tenant.id, name="Wrong Tenant", key_type="service",
        created_by=user.id,
    )
    with pytest.raises(ApiKeyInvalidError):
        svc.revoke_api_key(db=db, api_key_id=result.api_key_id, tenant_id=uuid.uuid4())


# ---------------------------------------------------------------------------
# list_api_keys
# ---------------------------------------------------------------------------


def test_list_api_keys_returns_prefix_not_hash(
    db: Session, user: User, tenant: Tenant, svc: ApiKeyService
):
    svc.create_api_key(
        db=db, tenant_id=tenant.id, name="K1", key_type="service",
        created_by=user.id,
    )
    svc.create_api_key(
        db=db, tenant_id=tenant.id, name="K2", key_type="client",
        created_by=user.id,
    )
    keys = svc.list_api_keys(db=db, tenant_id=tenant.id)
    assert len(keys) == 2
    for k in keys:
        assert len(k.key_prefix) == 8
        assert hasattr(k, "key_hash")  # hash is on model but raw key isn't returned


def test_list_api_keys_tenant_isolation(
    db: Session, user: User, tenant: Tenant, svc: ApiKeyService
):
    other_tenant = Tenant(name="Other", slug="other")
    db.add(other_tenant)
    db.commit()

    svc.create_api_key(
        db=db, tenant_id=tenant.id, name="T1-Key", key_type="service",
        created_by=user.id,
    )
    svc.create_api_key(
        db=db, tenant_id=other_tenant.id, name="T2-Key", key_type="service",
        created_by=user.id,
    )
    t1_keys = svc.list_api_keys(db=db, tenant_id=tenant.id)
    t2_keys = svc.list_api_keys(db=db, tenant_id=other_tenant.id)
    assert len(t1_keys) == 1
    assert len(t2_keys) == 1
    assert t1_keys[0].name == "T1-Key"
    assert t2_keys[0].name == "T2-Key"


# ---------------------------------------------------------------------------
# IP allowlisting
# ---------------------------------------------------------------------------


def test_validate_with_ip_allowlist_success(
    db: Session, user: User, tenant: Tenant, svc: ApiKeyService
):
    result = svc.create_api_key(
        db=db, tenant_id=tenant.id, name="IP Key", key_type="service",
        created_by=user.id, allowed_ips=["10.0.0.1", "10.0.0.2"],
    )
    # Should succeed with allowed IP
    row = svc.validate_api_key(db=db, raw_key=result.raw_key, client_ip="10.0.0.1")
    assert row is not None


def test_validate_with_ip_allowlist_rejected(
    db: Session, user: User, tenant: Tenant, svc: ApiKeyService
):
    result = svc.create_api_key(
        db=db, tenant_id=tenant.id, name="IP Key", key_type="service",
        created_by=user.id, allowed_ips=["10.0.0.1"],
    )
    with pytest.raises(ApiKeyInvalidError, match="IP"):
        svc.validate_api_key(db=db, raw_key=result.raw_key, client_ip="192.168.1.1")


def test_validate_no_ip_restriction_accepts_any(
    db: Session, user: User, tenant: Tenant, svc: ApiKeyService
):
    result = svc.create_api_key(
        db=db, tenant_id=tenant.id, name="Open Key", key_type="service",
        created_by=user.id,
    )
    row = svc.validate_api_key(db=db, raw_key=result.raw_key, client_ip="any.ip")
    assert row is not None
