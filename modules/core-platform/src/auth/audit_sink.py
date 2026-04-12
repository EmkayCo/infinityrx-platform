"""Audit sink protocol + in-memory implementation.

The real audit sink lives in Teammate 3's audit service (writes to
core.audit_log). This module defines the contract and a test fake so
auth flows can emit audit events without hard-coupling to T3.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol


@dataclass(frozen=True)
class AuditEvent:
    tenant_id: uuid.UUID | None
    user_id: uuid.UUID | None
    action: str
    module: str
    entity_type: str | None
    entity_id: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    created_at: datetime


class AuditSink(Protocol):
    def emit(self, event: AuditEvent) -> None: ...


@dataclass
class InMemoryAuditSink:
    events: list[AuditEvent] = field(default_factory=list)

    def emit(self, event: AuditEvent) -> None:
        self.events.append(event)

    def by_action(self, action: str) -> list[AuditEvent]:
        return [e for e in self.events if e.action == action]


def make_event(
    *,
    tenant_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> AuditEvent:
    return AuditEvent(
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
        module="core.auth",
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
        created_at=datetime.now(tz=timezone.utc),
    )
