"""PHIMixin — standard encrypted columns for any table holding patient PHI.

All Member / Patient / Prescriber tables that store personally
identifiable health information MUST inherit from ``PHIMixin`` so the
name / DOB / SSN / address columns are encrypted at rest via
``EncryptedString`` (AES-256-GCM). This satisfies HIPAA §164.312(a)(2)(iv)
"encryption and decryption" and §164.312(e)(2)(ii) transmission security
(ciphertext at rest cannot be read from a stolen backup).

Usage::

    from shared.db.base import Base
    from shared.db.models.phi_mixin import PHIMixin
    from sqlalchemy.orm import Mapped, mapped_column

    class Member(Base, PHIMixin):
        __tablename__ = "members"
        __table_args__ = ({"schema": "core"},)
        id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
        tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
        # ... your non-PHI columns here

Why a mixin vs per-column ``EncryptedString`` on the model directly?
    * One import, one audit point — reviewers check "does it use PHIMixin?"
      rather than "does every PHI column have EncryptedString?"
    * Uniform naming (``*_encrypted`` suffix) across modules so scanners
      and query-guards can pattern-match PHI columns.
    * Future-proof: adding a new standard PHI field (e.g., phone, email)
      is one change here and every inheriting table picks it up via a
      single migration.

Security properties preserved by inheritance:
    * Storage is LargeBinary (ciphertext); no plaintext ever touches disk
      or replication logs.
    * ``None`` passes through unchanged, so NULLability of PHI is still
      expressible (e.g., DOB optional for newborns pending registration).
    * Key rotation is transparent — AES key_id header lets old rows decrypt
      with historical keys while new rows bind to the current key.

What this mixin intentionally does NOT do:
    * Enforce nullability constraints — subclasses decide what's required.
    * Add tenant_id — not all PHI tables are tenant-scoped identically;
      subclasses add their own tenant_id column with the correct FK.
    * Add indexes — encrypted columns are not useful as index keys. If a
      table needs a searchable form (e.g., last-4 SSN), add a separate
      non-encrypted ``ssn_last4`` column and index that.
"""

from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column

from shared.crypto.sqlalchemy_types import EncryptedString

__all__ = ["PHIMixin"]


class PHIMixin:
    """Encrypted PHI columns for Member / Patient / Prescriber tables.

    All columns are optional at the SQL level (nullable=True). Subclasses
    tighten this by overriding with ``nullable=False`` when the record
    type demands the field (e.g., ``Member.dob_encrypted`` is required,
    but a ``PrescriberLite`` cache may store only a name).
    """

    first_name_encrypted: Mapped[str | None] = mapped_column(
        EncryptedString(), nullable=True
    )
    last_name_encrypted: Mapped[str | None] = mapped_column(
        EncryptedString(), nullable=True
    )
    # DOB stored as ISO-8601 ``YYYY-MM-DD`` string — avoids a Date column
    # that would leak information through index statistics. Callers parse
    # with datetime.date.fromisoformat on read.
    dob_encrypted: Mapped[str | None] = mapped_column(
        EncryptedString(), nullable=True
    )
    # SSN stored as the raw 9-digit string (no dashes). Validators live
    # with the Member service; the mixin owns only storage.
    ssn_encrypted: Mapped[str | None] = mapped_column(
        EncryptedString(), nullable=True
    )
    # Full address stored as a JSON string (serialized by caller) so we
    # get one encrypted column instead of five. Use ``EncryptedJSON`` in
    # a future extension if structured access is needed.
    address_encrypted: Mapped[str | None] = mapped_column(
        EncryptedString(), nullable=True
    )
