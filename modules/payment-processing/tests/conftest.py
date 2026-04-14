"""Module-level conftest: SQLite DB fixtures, user fixtures, event bus reset."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src._shim.auth import CurrentUser, set_current_user
from src._shim.db import Base, configure_engine
from src._shim.events import reset_events
from src._shim.notifications import NotificationService
from src.models.tables import (
    AchReturnCode,
    VendorAdapter,
)
from src.services.ach_return_codes import ACH_RETURN_CODES

TENANT_ID = str(uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001"))
USER_ID = str(uuid.UUID("bbbbbbbb-0000-0000-0000-000000000001"))
VENDOR_ID = str(uuid.UUID("cccccccc-0000-0000-0000-000000000001"))


@pytest.fixture(autouse=True)
def reset_shims() -> None:
    reset_events()
    NotificationService.reset()


@pytest.fixture(scope="session")
def db_engine():
    configure_engine("sqlite:///:memory:")
    from src._shim.db import get_engine

    engine = get_engine()
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine) -> Session:
    """Fresh session with rollback between tests using connection-level transaction."""
    from sqlalchemy.orm import Session as SASession
    conn = db_engine.connect()
    trans = conn.begin()
    session: SASession = SASession(bind=conn)
    yield session
    session.close()
    trans.rollback()
    conn.close()


@pytest.fixture(autouse=True)
def default_user():
    user = CurrentUser(
        id=uuid.UUID(USER_ID),
        tenant_id=uuid.UUID(TENANT_ID),
        roles=["tenant_admin"],
    )
    set_current_user(user)
    yield user
    set_current_user(None)


@pytest.fixture
def vendor_adapter(db_session: Session) -> VendorAdapter:
    v = VendorAdapter(
        id=VENDOR_ID,
        tenant_id=TENANT_ID,
        vendor_type="direct_ach",
        name="Test ACH Bank",
        connection_type="sftp",
        settlement_method="file_upload",
        supports_ach=True,
    )
    db_session.add(v)
    db_session.flush()
    return v


@pytest.fixture
def preloaded_return_codes(db_session: Session) -> None:
    """Load ACH return codes into test DB."""
    for rc in ACH_RETURN_CODES:
        row = AchReturnCode(
            code=rc.code,
            description=rc.description,
            category=rc.category,
            is_retryable=rc.is_retryable,
            default_action=rc.default_action,
            retry_delay_days=rc.retry_delay_days,
            triggers_fwa_alert=rc.triggers_fwa_alert,
        )
        db_session.merge(row)
    db_session.flush()


@pytest.fixture
def test_client(db_session: Session):
    from src.app import app
    from src.api.dependencies import get_db

    app.dependency_overrides[get_db] = lambda: iter([db_session])
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
