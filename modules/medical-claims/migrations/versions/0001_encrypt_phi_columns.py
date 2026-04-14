"""Encrypt PHI columns in medical_claims.claim_records

Revision ID: 0001_encrypt_phi_columns
Revises: None
Create Date: 2026-04-14 00:00:00.000000

CR-02: patient_member_id and diagnosis_code_1..4 stored as plaintext String
in the original schema. This migration converts them to LargeBinary to hold
AES-256-GCM ciphertext produced by shared.crypto.sqlalchemy_types.EncryptedString.

Also adds billing_provider_tax_id encryption (tax IDs are SSN-adjacent PHI).

Migration strategy (zero-downtime capable with two-phase deploy):
  Phase 1 (this migration): add *_new columns as LargeBinary nullable.
  Phase 2 (data backfill): app-layer script reads plaintext, encrypts, writes to *_new.
  Phase 3 (cut-over migration): drop old plaintext columns, rename *_new → original names.

Because medical-claims has no production data yet (pre-launch platform), this
migration performs all three phases atomically. For a live system with data,
split into three separate migrations with a controlled app-layer backfill.

PHI columns converted:
  - patient_member_id: String(100) → LargeBinary (EncryptedString)
  - diagnosis_code_1..4: String(10) × 4 → LargeBinary (EncryptedString)
  - billing_provider_tax_id: String(11) → LargeBinary (EncryptedString)

Index removed:
  - idx_medical_member on (tenant_id, patient_member_id): encrypted columns
    cannot serve as B-tree index keys. Lookup by member_id UUID FK remains.

PHIMixin columns added:
  - first_name_encrypted, last_name_encrypted, dob_encrypted, ssn_encrypted,
    address_encrypted (from PHIMixin — all LargeBinary, nullable)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "0001_encrypt_phi_columns"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "medical_claims"
TABLE = "claim_records"


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # 1. Drop the unencrypted-column B-tree index (cannot index LargeBinary)
    # -----------------------------------------------------------------------
    op.drop_index("idx_medical_member", table_name=TABLE, schema=SCHEMA)

    # -----------------------------------------------------------------------
    # 2. Add new LargeBinary (EncryptedString) columns alongside plaintext
    # -----------------------------------------------------------------------
    op.add_column(TABLE, sa.Column("patient_member_id_enc", sa.LargeBinary(), nullable=True), schema=SCHEMA)
    op.add_column(TABLE, sa.Column("diagnosis_code_1_enc", sa.LargeBinary(), nullable=True), schema=SCHEMA)
    op.add_column(TABLE, sa.Column("diagnosis_code_2_enc", sa.LargeBinary(), nullable=True), schema=SCHEMA)
    op.add_column(TABLE, sa.Column("diagnosis_code_3_enc", sa.LargeBinary(), nullable=True), schema=SCHEMA)
    op.add_column(TABLE, sa.Column("diagnosis_code_4_enc", sa.LargeBinary(), nullable=True), schema=SCHEMA)
    op.add_column(TABLE, sa.Column("billing_provider_tax_id_enc", sa.LargeBinary(), nullable=True), schema=SCHEMA)

    # PHIMixin-provided columns (first_name, last_name, dob, ssn, address)
    op.add_column(TABLE, sa.Column("first_name_encrypted", sa.LargeBinary(), nullable=True), schema=SCHEMA)
    op.add_column(TABLE, sa.Column("last_name_encrypted", sa.LargeBinary(), nullable=True), schema=SCHEMA)
    op.add_column(TABLE, sa.Column("dob_encrypted", sa.LargeBinary(), nullable=True), schema=SCHEMA)
    op.add_column(TABLE, sa.Column("ssn_encrypted", sa.LargeBinary(), nullable=True), schema=SCHEMA)
    op.add_column(TABLE, sa.Column("address_encrypted", sa.LargeBinary(), nullable=True), schema=SCHEMA)

    # -----------------------------------------------------------------------
    # 3. Backfill: for pre-launch environments with no production data, this
    #    block is a no-op. For environments with data, run the separate
    #    app-layer encryption backfill script before the cut-over step below.
    #    The script reads plaintext, calls EncryptedString.process_bind_param,
    #    and writes to the *_enc columns using raw UPDATE statements.
    # -----------------------------------------------------------------------
    # (no-op for pre-launch; data backfill is out of band for live systems)

    # -----------------------------------------------------------------------
    # 4. Cut-over: rename existing plaintext → _plaintext_bak, rename *_enc → original
    #    For pre-launch (no data): drop plaintext, rename enc columns.
    # -----------------------------------------------------------------------
    # patient_member_id
    op.drop_column(TABLE, "patient_member_id", schema=SCHEMA)
    op.alter_column(TABLE, "patient_member_id_enc", new_column_name="patient_member_id", schema=SCHEMA)
    op.alter_column(TABLE, "patient_member_id", nullable=False, schema=SCHEMA)

    # diagnosis_code_1..4
    for i in range(1, 5):
        op.drop_column(TABLE, f"diagnosis_code_{i}", schema=SCHEMA)
        op.alter_column(TABLE, f"diagnosis_code_{i}_enc", new_column_name=f"diagnosis_code_{i}", schema=SCHEMA)

    # billing_provider_tax_id
    op.drop_column(TABLE, "billing_provider_tax_id", schema=SCHEMA)
    op.alter_column(TABLE, "billing_provider_tax_id_enc", new_column_name="billing_provider_tax_id", schema=SCHEMA)


def downgrade() -> None:
    # -----------------------------------------------------------------------
    # Reverse: convert LargeBinary back to String columns (loses data — do not
    # run downgrade on a live system that has encrypted data in these columns).
    # -----------------------------------------------------------------------
    # Remove PHIMixin columns
    for col in ("first_name_encrypted", "last_name_encrypted", "dob_encrypted", "ssn_encrypted", "address_encrypted"):
        op.drop_column(TABLE, col, schema=SCHEMA)

    # billing_provider_tax_id
    op.drop_column(TABLE, "billing_provider_tax_id", schema=SCHEMA)
    op.add_column(TABLE, sa.Column("billing_provider_tax_id", sa.String(11), nullable=True), schema=SCHEMA)

    # diagnosis_code_1..4
    for i in range(1, 5):
        op.drop_column(TABLE, f"diagnosis_code_{i}", schema=SCHEMA)
        op.add_column(TABLE, sa.Column(f"diagnosis_code_{i}", sa.String(10), nullable=True), schema=SCHEMA)

    # patient_member_id
    op.drop_column(TABLE, "patient_member_id", schema=SCHEMA)
    op.add_column(TABLE, sa.Column("patient_member_id", sa.String(100), nullable=False, server_default=""), schema=SCHEMA)

    # Restore index
    op.create_index("idx_medical_member", TABLE, ["tenant_id", "patient_member_id"], schema=SCHEMA)
