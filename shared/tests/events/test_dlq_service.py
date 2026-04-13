"""Tests for DLQService (list/replay/drop) and the FastAPI router."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from shared.db.models.events import EventDLQEntry
from shared.events.dlq import DLQService
from shared.events.in_memory_bus import InMemoryEventBus
from shared.events.types import EventEnvelope
from shared.events import event_types


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------


def _make_entry(
    *,
    event_type: str = event_types.PAYMENT_GENERATED,
    status: str = "queued",
    tenant_id: uuid.UUID | None = None,
) -> EventDLQEntry:
    tid = tenant_id or uuid.uuid4()
    env = EventEnvelope(
        event_type=event_type,
        tenant_id=tid,
        correlation_id=uuid.uuid4(),
        source_module="test-module",
        payload={"amount": "9.99"},
    )
    return EventDLQEntry(
        id=uuid.uuid4(),
        event_id=env.event_id,
        tenant_id=tid,
        event_type=event_type,
        envelope=env.to_wire(),
        failure_reason="timeout",
        attempt_count=3,
        first_failed_at=datetime.now(UTC),
        last_failed_at=datetime.now(UTC),
        dlq_topic=event_type,
        status=status,
    )


class InMemoryDLQRepository:
    """Minimal in-memory store for DLQService tests."""

    def __init__(self, entries: list[EventDLQEntry] | None = None) -> None:
        self._entries: dict[uuid.UUID, EventDLQEntry] = {e.id: e for e in (entries or [])}

    async def list(
        self,
        *,
        tenant_id: uuid.UUID | None = None,
        event_type: str | None = None,
        status: str = "queued",
        limit: int = 100,
    ) -> list[EventDLQEntry]:
        results = [
            e
            for e in self._entries.values()
            if (tenant_id is None or e.tenant_id == tenant_id)
            and (event_type is None or e.event_type == event_type)
            and e.status == status
        ]
        return results[:limit]

    async def get(self, entry_id: uuid.UUID) -> EventDLQEntry | None:
        return self._entries.get(entry_id)

    async def save(self, entry: EventDLQEntry) -> None:
        self._entries[entry.id] = entry


# ---------------------------------------------------------------------------
# DLQService tests
# ---------------------------------------------------------------------------


async def test_list_returns_queued_by_default():
    entry = _make_entry(status="queued")
    dropped = _make_entry(status="dropped")
    repo = InMemoryDLQRepository([entry, dropped])
    service = DLQService(repo)

    results = await service.list()
    assert len(results) == 1
    assert results[0].id == entry.id


async def test_list_filters_by_tenant_id():
    tid = uuid.uuid4()
    entry_mine = _make_entry(tenant_id=tid)
    entry_other = _make_entry()
    repo = InMemoryDLQRepository([entry_mine, entry_other])
    service = DLQService(repo)

    results = await service.list(tenant_id=tid)
    assert len(results) == 1
    assert results[0].tenant_id == tid


async def test_list_filters_by_event_type():
    entry_pay = _make_entry(event_type=event_types.PAYMENT_GENERATED)
    entry_batch = _make_entry(event_type=event_types.BATCH_CREATED)
    repo = InMemoryDLQRepository([entry_pay, entry_batch])
    service = DLQService(repo)

    results = await service.list(event_type=event_types.PAYMENT_GENERATED)
    assert len(results) == 1
    assert results[0].event_type == event_types.PAYMENT_GENERATED


async def test_list_respects_limit():
    entries = [_make_entry() for _ in range(20)]
    repo = InMemoryDLQRepository(entries)
    service = DLQService(repo)

    results = await service.list(limit=5)
    assert len(results) == 5


async def test_list_returns_empty_when_no_matches():
    repo = InMemoryDLQRepository([])
    service = DLQService(repo)
    results = await service.list()
    assert results == []


async def test_replay_republishes_to_bus_and_marks_replayed():
    bus = InMemoryEventBus()
    await bus.start()
    received: list[EventEnvelope] = []

    async def handler(env: EventEnvelope) -> None:
        received.append(env)

    entry = _make_entry(event_type=event_types.PAYMENT_GENERATED)
    await bus.subscribe(event_types.PAYMENT_GENERATED, handler)

    repo = InMemoryDLQRepository([entry])
    service = DLQService(repo)

    await service.replay(entry.id, bus)

    # Entry status updated to replayed
    updated = await repo.get(entry.id)
    assert updated is not None
    assert updated.status == "replayed"
    assert updated.replayed_at is not None

    # Message was re-published to the bus
    assert len(received) == 1
    assert received[0].event_type == event_types.PAYMENT_GENERATED
    await bus.stop()


async def test_replay_raises_if_entry_not_found():
    bus = InMemoryEventBus()
    await bus.start()
    repo = InMemoryDLQRepository([])
    service = DLQService(repo)

    with pytest.raises(KeyError):
        await service.replay(uuid.uuid4(), bus)
    await bus.stop()


async def test_drop_sets_status_to_dropped():
    entry = _make_entry(status="queued")
    repo = InMemoryDLQRepository([entry])
    service = DLQService(repo)

    await service.drop(entry.id, reason="invalid message, cannot retry")

    updated = await repo.get(entry.id)
    assert updated is not None
    assert updated.status == "dropped"


async def test_drop_raises_if_entry_not_found():
    repo = InMemoryDLQRepository([])
    service = DLQService(repo)

    with pytest.raises(KeyError):
        await service.drop(uuid.uuid4(), reason="test")


# ---------------------------------------------------------------------------
# FastAPI router tests
# ---------------------------------------------------------------------------


async def test_router_list_returns_200():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from shared.events.dlq import build_dlq_router

    entry = _make_entry(status="queued")
    repo = InMemoryDLQRepository([entry])
    service = DLQService(repo)

    app = FastAPI()

    async def get_service():
        return service

    async def get_current_perms():
        return {"events:dlq:read", "events:dlq:replay"}

    app.include_router(
        build_dlq_router(get_service=get_service, get_permissions=get_current_perms)
    )
    client = TestClient(app)
    response = client.get("/api/v1/events/dlq")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1


async def test_router_list_forbidden_without_permission():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from shared.events.dlq import build_dlq_router

    repo = InMemoryDLQRepository([])
    service = DLQService(repo)

    app = FastAPI()

    async def get_service():
        return service

    async def get_current_perms():
        return set()  # no permissions

    app.include_router(
        build_dlq_router(get_service=get_service, get_permissions=get_current_perms)
    )
    client = TestClient(app)
    response = client.get("/api/v1/events/dlq")
    assert response.status_code == 403


async def test_router_drop_returns_204():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from shared.events.dlq import build_dlq_router

    entry = _make_entry(status="queued")
    repo = InMemoryDLQRepository([entry])
    service = DLQService(repo)

    app = FastAPI()

    async def get_service():
        return service

    async def get_current_perms():
        return {"events:dlq:read", "events:dlq:replay"}

    app.include_router(
        build_dlq_router(get_service=get_service, get_permissions=get_current_perms)
    )
    client = TestClient(app)
    response = client.post(
        f"/api/v1/events/dlq/{entry.id}/drop", json={"reason": "test drop"}
    )
    assert response.status_code == 204


async def test_router_drop_404_for_unknown_entry():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from shared.events.dlq import build_dlq_router

    repo = InMemoryDLQRepository([])
    service = DLQService(repo)
    app = FastAPI()

    async def get_service():
        return service

    async def get_current_perms():
        return {"events:dlq:read", "events:dlq:replay"}

    app.include_router(
        build_dlq_router(get_service=get_service, get_permissions=get_current_perms)
    )
    client = TestClient(app)
    response = client.post(
        f"/api/v1/events/dlq/{uuid.uuid4()}/drop", json={"reason": "test"}
    )
    assert response.status_code == 404


async def test_router_replay_forbidden_without_replay_permission():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from shared.events.dlq import build_dlq_router

    repo = InMemoryDLQRepository([])
    service = DLQService(repo)
    app = FastAPI()

    async def get_service():
        return service

    async def get_current_perms():
        return {"events:dlq:read"}  # read only — no replay permission

    app.include_router(
        build_dlq_router(get_service=get_service, get_permissions=get_current_perms)
    )
    client = TestClient(app)
    response = client.post(f"/api/v1/events/dlq/{uuid.uuid4()}/replay")
    assert response.status_code == 403


async def test_router_replay_returns_204_and_routes_event():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from shared.events.dlq import build_dlq_router

    bus = InMemoryEventBus()
    await bus.start()
    received: list[EventEnvelope] = []

    async def handler(env: EventEnvelope) -> None:
        received.append(env)

    entry = _make_entry(event_type=event_types.PAYMENT_GENERATED)
    await bus.subscribe(event_types.PAYMENT_GENERATED, handler)

    repo = InMemoryDLQRepository([entry])
    service = DLQService(repo)
    app = FastAPI()

    async def get_service():
        return service

    async def get_current_perms():
        return {"events:dlq:read", "events:dlq:replay"}

    app.include_router(
        build_dlq_router(get_service=get_service, get_permissions=get_current_perms, bus=bus)
    )
    client = TestClient(app)
    response = client.post(f"/api/v1/events/dlq/{entry.id}/replay")
    assert response.status_code == 204
    assert len(received) == 1
    await bus.stop()


async def test_router_replay_uses_default_bus_when_not_provided():
    """Replay endpoint falls back to get_event_bus() when bus=None."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from shared.events.dlq import build_dlq_router
    from shared.events.factory import set_event_bus, reset_event_bus

    bus = InMemoryEventBus()
    await bus.start()
    set_event_bus(bus)

    try:
        entry = _make_entry(event_type=event_types.BATCH_CREATED)
        repo = InMemoryDLQRepository([entry])
        service = DLQService(repo)
        app = FastAPI()

        async def get_service():
            return service

        async def get_current_perms():
            return {"events:dlq:read", "events:dlq:replay"}

        # bus=None triggers the get_event_bus() fallback path
        app.include_router(
            build_dlq_router(get_service=get_service, get_permissions=get_current_perms, bus=None)
        )
        client = TestClient(app)
        response = client.post(f"/api/v1/events/dlq/{entry.id}/replay")
        assert response.status_code == 204
    finally:
        reset_event_bus()
        await bus.stop()


