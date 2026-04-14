"""Normalized NPPES reference tables for the prescriber-directory module.

Schema: prescriber_dir

Three satellite tables are added to hold the full NPPES V2 column set:
  - NppesPrescriberDetail  (all 300+ fields from NPPES not in Prescriber)
  - PrescriberAddress      (up to 2 per NPI: mailing + practice)
  - PrescriberTaxonomy     (up to 15 per NPI, exploded from _1.._15 groups)
  - PrescriberIdentifier   (up to 50 per NPI, exploded from _1.._50 groups)

LESSON-010: NPI is a public NPPES registry identifier — plaintext OK, do NOT encrypt.
LESSON-011: These are global reference tables — no TenantScopedMixin, no tenant_id.

The existing Prescriber model in tables.py is the canonical core record.
These tables extend it with the full NPPES column payload rather than
duplicating the core model.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .tables import PrescriberBase


class PrescriberAddress(PrescriberBase):
    """Up to 2 address rows per NPI: mailing and practice.

    LESSON-011: global reference — no TenantScopedMixin.
    """

    __tablename__ = "prescriber_addresses"
    __table_args__ = (
        UniqueConstraint("npi", "address_type", name="uq_prescriber_address_npi_type"),
        Index("idx_prescriber_addr_npi", "npi"),
        {"schema": "prescriber_dir"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    npi: Mapped[str] = mapped_column(String(10), nullable=False)
    address_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "mailing" | "practice"
    line_1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    line_2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    telephone_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    fax_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PrescriberTaxonomy(PrescriberBase):
    """Exploded taxonomy rows — up to 15 per NPI.

    LESSON-011: global reference — no TenantScopedMixin.
    Indexed on (taxonomy_code) and (license_number, license_state_code) per spec.
    """

    __tablename__ = "prescriber_taxonomies"
    __table_args__ = (
        UniqueConstraint("npi", "sequence", name="uq_prescriber_taxonomy_npi_seq"),
        Index("idx_prescriber_tax_npi", "npi"),
        Index("idx_prescriber_tax_code", "taxonomy_code"),
        Index("idx_prescriber_tax_license", "license_number", "license_state_code"),
        {"schema": "prescriber_dir"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    npi: Mapped[str] = mapped_column(String(10), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)  # 1–15
    taxonomy_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    license_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    license_state_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    is_primary: Mapped[str | None] = mapped_column(String(1), nullable=True)  # Y / N / X
    taxonomy_group: Mapped[str | None] = mapped_column(String(100), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PrescriberIdentifier(PrescriberBase):
    """Exploded other-provider identifier rows — up to 50 per NPI.

    LESSON-011: global reference — no TenantScopedMixin.
    """

    __tablename__ = "prescriber_identifiers"
    __table_args__ = (
        UniqueConstraint("npi", "sequence", name="uq_prescriber_identifier_npi_seq"),
        Index("idx_prescriber_ident_npi", "npi"),
        {"schema": "prescriber_dir"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    npi: Mapped[str] = mapped_column(String(10), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)  # 1–50
    identifier: Mapped[str | None] = mapped_column(String(100), nullable=True)
    identifier_type_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    identifier_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    identifier_issuer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NppesPrescriberDetail(PrescriberBase):
    """Full NPPES V2 detail row — all fields not stored in the core Prescriber model.

    One row per NPI.  Stores the extended columns from NPPES: replacement NPI,
    EIN, full authorized-official fields, sole-proprietor, parent-org, etc.

    LESSON-010: NPI plaintext — public reference identifier.
    LESSON-011: global reference — no TenantScopedMixin.
    """

    __tablename__ = "nppes_prescriber_details"
    __table_args__ = (
        UniqueConstraint("npi", name="uq_nppes_detail_npi"),
        Index("idx_nppes_detail_npi", "npi"),
        Index("idx_nppes_detail_entity_type", "entity_type_code"),
        Index("idx_nppes_detail_enumeration_date", "provider_enumeration_date"),
        {"schema": "prescriber_dir"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # --- Core identifiers ---
    npi: Mapped[str] = mapped_column(String(10), nullable=False)
    entity_type_code: Mapped[str | None] = mapped_column(String(1), nullable=True)  # 1 | 2
    replacement_npi: Mapped[str | None] = mapped_column(String(10), nullable=True)
    ein: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # --- Individual name (legal) ---
    provider_last_name_legal: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_middle_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_name_prefix: Mapped[str | None] = mapped_column(String(10), nullable=True)
    provider_name_suffix: Mapped[str | None] = mapped_column(String(10), nullable=True)
    provider_credential_text: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # --- Organization ---
    provider_organization_name_legal: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_other_organization_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_other_organization_name_type_code: Mapped[str | None] = mapped_column(String(2), nullable=True)

    # --- Other provider name fields ---
    provider_other_last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_other_first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_other_middle_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_other_name_prefix: Mapped[str | None] = mapped_column(String(10), nullable=True)
    provider_other_name_suffix: Mapped[str | None] = mapped_column(String(10), nullable=True)
    provider_other_credential_text: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_other_last_name_type_code: Mapped[str | None] = mapped_column(String(2), nullable=True)

    # --- Enumeration / dates ---
    provider_enumeration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_update_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    npi_deactivation_reason_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    npi_deactivation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    npi_reactivation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    certification_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # --- Provider attributes ---
    provider_gender_code: Mapped[str | None] = mapped_column(String(1), nullable=True)
    is_sole_proprietor: Mapped[str | None] = mapped_column(String(1), nullable=True)  # Y/N/X
    is_organization_subpart: Mapped[str | None] = mapped_column(String(1), nullable=True)  # Y/N/X
    parent_organization_lbn: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parent_organization_tin: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # --- Authorized official (organization only) ---
    authorized_official_last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    authorized_official_first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    authorized_official_middle_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    authorized_official_title_or_position: Mapped[str | None] = mapped_column(String(100), nullable=True)
    authorized_official_telephone_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    authorized_official_credential: Mapped[str | None] = mapped_column(String(50), nullable=True)
    authorized_official_name_prefix: Mapped[str | None] = mapped_column(String(10), nullable=True)
    authorized_official_name_suffix: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # --- Metadata ---
    nppes_loaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = [
    "NppesPrescriberDetail",
    "PrescriberAddress",
    "PrescriberIdentifier",
    "PrescriberTaxonomy",
]
