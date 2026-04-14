"""Tests for the MFA enforcement gate on /auth/login.

P1 Item 2 of the emergency wiring pass: before this change, the login
endpoint issued a JWT immediately after password verification regardless
of ``tenant.mfa_required`` or ``user.mfa_enabled``. HIPAA 2026 requires
MFA for any user accessing ePHI; this suite captures the gate contract.
"""

from __future__ import annotations

import uuid
from typing import Iterator

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from shared.auth.mfa.challenge import InMemoryChallengeStore
from shared.auth.passwords import hash_password
from src.auth import deps
from src.auth._models import Tenant, User
from src.auth.service import _assign_roles


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _fresh_challenge_store() -> Iterator[InMemoryChallengeStore]:
    store = InMemoryChallengeStore()
    prev = deps._challenge_store if hasattr(deps, "_challenge_store") else None
    deps.configure_challenge_store(store)
    yield store
    if prev is not None:
        deps.configure_challenge_store(prev)
    else:
        deps.reset_challenge_store()


def _make_user(
    db: Session,
    tenant: Tenant,
    email: str,
    *,
    mfa_enabled: bool = False,
    mfa_secret: str | None = None,
) -> User:
    u = User(
        tenant_id=tenant.id,
        email=email,
        display_name=email.split("@")[0],
        password_hash=hash_password("password123!"),
        status="active",
        mfa_enabled=mfa_enabled,
        mfa_secret=mfa_secret,
    )
    db.add(u)
    db.flush()
    _assign_roles(db, u, ["tenant_admin"])
    db.commit()
    return u


# ---------------------------------------------------------------------------
# Login flow — MFA NOT required (baseline, tenant default)
# ---------------------------------------------------------------------------


