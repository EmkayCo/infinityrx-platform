"""shared.crypto.sqlalchemy_types — SQLAlchemy TypeDecorators for encrypted columns.

Usage example::

    from sqlalchemy import Column
    from shared.crypto.sqlalchemy_types import EncryptedString, EncryptedJSON

    class Member(Base):
        __tablename__ = "members"
        id = Column(UUID, primary_key=True)
        tenant_id = Column(String(50), nullable=False)
        full_name = Column(EncryptedString(), nullable=True)
        address = Column(EncryptedJSON(), nullable=True)

Both types store raw bytes (LargeBinary) on the database side.  All
encrypted values are unreadable without the active key.

``None`` values pass through unchanged (no encryption of NULL).

Key provider defaults to the singleton from
:func:`~shared.crypto.keys.get_key_provider`.  Override via the
``key_provider`` constructor argument for testing.

Associated data (AAD): pass ``associated_data=<bytes>`` to the constructor to
bind every value in the column to a fixed context.  For per-row AAD (e.g.,
binding to a tenant_id column), use the :func:`~shared.crypto.aes.encrypt` /
:func:`~shared.crypto.aes.decrypt` primitives directly in your model layer.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import LargeBinary
from sqlalchemy.types import TypeDecorator

from shared.crypto.aes import decrypt, encrypt
from shared.crypto.keys import KeyProvider, get_key_provider

__all__ = ["EncryptedString", "EncryptedJSON"]


class EncryptedString(TypeDecorator):
    """Stores a Python ``str`` as AES-256-GCM encrypted bytes in the database.

    The DB column type is ``LargeBinary``.  Transparently encrypts on write
    and decrypts on read.

    Args:
        key_provider: Override the default singleton key provider.
        associated_data: Optional bytes bound to every ciphertext in this
            column.  Must be supplied identically on decryption.
    """

    impl = LargeBinary
    cache_ok = True

    def __init__(
        self,
        *args: Any,
        key_provider: KeyProvider | None = None,
        associated_data: bytes | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._key_provider = key_provider
        self._associated_data = associated_data

    def _provider(self) -> KeyProvider:
        return self._key_provider or get_key_provider()

    def process_bind_param(self, value: str | None, dialect: Any) -> bytes | None:
        """Encrypt Python str → DB bytes."""
        if value is None:
            return None
        return encrypt(
            value.encode(),
            key_provider=self._provider(),
            associated_data=self._associated_data,
        )

    def process_result_value(self, value: bytes | None, dialect: Any) -> str | None:
        """Decrypt DB bytes → Python str."""
        if value is None:
            return None
        if isinstance(value, memoryview):
            value = bytes(value)
        return decrypt(
            value,
            key_provider=self._provider(),
            associated_data=self._associated_data,
        ).decode()


class EncryptedJSON(TypeDecorator):
    """Stores a Python object as JSON, then AES-256-GCM encrypted bytes in DB.

    The DB column type is ``LargeBinary``.  Serializes via :mod:`json` before
    encryption; deserializes after decryption.

    Args:
        key_provider: Override the default singleton key provider.
        associated_data: Optional bytes bound to every ciphertext in this
            column.
    """

    impl = LargeBinary
    cache_ok = True

    def __init__(
        self,
        *args: Any,
        key_provider: KeyProvider | None = None,
        associated_data: bytes | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._key_provider = key_provider
        self._associated_data = associated_data

    def _provider(self) -> KeyProvider:
        return self._key_provider or get_key_provider()

    def process_bind_param(self, value: Any | None, dialect: Any) -> bytes | None:
        """Serialize to JSON bytes then encrypt → DB bytes."""
        if value is None:
            return None
        serialized = json.dumps(value, separators=(",", ":")).encode()
        return encrypt(
            serialized,
            key_provider=self._provider(),
            associated_data=self._associated_data,
        )

    def process_result_value(self, value: bytes | None, dialect: Any) -> Any | None:
        """Decrypt DB bytes → deserialize JSON → Python object."""
        if value is None:
            return None
        if isinstance(value, memoryview):
            value = bytes(value)
        raw = decrypt(
            value,
            key_provider=self._provider(),
            associated_data=self._associated_data,
        )
        return json.loads(raw.decode())
