"""Shared test fixtures for core-platform.

Combines T2 (auth) sys.path/env bootstrap with T4 (jobs/files/exclusions/
health) shim-based DB fixtures. T3 tests bring their own conftest under
modules/core-platform/tests/conftest.py subtrees where needed.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from typing import Iterator

# --- T2: sys.path + JWT env bootstrap (must run before any shared.auth import) ---
_MODULE_ROOT = Path(__file__).resolve().parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")
os.environ.setdefault("JWT_EXPIRES_MINUTES", "60")
os.environ.setdefault("JWT_REFRESH_EXPIRES_MINUTES", "10080")

# --- T4: shim-based DB + FastAPI fixtures for jobs/files/exclusions/health ---
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src._shim import auth as auth_shim
from src._shim import db as db_shim
from src._shim import events as events_shim
from src._shim.notifications import NotificationService
from src.api import router as core_router
from src.files import api as files_api
from src.files.storage import LocalStorageBackend


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path, monkeypatch) -> Iterator[None]:
    db_path = tmp_path / "t.db"
    db_shim.configure_engine(f"sqlite:///{db_path}")
    db_shim.create_all()

    storage_root = tmp_path / "storage"
    storage_root.mkdir()
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(storage_root))
    files_api.set_backend(LocalStorageBackend(str(storage_root)))

    events_shim.reset_events()
    NotificationService.reset()

    yield

    try:
        db_shim.drop_all()
    except Exception:
        pass
    engine = db_shim.get_engine()
    engine.dispose()
    auth_shim.set_current_user(None)


TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = uuid.UUID("22222222-2222-2222-2222-222222222222")


def _user_for(tenant: uuid.UUID, roles: list[str]) -> auth_shim.CurrentUser:
    return auth_shim.CurrentUser(
        id=uuid.uuid4(),
        tenant_id=tenant,
        email=f"user-{tenant}@example.com",
        roles=roles,
    )


@pytest.fixture
def tenant_admin_a() -> auth_shim.CurrentUser:
    u = _user_for(TENANT_A, ["tenant_admin"])
    auth_shim.set_current_user(u)
    return u


@pytest.fixture
def tenant_admin_b() -> auth_shim.CurrentUser:
    u = _user_for(TENANT_B, ["tenant_admin"])
    auth_shim.set_current_user(u)
    return u


@pytest.fixture
def platform_admin() -> auth_shim.CurrentUser:
    u = _user_for(TENANT_A, ["platform_admin"])
    auth_shim.set_current_user(u)
    return u


@pytest.fixture
def tenant_operator_a() -> auth_shim.CurrentUser:
    u = _user_for(TENANT_A, ["tenant_operator"])
    auth_shim.set_current_user(u)
    return u


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(core_router, prefix="/api/v1")
    return a


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture
def db_session():
    SessionLocal = db_shim.get_sessionmaker()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()
