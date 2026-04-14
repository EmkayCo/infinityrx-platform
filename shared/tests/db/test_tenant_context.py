"""Tests for session-layer tenant isolation.

These tests are the security floor of the platform. They must prove, on
real Postgres, that:

* A session with tenant context A cannot read, update, or delete tenant B's
  rows — regardless of how the query is phrased.
* A query against a tenant-scoped model with *no* tenant context set is
  refused at the ORM layer with :class:`MissingTenantContextError`.
* ``tenant_exempt()`` reliably flips off the filter for legitimate
  platform-admin queries and is otherwise inert.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, select, update

# Drives real Postgres — the security-floor guarantees only make sense
# against a real database. Marked integration so the default local run
# skips when no DB is reachable.
pytestmark = pytest.mark.integration

from shared.db.models.core import Tenant, User
from shared.db.tenant_context import (
    MissingTenantContextError,
    clear_tenant_context,
    set_tenant_context,
    tenant_exempt,
)


async def _seed_two_tenants(sessionmaker) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """Create two tenants each with one user. Returns (t1, t2, u1, u2).

    Seeding disables autoflush and does not issue any ORM queries, so the
    pending INSERTs are carried to ``commit()`` untouched. All three
    objects are inserted in a single commit, bypassing the need to set
    tenant context mid-seed.
    """
    t1, t2 = uuid.uuid4(), uuid.uuid4()
    u1, u2 = uuid.uuid4(), uuid.uuid4()
    async with sessionmaker() as session:
        with session.no_autoflush:
            session.add_all(
                [
                    Tenant(id=t1, name="T1", slug=f"t1-{t1.hex[:6]}", display_name="T1"),
                    Tenant(id=t2, name="T2", slug=f"t2-{t2.hex[:6]}", display_name="T2"),
                    User(id=u1, tenant_id=t1, email="a@t1.test", display_name="A"),
                    User(id=u2, tenant_id=t2, email="b@t2.test", display_name="B"),
                ]
            )
        await session.commit()
    return t1, t2, u1, u2


async def test_tenant_scoped_select_blocks_cross_tenant_reads(pg_sessionmaker) -> None:
    t1, t2, u1, u2 = await _seed_two_tenants(pg_sessionmaker)
    async with pg_sessionmaker() as session:
        token = set_tenant_context(t1)
        try:
            rows = (await session.execute(select(User))).scalars().all()
        finally:
            clear_tenant_context(token)
    assert {r.id for r in rows} == {u1}


async def test_tenant_scoped_select_allows_within_scope(pg_sessionmaker) -> None:
    t1, t2, u1, u2 = await _seed_two_tenants(pg_sessionmaker)
    async with pg_sessionmaker() as session:
        token = set_tenant_context(t2)
        try:
            fetched = (
                await session.execute(select(User).where(User.id == u2))
            ).scalar_one()
        finally:
            clear_tenant_context(token)
    assert fetched.id == u2


async def test_tenant_scoped_select_by_id_blocks_cross_tenant_by_id(
    pg_sessionmaker,
) -> None:
    """Even querying by the other tenant's exact id must return nothing."""
    t1, _, _, u2 = await _seed_two_tenants(pg_sessionmaker)
    async with pg_sessionmaker() as session:
        token = set_tenant_context(t1)
        try:
            result = (
                await session.execute(select(User).where(User.id == u2))
            ).one_or_none()
        finally:
            clear_tenant_context(token)
    assert result is None


async def test_missing_tenant_context_raises(pg_sessionmaker) -> None:
    await _seed_two_tenants(pg_sessionmaker)
    async with pg_sessionmaker() as session:
        clear_tenant_context()
        with pytest.raises(MissingTenantContextError):
            await session.execute(select(User))


async def test_tenant_exempt_allows_cross_tenant(pg_sessionmaker) -> None:
    t1, t2, u1, u2 = await _seed_two_tenants(pg_sessionmaker)
    async with pg_sessionmaker() as session:
        clear_tenant_context()
        stmt = tenant_exempt(select(User))
        rows = (await session.execute(stmt)).scalars().all()
    assert {r.id for r in rows} == {u1, u2}


async def test_tenant_exempt_does_not_affect_non_scoped_models(pg_sessionmaker) -> None:
    t1, t2, _, _ = await _seed_two_tenants(pg_sessionmaker)
    async with pg_sessionmaker() as session:
        clear_tenant_context()
        rows = (await session.execute(select(Tenant))).scalars().all()
    assert {r.id for r in rows} == {t1, t2}


async def test_tenant_scoped_update_is_filtered(pg_sessionmaker) -> None:
    t1, t2, u1, u2 = await _seed_two_tenants(pg_sessionmaker)
    async with pg_sessionmaker() as session:
        token = set_tenant_context(t1)
        try:
            await session.execute(
                update(User).values(display_name="changed")
            )
            await session.commit()
        finally:
            clear_tenant_context(token)

    async with pg_sessionmaker() as session:
        clear_tenant_context()
        all_users = (await session.execute(tenant_exempt(select(User)))).scalars().all()
    by_id = {u.id: u for u in all_users}
    assert by_id[u1].display_name == "changed"
    assert by_id[u2].display_name == "B"  # Untouched.


async def test_tenant_scoped_delete_is_filtered(pg_sessionmaker) -> None:
    t1, t2, u1, u2 = await _seed_two_tenants(pg_sessionmaker)
    async with pg_sessionmaker() as session:
        token = set_tenant_context(t1)
        try:
            await session.execute(delete(User))
            await session.commit()
        finally:
            clear_tenant_context(token)
    async with pg_sessionmaker() as session:
        clear_tenant_context()
        remaining = (
            await session.execute(tenant_exempt(select(User)))
        ).scalars().all()
    assert {r.id for r in remaining} == {u2}


async def test_set_and_clear_via_token(pg_sessionmaker) -> None:
    from shared.db.tenant_context import current_tenant_id

    assert current_tenant_id.get() is None
    token = set_tenant_context(uuid.uuid4())
    assert current_tenant_id.get() is not None
    clear_tenant_context(token)
    assert current_tenant_id.get() is None
