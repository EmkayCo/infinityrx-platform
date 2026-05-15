"""Event-to-notification routing rules."""

from __future__ import annotations

import uuid

import pytest
from src.notifications.delivery import NoOpEmailDelivery, NoOpSmsDelivery
from src.notifications.models import Notification
from src.notifications.routing import (
    DEFAULT_RULES,
    Recipient,
    ServiceContext,
    register_event_routing,
)
from src.notifications.service import NotificationService

from shared.events import EventEnvelope, InMemoryEventBus, event_types

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
ADMIN = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def test_default_rules_cover_required_events():
    keys = [r.event_pattern for r in DEFAULT_RULES]
    assert len(keys) == 6
    assert set(keys) == {
        event_types.EXCLUSION_MATCH_FOUND,
        event_types.JOB_FAILED,
        event_types.SFTP_DELIVERY_FAILED,
        event_types.ANOMALY_DETECTED,
        event_types.BATCH_FAILED,
        event_types.AUDIT_CHAIN_BROKEN,
    }


@pytest.mark.parametrize(
    "event_type,payload,expected_type",
    [
        (event_types.EXCLUSION_MATCH_FOUND, {"entity_type": "pharmacy", "entity_id": "npi-1"}, "exclusion_match"),
        (event_types.JOB_FAILED, {"job_name": "fdb_refresh", "error": "boom"}, "system_health_warning"),
        (event_types.SFTP_DELIVERY_FAILED, {"destination": "sftp://x", "error": "auth"}, "sftp_delivery_failed"),
        (event_types.ANOMALY_DETECTED, {"description": "weird"}, "anomaly_detected"),
        (event_types.BATCH_FAILED, {"batch_id": "b9", "reason": "nan"}, "batch_failed"),
    ],
)
async def test_rule_creates_matching_notification(
    db_session, event_type, payload, expected_type
):
    bus = InMemoryEventBus()

    svc = NotificationService(
        db_session,
        event_bus=bus,
        email_delivery=NoOpEmailDelivery(),
        sms_delivery=NoOpSmsDelivery(),
    )

    def _factory() -> ServiceContext:
        return ServiceContext(service=svc, close=lambda: None)

    def _recipients(env: EventEnvelope):
        return [Recipient(tenant_id=env.tenant_id, user_id=ADMIN)]

    await register_event_routing(bus, service_factory=_factory, recipient_selector=_recipients)

    env = EventEnvelope(
        event_type=event_type,
        tenant_id=TENANT,
        correlation_id=uuid.uuid4(),
        source_module="test",
        payload=payload,
    )
    await bus.publish(env)
    db_session.commit()

    rows = (
        db_session.query(Notification)
        .filter(Notification.notification_type == expected_type)
        .all()
    )
    assert len(rows) == 1


async def test_rule_no_recipients_is_noop(db_session):
    bus = InMemoryEventBus()
    svc = NotificationService(
        db_session,
        event_bus=bus,
        email_delivery=NoOpEmailDelivery(),
        sms_delivery=NoOpSmsDelivery(),
    )
    await register_event_routing(
        bus,
        service_factory=lambda: ServiceContext(service=svc, close=lambda: None),
        recipient_selector=lambda env: [],
    )
    env = EventEnvelope(
        event_type=event_types.JOB_FAILED,
        tenant_id=TENANT,
        correlation_id=uuid.uuid4(),
        source_module="test",
        payload={"job_name": "x", "error": "y"},
    )
    await bus.publish(env)
    rows = db_session.query(Notification).all()
    assert rows == []


def test_template_renders_and_missing_key_falls_back():
    from src.notifications.routing import _render

    assert _render("hello {name}", {"name": "world"}) == "hello world"
    assert _render("oops {missing}", {}) == "oops {missing}"
