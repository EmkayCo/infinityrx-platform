"""NotificationService — create, deliver, list, mark-read.

Delivery respects per-user ``notification_preferences``:
    - in_app: always create a row (row existence IS the in-app delivery)
    - email: if enabled, dispatch via EmailDelivery backend
    - sms:   if enabled, dispatch via SmsDelivery backend (NoOp default)

Publishes ``notification.created`` on the event bus so downstream
modules can react (e.g. audit enrichment, push channels).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.events import EventBus, EventEnvelope, event_types
from src.notifications.defaults import DEFAULT_TYPE_MAP
from src.notifications.delivery import (
    EmailDelivery,
    EmailMessage,
    NoOpEmailDelivery,
    NoOpSmsDelivery,
)
from src.notifications.models import Notification, NotificationPreference


@dataclass(frozen=True)
class UserEmailLookup:
    """Callable mapping user_id -> email. Kept simple so stand-ins can be
    injected without pulling in T2's user model."""

    resolve: callable  # (user_id: uuid.UUID) -> str | None


class NotificationService:
    def __init__(
        self,
        session: Session,
        *,
        event_bus: EventBus,
        email_delivery: EmailDelivery | None = None,
        sms_delivery=None,
        user_email_lookup: UserEmailLookup | None = None,
    ) -> None:
        self._session = session
        self._event_bus = event_bus
        self._email = email_delivery or NoOpEmailDelivery()
        self._sms = sms_delivery or NoOpSmsDelivery()
        self._email_lookup = user_email_lookup

    # ------------------------------------------------------------------
    # Create + deliver
    # ------------------------------------------------------------------
    async def create(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        notification_type: str,
        title: str,
        message: str,
        severity: str | None = None,
        link: str | None = None,
    ) -> Notification:
        default = DEFAULT_TYPE_MAP.get(notification_type)
        resolved_severity = severity or (default.severity if default else "info")

        prefs = self._get_or_default_prefs(user_id, notification_type)
        row: Notification | None = None
        if prefs.in_app_enabled:
            row = Notification(
                tenant_id=str(tenant_id),
                user_id=str(user_id),
                notification_type=notification_type,
                severity=resolved_severity,
                title=title,
                message=message,
                link=link,
            )
            self._session.add(row)
            self._session.flush()

        if prefs.email_enabled and self._email_lookup is not None:
            email = self._email_lookup.resolve(user_id)
            if email:
                self._email.send(EmailMessage(to=email, subject=title, body=_render_body(message, link)))

        if prefs.sms_enabled:
            self._sms.send(str(user_id), title)

        await self._event_bus.publish(
            EventEnvelope(
                event_type=event_types.NOTIFICATION_CREATED,
                tenant_id=tenant_id,
                correlation_id=uuid.uuid4(),
                source_module="core-platform",
                payload={
                    "user_id": str(user_id),
                    "notification_type": notification_type,
                    "severity": resolved_severity,
                },
            )
        )
        assert row is not None, "in_app_enabled default is True; row must exist"
        return row

    # ------------------------------------------------------------------
    # Queries / mutations
    # ------------------------------------------------------------------
    def list(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Notification]:
        stmt = (
            select(Notification)
            .where(Notification.tenant_id == str(tenant_id))
            .where(Notification.user_id == str(user_id))
            .order_by(Notification.created_at.desc())
        )
        if unread_only:
            stmt = stmt.where(Notification.read_at.is_(None))
        stmt = stmt.limit(limit).offset(offset)
        return list(self._session.execute(stmt).scalars())

    def mark_as_read(self, *, user_id: uuid.UUID, notification_id: uuid.UUID) -> Notification | None:
        row = self._session.execute(
            select(Notification).where(
                Notification.id == str(notification_id),
                Notification.user_id == str(user_id),
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        if row.read_at is None:
            row.read_at = datetime.now(UTC)
            self._session.flush()
        return row

    def mark_all_as_read(self, *, tenant_id: uuid.UUID, user_id: uuid.UUID) -> int:
        rows = self._session.execute(
            select(Notification).where(
                Notification.tenant_id == str(tenant_id),
                Notification.user_id == str(user_id),
                Notification.read_at.is_(None),
            )
        ).scalars()
        count = 0
        now = datetime.now(UTC)
        for row in rows:
            row.read_at = now
            count += 1
        self._session.flush()
        return count

    # ------------------------------------------------------------------
    # Preferences
    # ------------------------------------------------------------------
    def list_preferences(self, user_id: uuid.UUID) -> list[NotificationPreference]:
        return list(
            self._session.execute(
                select(NotificationPreference).where(NotificationPreference.user_id == str(user_id))
            ).scalars()
        )

    def update_preference(
        self,
        *,
        user_id: uuid.UUID,
        notification_type: str,
        email_enabled: bool | None = None,
        in_app_enabled: bool | None = None,
        sms_enabled: bool | None = None,
    ) -> NotificationPreference:
        row = self._session.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == str(user_id),
                NotificationPreference.notification_type == notification_type,
            )
        ).scalar_one_or_none()
        if row is None:
            default = DEFAULT_TYPE_MAP.get(notification_type)
            row = NotificationPreference(
                user_id=str(user_id),
                notification_type=notification_type,
                email_enabled=default.default_email_enabled if default else True,
                in_app_enabled=default.default_in_app_enabled if default else True,
                sms_enabled=default.default_sms_enabled if default else False,
            )
            self._session.add(row)
        if email_enabled is not None:
            row.email_enabled = email_enabled
        if in_app_enabled is not None:
            row.in_app_enabled = in_app_enabled
        if sms_enabled is not None:
            row.sms_enabled = sms_enabled
        self._session.flush()
        return row

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _get_or_default_prefs(
        self, user_id: uuid.UUID, notification_type: str
    ) -> NotificationPreference:
        row = self._session.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == str(user_id),
                NotificationPreference.notification_type == notification_type,
            )
        ).scalar_one_or_none()
        if row is not None:
            return row
        default = DEFAULT_TYPE_MAP.get(notification_type)
        return NotificationPreference(
            user_id=str(user_id),
            notification_type=notification_type,
            email_enabled=default.default_email_enabled if default else True,
            in_app_enabled=True,
            sms_enabled=False,
        )


def _render_body(message: str, link: str | None) -> str:
    if link:
        return f"{message}\n\n{link}"
    return message
