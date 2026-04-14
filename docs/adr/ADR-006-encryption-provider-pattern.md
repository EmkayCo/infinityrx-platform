# ADR-006: Encryption provider pattern for ePHI at rest

**Status:** Accepted
**Date:** 2026-04-14
**Deciders:** Platform architecture / Security Officer

## Context

InfinityRx stores ePHI (member names, DOB, SSN, addresses, diagnosis codes,
provider information) across multiple PostgreSQL schemas. The HIPAA 2026 Final
Rule requires AES-256 encryption at rest for all ePHI. Two design decisions
needed to be made explicit:

1. **How is the encryption key managed?** Raw environment variables work for
   development but are not acceptable for production HIPAA deployment.
   Azure Key Vault provides FIPS 140-2 Level 3 certified HSM-backed storage.

2. **How is tenant isolation enforced at the encryption layer?** If all tenants
   share the same encryption key, a compromised key exposes all tenants' data
   simultaneously. If ciphertext can be cross-tenant-replayed, a SQL injection
   could expose another tenant's ePHI.

These issues were partially addressed (LESSON-006 context): `EncryptedString`
(`shared/crypto/sqlalchemy_types.py`) existed with AES-256-GCM but Key Vault
integration was listed as a planned item (audit CR-10).

## Decision

### Encryption algorithm

AES-256-GCM with:
- 256-bit data encryption key (DEK)
- 96-bit random nonce per encryption (not reused)
- 128-bit authentication tag (integrity protection)
- Additional Authenticated Data (AAD) = `f"tenant:{tenant_id}"` — ensures
  ciphertext from tenant A cannot be decrypted in tenant B's context

### Key hierarchy

```
Azure Key Vault (production)
    ├── Key Encryption Key (KEK) — RSA-4096, never exported
    │       Used to wrap/unwrap DEKs
    └── Data Encryption Keys (DEKs) — AES-256, one per tenant
            Stored as encrypted blobs in Key Vault Secrets
            Loaded at startup and cached in process memory (TTL: 1h)
```

For development: DEK loaded from `ENCRYPTION_KEY_ACTIVE` environment variable
(base64-encoded 32 bytes). The `ENCRYPTION_PROVIDER=env` setting enables this.

For production: `ENCRYPTION_PROVIDER=azure_keyvault`. The provider fetches
the DEK from Key Vault at startup, unwraps it using the KEK, and caches
the plaintext DEK in memory for the process lifetime (1 hour TTL, then re-fetch).

### Provider interface

```python
class EncryptionProvider(ABC):
    @abstractmethod
    def encrypt(self, plaintext: bytes, tenant_id: str) -> bytes: ...
    @abstractmethod
    def decrypt(self, ciphertext: bytes, tenant_id: str) -> bytes: ...
    @abstractmethod
    async def rotate_key(self, tenant_id: str) -> None: ...
```

Implementations:
- `EnvEncryptionProvider` — dev/test, key from env var
- `AzureKeyVaultProvider` — production, key from Key Vault

### EncryptedString type decorator

`shared/crypto/sqlalchemy_types.py` implements `EncryptedString` as a
SQLAlchemy `TypeDecorator`:
- `process_bind_param`: calls `provider.encrypt(value, tenant_id)` before write
- `process_result_value`: calls `provider.decrypt(ciphertext, tenant_id)` after read
- Tenant ID is sourced from `shared.db.tenant_context.current_tenant_id`

`PHIMixin` (`shared/db/models/phi_mixin.py`) applies `EncryptedString` to all
PHI columns automatically for any model that inherits it.

### Key rotation

1. Generate new DEK for the tenant.
2. Wrap new DEK with KEK, store in Key Vault.
3. Background job re-encrypts all PHI rows for the tenant in batches of 1000.
4. Old DEK is kept in Key Vault (soft-deleted) for 90 days to allow decryption
   of any records that may not have been re-encrypted yet.
5. After 90 days, old DEK is purged.
6. Key rotation is logged to the tamper-evident audit chain with
   `action="key_rotation"`.

Keys are rotated:
- Annually (scheduled)
- Immediately on suspected compromise
- On workforce member departure who had Key Vault access

### Key Vault integration plan

The `AzureKeyVaultProvider` is a planned implementation (audit CR-10).
Until it ships:
- Production deployments MUST use `ENCRYPTION_PROVIDER=env` with a
  secret injected by AKS Secrets Store CSI Driver from Key Vault.
- This is acceptable as a transitional measure: the key never touches the
  codebase, but it does reside in pod environment — not ideal for HSM-grade
  protection. Tracked as a prerequisite for HIPAA production certification.

---

## Alternatives considered

1. **Per-column encryption with different keys per PHI type.** Rejected:
   increases key management complexity significantly. AES-256-GCM with
   tenant-scoped AAD provides adequate isolation at the tenant level, which
   is our primary threat model.

2. **Transparent Database Encryption (TDE) only.** Rejected: TDE protects
   data at rest on disk but not in memory or in transit to the application.
   Application-level encryption protects against SQL injection attacks that
   could read plaintext values even from an encrypted tablespace.

3. **Column-level PostgreSQL pgcrypto.** Rejected: `pgcrypto` performs
   encryption in the database process, meaning the key must be present in
   the DB server — a more exposed attack surface than the application server.
   Also incompatible with our multi-cloud portability goal.

4. **Single shared key for all tenants.** Rejected: a single compromised
   key exposes all tenants. Tenant-scoped keys with AAD ensures blast radius
   is limited to a single tenant even if a key is extracted.

## Consequences

**Positive:**
- Cross-tenant PHI replay is computationally infeasible (AAD mismatch → GCM tag verification failure).
- Key never persists in source code, backups, or logs.
- Provider abstraction allows dev (env var) and prod (Key Vault) without code changes.
- Annual key rotation is operationally simple via the rotation job.

**Negative:**
- Application-level encryption adds ~1ms per encrypted column read/write.
  With 8 PHI columns per member record, a full member read costs ~8ms in
  encryption overhead — acceptable for HIPAA compliance.
- Re-encryption during key rotation requires a maintenance window or a
  rolling background job that handles concurrent reads/writes carefully.
- AzureKeyVaultProvider not yet implemented (CR-10 is an open critical finding).

## Cross-references

- Audit CR-02 — medical-claims PHI stored plaintext (not using EncryptedString)
- Audit CR-10 — no Azure Key Vault integration
- `shared/crypto/sqlalchemy_types.py` — EncryptedString
- `shared/db/models/phi_mixin.py` — PHIMixin
- `.claude/rules/phi-compliance.md` — PHI handling rules
- `.claude/rules/hipaa-2026.md` — AES-256 encryption requirement
- `docs/compliance/sop-device-media-controls.md` — encryption at rest SOP
