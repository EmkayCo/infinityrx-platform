"""Tests for shared.crypto.aes — AES-256-GCM encrypt/decrypt primitives."""

import base64
import os
import secrets
from unittest import mock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from shared.crypto.aes import (
    DecryptionError,
    decrypt,
    decrypt_str,
    encrypt,
    encrypt_str,
)
from shared.crypto.keys import get_key_provider

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_key_b64(n_bytes: int = 32) -> str:
    return base64.b64encode(secrets.token_bytes(n_bytes)).decode()


KEY_V1 = _make_key_b64()
KEY_V0 = _make_key_b64()


@pytest.fixture()
def env_provider():
    """Return an EnvKeyProvider with a single active key."""
    with mock.patch.dict(
        os.environ,
        {
            "ENCRYPTION_KEY_ACTIVE": KEY_V1,
            "ENCRYPTION_KEY_ACTIVE_ID": "v1",
        },
    ):
        yield get_key_provider(_reset=True)


@pytest.fixture()
def rotation_provider():
    """Return an EnvKeyProvider with v1 active and v0 as old key."""
    with mock.patch.dict(
        os.environ,
        {
            "ENCRYPTION_KEY_ACTIVE": KEY_V1,
            "ENCRYPTION_KEY_ACTIVE_ID": "v1",
            "ENCRYPTION_KEY_v0": KEY_V0,
        },
    ):
        yield get_key_provider(_reset=True)


# ---------------------------------------------------------------------------
# Round-trip: bytes
# ---------------------------------------------------------------------------


class TestEncryptDecryptBytes:
    def test_round_trip_simple(self, env_provider):
        plaintext = b"Hello, World!"
        ciphertext = encrypt(plaintext, key_provider=env_provider)
        assert decrypt(ciphertext, key_provider=env_provider) == plaintext

    def test_round_trip_empty_bytes(self, env_provider):
        ciphertext = encrypt(b"", key_provider=env_provider)
        assert decrypt(ciphertext, key_provider=env_provider) == b""

    def test_round_trip_large_payload(self, env_provider):
        plaintext = secrets.token_bytes(10_000)
        ciphertext = encrypt(plaintext, key_provider=env_provider)
        assert decrypt(ciphertext, key_provider=env_provider) == plaintext

    def test_ciphertext_is_bytes(self, env_provider):
        ct = encrypt(b"test", key_provider=env_provider)
        assert isinstance(ct, bytes)

    def test_ciphertext_length_greater_than_plaintext(self, env_provider):
        plaintext = b"short"
        ct = encrypt(plaintext, key_provider=env_provider)
        # header + nonce (12) + ciphertext+tag (len+16)
        assert len(ct) > len(plaintext)


# ---------------------------------------------------------------------------
# Round-trip: strings
# ---------------------------------------------------------------------------


class TestEncryptDecryptStr:
    def test_round_trip_simple(self, env_provider):
        plaintext = "member name: John Doe"
        ct = encrypt_str(plaintext, key_provider=env_provider)
        assert decrypt_str(ct, key_provider=env_provider) == plaintext

    def test_encrypt_str_returns_str(self, env_provider):
        ct = encrypt_str("test", key_provider=env_provider)
        assert isinstance(ct, str)

    def test_round_trip_unicode(self, env_provider):
        plaintext = "Ñoño — café résumé 日本語"
        ct = encrypt_str(plaintext, key_provider=env_provider)
        assert decrypt_str(ct, key_provider=env_provider) == plaintext

    def test_encrypted_str_is_valid_base64url(self, env_provider):
        ct = encrypt_str("test data", key_provider=env_provider)
        # Should not raise
        decoded = base64.urlsafe_b64decode(ct + "==")
        assert isinstance(decoded, bytes)


# ---------------------------------------------------------------------------
# Nonce randomness: same plaintext → different ciphertexts
# ---------------------------------------------------------------------------


class TestNonceRandomness:
    def test_same_plaintext_different_ciphertext(self, env_provider):
        plaintext = b"determinism test"
        ct1 = encrypt(plaintext, key_provider=env_provider)
        ct2 = encrypt(plaintext, key_provider=env_provider)
        assert ct1 != ct2

    def test_multiple_encryptions_all_different(self, env_provider):
        results = {encrypt(b"x", key_provider=env_provider) for _ in range(20)}
        assert len(results) == 20  # all unique nonces


# ---------------------------------------------------------------------------
# Associated Data (AAD)
# ---------------------------------------------------------------------------


class TestAssociatedData:
    def test_round_trip_with_aad(self, env_provider):
        aad = b"tenant:acme"
        plaintext = b"sensitive data"
        ct = encrypt(plaintext, key_provider=env_provider, associated_data=aad)
        result = decrypt(ct, key_provider=env_provider, associated_data=aad)
        assert result == plaintext

    def test_aad_mismatch_raises_decryption_error(self, env_provider):
        ct = encrypt(b"data", key_provider=env_provider, associated_data=b"tenant:acme")
        with pytest.raises(DecryptionError):
            decrypt(ct, key_provider=env_provider, associated_data=b"tenant:evil")

    def test_missing_aad_on_decrypt_raises(self, env_provider):
        ct = encrypt(b"data", key_provider=env_provider, associated_data=b"tenant:acme")
        with pytest.raises(DecryptionError):
            decrypt(ct, key_provider=env_provider)  # no AAD

    def test_unexpected_aad_on_decrypt_raises(self, env_provider):
        ct = encrypt(b"data", key_provider=env_provider)  # no AAD
        with pytest.raises(DecryptionError):
            decrypt(ct, key_provider=env_provider, associated_data=b"tenant:acme")


