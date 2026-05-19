"""DB-backed DLQ repository for ReclaimRx.

Replaces _EmptyDLQRepository stub in main.py.
Uses shared.db.models.events.EventDLQEntry ORM model.
Satisfies shared.events.dlq.DLQRepository Protocol.
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

from shared.db.models.events import EventDLQEntry

# R7 BLOCK-21: logger referenced in the get() tenant-fallback path and
# in replay()/drop() (replayed_at = datetime.now(UTC)).
logger = logging.getLogger("reclaimrx.events.dlq_repository")


class ReclaimRxDLQRepository:
    """Async SQLAlchemy DLQ repository backed by shared EventDLQEntry table.

    Tenant-scoped: list() filters by tenant_id when provided.
    """

    def __init__(self, engine: "AsyncEngine") -> None:
        self._engine = engine

    async def list(
        self,
        *,
        tenant_id: uuid.UUID | None = None,
        event_type: str | None = None,
        status: str = "queued",
        limit: int = 100,
    ) -> list[EventDLQEntry]:
        # R8 BLOCK-26: bind AsyncSession to the engine (not to a connection we own),
        # so SQLAlchemy owns the connection + transaction lifecycle.
        from sqlalchemy.ext.asyncio import AsyncSession  # noqa: PLC0415
        async with AsyncSession(self._engine) as session:
            q = select(EventDLQEntry).where(EventDLQEntry.status == status)
            if tenant_id is not None:
                q = q.where(EventDLQEntry.tenant_id == tenant_id)
            if event_type is not None:
                q = q.where(EventDLQEntry.event_type == event_type)
            q = q.limit(limit)
            result = await session.execute(q)
            return list(result.scalars().all())

    async def get(
        self,
        entry_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID | None = None,
    ) -> EventDLQEntry | None:
        """Fetch one DLQ entry, scoped to a specific tenant.

        R6 BLOCK-17: tenant_id is OPTIONAL to satisfy the shared DLQRepository
        protocol signature. When called without tenant_id (e.g. from shared
        DLQService.replay), resolve tenant from shared ContextVar.
        R10 BLOCK-30: current_tenant_id is a ContextVar -- call .get(), NEVER call
        it as a function (raises TypeError: ContextVar is not callable).
        """
        if tenant_id is None:
            from shared.db.tenant_context import current_tenant_id  # noqa: PLC0415
            resolved = current_tenant_id.get()
            if resolved is None:
                logger.warning(
                    "reclaimrx.dlq_repository.no_tenant_context",
                    extra={"audit_action": "dlq_get_missing_tenant"},
                )
                return None
            tenant_id = resolved
        from sqlalchemy.ext.asyncio import AsyncSession  # noqa: PLC0415
        async with AsyncSession(self._engine) as session:
            result = await session.execute(
                select(EventDLQEntry).where(
                    EventDLQEntry.id == entry_id,
                    EventDLQEntry.tenant_id == tenant_id,
                )
            )
            return result.scalar_one_or_none()

    async def replay(self, entry_id: uuid.UUID, *, tenant_id: uuid.UUID) -> int:
        """Re-enqueue a DLQ entry. Returns row-count (0 = not found or wrong tenant).

        R3 BLOCK 9+13: execute a single-session, tenant-scoped UPDATE.
        """
        from sqlalchemy import update  # noqa: PLC0415
        async with self._engine.begin() as conn:
            result = await conn.execute(
                update(EventDLQEntry)
                .where(
                    EventDLQEntry.id == entry_id,
                    EventDLQEntry.tenant_id == tenant_id,
                    EventDLQEntry.status == "queued",
                )
                .values(status="replayed", replayed_at=datetime.now(UTC))
            )
            return int(result.rowcount or 0)

    async def drop(self, entry_id: uuid.UUID, *, tenant_id: uuid.UUID) -> int:
        """Permanently discard a DLQ entry. Returns row-count.

        R3 BLOCK 10: EventDLQEntry has NO dropped_at column (verified against
        shared/db/models/events.py). Track via status='dropped' only.
        R3 BLOCK 9+13: tenant-scoped single-session UPDATE.
        """
        from sqlalchemy import update  # noqa: PLC0415
        async with self._engine.begin() as conn:
            result = await conn.execute(
                update(EventDLQEntry)
                .where(
                    EventDLQEntry.id == entry_id,
                    EventDLQEntry.tenant_id == tenant_id,
                )
                .values(status="dropped")
            )
            return int(result.rowcount or 0)

    async def save(self, entry: EventDLQEntry) -> None:
        # R8 BLOCK-26: AsyncSession bound to the engine for clean lifecycle.
        from sqlalchemy.ext.asyncio import AsyncSession  # noqa: PLC0415
        async with AsyncSession(self._engine) as session:
            session.add(entry)
            await session.commit()
