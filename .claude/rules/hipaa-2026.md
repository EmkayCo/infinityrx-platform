# HIPAA 2026 Rules

## MFA (Required — no longer addressable)
- MUST enforce MFA for all ePHI access — SMS is insufficient, TOTP or FIDO2 required.
- MUST force MFA enrollment on first login when `tenant.mfa_required` is true.

## Encryption (Required — no longer addressable)
- MUST encrypt ALL ePHI at rest with AES-256.
- MUST use TLS 1.3 for all data in transit (TLS 1.2 minimum for legacy).

## Audit (Tamper-evident)
- MUST compute `entry_hash` on EVERY audit log write — never write with empty hash.
- MUST maintain hash chain (each entry includes hash of previous entry).
- MUST run daily integrity verification job.
- MUST NOT modify or delete audit entries.

## Restoration
- MUST demonstrate 72-hour system restoration capability.
- MUST have documented and TESTED backup/restore procedure.
- MUST run weekly verified restore test.

## Sessions
- MUST enforce automatic session timeout (default: 15 minutes inactivity).
- MUST limit concurrent sessions per user (default: 5).
