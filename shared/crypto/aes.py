"""shared.crypto.aes — AES-256-GCM symmetric encryption primitives.

Wire format for encrypted blobs:

    key_id_len  (1 byte, uint8)
    key_id      (key_id_len bytes, UTF-8)
    nonce       (12 bytes, random per encryption)
    ciphertext  (variable, includes 16-byte GCM auth tag)

The key_id embedded in the header allows seamless key rotation: decrypt
looks up the key by id from the provider rather than always using the
active key.

Associated data (AAD) binds the ciphertext to a context (e.g., tenant_id).
The same AAD must be supplied for decryption; mismatches raise DecryptionError.

Never log plaintext or key material.
"""

from __future__ import annotations

import base64
import secrets
from typing import TYPE_CHECKING

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from shared.crypto.keys import KeyError as CryptoKeyError
from shared.crypto.keys import KeyProvider, get_key_provider

if TYPE_CHECKING:
    pass

__all__ = [
    "DecryptionError",
    "encrypt",
    "decrypt",
    "encrypt_str",
    "decrypt_str",
]

_NONCE_BYTES = 12


class DecryptionError(Exception):
    """Raised when decryption fails for any reason.

    Intentionally generic — callers must not distinguish between key-not-found,
    auth-tag failure, and truncation, as that distinction leaks information.
    """


# ---------------------------------------------------------------------------
# Core primitives
# ---------------------------------------------------------------------------


def encrypt(
    plaintext: bytes,
    *,
    key_provider: KeyProvider | None = None,
    associated_data: bytes | None = None,
) -> bytes:
    """Encrypt *plaintext* using AES-256-GCM.

    Returns a blob: ``key_id_len || key_id || nonce || ciphertext+tag``.

    A fresh random nonce is generated for each call (never reused).

    Args:
        plaintext: The raw bytes to encrypt.
        key_provider: Key provider to use.  Defaults to the singleton from
            :func:`~shared.crypto.keys.get_key_provider`.
        associated_data: Optional AAD bound to the ciphertext.  The same value
            must be supplied to :func:`decrypt`.

    Returns:
        Encrypted bytes blob.
    """
    provider = key_provider or get_key_provider()
    key_id = provider.active_key_id
    key = provider.get_active_key()

    nonce = secrets.token_bytes(_NONCE_BYTES)
    aesgcm = AESGCM(key)
    ciphertext_and_tag = aesgcm.encrypt(nonce, plaintext, associated_data)

    key_id_bytes = key_id.encode()
    return bytes([len(key_id_bytes)]) + key_id_bytes + nonce + ciphertext_and_tag


def decrypt(
    ciphertext: bytes,
    *,
    key_provider: KeyProvider | None = None,
    associated_data: bytes | None = None,
) -> bytes:
    """Decrypt a blob produced by :func:`encrypt`.

    Parses the key_id from the header, fetches the matching key from the
    provider, and decrypts.

    Args:
        ciphertext: Encrypted blob.
        key_provider: Key provider.  Defaults to the singleton.
        associated_data: Must match the value supplied at encryption time.

    Returns:
        Decrypted plaintext bytes.

    Raises:
        DecryptionError: On truncated blob, missing key, or authentication
            failure (including AAD mismatch or corrupted ciphertext).
    """
    provider = key_provider or get_key_provider()

    # --- Parse header ---
    if len(ciphertext) < 1:
        raise DecryptionError("Truncated blob: too short to contain key_id_len byte.")

    key_id_len = ciphertext[0]
    offset = 1

    if len(ciphertext) < offset + key_id_len:
        raise DecryptionError("Truncated blob: key_id extends beyond blob boundary.")

    key_id = ciphertext[offset : offset + key_id_len].decode("utf-8", errors="replace")
    offset += key_id_len

    # --- Nonce ---
    if len(ciphertext) < offset + _NONCE_BYTES:
        raise DecryptionError("Truncated blob: nonce extends beyond blob boundary.")

    nonce = ciphertext[offset : offset + _NONCE_BYTES]
    offset += _NONCE_BYTES

    payload = ciphertext[offset:]
    # AES-GCM tag is 16 bytes; payload must have at least 16 bytes
    if len(payload) < 16:
        raise DecryptionError("Truncated blob: ciphertext+tag too short.")

    # --- Key lookup ---
    try:
        key = provider.get_key(key_id)
    except CryptoKeyError as exc:
        raise DecryptionError(f"Key not found for key_id '{key_id}': {exc}") from exc

    # --- Decrypt ---
    aesgcm = AESGCM(key)
    try:
        return aesgcm.decrypt(nonce, payload, associated_data)
    except InvalidTag as exc:
        raise DecryptionError(
            "Decryption authentication failed: ciphertext may be corrupted, "
            "wrong key, or AAD mismatch."
        ) from exc


# ---------------------------------------------------------------------------
# String convenience wrappers (base64url encoding)
# ---------------------------------------------------------------------------


def encrypt_str(
    plaintext: str,
    *,
    key_provider: KeyProvider | None = None,
    associated_data: bytes | None = None,
) -> str:
    """Encrypt a string, returning a base64url-encoded ciphertext string."""
    raw = encrypt(plaintext.encode(), key_provider=key_provider, associated_data=associated_data)
    return base64.urlsafe_b64encode(raw).decode()


def decrypt_str(
    ciphertext: str,
    *,
    key_provider: KeyProvider | None = None,
    associated_data: bytes | None = None,
) -> str:
    """Decrypt a base64url-encoded ciphertext string, returning the plaintext."""
    try:
        raw = base64.urlsafe_b64decode(ciphertext + "==")
    except Exception as exc:
        raise DecryptionError(f"Invalid base64url encoding: {exc}") from exc
    return decrypt(raw, key_provider=key_provider, associated_data=associated_data).decode()
