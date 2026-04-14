"""Unit tests for file encryption service — PHI/security path, 100% coverage."""
from __future__ import annotations


from src.services.encryption import FileEncryptionService


class TestFileEncryptionService:
    def test_encrypt_returns_result(self):
        svc = FileEncryptionService()
        result = svc.encrypt(b"hello world")
        assert result.ciphertext_b64 != ""
        assert result.nonce_b64 != ""
        assert result.key_ref is not None

    def test_decrypt_roundtrip(self):
        svc = FileEncryptionService()
        plaintext = b"NACHA file content with sensitive bank data"
        encrypted = svc.encrypt(plaintext)
        decrypted = svc.decrypt(encrypted)
        assert decrypted.plaintext == plaintext

    def test_different_plaintexts_produce_different_ciphertexts(self):
        svc = FileEncryptionService()
        r1 = svc.encrypt(b"data one")
        r2 = svc.encrypt(b"data two")
        assert r1.ciphertext_b64 != r2.ciphertext_b64

    def test_custom_key_ref(self):
        svc = FileEncryptionService(key_ref="azure-kv://prod-key")
        result = svc.encrypt(b"test")
        assert result.key_ref == "azure-kv://prod-key"

    def test_encrypt_empty_bytes(self):
        svc = FileEncryptionService()
        result = svc.encrypt(b"")
        decrypted = svc.decrypt(result)
        assert decrypted.plaintext == b""

    def test_encrypt_large_file(self):
        svc = FileEncryptionService()
        large_data = b"X" * 1_000_000
        encrypted = svc.encrypt(large_data)
        decrypted = svc.decrypt(encrypted)
        assert decrypted.plaintext == large_data

    def test_base64_dev_fallback_decrypt(self):
        from src.services.encryption import EncryptionResult
        svc = FileEncryptionService()
        import base64
        fallback = EncryptionResult(
            ciphertext_b64=base64.b64encode(b"plaintext").decode(),
            nonce_b64=base64.b64encode(b"\x00" * 12).decode(),
            key_ref="local-dev",
            algorithm="base64-dev-only",
        )
        decrypted = svc.decrypt(fallback)
        assert decrypted.plaintext == b"plaintext"

    def test_encrypt_fallback_when_cryptography_unavailable(self):
        import sys
        from unittest.mock import patch
        svc = FileEncryptionService()
        with patch.dict(sys.modules, {"cryptography.hazmat.primitives.ciphers.aead": None}):
            result = svc.encrypt(b"test data")
        assert result.algorithm == "base64-dev-only"

    def test_decrypt_fallback_when_cryptography_unavailable(self):
        import sys
        import base64
        from unittest.mock import patch
        from src.services.encryption import EncryptionResult
        svc = FileEncryptionService()
        ciphertext = base64.b64encode(b"test data").decode()
        er = EncryptionResult(
            ciphertext_b64=ciphertext,
            nonce_b64=base64.b64encode(b"\x00" * 12).decode(),
            key_ref="local-dev",
            algorithm="AES-256-GCM",
        )
        with patch.dict(sys.modules, {"cryptography.hazmat.primitives.ciphers.aead": None}):
            result = svc.decrypt(er)
        assert result.plaintext == b"test data"
