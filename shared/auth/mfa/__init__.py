"""shared.auth.mfa — HIPAA 2026 MFA primitives.

Provides TOTP, FIDO2/WebAuthn, backup codes, and challenge store.
All secrets are kept encrypted at rest via shared.crypto.
"""
