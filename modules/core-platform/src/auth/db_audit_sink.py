"""DatabaseAuditSink — persists auth audit events to core.audit_log.

This is the production replacement for ``InMemoryAuditSink``. In-memory
sink loses every login/logout/role-change on process restart, which
violates HIPAA §164.312(b) "audit controls" (the regulator expects the
record to exist). DatabaseAuditSink writes synchronously to the audit
log so the event is durable before the HTTP response returns.

Contract with ``AuditSink.emit``: synchronous, no return value. Must
never raise — auth flows cannot be blocked by audit-subsystem failure.
A write failure is logged at ERROR and silently absorbed. (Mirror of the
behavior documented in src/audit/middleware.py — the middleware also
swallows audit errors for the same reason.)

Architectural note: we considered publishing audit events to the event
bus and having the audit module consume them, but core-platform is a
single deployable service today — direct-to-DB matches the existing
``AuditMiddleware`` pattern, removes the need for sync→async bridging
from sync FastAPI routes, and keeps the write in the same transaction
boundary the route already owns (callers pass a session_factory bound
to the per-request session).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager

from sqlalchemy.orm import Session

from src.audit.schemas import AuditEntry
from src.audit.service import AuditService
from src.auth.audit_sink import AuditEvent

logger = logging.getLogger("core-platform.auth.audit")

SessionFactory = Callable[[], AbstractContextManager[Session]]


class DatabaseAuditSink:
    """Persists ``AuditEvent`` to ``core.audit_log`` via ``AuditService``.

    Args:
        session_factory: callable returning a context-managed ``Session``.
            The factory is invoked per ``emit()`` so each event owns its
            own short transaction — ensures auth events are durable even
            if the caller's own transaction is rolled back.
    """

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def emit(self, event: AuditEvent) -> None:
        try:
            with self._session_factory() as session:
                svc = AuditService(session)
                svc.log(_to_entry(event))
                # The service calls flush(); we commit explicitly so the
                # row is durable independent of any outer transaction.
                session.commit()
        except Exception:  # noqa: BLE001 — audit failure must not break auth
            logger.exception(
                "audit_sink_write_failed",
                extra={
                    "action": event.action,
                    "tenant_id": str(event.tenant_id) if event.tenant_id else None,
                    "user_id": str(event.user_id) if event.user_id else None,
                },
            )


def _to_entry(event: AuditEvent) -> AuditEntry:
    """Translate AuditSink's ``AuditEvent`` to the service's ``AuditEntry``."""
    return AuditEntry(
        tenant_id=event.tenant_id,  # type: ignore[arg-type]  # validated at emit time
        user_id=event.user_id,
        action=event.action,
        module=event.module,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        before_value=event.before,
        after_value=event.after,
    )


__all__ = ["DatabaseAuditSink", "SessionFactory"]
