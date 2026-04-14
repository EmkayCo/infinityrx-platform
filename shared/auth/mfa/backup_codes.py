"""shared.auth.mfa.backup_codes — single-use backup codes for MFA recovery.

Codes are cryptographically random, stored as SHA-256 hashes in a JSON list
that is then encrypted via EncryptedString on the DB column.

NEVER log raw backup codes.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from typing import Protocol

__all__ = [
    "BackupCodeAuditSink",
    "generate_backup_codes",
    "hash_code",
    "verify_and_consume",
]

_CODE_SEGMENT_LEN = 5
_CODE_FORMAT = f"{{:0{_CODE_SEGMENT_LEN}X}}-{{:0{_CODE_SEGMENT_LEN}X}}"


class BackupCodeAuditSink(Protocol):
    """Protocol for audit sink used during backup code consumption."""

    def emit_backup_code_used(
        self,
        user_id: object,
        tenant_id: object,
    ) -> None: ...

    def emit_backup_code_invalid(
        self,
        user_id: object,
        tenant_id: object,
    ) -> None: ...


def generate_backup_codes(n: int = 10) -> list[str]:
    """Generate *n* cryptographically random backup codes.

    Each code is formatted as XXXXX-XXXXX (uppercase hex).

    Args:
        n: Number of codes to generate (default 10).

    Returns:
        List of plaintext backup code strings.
    """
    codes: list[str] = []
    for _ in range(n):
        a = secrets.randbelow(16**_CODE_SEGMENT_LEN)
        b = secrets.randbelow(16**_CODE_SEGMENT_LEN)
        codes.append(_CODE_FORMAT.format(a, b))
    return codes


def hash_code(code: str) -> str:
    """Return the SHA-256 hex digest of *code* (for storage).

    Args:
        code: Plaintext backup code.

    Returns:
        Hex-encoded SHA-256 digest string.
    """
    return hashlib.sha256(code.encode()).hexdigest()


def _load_hashes(user: object) -> list[str]:
    """Load the list of stored hashes from the user model."""
    raw = getattr(user, "mfa_backup_codes_encrypted", None)
    if not raw:
        return []
    return json.loads(raw)


def _save_hashes(user: object, hashes: list[str], session: object) -> None:
    """Persist updated hash list to the user model."""
    user.mfa_backup_codes_encrypted = json.dumps(hashes)  # type: ignore[attr-defined]
    session.commit()  # type: ignore[attr-defined]


def verify_and_consume(
    user: object,
    code: str,
    session: object,
    *,
    audit: BackupCodeAuditSink | None = None,
) -> bool:
    """Verify *code* against the user's stored backup code hashes.

    If valid, removes that hash (single-use enforcement) and commits the
    session. Emits an audit event via *audit* if provided.

    Args:
        user: User ORM object with ``mfa_backup_codes_encrypted`` attribute.
        code: The plaintext backup code submitted by the user.
        session: Active SQLAlchemy session.
        audit: Optional audit sink for compliance logging.

    Returns:
        True if the code was valid and consumed, False otherwise.
    """
    hashes = _load_hashes(user)
    candidate = hash_code(code)

    # Find a match using constant-time comparison on each hash
    matched_hash: str | None = None
    for stored in hashes:
        if hmac.compare_digest(candidate, stored):
            matched_hash = stored
            break

    if matched_hash is None:
        if audit is not None:
            audit.emit_backup_code_invalid(
                getattr(user, "id", None),
                getattr(user, "tenant_id", None),
            )
        return False

    # Remove the consumed hash (single-use)
    hashes.remove(matched_hash)
    _save_hashes(user, hashes, session)

    if audit is not None:
        audit.emit_backup_code_used(
            getattr(user, "id", None),
            getattr(user, "tenant_id", None),
        )
    return True
