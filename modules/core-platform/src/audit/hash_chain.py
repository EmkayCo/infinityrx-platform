"""SHA-256 hash chain primitive for tamper-evident audit logs.

HIPAA 2026 requirement: each audit entry carries a cryptographic link to the
preceding entry for the same tenant, forming a chain whose integrity can be
verified without trusting the database.

Canonical serialization format
-------------------------------
``{tenant_id}|{action}|{entity_type}|{entity_id}|{created_at.isoformat()}|{previous_hash}``

Rules:
- ``None`` values for optional fields are serialized as empty strings.
- All string fields are NFC-normalized before hashing to prevent ambiguous
  representations of the same logical string producing different hashes.
- ``created_at`` MUST be timezone-aware (UTC).  ``isoformat()`` emits the
  ``+00:00`` suffix, making the serialization timezone-unambiguous.
- Returns a 64-character lowercase hexadecimal SHA-256 digest.
"""

from __future__ import annotations

import hashlib
import unicodedata
from datetime import datetime
from uuid import UUID

#: Sentinel previous_hash used for the first entry in each tenant's chain.
GENESIS_HASH: str = "0" * 64


def _nfc(value: str | None) -> str:
    """Normalize to NFC and coerce None to empty string."""
    if value is None:
        return ""
    return unicodedata.normalize("NFC", value)


def compute_entry_hash(
    *,
    tenant_id: UUID,
    action: str,
    entity_type: str | None,
    entity_id: str | None,
    created_at: datetime,
    previous_hash: str | None,
) -> str:
    """Return the SHA-256 hash of a canonical audit log entry representation.

    Parameters
    ----------
    tenant_id:
        The tenant that owns this audit entry.
    action:
        The action string (e.g. ``"create"``, ``"update"``, ``"delete"``).
    entity_type:
        Optional entity type; ``None`` treated as empty string.
    entity_id:
        Optional entity identifier; ``None`` treated as empty string.
    created_at:
        Timezone-aware UTC timestamp of the entry.
    previous_hash:
        The ``entry_hash`` of the immediately preceding entry for this tenant,
        or ``None`` / empty string when there is no predecessor.

    Returns
    -------
    str
        64-character lowercase hex SHA-256 digest.
    """
    canonical = "|".join(
        [
            _nfc(str(tenant_id)),
            _nfc(action),
            _nfc(entity_type),
            _nfc(entity_id),
            created_at.isoformat(),
            _nfc(previous_hash),
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
