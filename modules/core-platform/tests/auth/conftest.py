"""Fixtures for core-platform auth tests — DB, app, seeded tenants/users."""

from __future__ import annotations

from typing import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from shared.auth.jwt_tokens import create_access_token
from src.auth import auth_api_router
from src.auth._db import get_session as app_get_session
from src.auth._models import Base, Tenant, User
from src.auth.audit_sink import InMemoryAuditSink
from src.auth.deps import get_audit_sink
from src.auth.seed.system_roles import seed_system_roles
from src.auth.service import _assign_roles  # noqa: PLC2701  (intentional test access)
from shared.auth.passwords import hash_password
from src.auth.wiring import configure_core_auth


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
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
def seeded_roles(db: Session):
    return seed_system_roles(db)


@pytest.fixture
def tenant_a(db: Session, seeded_roles) -> Tenant:
    t = Tenant(name="Alpha", slug="alpha")
    db.add(t)
    db.commit()
    return t


@pytest.fixture
def tenant_b(db: Session, seeded_roles) -> Tenant:
    t = Tenant(name="Beta", slug="beta")
    db.add(t)
    db.commit()
    return t


def _make_user(
    db: Session,
    tenant: Tenant,
    email: str,
    password: str,
    role_names: list[str],
    *,
    status: str = "active",
) -> User:
    u = User(
        tenant_id=tenant.id,
        email=email,
        display_name=email.split("@")[0],
        password_hash=hash_password(password),
        status=status,
    )
    db.add(u)
    db.flush()
    _assign_roles(db, u, role_names)
    db.commit()
    return u


@pytest.fixture
def admin_a(db: Session, tenant_a: Tenant) -> User:
    return _make_user(db, tenant_a, "admin-a@example.com", "password123!", ["tenant_admin"])


@pytest.fixture
def viewer_a(db: Session, tenant_a: Tenant) -> User:
    return _make_user(db, tenant_a, "view-a@example.com", "password123!", ["tenant_viewer"])


@pytest.fixture
def admin_b(db: Session, tenant_b: Tenant) -> User:
    return _make_user(db, tenant_b, "admin-b@example.com", "password123!", ["tenant_admin"])


@pytest.fixture
def audit_sink() -> InMemoryAuditSink:
    return InMemoryAuditSink()


@pytest.fixture
def app(SessionLocal, audit_sink) -> FastAPI:
    app = FastAPI()
    app.include_router(auth_api_router)

    def _session_override() -> Iterator[Session]:
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[app_get_session] = _session_override
    app.dependency_overrides[get_audit_sink] = lambda: audit_sink

    configure_core_auth(SessionLocal)
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def auth_header_for(user: User) -> dict[str, str]:
    # Load roles from user
    role_names = [r.name for r in user.roles]
    token = create_access_token(user.id, user.tenant_id, role_names)
    return {"Authorization": f"Bearer {token}"}
