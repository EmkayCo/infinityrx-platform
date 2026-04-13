"""DLQ inspection and replay service with a thin FastAPI router.

The DLQService operates on any ``DLQRepository`` Protocol, keeping it
decoupled from SQLAlchemy so unit tests can use an in-memory repository.

Authentication is pluggable: callers inject a ``get_permissions`` dependency
that returns the current user's permission set.  The router checks for
``events:dlq:read`` and ``events:dlq:replay`` without importing
``shared.auth`` directly.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any, Protocol

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from shared.db.models.events import EventDLQEntry
from shared.events.bus import EventBus
from shared.events.types import EventEnvelope


# ---------------------------------------------------------------------------
# DLQ Repository Protocol
# ---------------------------------------------------------------------------


class DLQRepository(Protocol):
    """Minimal data-access contract used by DLQService."""

    async def list(
        self,
        *,
        tenant_id: uuid.UUID | None = None,
        event_type: str | None = None,
        status: str = "queued",
        limit: int = 100,
    ) -> list[EventDLQEntry]: ...

    async def get(self, entry_id: uuid.UUID) -> EventDLQEntry | None: ...

    async def save(self, entry: EventDLQEntry) -> None: ...


# ---------------------------------------------------------------------------
# DLQService
# ---------------------------------------------------------------------------


class DLQService:
    """Business logic for DLQ inspection and replay.

    Operations:
    - list: filtered view of DLQ entries.
    - replay: re-publishes the original envelope, marks entry as replayed.
    - drop: marks entry as dropped (will never be retried).
    """

    def __init__(self, repository: DLQRepository) -> None:
        self._repo = repository

    async def list(
        self,
        *,
        tenant_id: uuid.UUID | None = None,
        event_type: str | None = None,
        status: str = "queued",
        limit: int = 100,
    ) -> list[EventDLQEntry]:
        return await self._repo.list(
            tenant_id=tenant_id,
            event_type=event_type,
            status=status,
            limit=limit,
        )

    async def replay(self, entry_id: uuid.UUID, bus: EventBus) -> None:
        """Re-publish the DLQ entry's envelope to its original topic.

        Raises ``KeyError`` if the entry is not found.
        """
        entry = await self._repo.get(entry_id)
        if entry is None:
            raise KeyError(f"DLQ entry {entry_id} not found")

        envelope = EventEnvelope.from_wire(entry.envelope)
        await bus.publish(envelope)

        entry.status = "replayed"
        entry.replayed_at = datetime.now(UTC)
        await self._repo.save(entry)

    async def drop(self, entry_id: uuid.UUID, *, reason: str) -> None:
        """Mark an entry as dropped — it will not be replayed.

        Raises ``KeyError`` if the entry is not found.
        """
        entry = await self._repo.get(entry_id)
        if entry is None:
            raise KeyError(f"DLQ entry {entry_id} not found")

        entry.status = "dropped"
        await self._repo.save(entry)


# ---------------------------------------------------------------------------
# FastAPI router
# ---------------------------------------------------------------------------


class _DropRequest(BaseModel):
    reason: str


def _entry_to_dict(entry: EventDLQEntry) -> dict[str, Any]:
    return {
        "id": str(entry.id),
        "event_id": str(entry.event_id),
        "tenant_id": str(entry.tenant_id),
        "event_type": entry.event_type,
        "failure_reason": entry.failure_reason,
        "attempt_count": entry.attempt_count,
        "dlq_topic": entry.dlq_topic,
        "status": entry.status,
        "first_failed_at": entry.first_failed_at.isoformat(),
        "last_failed_at": entry.last_failed_at.isoformat(),
        "replayed_at": entry.replayed_at.isoformat() if entry.replayed_at else None,
    }


GetServiceDep = Callable[[], Coroutine[Any, Any, DLQService]]
GetPermsDep = Callable[[], Coroutine[Any, Any, set[str]]]


def build_dlq_router(
    *,
    get_service: GetServiceDep,
    get_permissions: GetPermsDep,
    bus: EventBus | None = None,
) -> APIRouter:
    """Build and return the DLQ inspection router.

    Parameters
    ----------
    get_service:
        FastAPI dependency that resolves to a ``DLQService`` instance.
    get_permissions:
        FastAPI dependency that resolves to the current user's permission set.
    bus:
        Event bus for replay operations.  Required only for the replay endpoint.
        If ``None``, replay will use the process-wide singleton via
        ``shared.events.factory.get_event_bus()``.
    """
    router = APIRouter(prefix="/api/v1/events/dlq", tags=["events-dlq"])

    async def _require_read(perms: set[str] = Depends(get_permissions)) -> set[str]:
        if "events:dlq:read" not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return perms

    async def _require_replay(perms: set[str] = Depends(get_permissions)) -> set[str]:
        if "events:dlq:replay" not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return perms

    @router.get("")
    async def list_dlq(
        tenant_id: uuid.UUID | None = None,
        event_type: str | None = None,
        dlq_status: str = "queued",
        limit: int = 100,
        svc: DLQService = Depends(get_service),
        _perms: set[str] = Depends(_require_read),
    ) -> list[dict[str, Any]]:
        entries = await svc.list(
            tenant_id=tenant_id,
            event_type=event_type,
            status=dlq_status,
            limit=limit,
        )
        return [_entry_to_dict(e) for e in entries]

    @router.post("/{entry_id}/replay", status_code=status.HTTP_204_NO_CONTENT)
    async def replay_entry(
        entry_id: uuid.UUID,
        svc: DLQService = Depends(get_service),
        _perms: set[str] = Depends(_require_replay),
    ) -> None:
        replay_bus = bus
        if replay_bus is None:
            from shared.events.factory import get_event_bus

            replay_bus = get_event_bus()
        try:
            await svc.replay(entry_id, replay_bus)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    @router.post("/{entry_id}/drop", status_code=status.HTTP_204_NO_CONTENT)
    async def drop_entry(
        entry_id: uuid.UUID,
        body: _DropRequest,
        svc: DLQService = Depends(get_service),
        _perms: set[str] = Depends(_require_replay),
    ) -> None:
        try:
            await svc.drop(entry_id, reason=body.reason)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return router
