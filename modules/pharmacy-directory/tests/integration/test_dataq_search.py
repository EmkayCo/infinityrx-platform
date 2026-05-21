"""Integration test: PharmacyLookupService returns seeded rows from dataq_master.

Runs against the live infinityrx_reference DB (asyncpg). Requires the service
environment to be up (DATABASE_URL env var pointing at infinityrx_reference).
Skips automatically if the DB is unreachable or the env var is not set.

This test validates FIX 1 from docs/audit/pharmacy-drug-dataflow-fix-plan.md:
search_by_name and get_by_npi both return real rows from pharmacy_dir.dataq_master.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
_PROJECT_ROOT = _MODULE_ROOT.parent.parent
for _p in [str(_MODULE_ROOT), str(_PROJECT_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Known NPI from dataq_master (Walgreens — high-confidence always-present row)
KNOWN_NPI = "1003834180"
KNOWN_NAME_FRAGMENT = "walgreens"

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set — skipping live DB test",
)


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(scope="module")
async def live_db():
    """Async session against the real infinityrx_reference DB."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL not set")

    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(db_url, poolclass=NullPool)
    async with engine.connect() as conn:
        session = AsyncSession(bind=conn)
        try:
            yield session
        finally:
            await session.close()
    await engine.dispose()


@pytest.mark.asyncio
async def test_search_by_name_returns_seeded_rows(live_db):
    """search_by_name('walgreens') must return at least one row from dataq_master."""
    from src.services.lookup import PharmacyLookupService
    import uuid

    svc = PharmacyLookupService(live_db)
    results = await svc.search_by_name(KNOWN_NAME_FRAGMENT, limit=5)
    assert len(results) > 0, (
        "search_by_name returned 0 rows for 'walgreens' — dataq_master repoint failed"
    )
    # Every result must have an id (ncpdp_provider_id surrogate)
    for r in results:
        assert r["id"], f"Result missing id: {r}"
        assert r["display_name"], f"Result missing display_name: {r}"


@pytest.mark.asyncio
async def test_get_by_npi_returns_seeded_row(live_db):
    """get_by_npi with a known NPI must return a non-None result."""
    from src.services.lookup import PharmacyLookupService
    import uuid

    svc = PharmacyLookupService(live_db)
    result = await svc.get_by_npi(uuid.uuid4(), KNOWN_NPI)
    assert result is not None, (
        f"get_by_npi({KNOWN_NPI!r}) returned None — NPI not found in dataq_master"
    )
    assert result["npi"] == KNOWN_NPI
    assert result["id"]  # surrogate key must be set
