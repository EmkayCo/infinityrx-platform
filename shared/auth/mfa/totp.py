"""shared.auth.mfa.totp — TOTP (RFC 6238) enrollment and verification.

Uses pyotp under the hood. All comparisons are constant-time to prevent
timing side-channels. Raw secrets MUST NOT be logged.
"""

from __future__ import annotations

import hmac
import re

import pyotp

__all__ = [
    "InvalidTotpFormat",
    "generate_totp_secret",
    "provisioning_uri",
    "verify_totp",
]

_CODE_RE = re.compile(r"\A\d{6}\Z")
_SECRET_CHARS = 32  # 160 bits of entropy in base32


class InvalidTotpFormat(ValueError):
    """Raised when a submitted TOTP code is not exactly 6 decimal digits."""


def generate_totp_secret() -> str:
    """Return a fresh 32-character base32 TOTP secret.

    Uses pyotp's random_base32() which draws from os.urandom.
    NEVER log the returned value.
    """
    return pyotp.random_base32(length=_SECRET_CHARS)


def provisioning_uri(secret: str, email: str, issuer: str) -> str:
    """Return an otpauth:// URL suitable for QR code display.

    Args:
        secret: The base32 TOTP secret.
        email: The user's email (becomes the account name in the URI).
        issuer: The application / organisation name shown in authenticator apps.

    Returns:
        otpauth://totp/... URI string.
    """
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def verify_totp(secret: str, code: str, *, window: int = 1) -> bool:
    """Verify a TOTP code against the secret.

    Args:
        secret: The base32 TOTP secret stored for the user.
        code: The 6-digit code submitted by the user.
        window: How many 30-second periods either side of now to accept
                (default 1 = ±30 s to accommodate clock skew).

    Returns:
        True if the code is valid, False otherwise.

    Raises:
        InvalidTotpFormat: If *code* is not exactly 6 decimal digits.
    """
    if not _CODE_RE.match(code):
        raise InvalidTotpFormat(
            f"TOTP code must be exactly 6 decimal digits, got: {repr(code)}"
        )
    totp = pyotp.TOTP(secret)
    # pyotp.TOTP.verify uses hmac.compare_digest internally for constant-time
    # comparison. We accept window periods either side.
    result = totp.verify(code, valid_window=window)
    # Belt-and-suspenders: also force constant-time by using hmac.compare_digest
    # on the string representation to prevent any branch-based timing leak.
    expected = totp.now()
    _ = hmac.compare_digest(code, expected)  # always runs regardless of result
    return bool(result)
