"""NPPES normalized satellite tables.

Creates:
  prescriber_dir.nppes_prescriber_details
  prescriber_dir.prescriber_addresses
  prescriber_dir.prescriber_taxonomies
  prescriber_dir.prescriber_identifiers

Revision ID: 0001_nppes
Revises: None
Create Date: 2026-04-14

LESSON-011: Global reference tables — no tenant_id, no TenantScopedMixin.
LESSON-010: NPI plaintext — public identifier, do NOT encrypt.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_nppes"
down_revision: Union[str, None] = "0000_prescriber_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "prescriber_dir"


def upgrade() -> None:
    # Ensure schema exists
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    # ── nppes_prescriber_details ─────────────────────────────────────────
    op.create_table(
        "nppes_prescriber_details",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("npi", sa.String(10), nullable=False),
        sa.Column("entity_type_code", sa.String(1), nullable=True),
        sa.Column("replacement_npi", sa.String(10), nullable=True),
        sa.Column("ein", sa.String(20), nullable=True),
        sa.Column("provider_last_name_legal", sa.String(100), nullable=True),
        sa.Column("provider_first_name", sa.String(100), nullable=True),
        sa.Column("provider_middle_name", sa.String(100), nullable=True),
        sa.Column("provider_name_prefix", sa.String(10), nullable=True),
        sa.Column("provider_name_suffix", sa.String(10), nullable=True),
        sa.Column("provider_credential_text", sa.String(100), nullable=True),
        sa.Column("provider_organization_name_legal", sa.String(255), nullable=True),
        sa.Column("provider_other_organization_name", sa.String(255), nullable=True),
        sa.Column("provider_other_organization_name_type_code", sa.String(2), nullable=True),
        sa.Column("provider_other_last_name", sa.String(100), nullable=True),
        sa.Column("provider_other_first_name", sa.String(100), nullable=True),
        sa.Column("provider_other_middle_name", sa.String(100), nullable=True),
        sa.Column("provider_other_name_prefix", sa.String(10), nullable=True),
        sa.Column("provider_other_name_suffix", sa.String(10), nullable=True),
        sa.Column("provider_other_credential_text", sa.String(100), nullable=True),
        sa.Column("provider_other_last_name_type_code", sa.String(2), nullable=True),
        sa.Column("provider_enumeration_date", sa.Date(), nullable=True),
        sa.Column("last_update_date", sa.Date(), nullable=True),
        sa.Column("npi_deactivation_reason_code", sa.String(2), nullable=True),
        sa.Column("npi_deactivation_date", sa.Date(), nullable=True),
        sa.Column("npi_reactivation_date", sa.Date(), nullable=True),
        sa.Column("certification_date", sa.Date(), nullable=True),
        sa.Column("provider_gender_code", sa.String(1), nullable=True),
        sa.Column("is_sole_proprietor", sa.String(1), nullable=True),
        sa.Column("is_organization_subpart", sa.String(1), nullable=True),
        sa.Column("parent_organization_lbn", sa.String(255), nullable=True),
        sa.Column("parent_organization_tin", sa.String(20), nullable=True),
        sa.Column("authorized_official_last_name", sa.String(100), nullable=True),
        sa.Column("authorized_official_first_name", sa.String(100), nullable=True),
        sa.Column("authorized_official_middle_name", sa.String(100), nullable=True),
        sa.Column("authorized_official_title_or_position", sa.String(100), nullable=True),
        sa.Column("authorized_official_telephone_number", sa.String(30), nullable=True),
        sa.Column("authorized_official_credential", sa.String(50), nullable=True),
        sa.Column("authorized_official_name_prefix", sa.String(10), nullable=True),
        sa.Column("authorized_official_name_suffix", sa.String(10), nullable=True),
        sa.Column("nppes_loaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("npi", name="uq_nppes_detail_npi"),
        schema=_SCHEMA,
    )
    op.create_index("idx_nppes_detail_npi", "nppes_prescriber_details", ["npi"], schema=_SCHEMA)
    op.create_index(
        "idx_nppes_detail_entity_type",
        "nppes_prescriber_details",
        ["entity_type_code"],
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_nppes_detail_enumeration_date",
        "nppes_prescriber_details",
        ["provider_enumeration_date"],
        schema=_SCHEMA,
    )

    # ── prescriber_addresses ─────────────────────────────────────────────
    op.create_table(
        "prescriber_addresses",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("npi", sa.String(10), nullable=False),
        sa.Column("address_type", sa.String(10), nullable=False),
        sa.Column("line_1", sa.String(255), nullable=True),
        sa.Column("line_2", sa.String(255), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(2), nullable=True),
        sa.Column("postal_code", sa.String(20), nullable=True),
        sa.Column("country_code", sa.String(3), nullable=True),
        sa.Column("telephone_number", sa.String(30), nullable=True),
        sa.Column("fax_number", sa.String(30), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("npi", "address_type", name="uq_prescriber_address_npi_type"),
        schema=_SCHEMA,
    )
    op.create_index("idx_prescriber_addr_npi", "prescriber_addresses", ["npi"], schema=_SCHEMA)

    # ── prescriber_taxonomies ────────────────────────────────────────────
    op.create_table(
        "prescriber_taxonomies",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("npi", sa.String(10), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("taxonomy_code", sa.String(20), nullable=True),
        sa.Column("license_number", sa.String(100), nullable=True),
        sa.Column("license_state_code", sa.String(2), nullable=True),
        sa.Column("is_primary", sa.String(1), nullable=True),
        sa.Column("taxonomy_group", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("npi", "sequence", name="uq_prescriber_taxonomy_npi_seq"),
        schema=_SCHEMA,
    )
    op.create_index("idx_prescriber_tax_npi", "prescriber_taxonomies", ["npi"], schema=_SCHEMA)
    op.create_index(
        "idx_prescriber_tax_code", "prescriber_taxonomies", ["taxonomy_code"], schema=_SCHEMA
    )
    op.create_index(
        "idx_prescriber_tax_license",
        "prescriber_taxonomies",
        ["license_number", "license_state_code"],
        schema=_SCHEMA,
    )

    # ── prescriber_identifiers ───────────────────────────────────────────
    op.create_table(
        "prescriber_identifiers",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("npi", sa.String(10), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("identifier", sa.String(100), nullable=True),
        sa.Column("identifier_type_code", sa.String(2), nullable=True),
        sa.Column("identifier_state", sa.String(2), nullable=True),
        sa.Column("identifier_issuer", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("npi", "sequence", name="uq_prescriber_identifier_npi_seq"),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_prescriber_ident_npi", "prescriber_identifiers", ["npi"], schema=_SCHEMA
    )


def downgrade() -> None:
    op.drop_table("prescriber_identifiers", schema=_SCHEMA)
    op.drop_table("prescriber_taxonomies", schema=_SCHEMA)
    op.drop_table("prescriber_addresses", schema=_SCHEMA)
    op.drop_table("nppes_prescriber_details", schema=_SCHEMA)
