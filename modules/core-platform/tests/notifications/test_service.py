"""NotificationService behaviour: create, preferences, delivery, routing."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import select
from src.notifications.defaults import DEFAULT_NOTIFICATION_TYPES
from src.notifications.delivery import NoOpEmailDelivery, NoOpSmsDelivery
from src.notifications.models import NotificationPreference
from src.notifications.seed import seed_default_preferences
from src.notifications.service import NotificationService, UserEmailLookup

from shared.events import InMemoryEventBus, event_types


@dataclass
class _Lookup:
    mapping: dict

    def resolve(self, user_id):
        return self.mapping.get(str(user_id))


@pytest.fixture
def bus():
    return InMemoryEventBus()


@pytest.fixture
def email():
    return NoOpEmailDelivery()


@pytest.fixture
def sms():
    return NoOpSmsDelivery()


def _svc(db_session, bus, email, sms, *, lookup=None):
    return NotificationService(
        db_session,
        event_bus=bus,
        email_delivery=email,
        sms_delivery=sms,
        user_email_lookup=lookup,
    )


async def test_create_persists_row_and_publishes_event(db_session, bus, email, sms, tenant_id, user_id):
    svc = _svc(db_session, bus, email, sms)
    row = await svc.create(
        tenant_id=tenant_id,
        user_id=user_id,
        notification_type="batch_failed",
        title="Batch failed",
        message="Nightly batch failed.",
    )
    db_session.commit()
    assert row.id is not None
    assert row.severity == "critical"
    published = bus.published
    assert len(published) == 1
    assert published[0].event_type == event_types.NOTIFICATION_CREATED


async def test_email_respected_when_preference_off(db_session, bus, email, sms, tenant_id, user_id):
    db_session.add(
        NotificationPreference(
            user_id=str(user_id),
            notification_type="batch_failed",
            email_enabled=False,
            in_app_enabled=True,
            sms_enabled=False,
        )
    )
    db_session.flush()
    lookup = UserEmailLookup(resolve=_Lookup({str(user_id): "u@example.com"}).resolve)
    svc = _svc(db_session, bus, email, sms, lookup=lookup)
    await svc.create(
        tenant_id=tenant_id,
        user_id=user_id,
        notification_type="batch_failed",
        title="t",
        message="m",
    )
    assert email.sent == []


async def test_email_sent_when_preference_on(db_session, bus, email, sms, tenant_id, user_id):
    db_session.add(
        NotificationPreference(
            user_id=str(user_id),
            notification_type="batch_failed",
            email_enabled=True,
            in_app_enabled=True,
            sms_enabled=False,
        )
    )
    db_session.flush()
    lookup = UserEmailLookup(resolve=_Lookup({str(user_id): "u@example.com"}).resolve)
    svc = _svc(db_session, bus, email, sms, lookup=lookup)
    await svc.create(
        tenant_id=tenant_id,
        user_id=user_id,
        notification_type="batch_failed",
        title="Batch",
        message="fail",
        link="https://app/batch/1",
    )
    assert len(email.sent) == 1
    assert email.sent[0].to == "u@example.com"
    assert "https://app/batch/1" in email.sent[0].body


async def test_email_body_without_link(db_session, bus, email, sms, tenant_id, user_id):
    db_session.add(
        NotificationPreference(
            user_id=str(user_id),
            notification_type="batch_failed",
            email_enabled=True,
            in_app_enabled=True,
            sms_enabled=False,
        )
    )
    db_session.flush()
    lookup = UserEmailLookup(resolve=_Lookup({str(user_id): "u@example.com"}).resolve)
    svc = _svc(db_session, bus, email, sms, lookup=lookup)
    await svc.create(
        tenant_id=tenant_id,
        user_id=user_id,
        notification_type="batch_failed",
        title="t",
        message="just a message",
    )
    assert email.sent[0].body == "just a message"


async def test_email_lookup_no_email_skips_send(db_session, bus, email, sms, tenant_id, user_id):
    db_session.add(
        NotificationPreference(
            user_id=str(user_id),
            notification_type="batch_failed",
            email_enabled=True,
            in_app_enabled=True,
            sms_enabled=False,
        )
    )
    db_session.flush()
    lookup = UserEmailLookup(resolve=lambda _uid: None)
    svc = _svc(db_session, bus, email, sms, lookup=lookup)
    await svc.create(
        tenant_id=tenant_id, user_id=user_id, notification_type="batch_failed", title="t", message="m"
    )
    assert email.sent == []


async def test_sms_sent_when_preference_on(db_session, bus, email, sms, tenant_id, user_id):
    db_session.add(
        NotificationPreference(
            user_id=str(user_id),
            notification_type="prefund_critical",
            email_enabled=False,
            in_app_enabled=True,
            sms_enabled=True,
        )
    )
    db_session.flush()
    svc = _svc(db_session, bus, email, sms)
    await svc.create(
        tenant_id=tenant_id,
        user_id=user_id,
        notification_type="prefund_critical",
        title="Prefund critical",
        message="m",
    )
    assert sms.sent and sms.sent[0][1] == "Prefund critical"


async def test_list_filters_and_tenant_isolation(db_session, bus, email, sms, tenant_id, other_tenant_id, user_id):
    svc = _svc(db_session, bus, email, sms)
    await svc.create(tenant_id=tenant_id, user_id=user_id, notification_type="batch_failed", title="a", message="m")
    await svc.create(tenant_id=other_tenant_id, user_id=user_id, notification_type="batch_failed", title="b", message="m")
    db_session.commit()

    rows = svc.list(tenant_id=tenant_id, user_id=user_id)
    assert len(rows) == 1 and rows[0].title == "a"


async def test_mark_as_read_and_all(db_session, bus, email, sms, tenant_id, user_id):
    svc = _svc(db_session, bus, email, sms)
    n1 = await svc.create(tenant_id=tenant_id, user_id=user_id, notification_type="batch_failed", title="a", message="m")
    await svc.create(tenant_id=tenant_id, user_id=user_id, notification_type="batch_failed", title="b", message="m")
    db_session.commit()

    read = svc.mark_as_read(user_id=user_id, notification_id=uuid.UUID(n1.id))
    assert read is not None and read.read_at is not None
    # idempotent
    again = svc.mark_as_read(user_id=user_id, notification_id=uuid.UUID(n1.id))
    assert again.read_at == read.read_at
    # unknown id
    assert svc.mark_as_read(user_id=user_id, notification_id=uuid.uuid4()) is None

    count = svc.mark_all_as_read(tenant_id=tenant_id, user_id=user_id)
    assert count == 1  # n2 was still unread

    unread = svc.list(tenant_id=tenant_id, user_id=user_id, unread_only=True)
    assert unread == []


async def test_unknown_type_defaults_applied(db_session, bus, email, sms, tenant_id, user_id):
    svc = _svc(db_session, bus, email, sms)
    row = await svc.create(
        tenant_id=tenant_id,
        user_id=user_id,
        notification_type="unknown.custom.type",
        title="t",
        message="m",
    )
    assert row.severity == "info"


def test_seeder_creates_nineteen_preferences(db_session, user_id):
    created = seed_default_preferences(db_session, user_id)
    assert len(created) == 19
    # idempotent
    again = seed_default_preferences(db_session, user_id)
    assert again == []
    rows = db_session.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == str(user_id))
    ).scalars().all()
    assert len(rows) == 19


def test_defaults_cover_all_nineteen_keys():
    keys = {t.key for t in DEFAULT_NOTIFICATION_TYPES}
    assert len(keys) == 19
    assert "batch_failed" in keys and "system_health_warning" in keys


def test_list_preferences_and_update(db_session, bus, email, sms, user_id):
    svc = _svc(db_session, bus, email, sms)
    assert svc.list_preferences(user_id) == []
    updated = svc.update_preference(
        user_id=user_id, notification_type="batch_released", email_enabled=True
    )
    assert updated.email_enabled is True
    # update existing
    again = svc.update_preference(
        user_id=user_id, notification_type="batch_released", in_app_enabled=False, sms_enabled=True
    )
    assert again.in_app_enabled is False and again.sms_enabled is True
    assert len(svc.list_preferences(user_id)) == 1
