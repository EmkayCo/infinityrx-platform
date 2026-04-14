"""Module-local FastAPI dependencies for auth routers.

``get_audit_sink`` is the dependency key routers declare; tests and
application composition inject a concrete ``AuditSink`` instance via
``app.dependency_overrides``.

The default is ``DatabaseAuditSink`` (writes to core.audit_log) — auth
events must persist across restarts per HIPAA §164.312(b). Tests that
want to inspect emitted events should override with ``InMemoryAuditSink``
through ``app.dependency_overrides[get_audit_sink]``.
"""

from __future__ import annotations

from shared.auth.mfa.challenge import ChallengeStore, InMemoryChallengeStore
from src.auth.audit_sink import AuditSink, InMemoryAuditSink
from src.auth.db_audit_sink import DatabaseAuditSink, SessionFactory

_configured_sink: AuditSink | None = None
_fallback_sink: AuditSink = InMemoryAuditSink()

# MFA challenge store — process-wide singleton used by the login gate and
# the /auth/mfa/verify endpoint. Tests swap this for an InMemoryChallengeStore
# via ``configure_challenge_store``; production wiring (in ``main.py``) can
# substitute a RedisChallengeStore.
_challenge_store: ChallengeStore | None = None
_fallback_challenge_store: ChallengeStore = InMemoryChallengeStore()


def configure_audit_sink(session_factory: SessionFactory) -> AuditSink:
    """Install the production ``DatabaseAuditSink`` as the default.

    Called once at application startup with a session factory bound to
    the configured SessionLocal. Idempotent: re-calling replaces the
    previously-installed sink.
    """
    global _configured_sink
    _configured_sink = DatabaseAuditSink(session_factory)
    return _configured_sink


def reset_audit_sink() -> None:
    """Clear any configured sink — tests use this between cases."""
    global _configured_sink
    _configured_sink = None


def get_audit_sink() -> AuditSink:
    """FastAPI dependency: returns the active sink.

    Resolution order:
        1. The sink installed by ``configure_audit_sink`` (production).
        2. A process-wide ``InMemoryAuditSink`` fallback — used only when
           ``configure_audit_sink`` was never called (unit tests, fresh
           TestClient sessions without explicit override).
    """
    return _configured_sink if _configured_sink is not None else _fallback_sink


# ---------------------------------------------------------------------------
# MFA challenge store
# ---------------------------------------------------------------------------


def configure_challenge_store(store: ChallengeStore) -> ChallengeStore:
    """Install an MFA challenge store (production: RedisChallengeStore)."""
    global _challenge_store
    _challenge_store = store
    return _challenge_store


def reset_challenge_store() -> None:
    """Clear any configured challenge store and re-initialise the fallback."""
    global _challenge_store, _fallback_challenge_store
    _challenge_store = None
    _fallback_challenge_store = InMemoryChallengeStore()


def get_challenge_store() -> ChallengeStore:
    """FastAPI dependency: returns the active MFA challenge store."""
    return (
        _challenge_store if _challenge_store is not None else _fallback_challenge_store
    )
