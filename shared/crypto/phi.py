"""shared.crypto.phi — Field-level PHI encryption helpers.

Provides typed helpers for encrypting and decrypting common PHI/PII shapes.
Every function binds the ciphertext to a ``tenant_id`` via AES-GCM associated
data (AAD), preventing cross-tenant ciphertext confusion attacks.

NEVER log plaintext PHI or encryption keys anywhere in this module.

Supported shapes:
- Name (first + last as separate fields)
- Date of birth
- SSN (9 digits only; rejects all other formats)
- Address (arbitrary dict serialised via JSON)

For each shape there is a matching ``decrypt_*`` function.

``ssn_last4`` decrypts an SSN ciphertext and returns only the last 4 digits.
The full SSN is never written to logs.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date

from shared.crypto.aes import decrypt, encrypt

__all__ = [
    "EncryptedName",
    "encrypt_name",
    "decrypt_name",
    "encrypt_dob",
    "decrypt_dob",
    "encrypt_ssn",
    "decrypt_ssn",
    "encrypt_address",
    "decrypt_address",
    "ssn_last4",
]

_SSN_RE = re.compile(r"^\d{9}$")

# ISO 8601 date format used for DOB serialisation
_DOB_FORMAT = "%Y-%m-%d"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _aad(tenant_id: str) -> bytes:
    """Return deterministic associated data bytes for a tenant."""
    return f"tenant:{tenant_id}".encode()


# ---------------------------------------------------------------------------
# Name
# ---------------------------------------------------------------------------


@dataclass
class EncryptedName:
    """Container for separately-encrypted first and last name fields."""

    first_encrypted: bytes
    last_encrypted: bytes


@dataclass
class DecryptedName:
    """Plaintext first and last name after decryption."""

    first: str
    last: str


def encrypt_name(first: str, last: str, *, tenant_id: str) -> EncryptedName:
    """Encrypt first and last name, bound to *tenant_id*.

    Each field is independently encrypted so that queries against one
    field do not require decrypting the other.

    Args:
        first: Plaintext first name.
        last: Plaintext last name.
        tenant_id: Tenant identifier used as AAD.

    Returns:
        :class:`EncryptedName` with separate encrypted byte blobs.
    """
    aad = _aad(tenant_id)
    return EncryptedName(
        first_encrypted=encrypt(first.encode(), associated_data=aad),
        last_encrypted=encrypt(last.encode(), associated_data=aad),
    )


def decrypt_name(enc: EncryptedName, *, tenant_id: str) -> DecryptedName:
    """Decrypt an :class:`EncryptedName`, verifying AAD against *tenant_id*.

    Args:
        enc: Encrypted name container.
        tenant_id: Must match the value used at encryption time.

    Returns:
        :class:`DecryptedName` with plaintext fields.

    Raises:
        DecryptionError: If the tenant_id does not match or the ciphertext
            is corrupted.
    """
    aad = _aad(tenant_id)
    return DecryptedName(
        first=decrypt(enc.first_encrypted, associated_data=aad).decode(),
        last=decrypt(enc.last_encrypted, associated_data=aad).decode(),
    )


# ---------------------------------------------------------------------------
# Date of Birth
# ---------------------------------------------------------------------------


def encrypt_dob(dob: date, *, tenant_id: str) -> bytes:
    """Encrypt a date of birth as ISO 8601 string, bound to *tenant_id*.

    Args:
        dob: The date of birth to encrypt.
        tenant_id: Tenant identifier used as AAD.

    Returns:
        Encrypted bytes blob.
    """
    return encrypt(dob.strftime(_DOB_FORMAT).encode(), associated_data=_aad(tenant_id))


def decrypt_dob(ciphertext: bytes, *, tenant_id: str) -> date:
    """Decrypt a DOB ciphertext, verifying AAD against *tenant_id*.

    Args:
        ciphertext: Encrypted bytes blob from :func:`encrypt_dob`.
        tenant_id: Must match the value used at encryption time.

    Returns:
        The decrypted :class:`datetime.date`.

    Raises:
        DecryptionError: If tenant_id does not match or ciphertext is invalid.
    """
    raw = decrypt(ciphertext, associated_data=_aad(tenant_id))
    return date.fromisoformat(raw.decode())


# ---------------------------------------------------------------------------
# SSN
# ---------------------------------------------------------------------------


def encrypt_ssn(ssn: str, *, tenant_id: str) -> bytes:
    """Encrypt a 9-digit SSN, bound to *tenant_id*.

    Args:
        ssn: Exactly 9 decimal digits (no dashes, spaces, or other chars).
        tenant_id: Tenant identifier used as AAD.

    Returns:
        Encrypted bytes blob.

    Raises:
        ValueError: If *ssn* is not exactly 9 decimal digits.
    """
    if not _SSN_RE.match(ssn):
        raise ValueError(
            f"SSN must be exactly 9 digits with no formatting; got {len(ssn)!r} chars."
        )
    return encrypt(ssn.encode(), associated_data=_aad(tenant_id))


def decrypt_ssn(ciphertext: bytes, *, tenant_id: str) -> str:
    """Decrypt an SSN ciphertext, verifying AAD against *tenant_id*.

    Args:
        ciphertext: Encrypted bytes blob from :func:`encrypt_ssn`.
        tenant_id: Must match the value used at encryption time.

    Returns:
        The plaintext 9-digit SSN string.

    Raises:
        DecryptionError: If tenant_id does not match or ciphertext is invalid.
    """
    return decrypt(ciphertext, associated_data=_aad(tenant_id)).decode()


def ssn_last4(ciphertext: bytes, *, tenant_id: str) -> str:
    """Return the last 4 digits of an encrypted SSN without logging the full SSN.

    Intended for display in UIs where the full SSN must not be exposed.
    The full SSN is decrypted transiently in memory and immediately discarded;
    it is never written to any log or audit record by this function.

    Args:
        ciphertext: Encrypted bytes blob from :func:`encrypt_ssn`.
        tenant_id: Must match the value used at encryption time.

    Returns:
        A 4-character string containing only the last 4 digits.

    Raises:
        DecryptionError: If tenant_id does not match or ciphertext is invalid.
    """
    full = decrypt_ssn(ciphertext, tenant_id=tenant_id)
    return full[-4:]


# ---------------------------------------------------------------------------
# Address
# ---------------------------------------------------------------------------


def encrypt_address(address_dict: dict, *, tenant_id: str) -> bytes:
    """Encrypt an address dict as JSON, bound to *tenant_id*.

    Args:
        address_dict: Arbitrary dict (e.g., ``{"street": ..., "city": ...}``).
        tenant_id: Tenant identifier used as AAD.

    Returns:
        Encrypted bytes blob.
    """
    serialized = json.dumps(address_dict, separators=(",", ":")).encode()
    return encrypt(serialized, associated_data=_aad(tenant_id))


def decrypt_address(ciphertext: bytes, *, tenant_id: str) -> dict:
    """Decrypt an address ciphertext, verifying AAD against *tenant_id*.

    Args:
        ciphertext: Encrypted bytes blob from :func:`encrypt_address`.
        tenant_id: Must match the value used at encryption time.

    Returns:
        The decrypted address dict.

    Raises:
        DecryptionError: If tenant_id does not match or ciphertext is invalid.
    """
    raw = decrypt(ciphertext, associated_data=_aad(tenant_id))
    return json.loads(raw.decode())
