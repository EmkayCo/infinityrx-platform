"""Tests for shared.auth.passwords."""

from __future__ import annotations

import pytest

from shared.auth.passwords import bcrypt_rounds, hash_password, verify_password


class TestHashPassword:
    def test_round_trip_verifies(self) -> None:
        hashed = hash_password("correct horse battery staple")
        assert verify_password("correct horse battery staple", hashed) is True

    def test_wrong_password_fails(self) -> None:
        hashed = hash_password("s3cret!")
        assert verify_password("nope", hashed) is False

    def test_hash_is_salted_unique(self) -> None:
        a = hash_password("same-password")
        b = hash_password("same-password")
        assert a != b
        assert verify_password("same-password", a)
        assert verify_password("same-password", b)

    def test_empty_password_rejected(self) -> None:
        with pytest.raises(ValueError):
            hash_password("")

    def test_whitespace_password_rejected(self) -> None:
        with pytest.raises(ValueError):
            hash_password("   ")

    def test_non_string_password_rejected(self) -> None:
        with pytest.raises(ValueError):
            hash_password(None)  # type: ignore[arg-type]

    def test_configured_rounds_at_least_12(self) -> None:
        assert bcrypt_rounds() >= 12

    def test_hash_uses_bcrypt_prefix(self) -> None:
        h = hash_password("x")
        assert h.startswith("$2b$") or h.startswith("$2a$") or h.startswith("$2y$")


class TestVerifyPassword:
    def test_empty_plaintext_returns_false(self) -> None:
        hashed = hash_password("abc")
        assert verify_password("", hashed) is False

    def test_empty_hash_returns_false(self) -> None:
        assert verify_password("abc", "") is False

    def test_malformed_hash_returns_false(self) -> None:
        assert verify_password("abc", "not-a-bcrypt-hash") is False