# ---------------------------------------------------------------------------
# Error cases: truncated / corrupted blob
# ---------------------------------------------------------------------------


class TestDecryptionErrors:
    def test_empty_blob_raises(self, env_provider):
        with pytest.raises(DecryptionError, match="[Tt]runcated|[Ss]hort|[Ii]nvalid"):
            decrypt(b"", key_provider=env_provider)

    def test_single_byte_raises(self, env_provider):
        with pytest.raises(DecryptionError):
            decrypt(b"\x00", key_provider=env_provider)

    def test_truncated_after_key_id_raises(self, env_provider):
        # Build a blob with just the key_id header, no nonce/ciphertext
        key_id = b"v1"
        blob = bytes([len(key_id)]) + key_id  # no nonce, no ciphertext
        with pytest.raises(DecryptionError):
            decrypt(blob, key_provider=env_provider)

    def test_bit_flip_raises(self, env_provider):
        plaintext = b"sensitive"
        ct = bytearray(encrypt(plaintext, key_provider=env_provider))
        ct[-1] ^= 0xFF  # flip last byte (in auth tag)
        with pytest.raises(DecryptionError):
            decrypt(bytes(ct), key_provider=env_provider)

    def test_wrong_key_raises(self, env_provider):
        ct = encrypt(b"data", key_provider=env_provider)
        # Create a new provider with a different key but same id "v1"
        different_key = _make_key_b64()
        with mock.patch.dict(
            os.environ,
            {
                "ENCRYPTION_KEY_ACTIVE": different_key,
                "ENCRYPTION_KEY_ACTIVE_ID": "v1",
            },
        ):
            wrong_provider = get_key_provider(_reset=True)
            with pytest.raises(DecryptionError):
                decrypt(ct, key_provider=wrong_provider)

    def test_unknown_key_id_in_blob_raises(self, env_provider):
        # Craft a blob claiming key_id "v99" which doesn't exist in provider
        key_id = b"v99"
        nonce = secrets.token_bytes(12)
        fake_tag = secrets.token_bytes(16)
        blob = bytes([len(key_id)]) + key_id + nonce + fake_tag
        with pytest.raises(DecryptionError, match="[Kk]ey"):
            decrypt(blob, key_provider=env_provider)

    def test_blob_with_key_id_len_larger_than_blob_raises(self, env_provider):
        # key_id_len says 10 but only 3 bytes follow
        blob = bytes([10]) + b"abc"
        with pytest.raises(DecryptionError, match="[Tt]runcated"):
            decrypt(blob, key_provider=env_provider)

    def test_payload_too_short_for_auth_tag_raises(self, env_provider):
        # Valid header + nonce, but only a few ciphertext bytes (< 16)
        key_id = b"v1"
        nonce = secrets.token_bytes(12)
        short_payload = secrets.token_bytes(4)  # need >= 16 for GCM tag
        blob = bytes([len(key_id)]) + key_id + nonce + short_payload
        with pytest.raises(DecryptionError, match="[Tt]runcated"):
            decrypt(blob, key_provider=env_provider)

    def test_decrypt_str_invalid_base64url_raises(self, env_provider):
        with pytest.raises(DecryptionError, match="[Bb]ase64|[Ii]nvalid"):
            # pass something that will fail base64 decode
            decrypt_str("!!not-base64url!!", key_provider=env_provider)


# ---------------------------------------------------------------------------
# Key rotation: encrypt with v0, active is v1, still decryptable
# ---------------------------------------------------------------------------


class TestKeyRotation:
    def test_decrypt_data_encrypted_with_old_key(self, rotation_provider):
        # Simulate: data was encrypted when v0 was active
        old_key_b64 = KEY_V0
        import os as _os
        with mock.patch.dict(
            _os.environ,
            {
                "ENCRYPTION_KEY_ACTIVE": old_key_b64,
                "ENCRYPTION_KEY_ACTIVE_ID": "v0",
            },
        ):
            old_provider = get_key_provider(_reset=True)
            plaintext = b"old record data"
            ct = encrypt(plaintext, key_provider=old_provider)

        # Now rotation_provider has v1 active + v0 for rotation
        result = decrypt(ct, key_provider=rotation_provider)
        assert result == plaintext

    def test_new_data_encrypted_with_new_key(self, rotation_provider):
        ct = encrypt(b"new data", key_provider=rotation_provider)
        # Key id in blob header should be v1 (active key)
        key_id_len = ct[0]
        key_id = ct[1 : 1 + key_id_len].decode()
        assert key_id == "v1"


# ---------------------------------------------------------------------------
# Property-based test: arbitrary strings survive round-trip
# ---------------------------------------------------------------------------


@given(st.text(min_size=0, max_size=500))
@settings(max_examples=100)
def test_encrypt_str_round_trip_arbitrary(text: str):
    with mock.patch.dict(
        os.environ,
        {
            "ENCRYPTION_KEY_ACTIVE": KEY_V1,
            "ENCRYPTION_KEY_ACTIVE_ID": "v1",
        },
    ):
        provider = get_key_provider(_reset=True)
        ct = encrypt_str(text, key_provider=provider)
        assert decrypt_str(ct, key_provider=provider) == text
