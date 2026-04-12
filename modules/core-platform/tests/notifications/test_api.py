"""Notification HTTP API tests."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.notifications.api import build_notifications_router
from src.notifications.delivery import NoOpEmailDelivery, NoOpSmsDelivery
from src.notifications.models import Notification, NotificationPreference
from src.notifications.service import NotificationService

from shared.events import InMemoryEventBus

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@dataclass
class _User:
    id: uuid.UUID
    tenant_id: uuid.UUID


def _current_user():
    return _User(id=USER, tenant_id=TENANT)


@pytest.fixture
def app(db_session):
    db_session.execute(Notification.__table__.delete())
    db_session.execute(NotificationPreference.__table__.delete())
    db_session.commit()

    def _get_session():
        yield db_session

    bus = InMemoryEventBus()

    def _factory(session):
        return NotificationService(
            session,
            event_bus=bus,
            email_delivery=NoOpEmailDelivery(),
            sms_delivery=NoOpSmsDelivery(),
        )

    app = FastAPI()
    app.state.bus = bus
    app.state.factory = _factory
    app.include_router(
        build_notifications_router(
            get_session=_get_session,
            current_user_dep=_current_user,
            service_factory=_factory,
        )
    )
    return app


async def _seed_notification(db_session, bus, tenant=TENANT, user=USER):
    svc = NotificationService(
        db_session,
        event_bus=bus,
        email_delivery=NoOpEmailDelivery(),
        sms_delivery=NoOpSmsDelivery(),
    )
    return await svc.create(
        tenant_id=tenant,
        user_id=user,
        notification_type="batch_failed",
        title="Batch failed",
        message="Reason",
    )


async def test_list_endpoint(app, db_session):
    await _seed_notification(db_session, app.state.bus)
    db_session.commit()
    client = TestClient(app)
    resp = client.get("/api/v1/notifications")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_mark_read_endpoint(app, db_session):
    row = await _seed_notification(db_session, app.state.bus)
    db_session.commit()
    client = TestClient(app)
    resp = client.put(f"/api/v1/notifications/{row.id}/read")
    assert resp.status_code == 200
    assert resp.json()["read_at"] is not None

    missing = client.put(f"/api/v1/notifications/{uuid.uuid4()}/read")
    assert missing.status_code == 404


async def test_mark_all_read_endpoint(app, db_session):
    await _seed_notification(db_session, app.state.bus)
    await _seed_notification(db_session, app.state.bus)
    db_session.commit()
    client = TestClient(app)
    resp = client.put("/api/v1/notifications/read-all")
    assert resp.status_code == 200
    assert resp.json()["marked_read"] == 2


def test_preferences_list_and_update(app):
    client = TestClient(app)
    resp = client.get("/api/v1/notifications/preferences")
    assert resp.status_code == 200
    assert resp.json() == []

    resp = client.put(
        "/api/v1/notifications/preferences",
        json={"notification_type": "batch_released", "email_enabled": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["email_enabled"] is True
    assert body["notification_type"] == "batch_released"
