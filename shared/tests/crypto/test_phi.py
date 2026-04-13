"""Tests for shared.crypto.phi — field-level PHI encryption helpers."""

import base64
import logging
import os
import secrets
from datetime import date
from unittest import mock

import pytest

from shared.crypto.aes import DecryptionError
from shared.crypto.keys import get_key_provider
from shared.crypto.phi import (
    EncryptedName,
    decrypt_address,
    decrypt_dob,
    decrypt_name,
    decrypt_ssn,
    encrypt_address,
    encrypt_dob,
    encrypt_name,
    encrypt_ssn,
    ssn_last4,
)

# ---------------------------------------------------------------------------
# Provider setup
# ---------------------------------------------------------------------------

KEY_V1 = base64.b64encode(secrets.token_bytes(32)).decode()


@pytest.fixture(autouse=True)
def env_provider():
    with mock.patch.dict(
        os.environ,
        {
            "ENCRYPTION_KEY_ACTIVE": KEY_V1,
            "ENCRYPTION_KEY_ACTIVE_ID": "v1",
        },
    ):
        get_key_provider(_reset=True)
        yield
    import shared.crypto.keys as _keys_mod
    _keys_mod._provider_instance = None


# ---------------------------------------------------------------------------
# encrypt_name / decrypt_name
# ---------------------------------------------------------------------------


class TestEncryptName:
    def test_round_trip(self):
        enc = encrypt_name("John", "Doe", tenant_id="tenant_a")
        dec = decrypt_name(enc, tenant_id="tenant_a")
        assert dec.first == "John"
        assert dec.last == "Doe"

    def test_returns_encrypted_name_dataclass(self):
        enc = encrypt_name("Jane", "Smith", tenant_id="tenant_a")
        assert isinstance(enc, EncryptedName)
        assert isinstance(enc.first_encrypted, bytes)
        assert isinstance(enc.last_encrypted, bytes)

    def test_encrypted_blobs_not_plaintext(self):
        enc = encrypt_name("Alice", "Wonder", tenant_id="tenant_a")
        assert b"Alice" not in enc.first_encrypted
        assert b"Wonder" not in enc.last_encrypted

    def test_unicode_round_trip(self):
        enc = encrypt_name("José", "García", tenant_id="tenant_a")
        dec = decrypt_name(enc, tenant_id="tenant_a")
        assert dec.first == "José"
        assert dec.last == "García"

    def test_cross_tenant_decrypt_fails(self):
        enc = encrypt_name("Bob", "Jones", tenant_id="tenant_a")
        with pytest.raises(DecryptionError):
            decrypt_name(enc, tenant_id="tenant_b")


# ---------------------------------------------------------------------------
# encrypt_dob / decrypt_dob
# ---------------------------------------------------------------------------


class TestEncryptDob:
    def test_round_trip(self):
        dob = date(1985, 3, 15)
        ct = encrypt_dob(dob, tenant_id="tenant_a")
        assert decrypt_dob(ct, tenant_id="tenant_a") == dob

    def test_returns_bytes(self):
        ct = encrypt_dob(date(2000, 1, 1), tenant_id="tenant_a")
        assert isinstance(ct, bytes)

    def test_encrypted_bytes_not_plaintext(self):
        ct = encrypt_dob(date(1990, 6, 30), tenant_id="tenant_a")
        assert b"1990" not in ct
        assert b"1990-06-30" not in ct

    def test_cross_tenant_decrypt_fails(self):
        ct = encrypt_dob(date(1970, 1, 1), tenant_id="tenant_a")
        with pytest.raises(DecryptionError):
            decrypt_dob(ct, tenant_id="tenant_b")


# ---------------------------------------------------------------------------
# encrypt_ssn / decrypt_ssn
# ---------------------------------------------------------------------------


