"""Session management service.

Handles session lifecycle: create, validate, revoke, idle timeout,
concurrent session limit enforcement, and expired session cleanup.

Every query is tenant-scoped.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.auth.sessions.models import Session_ as SessionRow

__all__ = [
    "SessionService",
    "SessionNotFoundError",
    "SessionRevokedError",
    "SessionExpiredError",
    "ConcurrentSessionLimitError",
]


class SessionNotFoundError(Exception):
    """Raised when a session cannot be found (or is in another tenant)."""


class SessionRevokedError(Exception):
    """Raised when a revoked session is used."""


class SessionExpiredError(Exception):
    """Raised when an expired or idle-timed-out session is used."""


class ConcurrentSessionLimitError(Exception):
    """Raised when concurrent session limit is exceeded."""


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


class SessionService:
    """Manages user sessions with timeout and concurrency enforcement.

    Args:
        session_timeout_minutes: Idle timeout in minutes (default 15).
        max_concurrent_sessions: Max active sessions per user (default 5).
    """

    def __init__(
        self,
        *,
        session_timeout_minutes: int = 15,
        max_concurrent_sessions: int = 5,
    ) -> None:
        self._timeout_minutes = session_timeout_minutes
        self._max_concurrent = max_concurrent_sessions

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_session(
        self,
        *,
        db: Session,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        token_hash: str,
        device_info: dict | None = None,
        expires_in_minutes: int = 60,
    ) -> SessionRow:
        """Create a new session, enforcing the concurrent session limit.

        If the user already has ``max_concurrent_sessions`` active sessions,
        the oldest active session is revoked to make room.
        """
        self._enforce_concurrent_limit(db=db, user_id=user_id, tenant_id=tenant_id)

        now = _now()
        row = SessionRow(
            id=uuid.uuid4(),
            user_id=user_id,
            tenant_id=tenant_id,
            token_hash=token_hash,
            device_info=device_info,
            created_at=now,
            last_activity_at=now,
            expires_at=now + timedelta(minutes=expires_in_minutes),
            is_active=True,
        )
        db.add(row)
        db.commit()
        return row

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    def validate_session(
        self,
        *,
        db: Session,
        session_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> SessionRow:
        """Validate a session is active, not expired, and not idle.

        Raises:
            SessionNotFoundError: session doesn't exist or wrong tenant.
            SessionRevokedError: session was revoked.
            SessionExpiredError: session expired or idle-timed-out.
        """
        row = self._get_session(db, session_id, tenant_id)

        if not row.is_active:
            raise SessionRevokedError("session has been revoked")

        now = _now()
        if row.expires_at <= now:
            raise SessionExpiredError("session has expired")

        idle_cutoff = now - timedelta(minutes=self._timeout_minutes)
        if row.last_activity_at < idle_cutoff:
            # Auto-revoke on idle timeout
            row.is_active = False
            row.revoked_at = now
            row.revoked_reason = "idle_timeout"
            db.commit()
            raise SessionExpiredError("session expired due to idle timeout")

        return row

    # ------------------------------------------------------------------
    # Revoke
    # ------------------------------------------------------------------

    def revoke_session(
        self,
        *,
        db: Session,
        session_id: uuid.UUID,
        tenant_id: uuid.UUID,
        reason: str = "logout",
    ) -> SessionRow:
        """Revoke a specific session."""
        row = self._get_session(db, session_id, tenant_id)
        row.is_active = False
        row.revoked_at = _now()
        row.revoked_reason = reason
        db.commit()
        return row

    def revoke_all_user_sessions(
        self,
        *,
        db: Session,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        reason: str = "force_logout",
    ) -> int:
        """Revoke all active sessions for a user. Returns count revoked."""
        now = _now()
        stmt = (
            update(SessionRow)
            .where(
                SessionRow.user_id == user_id,
                SessionRow.tenant_id == tenant_id,
                SessionRow.is_active.is_(True),
            )
            .values(is_active=False, revoked_at=now, revoked_reason=reason)
        )
        result = db.execute(stmt)
        db.commit()
        return result.rowcount

    # ------------------------------------------------------------------
    # Activity tracking
    # ------------------------------------------------------------------

    def touch_activity(
        self,
        *,
        db: Session,
        session_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> None:
        """Update last_activity_at to now."""
        row = self._get_session(db, session_id, tenant_id)
        row.last_activity_at = _now()
        db.commit()

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def list_active_sessions(
        self,
        *,
        db: Session,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> list[SessionRow]:
        """List all active sessions for a user (tenant-scoped)."""
        stmt = (
            select(SessionRow)
            .where(
                SessionRow.user_id == user_id,
                SessionRow.tenant_id == tenant_id,
                SessionRow.is_active.is_(True),
            )
            .order_by(SessionRow.created_at.desc())
        )
        return list(db.execute(stmt).scalars().all())

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup_expired(self, *, db: Session) -> int:
        """Deactivate all sessions past their expires_at. Returns count."""
        now = _now()
        stmt = (
            update(SessionRow)
            .where(
                SessionRow.is_active.is_(True),
                SessionRow.expires_at <= now,
            )
            .values(is_active=False, revoked_at=now, revoked_reason="expired")
        )
        result = db.execute(stmt)
        db.commit()
        return result.rowcount

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_session(
        self, db: Session, session_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> SessionRow:
        """Fetch a session row by id + tenant. Raises SessionNotFoundError."""
        stmt = select(SessionRow).where(
            SessionRow.id == session_id,
            SessionRow.tenant_id == tenant_id,
        )
        row = db.execute(stmt).scalar_one_or_none()
        if row is None:
            raise SessionNotFoundError(
                f"session {session_id} not found for tenant {tenant_id}"
            )
        return row

    def _enforce_concurrent_limit(
        self, *, db: Session, user_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> None:
        """Evict oldest active sessions if the user is at the limit."""
        active = self.list_active_sessions(
            db=db, user_id=user_id, tenant_id=tenant_id
        )
        # If at or over limit, revoke the oldest to make room for 1 new session
        while len(active) >= self._max_concurrent:
            oldest = active[-1]  # list is sorted desc by created_at, so last is oldest
            oldest.is_active = False
            oldest.revoked_at = _now()
            oldest.revoked_reason = "concurrent_limit_exceeded"
            active.pop()
        db.flush()
