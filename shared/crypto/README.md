# shared.crypto

Application-level encryption primitives for InfinityRx. AES-256-GCM with
key rotation support, exposed both as standalone functions and as
SQLAlchemy `TypeDecorator`s.

## Mandatory rule: all PHI columns MUST use `EncryptedString`

HIPAA §164.312(a)(2)(iv) requires encryption of ePHI at rest. Any table
that stores patient-identifiable data (name, DOB, SSN, address, phone,
email, member IDs linkable to identity) must encrypt those columns. No
exceptions — a leaked disk image or stolen backup must not yield
plaintext PHI.

### Standard path: inherit `PHIMixin`

```python
from shared.db.base import Base
from shared.db.models.phi_mixin import PHIMixin
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

class Member(Base, PHIMixin):
    __tablename__ = "members"
    __table_args__ = ({"schema": "core"},)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    # Non-PHI columns only beyond this point.
    status: Mapped[str] = mapped_column(String(20), nullable=False)
```

Inheriting `PHIMixin` gives you `first_name_encrypted`, `last_name_encrypted`,
`dob_encrypted`, `ssn_encrypted`, `address_encrypted` — all stored as
`LargeBinary` ciphertext, transparently encrypted on write and decrypted
on read. The ORM sees Python `str`; disk sees AES-256-GCM bytes.

### Non-standard PHI fields: use `EncryptedString` directly

If your table holds a PHI field outside the mixin set (e.g., a medical
record number, a policy number, an email address), annotate it
explicitly:

```python
from shared.crypto.sqlalchemy_types import EncryptedString, EncryptedJSON

class Patient(Base, PHIMixin):
    __tablename__ = "patients"
    email_encrypted: Mapped[str | None] = mapped_column(EncryptedString(), nullable=True)
    insurance_history: Mapped[list | None] = mapped_column(EncryptedJSON(), nullable=True)
```

Column name convention: **`{field}_encrypted`** suffix so code reviewers
and static scanners can pattern-match PHI columns.

## What the encryption is

* **Algorithm:** AES-256 in GCM mode with a random 96-bit nonce per value.
* **Key management:** pluggable `KeyProvider` protocol in `shared.crypto.keys`.
  The default reads `ENCRYPTION_KEY_ACTIVE` (base64-encoded 32 bytes) +
  `ENCRYPTION_KEY_ACTIVE_ID` and additional retired keys from the
  environment. Azure Key Vault integration lives in the same module.
* **Key rotation:** ciphertexts prepend a short key-id header so rows
  encrypted under a retired key still decrypt via the retired key while
  new writes bind to the active one. Nothing to migrate at rotation.
* **AAD:** per-column associated data can be supplied via
  `EncryptedString(associated_data=b"tenant:42")` for additional
  context-binding. Per-row AAD requires the lower-level
  `shared.crypto.aes.encrypt/decrypt` primitives (see `shared.crypto.phi`).

## What `EncryptedString` does NOT provide

* **Searchability.** You cannot `WHERE ssn_encrypted = :ssn` because
  every write uses a fresh nonce, so the ciphertext for the same
  plaintext differs each time. If you need a search key, store a
  separate non-PHI derived column (e.g., `ssn_last4`, `email_sha256`)
  and index that. The mixin deliberately does not create those — pick
  whichever derivation your module actually needs.
* **Field-level access control.** Anyone with DB access + the active key
  can decrypt. Enforce PHI access via RBAC at the service layer.
* **Tenant isolation.** If cross-tenant leakage would be catastrophic
  for a column, bind an AAD of `tenant:{tenant_id}` via the lower-level
  `shared.crypto.phi` helpers — decryption then fails if the wrong tenant
  tries to read the row.

## What happens if the key is wrong

`EncryptedString.process_result_value` raises `DecryptionError` on an
auth-tag mismatch. The ORM lets this propagate. Investigate the key
provider configuration — do not silently swallow it.

## Migration recipe: add PHI encryption to an existing column

1. Add a new `*_encrypted` column via Alembic (nullable, `LargeBinary`).
2. Write a data-migration step that reads plaintext, encrypts via
   `shared.crypto.aes.encrypt`, writes ciphertext.
3. Drop the plaintext column.
4. Rename `*_encrypted` to its final name if desired.

Never leave both plaintext and ciphertext columns in prod — the
plaintext is the weak link.
