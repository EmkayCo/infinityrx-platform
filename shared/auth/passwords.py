"""Password hashing and verification using bcrypt.

We use the ``bcrypt`` library directly rather than passlib because passlib's
bcrypt backend is incompatible with bcrypt>=4.1 on Python 3.13 (it tries to
read ``bcrypt.__about__`` which no longer exists and then fails on its
backend probe). The bcrypt primitives are stable and give us full control.

- Minimum cost factor: 12 rounds
- Empty/whitespace passwords are rejected
- Passwords longer than 72 bytes (bcrypt's hard cap) are rejected explicitly
  so we never silently truncate security-critical input
- Verification uses bcrypt's ``checkpw`` which performs a constant-time
  comparison internally
"""

from __future__ import annotations

import bcrypt

_BCRYPT_ROUNDS = 12
_BCRYPT_MAX_BYTES = 72


def hash_password(plaintext: str) -> str:
    """Return a bcrypt hash of *plaintext*.

    Raises:
        ValueError: if plaintext is not a non-empty string, is whitespace
            only, or exceeds bcrypt's 72-byte limit.
    """
    if not isinstance(plaintext, str) or not plaintext.strip():
        raise ValueError("password must be a non-empty string")
    encoded = plaintext.encode("utf-8")
    if len(encoded) > _BCRYPT_MAX_BYTES:
        raise ValueError(f"password exceeds {_BCRYPT_MAX_BYTES}-byte bcrypt limit")
    salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    return bcrypt.hashpw(encoded, salt).decode("ascii")


def verify_password(plaintext: str, hashed: str) -> bool:
    """Return True iff *plaintext* matches *hashed*.

    Empty/invalid inputs return False rather than raising so call sites
    cannot accidentally short-circuit authentication on malformed input.
    """
    if not plaintext or not hashed:
        return False
    try:
        encoded = plaintext.encode("utf-8")
        if len(encoded) > _BCRYPT_MAX_BYTES:
            return False
        return bcrypt.checkpw(encoded, hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False


def bcrypt_rounds() -> int:
    """Expose configured cost factor for verification in tests."""
    return _BCRYPT_ROUNDS