def test_login_issues_jwt_when_tenant_mfa_not_required(
    client: TestClient, db: Session, tenant_a: Tenant
) -> None:
    """Regression guard: when tenant.mfa_required is False, login behaves
    exactly as before — password → JWT."""
    tenant_a.mfa_required = False
    db.commit()
    _make_user(db, tenant_a, "no-mfa@example.com")

    r = client.post(
        "/api/v1/auth/login",
        json={
            "email": "no-mfa@example.com",
            "password": "password123!",
            "tenant_slug": "alpha",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "access_token" in body
    assert "refresh_token" in body


# ---------------------------------------------------------------------------
# Login flow — MFA REQUIRED but user not enrolled
# ---------------------------------------------------------------------------


def test_login_returns_403_when_mfa_required_and_not_enrolled(
    client: TestClient, db: Session, tenant_a: Tenant
) -> None:
    tenant_a.mfa_required = True
    db.commit()
    _make_user(db, tenant_a, "unenrolled@example.com", mfa_enabled=False)

    r = client.post(
        "/api/v1/auth/login",
        json={
            "email": "unenrolled@example.com",
            "password": "password123!",
            "tenant_slug": "alpha",
        },
    )
    assert r.status_code == 403, r.text
    body = r.json()
    assert body["detail"]["error"] == "mfa_enrollment_required"
    # Body must NOT contain a JWT
    assert "access_token" not in body


# ---------------------------------------------------------------------------
# Login flow — MFA REQUIRED and user enrolled → 202 with challenge token
# ---------------------------------------------------------------------------


def test_login_returns_202_challenge_when_mfa_required_and_enrolled(
    client: TestClient, db: Session, tenant_a: Tenant
) -> None:
    tenant_a.mfa_required = True
    db.commit()
    secret = pyotp.random_base32(length=32)
    _make_user(
        db,
        tenant_a,
        "enrolled@example.com",
        mfa_enabled=True,
        mfa_secret=secret,
    )

    r = client.post(
        "/api/v1/auth/login",
        json={
            "email": "enrolled@example.com",
            "password": "password123!",
            "tenant_slug": "alpha",
        },
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["mfa_required"] is True
    assert body["method"] == "totp"
    assert "challenge_token" in body and len(body["challenge_token"]) >= 32
    assert "access_token" not in body


# ---------------------------------------------------------------------------
# /auth/mfa/verify — valid challenge + valid TOTP code → JWT
# ---------------------------------------------------------------------------


def test_mfa_verify_issues_jwt_on_valid_totp(
    client: TestClient, db: Session, tenant_a: Tenant
) -> None:
    tenant_a.mfa_required = True
    db.commit()
    secret = pyotp.random_base32(length=32)
    _make_user(
        db,
        tenant_a,
        "verify-ok@example.com",
        mfa_enabled=True,
        mfa_secret=secret,
    )

    # Step 1: login → challenge token
    r1 = client.post(
        "/api/v1/auth/login",
        json={
            "email": "verify-ok@example.com",
            "password": "password123!",
            "tenant_slug": "alpha",
        },
    )
    assert r1.status_code == 202
    challenge_token = r1.json()["challenge_token"]

    # Step 2: verify with valid TOTP code
    code = pyotp.TOTP(secret).now()
    r2 = client.post(
        "/api/v1/auth/mfa/verify",
        json={"challenge_token": challenge_token, "code": code},
    )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert "access_token" in body
    assert "refresh_token" in body


def test_mfa_verify_rejects_invalid_totp(
    client: TestClient, db: Session, tenant_a: Tenant
) -> None:
    tenant_a.mfa_required = True
    db.commit()
    secret = pyotp.random_base32(length=32)
    _make_user(
        db,
        tenant_a,
        "verify-bad@example.com",
        mfa_enabled=True,
        mfa_secret=secret,
    )

    r1 = client.post(
        "/api/v1/auth/login",
        json={
            "email": "verify-bad@example.com",
            "password": "password123!",
            "tenant_slug": "alpha",
        },
    )
    challenge_token = r1.json()["challenge_token"]

    # Wrong code
    r2 = client.post(
        "/api/v1/auth/mfa/verify",
        json={"challenge_token": challenge_token, "code": "000000"},
    )
    assert r2.status_code == 401
    assert "access_token" not in r2.json()


def test_mfa_verify_rejects_unknown_challenge_token(client: TestClient) -> None:
    r = client.post(
        "/api/v1/auth/mfa/verify",
        json={"challenge_token": "not-a-real-token", "code": "123456"},
    )
    assert r.status_code == 401


def test_mfa_verify_single_use_second_attempt_fails(
    client: TestClient, db: Session, tenant_a: Tenant
) -> None:
    tenant_a.mfa_required = True
    db.commit()
    secret = pyotp.random_base32(length=32)
    _make_user(
        db,
        tenant_a,
        "reused@example.com",
        mfa_enabled=True,
        mfa_secret=secret,
    )

    r1 = client.post(
        "/api/v1/auth/login",
        json={
            "email": "reused@example.com",
            "password": "password123!",
            "tenant_slug": "alpha",
        },
    )
    challenge_token = r1.json()["challenge_token"]
    code = pyotp.TOTP(secret).now()

    r2 = client.post(
        "/api/v1/auth/mfa/verify",
        json={"challenge_token": challenge_token, "code": code},
    )
    assert r2.status_code == 200

    # Reuse the same token — must be rejected
    r3 = client.post(
        "/api/v1/auth/mfa/verify",
        json={"challenge_token": challenge_token, "code": code},
    )
    assert r3.status_code == 401


def test_mfa_verify_rejects_malformed_code(
    client: TestClient, db: Session, tenant_a: Tenant
) -> None:
    tenant_a.mfa_required = True
    db.commit()
    secret = pyotp.random_base32(length=32)
    _make_user(
        db,
        tenant_a,
        "malformed@example.com",
        mfa_enabled=True,
        mfa_secret=secret,
    )
    r1 = client.post(
        "/api/v1/auth/login",
        json={
            "email": "malformed@example.com",
            "password": "password123!",
            "tenant_slug": "alpha",
        },
    )
    token = r1.json()["challenge_token"]

    # Malformed (non-digit)
    r2 = client.post(
        "/api/v1/auth/mfa/verify",
        json={"challenge_token": token, "code": "abcdef"},
    )
    assert r2.status_code == 401