class TestEncryptSsn:
    def test_round_trip_9_digits(self):
        ct = encrypt_ssn("123456789", tenant_id="tenant_a")
        assert decrypt_ssn(ct, tenant_id="tenant_a") == "123456789"

    def test_returns_bytes(self):
        ct = encrypt_ssn("987654321", tenant_id="tenant_a")
        assert isinstance(ct, bytes)

    def test_encrypted_bytes_not_plaintext(self):
        ct = encrypt_ssn("111223333", tenant_id="tenant_a")
        assert b"111223333" not in ct

    def test_cross_tenant_decrypt_fails(self):
        ct = encrypt_ssn("444556666", tenant_id="tenant_a")
        with pytest.raises(DecryptionError):
            decrypt_ssn(ct, tenant_id="tenant_b")

    def test_rejects_non_9_digit_ssn_short(self):
        with pytest.raises(ValueError, match="[Ss][Ss][Nn]|9.digit"):
            encrypt_ssn("12345", tenant_id="tenant_a")

    def test_rejects_non_9_digit_ssn_long(self):
        with pytest.raises(ValueError, match="[Ss][Ss][Nn]|9.digit"):
            encrypt_ssn("1234567890", tenant_id="tenant_a")

    def test_rejects_non_digit_ssn(self):
        with pytest.raises(ValueError, match="[Ss][Ss][Nn]|9.digit|[Dd]igit"):
            encrypt_ssn("12345678a", tenant_id="tenant_a")

    def test_rejects_empty_ssn(self):
        with pytest.raises(ValueError):
            encrypt_ssn("", tenant_id="tenant_a")

    def test_rejects_ssn_with_dashes(self):
        # 123-45-6789 has dashes — 9 non-digit chars — should be rejected
        with pytest.raises(ValueError):
            encrypt_ssn("123-45-6789", tenant_id="tenant_a")


# ---------------------------------------------------------------------------
# encrypt_address / decrypt_address
# ---------------------------------------------------------------------------


class TestEncryptAddress:
    def test_round_trip_full_address(self):
        addr = {
            "street": "123 Main St",
            "city": "Springfield",
            "state": "IL",
            "zip": "62701",
            "country": "US",
        }
        ct = encrypt_address(addr, tenant_id="tenant_a")
        result = decrypt_address(ct, tenant_id="tenant_a")
        assert result == addr

    def test_returns_bytes(self):
        ct = encrypt_address({"street": "1 Elm St"}, tenant_id="tenant_a")
        assert isinstance(ct, bytes)

    def test_encrypted_bytes_not_plaintext(self):
        ct = encrypt_address({"street": "999 Secret St"}, tenant_id="tenant_a")
        assert b"999 Secret St" not in ct

    def test_cross_tenant_decrypt_fails(self):
        ct = encrypt_address({"city": "Gotham"}, tenant_id="tenant_a")
        with pytest.raises(DecryptionError):
            decrypt_address(ct, tenant_id="tenant_b")

    def test_empty_dict_round_trip(self):
        ct = encrypt_address({}, tenant_id="tenant_a")
        assert decrypt_address(ct, tenant_id="tenant_a") == {}


# ---------------------------------------------------------------------------
# ssn_last4
# ---------------------------------------------------------------------------


class TestSsnLast4:
    def test_returns_last_4_digits(self):
        ct = encrypt_ssn("123456789", tenant_id="tenant_a")
        assert ssn_last4(ct, tenant_id="tenant_a") == "6789"

    def test_returns_string(self):
        ct = encrypt_ssn("000000001", tenant_id="tenant_a")
        result = ssn_last4(ct, tenant_id="tenant_a")
        assert isinstance(result, str)
        assert len(result) == 4

    def test_last4_does_not_log_full_ssn(self, caplog):
        ssn = "987654321"
        ct = encrypt_ssn(ssn, tenant_id="tenant_a")
        with caplog.at_level(logging.DEBUG):
            last4 = ssn_last4(ct, tenant_id="tenant_a")
        # Full SSN must not appear in any log record
        for record in caplog.records:
            assert ssn not in record.getMessage()
        assert last4 == "4321"

    def test_cross_tenant_last4_fails(self):
        ct = encrypt_ssn("111223344", tenant_id="tenant_a")
        with pytest.raises(DecryptionError):
            ssn_last4(ct, tenant_id="tenant_b")
