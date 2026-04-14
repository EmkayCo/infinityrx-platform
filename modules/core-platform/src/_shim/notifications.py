"""Shim NotificationService. Real version lives in shared/ (T3)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Notification:
    tenant_id: uuid.UUID
    notification_type: str
    title: str
    message: str
    severity: str = "info"
    link: Optional[str] = None
    user_id: Optional[uuid.UUID] = None


class NotificationService:
    _created: List[Notification] = []

    @classmethod
    def create(
        cls,
        *,
        tenant_id: uuid.UUID,
        notification_type: str,
        title: str,
        message: str,
        severity: str = "info",
        link: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
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
    def all(cls) -> List[Notification]:
        return list(cls._created)

    @classmethod
    def reset(cls) -> None:
        cls._created.clear()
