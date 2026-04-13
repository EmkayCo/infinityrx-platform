"""shared.crypto — PHI/PII encryption utilities for InfinityRx modules.

Provides AES-256-GCM field-level encryption, key management with rotation,
SQLAlchemy TypeDecorators, and PHI-specific helpers.

Import paths:
  from shared.crypto.keys import get_key_provider, EnvKeyProvider, FileKeyProvider
  from shared.crypto.aes import encrypt, decrypt, encrypt_str, decrypt_str
  from shared.crypto.sqlalchemy_types import EncryptedString, EncryptedJSON
  from shared.crypto.phi import encrypt_ssn, decrypt_ssn, ssn_last4, ...
"""
