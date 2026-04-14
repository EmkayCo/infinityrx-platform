"""API key management service.

Keys are generated as cryptographically random tokens, displayed to the user
exactly once at creation, then stored as SHA-256 hashes. Validation looks up
by prefix (first 8 chars), then does constant-time comparison of hashes.

Every query is tenant-scoped.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.api_keys.models import ApiKey

__all__ = [
    "ApiKeyService",
    "ApiKeyCreated",
    "ApiKeyInvalidError",
    "ApiKeyRevokedError",
    "ApiKeyExpiredError",
]

_KEY_BYTES = 32  # 256 bits of entropy


class ApiKeyInvalidError(Exception):
    """Raised when a key cannot be found or fails validation."""


class ApiKeyRevokedError(Exception):
    """Raised when a revoked key is used."""


class ApiKeyExpiredError(Exception):
    """Raised when an expired key is used."""


@dataclass(frozen=True)
class ApiKeyCreated:
    """Returned from create_api_key — contains the raw key shown once."""

    api_key_id: uuid.UUID
    raw_key: str
    key_prefix: str


def _generate_raw_key() -> str:
    """Generate a cryptographically random API key string."""
    return secrets.token_urlsafe(_KEY_BYTES)


def _hash_key(raw_key: str) -> str:
    """Return SHA-256 hex digest of a raw API key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


class ApiKeyService:
    """Manages API keys with creation, validation, revocation, and listing."""

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_api_key(
        self,
        *,
        db: Session,
        tenant_id: uuid.UUID,
        name: str,
        key_type: str,
        created_by: uuid.UUID | None = None,
        permissions: list[str] | None = None,
        allowed_ips: list[str] | None = None,
        rate_limit_per_minute: int = 100,
        expires_at: datetime | None = None,
    ) -> ApiKeyCreated:
        """Create a new API key. Returns the raw key exactly once."""
        raw_key = _generate_raw_key()
        key_hash = _hash_key(raw_key)
        key_prefix = raw_key[:8]

        row = ApiKey(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            key_type=key_type,
            permissions=permissions,
            allowed_ips=allowed_ips,
            rate_limit_per_minute=rate_limit_per_minute,
            is_active=True,
            expires_at=expires_at,
            created_at=_now(),
            created_by=created_by,
        )
        db.add(row)
        db.commit()

        return ApiKeyCreated(
            api_key_id=row.id,
            raw_key=raw_key,
            key_prefix=key_prefix,
        )

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    def validate_api_key(
        self,
        *,
        db: Session,
        raw_key: str,
        client_ip: str | None = None,
    ) -> ApiKey:
        """Validate a raw API key and return the matching row.

        Raises:
            ApiKeyInvalidError: key not found or IP not allowed.
            ApiKeyRevokedError: key has been revoked.
            ApiKeyExpiredError: key has expired.
        """
        prefix = raw_key[:8]
        candidate_hash = _hash_key(raw_key)

        # Look up by prefix (index-friendly), then constant-time hash compare
        stmt = select(ApiKey).where(ApiKey.key_prefix == prefix)
        candidates = list(db.execute(stmt).scalars().all())

        matched: ApiKey | None = None
        for row in candidates:
            if hmac.compare_digest(row.key_hash, candidate_hash):
                matched = row
                break

        if matched is None:
            raise ApiKeyInvalidError("invalid API key")

        if not matched.is_active:
            raise ApiKeyRevokedError("API key has been revoked")

        if matched.expires_at is not None:
            # Compare timezone-naive for SQLite compat
            now = _now()
            expires = matched.expires_at
            if expires.tzinfo is None:
                now = now.replace(tzinfo=None)
            if expires <= now:
                raise ApiKeyExpiredError("API key has expired")

        # IP allowlist check
        if matched.allowed_ips and client_ip:
            if client_ip not in matched.allowed_ips:
                raise ApiKeyInvalidError(
                    f"IP {client_ip} not in allowlist for this API key"
                )

        # Update last_used_at
        matched.last_used_at = _now()
        db.commit()

        return matched

    # ------------------------------------------------------------------
    # Revoke
    # ------------------------------------------------------------------

    def revoke_api_key(
        self,
        *,
        db: Session,
        api_key_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> ApiKey:
        """Revoke an API key (tenant-scoped)."""
        row = self._get_key(db, api_key_id, tenant_id)
        row.is_active = False
        db.commit()
        return row

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def list_api_keys(
        self,
        *,
        db: Session,
        tenant_id: uuid.UUID,
        include_revoked: bool = False,
    ) -> list[ApiKey]:
        """List API keys for a tenant. Never exposes the raw key."""
        stmt = select(ApiKey).where(ApiKey.tenant_id == tenant_id)
        if not include_revoked:
            stmt = stmt.where(ApiKey.is_active.is_(True))
        stmt = stmt.order_by(ApiKey.created_at.desc())
        return list(db.execute(stmt).scalars().all())

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_key(
        self, db: Session, api_key_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> ApiKey:
        stmt = select(ApiKey).where(
            ApiKey.id == api_key_id,
            ApiKey.tenant_id == tenant_id,
        )
        row = db.execute(stmt).scalar_one_or_none()
        if row is None:
            raise ApiKeyInvalidError(
                f"API key {api_key_id} not found for tenant {tenant_id}"
            )
        return row
