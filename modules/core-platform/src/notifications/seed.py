"""Idempotent seeder for default notification preferences per user."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.notifications.defaults import DEFAULT_NOTIFICATION_TYPES
from src.notifications.models import NotificationPreference


def seed_default_preferences(session: Session, user_id: uuid.UUID) -> list[NotificationPreference]:
    """Insert one preference row per default type, skipping types already set."""

    existing = set(
        session.execute(
            select(NotificationPreference.notification_type).where(
                NotificationPreference.user_id == str(user_id)
            )
        ).scalars()
    )
    created: list[NotificationPreference] = []
    for t in DEFAULT_NOTIFICATION_TYPES:
        if t.key in existing:
            continue
        row = NotificationPreference(
            user_id=str(user_id),
            notification_type=t.key,
            email_enabled=t.default_email_enabled,
            in_app_enabled=t.default_in_app_enabled,
            sms_enabled=t.default_sms_enabled,
        )
        session.add(row)
        created.append(row)
    session.flush()
    return created
