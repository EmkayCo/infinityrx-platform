"""Shim NotificationService for payment-processing. Real version lives in shared/ (T3)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass
class Notification:
    tenant_id: uuid.UUID
    notification_type: str
    title: str
    message: str
    severity: str = "info"
    link: str | None = None
    user_id: uuid.UUID | None = None


class NotificationService:
    _created: list[Notification] = []

    @classmethod
    def create(
        cls,
        *,
        tenant_id: uuid.UUID,
        notification_type: str,
        title: str,
        message: str,
        severity: str = "info",
        link: str | None = None,
        user_id: uuid.UUID | None = None,
    ) -> Notification:
        n = Notification(
            tenant_id=tenant_id,
            notification_type=notification_type,
            title=title,
            message=message,
            severity=severity,
            link=link,
            user_id=user_id,
        )
        cls._created.append(n)
        return n

    @classmethod
    def all(cls) -> list[Notification]:
        return list(cls._created)

    @classmethod
    def reset(cls) -> None:
        cls._created.clear()