async def test_router_replay_404_for_unknown_entry():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from shared.events.dlq import build_dlq_router

    bus = InMemoryEventBus()
    await bus.start()
    repo = InMemoryDLQRepository([])
    service = DLQService(repo)
    app = FastAPI()

    async def get_service():
        return service

    async def get_current_perms():
        return {"events:dlq:read", "events:dlq:replay"}

    app.include_router(
        build_dlq_router(get_service=get_service, get_permissions=get_current_perms, bus=bus)
    )
    client = TestClient(app)
    response = client.post(f"/api/v1/events/dlq/{uuid.uuid4()}/replay")
    assert response.status_code == 404
    await bus.stop()


async def test_postgres_dlq_sink_write():
    """PostgresDLQSink.write() stores entry via session factory."""
    from datetime import UTC, datetime
    from shared.events.dlq_sink import PostgresDLQSink
    from shared.db.models.events import EventDLQEntry

    committed: list[EventDLQEntry] = []

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def add(self, entry):
            committed.append(entry)

        async def commit(self):
            pass

    def fake_factory():
        return FakeSession()

    sink = PostgresDLQSink(fake_factory)
    entry = EventDLQEntry(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        event_type="payment.generated",
        envelope={},
        failure_reason="test",
        attempt_count=1,
        first_failed_at=datetime.now(UTC),
        last_failed_at=datetime.now(UTC),
        dlq_topic="payment.generated",
        status="queued",
    )
    await sink.write(entry)
    assert len(committed) == 1
    assert committed[0] is entry
