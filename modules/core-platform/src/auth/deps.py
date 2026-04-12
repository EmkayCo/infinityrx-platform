"""Module-local FastAPI dependencies for auth routers.

``get_audit_sink`` is the dependency key routers declare; tests and
application composition inject a concrete ``AuditSink`` instance via
``app.dependency_overrides``.
"""

from __future__ import annotations

from src.auth.audit_sink import AuditSink, InMemoryAuditSink

_default_sink: AuditSink = InMemoryAuditSink()


def get_audit_sink() -> AuditSink:
    return _default_sink
