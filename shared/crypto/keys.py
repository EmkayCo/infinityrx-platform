"""shared.crypto.keys — Key provider protocol and implementations.

Supports two providers:
- EnvKeyProvider: loads base64-encoded 32-byte keys from environment variables.
- FileKeyProvider: loads keys from a JSON file (for local development).

Key rotation is supported: old keys are retained by id for decryption of
existing data; new data is always encrypted with the active key.

Never log key material.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Protocol, runtime_checkable

__all__ = [
    "KeyProvider",
    "KeyError",
    "EnvKeyProvider",
    "FileKeyProvider",
    "get_key_provider",
]

_REQUIRED_KEY_BYTES = 32


class KeyError(Exception):
    """Raised when a key cannot be found or is invalid."""


@runtime_checkable
class KeyProvider(Protocol):
    """Protocol that all key providers must satisfy."""

    active_key_id: str

    def get_active_key(self) -> bytes:  # noqa: D102
        ...

    def get_key(self, key_id: str) -> bytes:  # noqa: D102
        ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _decode_and_validate(raw_b64: str, label: str) -> bytes:
    """Decode a base64 string and assert it is exactly 32 bytes."""
    try:
        key_bytes = base64.b64decode(raw_b64)
    except Exception as exc:
        raise KeyError(f"Key '{label}' is not valid base64: {exc}") from exc
    if len(key_bytes) != _REQUIRED_KEY_BYTES:
        raise KeyError(
            f"Key '{label}' must be exactly 32 bytes after base64 decode; "
            f"got {len(key_bytes)} bytes."
        )
    return key_bytes


# ---------------------------------------------------------------------------
# EnvKeyProvider
# ---------------------------------------------------------------------------


class EnvKeyProvider:
    """Loads encryption keys from environment variables.

    Active key:  ENCRYPTION_KEY_ACTIVE  (base64, 32 bytes)
    Active id:   ENCRYPTION_KEY_ACTIVE_ID  (default "v1")
    Old keys:    ENCRYPTION_KEY_{id}  e.g. ENCRYPTION_KEY_v0
    """

    def __init__(self) -> None:
        active_raw = os.environ.get("ENCRYPTION_KEY_ACTIVE")
        if not active_raw:
            raise KeyError(
                "ENCRYPTION_KEY_ACTIVE environment variable is not set. "
                "Set it to a base64-encoded 32-byte encryption key."
            )
        self._active_key_id: str = os.environ.get("ENCRYPTION_KEY_ACTIVE_ID", "v1")
        self._keys: dict[str, bytes] = {}

        # Validate and store active key under its id
        active_bytes = _decode_and_validate(active_raw, "ENCRYPTION_KEY_ACTIVE")
        self._keys[self._active_key_id] = active_bytes

        # Load any rotation keys: ENCRYPTION_KEY_{id}
        prefix = "ENCRYPTION_KEY_"
        for env_key, env_val in os.environ.items():
            if not env_key.startswith(prefix):
                continue
            suffix = env_key[len(prefix):]
            # Skip the "ACTIVE" and "ACTIVE_ID" special vars
            if suffix in ("ACTIVE", "ACTIVE_ID"):
                continue
            key_id = suffix  # e.g. "v0"
            key_bytes = _decode_and_validate(env_val, env_key)
            self._keys[key_id] = key_bytes

    @property
    def active_key_id(self) -> str:
        return self._active_key_id

    def get_active_key(self) -> bytes:
        return self._keys[self._active_key_id]

    def get_key(self, key_id: str) -> bytes:
        if key_id not in self._keys:
            raise KeyError(f"Key id '{key_id}' not found in environment variables.")
        return self._keys[key_id]


# ---------------------------------------------------------------------------
# FileKeyProvider
# ---------------------------------------------------------------------------


class FileKeyProvider:
    """Loads encryption keys from a JSON file.

    Expected format::

        {
            "active": "v1",
            "keys": {
                "v1": "<base64-32-bytes>",
                "v0": "<base64-32-bytes>"
            }
        }

    Intended for local development only.  Do NOT use in production.
    """

    def __init__(self, path: str | Path) -> None:
        path = Path(path)
        if not path.exists():
            raise KeyError(f"Key file not found: {path}")
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise KeyError(f"Invalid/malformed JSON in key file '{path}': {exc}") from exc

        if "active" not in data:
            raise KeyError(
                f"Key file '{path}' is missing required 'active' field."
            )
        if "keys" not in data or not isinstance(data["keys"], dict):
            raise KeyError(f"Key file '{path}' is missing required 'keys' dict.")

        self._active_key_id: str = data["active"]
        self._keys: dict[str, bytes] = {}

        for key_id, raw_b64 in data["keys"].items():
            self._keys[key_id] = _decode_and_validate(raw_b64, key_id)

        if self._active_key_id not in self._keys:
            raise KeyError(
                f"Active key id '{self._active_key_id}' is not present in 'keys' dict "
                f"of '{path}'."
            )

    @property
    def active_key_id(self) -> str:
        return self._active_key_id

    def get_active_key(self) -> bytes:
        return self._keys[self._active_key_id]

    def get_key(self, key_id: str) -> bytes:
        if key_id not in self._keys:
            raise KeyError(f"Key id '{key_id}' not found in key file.")
        return self._keys[key_id]


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

_provider_instance: KeyProvider | None = None


def get_key_provider(*, _reset: bool = False) -> KeyProvider:
    """Return the singleton key provider, creating it on first call.

    Provider selection via ``ENCRYPTION_PROVIDER`` env var (default: ``env``):

    - ``env``  → :class:`EnvKeyProvider`
    - ``file`` → :class:`FileKeyProvider` (requires ``ENCRYPTION_KEY_FILE``)
    """
    global _provider_instance
    if _reset or _provider_instance is None:
        provider_type = os.environ.get("ENCRYPTION_PROVIDER", "env").lower()
        if provider_type == "env":
            _provider_instance = EnvKeyProvider()
        elif provider_type == "file":
            key_file = os.environ.get("ENCRYPTION_KEY_FILE")
            if not key_file:
                raise KeyError(
                    "ENCRYPTION_KEY_FILE must be set when ENCRYPTION_PROVIDER=file"
                )
            _provider_instance = FileKeyProvider(key_file)
        else:
            raise KeyError(
                f"Unknown/unsupported ENCRYPTION_PROVIDER: '{provider_type}'. "
                "Supported values: 'env', 'file'."
            )
    return _provider_instance
