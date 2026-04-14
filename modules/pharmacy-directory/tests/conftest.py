"""Shared test fixtures for pharmacy-directory.

Uses async SQLite in-memory DB with SAVEPOINT isolation (LESSON-001).
All service methods are async so we need AsyncSession even in tests.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path
# sys.path must be set before any src.* imports
_MODULE_ROOT = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _MODULE_ROOT.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Minimal crypto env so EncryptedString works in SQLite tests
# ENCRYPTION_KEY_ACTIVE: 32-byte base64-encoded key required by EnvKeyProvider
os.environ.setdefault("ENCRYPTION_KEY_ACTIVE", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXRlc3RpbmchISE=")
os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXRlc3Rpbmch")
os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from shared.db.tenant_context import current_tenant_id, set_tenant_context
from shared.events.in_memory_bus import InMemoryEventBus

# Import models to register them on PharmacyBase.metadata before create_all
from src.models.base import PharmacyBase
from src.models.tables import (  # noqa: F401
    CredentialingApplication,
    CredentialMonitoring,
    CredentialingDocument,
    Network,
    NetworkMembership,
    Pharmacy,
    PharmacyPaymentInfo,
    PharmacyPerformanceSnapshot,
    Psao,
    PsaoMembership,
)

TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = uuid.UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def async_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {"pharmacy_dir": None}},
    )
    async with engine.begin() as conn:
        await conn.run_sync(PharmacyBase.metadata.create_all, checkfirst=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine) -> AsyncIterator[AsyncSession]:
    """SAVEPOINT-isolated async session.

    Routes use flush() not commit(), so the SAVEPOINT restart listener is
    not needed. Using a simple outer transaction rollback for isolation.
    """
    async with async_engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()


@pytest.fixture(autouse=True)
def set_tenant() -> None:
    set_tenant_context(TENANT_A)
    yield
    current_tenant_id.set(None)


@pytest_asyncio.fixture
async def router_session(async_engine) -> AsyncIterator[AsyncSession]:
    """Session for router tests (httpx.AsyncClient + ASGITransport).

    Routes call flush() only — never commit() — so the outer conn.begin()
    + conn.rollback() at teardown provides complete test isolation without
    a SAVEPOINT restart listener (see LESSON-008).
    """
    async with async_engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()


@pytest.fixture
def event_bus() -> InMemoryEventBus:
    return InMemoryEventBus()


@pytest_asyncio.fixture
async def pharmacy_a(db_session: AsyncSession) -> Pharmacy:
    p = Pharmacy(
        npi="1234567890",
        nabp_number="1234567",
        legal_name="Test Pharmacy A",
        display_name="Test Pharmacy A",
        pharmacy_type="retail",
        address_line_1="100 Main St",
        city="Springfield",
        state="IL",
        zip_code="62701",
        status="active",
    )
    db_session.add(p)
    await db_session.flush()
    return p


@pytest_asyncio.fixture
async def pharmacy_b(db_session: AsyncSession) -> Pharmacy:
    p = Pharmacy(
        npi="9876543210",
        nabp_number="9876543",
        legal_name="Test Pharmacy B",
        display_name="Test Pharmacy B",
        pharmacy_type="specialty",
        address_line_1="200 Oak Ave",
        city="Chicago",
        state="IL",
        zip_code="60601",
        status="active",
    )
    db_session.add(p)
    await db_session.flush()
    return p


@pytest_asyncio.fixture
async def network_a(db_session: AsyncSession) -> Network:
    n = Network(
        tenant_id=TENANT_A,
        name="Retail Network A",
        network_code="RET-A",
        network_type="retail",
        effective_date=date(2024, 1, 1),
    )
    db_session.add(n)
    await db_session.flush()
    return n


@pytest_asyncio.fixture
async def network_b(db_session: AsyncSession) -> Network:
    n = Network(
        tenant_id=TENANT_B,
        name="Retail Network B",
        network_code="RET-B",
        network_type="retail",
        effective_date=date(2024, 1, 1),
    )
    db_session.add(n)
    await db_session.flush()
    return n
