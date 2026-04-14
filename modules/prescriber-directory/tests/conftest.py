"""Shared test fixtures for prescriber-directory module.

LESSON-001: Uses SAVEPOINT-based isolation for any fixture that exercises
code that calls db.commit() inside route/service logic.
"""

from __future__ import annotations

import sys
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

# Add project root so `shared.*` resolves (needed after CR-09 session factory fix)
_PROJECT_ROOT = _MODULE_ROOT.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import os
os.environ.setdefault("ENCRYPTION_KEY_ACTIVE", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXVuaXQtdGVzdHM=")
os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from src.db.session import set_engine
from src.models.tables import PrescriberBase

# ---------------------------------------------------------------------------
# Auth configuration — module-level fake user for all integration tests
# ---------------------------------------------------------------------------
# Configure shared auth with in-memory fakes once per session.
# Integration tests that want to test the auth gate itself (test_auth_required.py)
# call configure_auth() in their own scope to test 401 behaviour.
# Other integration tests override get_current_user via dependency_overrides
# to bypass JWT auth and test business logic directly.

_TEST_TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
_TEST_USER_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def _configure_test_auth() -> str:
    """Set up in-memory auth and return a valid access token."""
    from shared.auth.dependencies import CurrentUser, configure_auth
    from shared.auth.jwt_tokens import create_access_token
    from shared.auth.tokens_repo import InMemoryRevokedTokenRepo

    global _FAKE_USER_FOR_TESTS
    _FAKE_USER_FOR_TESTS = CurrentUser(
        id=_TEST_USER_ID,
        tenant_id=_TEST_TENANT_ID,
        email="test@example.com",
        status="active",
        roles=("tenant_admin",),
    )
    configure_auth(
        user_loader=lambda uid: _FAKE_USER_FOR_TESTS if uid == _TEST_USER_ID else None,
        revoked_repo=InMemoryRevokedTokenRepo(),
    )
    return create_access_token(_TEST_USER_ID, _TEST_TENANT_ID, ["tenant_admin"])


# Will be set by _configure_test_auth(); exported for dependency_overrides in tests.
_FAKE_USER_FOR_TESTS = None  # type: ignore[assignment]

# Configure auth at import time so the token is available for module-scoped fixtures.
_AUTH_TOKEN: str = _configure_test_auth()


@pytest.fixture(scope="session")
def auth_token() -> str:
    """Return a valid access token for authenticated test requests."""
    return _AUTH_TOKEN


@pytest.fixture(scope="session")
def auth_headers(auth_token) -> dict:
    """Return Authorization + x-tenant-id headers for authenticated requests."""
    return {
        "Authorization": f"Bearer {auth_token}",
        "x-tenant-id": str(_TEST_TENANT_ID),
    }


TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = uuid.UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture(scope="session")
def _engine():
    # StaticPool forces all sessions to reuse the same underlying connection,
    # so all tests see the same in-memory SQLite database.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.close()

    # SQLite does not support schemas — patch all tables
    for table in PrescriberBase.metadata.tables.values():
        table.schema = None

    PrescriberBase.metadata.create_all(engine)
    set_engine(engine)
    yield engine
    PrescriberBase.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(_engine) -> Iterator[Session]:
    """LESSON-001: SAVEPOINT-based isolation for tests that commit."""
    connection = _engine.connect()
    outer = connection.begin()
    nested = connection.begin_nested()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, transaction):
        nonlocal nested
        if transaction.nested and not transaction._parent.nested:
            nested = connection.begin_nested()

    yield session
    session.close()
    outer.rollback()
    connection.close()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def make_prescriber(
    npi: str = "1234567893",
    entity_type: str = "1",
    last_name: str = "SMITH",
    first_name: str = "JOHN",
    display_name: str = "JOHN SMITH MD",
    status: str = "active",
    primary_taxonomy_code: str = "207Q00000X",
    primary_specialty: str = "family medicine",
    practice_state: str = "IL",
    dea_number: str | None = None,
    dea_status: str | None = None,
    dea_schedules: list | None = None,
) -> dict:
    return {
        "npi": npi,
        "entity_type": entity_type,
        "last_name": last_name,
        "first_name": first_name,
        "display_name": display_name,
        "status": status,
        "primary_taxonomy_code": primary_taxonomy_code,
        "primary_specialty": primary_specialty,
        "practice_state": practice_state,
        "dea_number": dea_number,
        "dea_status": dea_status,
        "dea_schedules": dea_schedules or [],
        "offers_telehealth": False,
        "medicare_opt_out": False,
        "taxonomy_codes": [],
        "created_at": now_utc(),
        "updated_at": now_utc(),
    }
