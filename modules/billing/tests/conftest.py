"""Shared fixtures for billing module tests."""

from __future__ import annotations

import os
import sys
import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

# Minimal crypto env for EncryptedJSON/EncryptedString in SQLite tests.
# Same 32-byte test key used by member-management, edi-compliance, medical-claims.
# Must be set before any model import that uses EncryptedJSON.
os.environ.setdefault(
    "ENCRYPTION_KEY_ACTIVE", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXVuaXQtdGVzdHM="
)
# Reset the key-provider singleton so it re-reads the env var we just set.
# Without this, a previous import with no key set would cache a broken provider.
try:
    import shared.crypto.keys as _ck
    _ck._provider_instance = None  # type: ignore[attr-defined]
except Exception:
    pass

_MODULE_ROOT = Path(__file__).resolve().parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from src.models.tables import BillingBase
from src.models.file_artifact import FileArtifact as _FileArtifact  # noqa: F401


@pytest.fixture(scope="session")
def _engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # SQLite doesn't support schemas; patch tables to remove schema prefix
    for table in BillingBase.metadata.tables.values():
        table.schema = None

    BillingBase.metadata.create_all(engine)
    yield engine
    BillingBase.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(_engine) -> Iterator[Session]:
    """SAVEPOINT-based isolation per LESSON-001.

    Uses begin_nested() + after_transaction_end listener so that code under
    test which calls db.commit() is safe: the outer transaction is never
    committed and all writes are rolled back after each test.
    """
    connection = _engine.connect()
    outer = connection.begin()
    nested = connection.begin_nested()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess: Session, transaction: object) -> None:
        nonlocal nested
        if transaction.nested and not transaction._parent.nested:  # type: ignore[attr-defined]
            nested = connection.begin_nested()

    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


# Standard tenant and user IDs for tests
TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = uuid.UUID("22222222-2222-2222-2222-222222222222")
CLIENT_A = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CLIENT_B = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
USER_A = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
PROGRAM_A = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")


@pytest.fixture
def tenant_id() -> uuid.UUID:
    return TENANT_A


@pytest.fixture
def other_tenant_id() -> uuid.UUID:
    return TENANT_B


@pytest.fixture
def client_id() -> uuid.UUID:
    return CLIENT_A


@pytest.fixture
def user_id() -> uuid.UUID:
    return USER_A


@pytest.fixture
def program_id() -> uuid.UUID:
    return PROGRAM_A


def now_utc() -> datetime:
    return datetime.now(UTC)


def make_claim_record(
    tenant_id: uuid.UUID,
    auth_number: str = "AUTH001",
    net_amount: Decimal = Decimal("100.00"),
    client_id: uuid.UUID | None = None,
    program_id: uuid.UUID | None = None,
    status: str = "ingested",
    payment_route: str | None = None,
    pay_to_entity_id: uuid.UUID | None = None,
    pay_to_entity_name: str | None = None,
    is_excluded: bool = False,
    is_statement: bool = False,
    claim_type: str = "new",
    pharmacy_npi: str = "1234567890",
    date_of_service: date | None = None,
) -> dict:
    return {
        "tenant_id": tenant_id,
        "auth_number": auth_number,
        "net_amount": net_amount,
        "client_id": client_id or CLIENT_A,
        "program_id": program_id or PROGRAM_A,
        "status": status,
        "payment_route": payment_route,
        "pay_to_entity_id": pay_to_entity_id,
        "pay_to_entity_name": pay_to_entity_name,
        "is_excluded": is_excluded,
        "is_statement": is_statement,
        "claim_type": claim_type,
        "pharmacy_npi": pharmacy_npi,
        "date_of_service": date_of_service or date(2026, 1, 15),
        "source_type": "api",
        "date_received": now_utc(),
        "created_at": now_utc(),
    }
