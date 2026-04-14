"""ORM models for NCPDP DataQ v3.1 reference data — 13 tables.

All 13 tables are GLOBAL reference data (not tenant-scoped) per LESSON-011:
pharmacies are a shared directory analogous to the NPI/NPPES registry.
Tenant-specific overlay data (network membership, contract rates) lives in
separate tenant-scoped tables in tables.py — NOT here.

Schema: ``pharmacy_dir``

Primary key strategy: UUID generated in Python (no server_default referencing
Postgres functions so tests can run against SQLite with SAVEPOINT isolation).

Field positions documented in:
    shared/data_ingestion/sources/ncpdp_field_positions.py
"""

from __future__ import annotations

import uuid as _uuid_module
from datetime import date, datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import PharmacyBase as Base

# Re-export JSON to use in place of JSONB for cross-dialect compatibility.
_JSONB = JSON

SCHEMA = "pharmacy_dir"


def _uuid_pk() -> Mapped[UUID]:
    return mapped_column(
        Uuid(),
        primary_key=True,
        default=_uuid_module.uuid4,
    )


def _ts_now() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


# ---------------------------------------------------------------------------
# 1. Pharmacy (mas.txt) — master record, one row per NCPDP Provider ID
# ---------------------------------------------------------------------------


class NCPDPPharmacy(Base):
    """NCPDP DataQ master pharmacy record (mas.txt).

    LESSON-011: Global reference data — NOT tenant-scoped.  Pharmacies are a
    shared directory analogous to the NPI/NPPES registry.  Tenant-specific
    network membership and contract data live in the Network/NetworkMembership
    tables in tables.py.

    Upsert key: ncpdp_provider_id (UNIQUE).  All 1000 bytes of each record are
    captured; unknown / ambiguous fields are stored in raw_field_* columns so
    no source byte is ever dropped.
    """

    __tablename__ = "ncpdp_pharmacies"
    __table_args__ = (
        Index("ix_ncpdp_pharmacies_npi", "npi"),
        Index("ix_ncpdp_pharmacies_state_city", "state", "city"),
        Index("ix_ncpdp_pharmacies_zip5", "zip5"),
        Index("ix_ncpdp_pharmacies_pharmacy_type", "pharmacy_type_code"),
        Index("ix_ncpdp_pharmacies_last_updated", "last_updated_at"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    ncpdp_provider_id: Mapped[str] = mapped_column(String(7), nullable=False, unique=True)

    # --- Identity fields ---
    legal_name: Mapped[str | None] = mapped_column(String(60))
    dba_name: Mapped[str | None] = mapped_column(String(60))
    store_number: Mapped[str | None] = mapped_column(String(10))
    nabp_number: Mapped[str | None] = mapped_column(String(10))
    pharmacy_type_code: Mapped[str | None] = mapped_column(String(2))
    npi: Mapped[str | None] = mapped_column(String(10))
    dea_number: Mapped[str | None] = mapped_column(String(9))
    dea_expiration_date: Mapped[date | None] = mapped_column(Date)
    federal_tax_id: Mapped[str | None] = mapped_column(String(9))

    # --- Physical address ---
    address_line_1: Mapped[str | None] = mapped_column(String(60))
    address_line_2: Mapped[str | None] = mapped_column(String(50))
    city: Mapped[str | None] = mapped_column(String(30))
    state: Mapped[str | None] = mapped_column(String(2))
    zip5: Mapped[str | None] = mapped_column(String(5))
    zip_plus4: Mapped[str | None] = mapped_column(String(4))
    cross_street: Mapped[str | None] = mapped_column(String(50))

    # --- Contact ---
    phone: Mapped[str | None] = mapped_column(String(10))
    phone_extension: Mapped[str | None] = mapped_column(String(5))
    fax: Mapped[str | None] = mapped_column(String(10))
    email: Mapped[str | None] = mapped_column(String(50))

    # --- Mailing address ---
    mailing_address_line_1: Mapped[str | None] = mapped_column(String(60))
    mailing_address_line_2: Mapped[str | None] = mapped_column(String(50))
    mailing_city: Mapped[str | None] = mapped_column(String(30))
    mailing_state: Mapped[str | None] = mapped_column(String(2))
    mailing_zip5: Mapped[str | None] = mapped_column(String(5))
    mailing_zip_plus4: Mapped[str | None] = mapped_column(String(4))

    # --- Authorized official ---
    auth_official_last_name: Mapped[str | None] = mapped_column(String(20))
    auth_official_first_name: Mapped[str | None] = mapped_column(String(20))
    auth_official_title: Mapped[str | None] = mapped_column(String(30))
    auth_official_phone: Mapped[str | None] = mapped_column(String(11))
    auth_official_email: Mapped[str | None] = mapped_column(String(50))

    # --- Dates ---
    store_open_date: Mapped[date | None] = mapped_column(Date)
    store_close_date: Mapped[date | None] = mapped_column(Date)
    deactivation_date: Mapped[date | None] = mapped_column(Date)

    # --- Raw / unknown fields — captured so no source byte is dropped ---
    raw_field_127: Mapped[str | None] = mapped_column(String(60))
    raw_field_483: Mapped[str | None] = mapped_column(String(4))
    raw_field_489: Mapped[str | None] = mapped_column(String(47))
    raw_field_834: Mapped[str | None] = mapped_column(String(5))
    raw_field_839: Mapped[str | None] = mapped_column(String(4))
    raw_field_843: Mapped[str | None] = mapped_column(String(14))
    raw_field_876: Mapped[str | None] = mapped_column(String(3))
    raw_field_896: Mapped[str | None] = mapped_column(String(12))
    raw_field_908: Mapped[str | None] = mapped_column(String(13))
    raw_field_929: Mapped[str | None] = mapped_column(String(71))

    # --- Ingestion tracking ---
    last_updated_at: Mapped[datetime] = _ts_now()
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# 2. Pharmacy Taxonomies (mas_tx.txt) — one-to-many by ncpdp_provider_id
# ---------------------------------------------------------------------------


class NCPDPPharmacyTaxonomy(Base):
    """NCPDP DataQ taxonomy codes (mas_tx.txt).

    LESSON-011: Global reference data — NOT tenant-scoped.
    Delete-then-insert by ncpdp_provider_id on each ingest run.
    """

    __tablename__ = "ncpdp_pharmacy_taxonomies"
    __table_args__ = (
        Index("ix_ncpdp_taxonomies_ncpdp_id", "ncpdp_provider_id"),
        Index("ix_ncpdp_taxonomies_code", "taxonomy_code"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    ncpdp_provider_id: Mapped[str] = mapped_column(String(7), nullable=False)
    taxonomy_code: Mapped[str | None] = mapped_column(String(10))
    primary_indicator: Mapped[str | None] = mapped_column(String(1))
    raw_field_18: Mapped[str | None] = mapped_column(String(1))
    deactivation_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# 3. Pharmacy State Licenses (mas_stl.txt)
# ---------------------------------------------------------------------------


class NCPDPPharmacyStateLicense(Base):
    """NCPDP DataQ state pharmacy licenses (mas_stl.txt).

    LESSON-011: Global reference data — NOT tenant-scoped.
    Delete-then-insert by ncpdp_provider_id on each ingest run.
    """

    __tablename__ = "ncpdp_pharmacy_state_licenses"
    __table_args__ = (
        Index("ix_ncpdp_stl_ncpdp_id", "ncpdp_provider_id"),
        Index("ix_ncpdp_stl_state", "state"),
        UniqueConstraint(
            "ncpdp_provider_id",
            "state",
            "license_number",
            name="uq_ncpdp_stl_ncpdp_state_lic",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    ncpdp_provider_id: Mapped[str] = mapped_column(String(7), nullable=False)
    state: Mapped[str | None] = mapped_column(String(2))
    license_number: Mapped[str | None] = mapped_column(String(20))
    expiration_date: Mapped[date | None] = mapped_column(Date)
    deactivation_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# 4. Pharmacy Services (mas_svc.txt)
# ---------------------------------------------------------------------------


class NCPDPPharmacyService(Base):
    """NCPDP DataQ pharmacy service flags (mas_svc.txt).

    LESSON-011: Global reference data — NOT tenant-scoped.
    One row per ncpdp_provider_id (upsert). Service codes parsed into
    named boolean columns plus raw_services_string for future-proofing.
    """

    __tablename__ = "ncpdp_pharmacy_services"
    __table_args__ = (
        Index("ix_ncpdp_svc_ncpdp_id", "ncpdp_provider_id"),
        Index("ix_ncpdp_svc_retail", "svc_retail"),
        Index("ix_ncpdp_svc_specialty", "svc_specialty"),
        Index("ix_ncpdp_svc_mail_order", "svc_mail_order"),
        Index("ix_ncpdp_svc_340b", "svc_340b"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    ncpdp_provider_id: Mapped[str] = mapped_column(String(7), nullable=False, unique=True)

    # Named service boolean flags (Y=True, N=False, absent=None)
    svc_retail: Mapped[bool | None] = mapped_column(Boolean)          # code 02
    svc_mail_order: Mapped[bool | None] = mapped_column(Boolean)      # code 03
    svc_specialty: Mapped[bool | None] = mapped_column(Boolean)       # code 04
    svc_long_term_care: Mapped[bool | None] = mapped_column(Boolean)  # code 05
    svc_home_infusion: Mapped[bool | None] = mapped_column(Boolean)   # code 06
    svc_compounding: Mapped[bool | None] = mapped_column(Boolean)     # code 07
    svc_clinic: Mapped[bool | None] = mapped_column(Boolean)          # code 10
    svc_nuclear: Mapped[bool | None] = mapped_column(Boolean)         # code 11
    svc_dme: Mapped[bool | None] = mapped_column(Boolean)             # code 12
    svc_home_health: Mapped[bool | None] = mapped_column(Boolean)     # code 13
    svc_hospice: Mapped[bool | None] = mapped_column(Boolean)         # code 14
    svc_hospital_outpatient: Mapped[bool | None] = mapped_column(Boolean)  # code 16
    svc_indian_health: Mapped[bool | None] = mapped_column(Boolean)   # code 18
    svc_correctional: Mapped[bool | None] = mapped_column(Boolean)    # code 19
    svc_military: Mapped[bool | None] = mapped_column(Boolean)        # code 23
    svc_340b: Mapped[bool | None] = mapped_column(Boolean)            # code 26
    svc_ambulatory_surgery: Mapped[bool | None] = mapped_column(Boolean)   # code 28
    svc_central_fill: Mapped[bool | None] = mapped_column(Boolean)    # code 29
    svc_dialysis: Mapped[bool | None] = mapped_column(Boolean)        # code 30
    svc_immunization: Mapped[bool | None] = mapped_column(Boolean)    # code 32
    svc_mtm: Mapped[bool | None] = mapped_column(Boolean)             # code 33/35
    svc_pharmacogenomics: Mapped[bool | None] = mapped_column(Boolean)  # code 36
    svc_specialty_infusion: Mapped[bool | None] = mapped_column(Boolean)  # code 37
    svc_other: Mapped[bool | None] = mapped_column(Boolean)           # code 40

    # Full raw service string preserved for forward compatibility
    services_raw: Mapped[str | None] = mapped_column(String(143))
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# 5. Pharmacy Remittance (mas_rr.txt)
# ---------------------------------------------------------------------------


class NCPDPPharmacyRemittance(Base):
    """NCPDP DataQ pharmacy remittance records (mas_rr.txt).

    LESSON-011: Global reference data — NOT tenant-scoped.
    Delete-then-insert by ncpdp_provider_id on each ingest run.
    """

    __tablename__ = "ncpdp_pharmacy_remittance"
    __table_args__ = (
        Index("ix_ncpdp_rr_ncpdp_id", "ncpdp_provider_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    ncpdp_provider_id: Mapped[str] = mapped_column(String(7), nullable=False)
    aba_routing_number: Mapped[str | None] = mapped_column(String(9))
    bank_account_number: Mapped[str | None] = mapped_column(String(8))
    electronic_payment_flag: Mapped[str | None] = mapped_column(String(1))
    effective_date: Mapped[date | None] = mapped_column(Date)
    deactivation_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# 6. Pharmacy eRx Capabilities (mas_erx.txt)
# ---------------------------------------------------------------------------


class NCPDPPharmacyErxCapability(Base):
    """NCPDP DataQ eRx capability flags (mas_erx.txt).

    LESSON-011: Global reference data — NOT tenant-scoped.
    Delete-then-insert by ncpdp_provider_id on each ingest run.
    """

    __tablename__ = "ncpdp_pharmacy_erx_capabilities"
    __table_args__ = (
        Index("ix_ncpdp_erx_ncpdp_id", "ncpdp_provider_id"),
        Index("ix_ncpdp_erx_capable", "erx_capable_flag"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    ncpdp_provider_id: Mapped[str] = mapped_column(String(7), nullable=False)
    software_vendor_code: Mapped[str | None] = mapped_column(String(2))
    erx_capable_flag: Mapped[str | None] = mapped_column(String(1))
    transaction_types: Mapped[str | None] = mapped_column(String(93))
    effective_date: Mapped[date | None] = mapped_column(Date)
    deactivation_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# 7. Pharmacy Medicaid (mas_md.txt)
# ---------------------------------------------------------------------------


class NCPDPPharmacyMedicaid(Base):
    """NCPDP DataQ pharmacy Medicaid enrollment (mas_md.txt).

    LESSON-011: Global reference data — NOT tenant-scoped.
    Delete-then-insert by ncpdp_provider_id on each ingest run.
    One row per (ncpdp_provider_id, state).
    """

    __tablename__ = "ncpdp_pharmacy_medicaid"
    __table_args__ = (
        Index("ix_ncpdp_md_ncpdp_id", "ncpdp_provider_id"),
        Index("ix_ncpdp_md_state", "state"),
        UniqueConstraint(
            "ncpdp_provider_id",
            "state",
            name="uq_ncpdp_md_ncpdp_state",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    ncpdp_provider_id: Mapped[str] = mapped_column(String(7), nullable=False)
    state: Mapped[str | None] = mapped_column(String(2))
    medicaid_provider_id: Mapped[str | None] = mapped_column(String(20))
    effective_date: Mapped[date | None] = mapped_column(Date)
    deactivation_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# 8. Pharmacy FWA Actions (mas_fwa.txt)
# ---------------------------------------------------------------------------


class NCPDPPharmacyFwaAction(Base):
    """NCPDP DataQ fraud, waste, and abuse annual review records (mas_fwa.txt).

    LESSON-011: Global reference data — NOT tenant-scoped.
    Delete-then-insert by ncpdp_provider_id on each ingest run.
    Multiple rows per pharmacy (one per review_year).
    """

    __tablename__ = "ncpdp_pharmacy_fwa_actions"
    __table_args__ = (
        Index("ix_ncpdp_fwa_ncpdp_id", "ncpdp_provider_id"),
        Index("ix_ncpdp_fwa_year", "review_year"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    ncpdp_provider_id: Mapped[str] = mapped_column(String(7), nullable=False)
    fwa_flag_1: Mapped[str | None] = mapped_column(String(1))
    fwa_flag_2: Mapped[str | None] = mapped_column(String(1))
    schema_version: Mapped[str | None] = mapped_column(String(3))
    review_year: Mapped[int | None] = mapped_column(Integer)
    review_flag_1: Mapped[str | None] = mapped_column(String(1))
    review_flag_2: Mapped[str | None] = mapped_column(String(1))
    effective_date: Mapped[date | None] = mapped_column(Date)
    raw_remainder: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# 9. Pharmacy Coordinates (mas_coo.txt)
# ---------------------------------------------------------------------------
# NOTE: In the v3.1 dataset, mas_coo.txt records the geocoding event dates
# (when the pharmacy address was geocoded) rather than lat/lon values directly.
# The latitude/longitude columns are provided for forward compatibility when/if
# the data file is updated to include coordinate values.


class NCPDPPharmacyCoordinate(Base):
    """NCPDP DataQ pharmacy geocoding records (mas_coo.txt).

    LESSON-011: Global reference data — NOT tenant-scoped.
    Upsert by ncpdp_provider_id.

    NOTE: v3.1 dataset encodes geocoding event dates, not explicit lat/lon.
    Latitude/longitude Numeric(9,6) columns retained for forward compatibility.
    """

    __tablename__ = "ncpdp_pharmacy_coordinates"
    __table_args__ = (
        Index("ix_ncpdp_coo_ncpdp_id", "ncpdp_provider_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    ncpdp_provider_id: Mapped[str] = mapped_column(String(7), nullable=False, unique=True)
    location_id: Mapped[str | None] = mapped_column(String(7))
    geocode_start_date: Mapped[date | None] = mapped_column(Date)
    geocode_end_date: Mapped[date | None] = mapped_column(Date)
    # Forward-compatibility lat/lon columns (not populated in v3.1)
    latitude: Mapped[Any] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Any] = mapped_column(Numeric(9, 6), nullable=True)
    geocode_match_type: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# 10. Pharmacy Additional Info (mas_af.txt) — chain/corporate level
# ---------------------------------------------------------------------------


class NCPDPPharmacyAdditionalInfo(Base):
    """NCPDP DataQ chain-level additional info (mas_af.txt).

    LESSON-011: Global reference data — NOT tenant-scoped.
    Key: chain_entity_id (5-char numeric string, NOT the 7-char NCPDP ID).
    This file contains chain/corporate parent entity information.
    """

    __tablename__ = "ncpdp_pharmacy_additional_info"
    __table_args__ = (
        Index("ix_ncpdp_af_chain_id", "chain_entity_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    chain_entity_id: Mapped[str] = mapped_column(String(5), nullable=False, unique=True)
    raw_content: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# 11. Pharmacy Patient Care (mas_pc.txt) — chain/corporate level
# ---------------------------------------------------------------------------


class NCPDPPharmacyPatientCare(Base):
    """NCPDP DataQ chain-level patient care data (mas_pc.txt).

    LESSON-011: Global reference data — NOT tenant-scoped.
    Key: chain_entity_id (6-char numeric string).
    """

    __tablename__ = "ncpdp_pharmacy_patient_care"
    __table_args__ = (
        Index("ix_ncpdp_pc_chain_id", "chain_entity_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    chain_entity_id: Mapped[str] = mapped_column(String(6), nullable=False, unique=True)
    raw_content: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# 12. Pharmacy Programs (mas_pr.txt) — chain/corporate level
# ---------------------------------------------------------------------------


class NCPDPPharmacyProgram(Base):
    """NCPDP DataQ chain-level program participation (mas_pr.txt).

    LESSON-011: Global reference data — NOT tenant-scoped.
    Key: chain_entity_id (6-char numeric string).
    """

    __tablename__ = "ncpdp_pharmacy_programs"
    __table_args__ = (
        Index("ix_ncpdp_pr_chain_id", "chain_entity_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    chain_entity_id: Mapped[str] = mapped_column(String(6), nullable=False, unique=True)
    raw_content: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# 13. Pharmacy Recertification (mas_rec.txt) — chain/corporate level
# ---------------------------------------------------------------------------


class NCPDPPharmacyRecertification(Base):
    """NCPDP DataQ chain-level recertification records (mas_rec.txt).

    LESSON-011: Global reference data — NOT tenant-scoped.
    Key: chain_entity_id (6-char numeric string).
    """

    __tablename__ = "ncpdp_pharmacy_recertification"
    __table_args__ = (
        Index("ix_ncpdp_rec_chain_id", "chain_entity_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    chain_entity_id: Mapped[str] = mapped_column(String(6), nullable=False, unique=True)
    raw_content: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# __all__
# ---------------------------------------------------------------------------

__all__ = [
    "NCPDPPharmacy",
    "NCPDPPharmacyTaxonomy",
    "NCPDPPharmacyStateLicense",
    "NCPDPPharmacyService",
    "NCPDPPharmacyRemittance",
    "NCPDPPharmacyErxCapability",
    "NCPDPPharmacyMedicaid",
    "NCPDPPharmacyFwaAction",
    "NCPDPPharmacyCoordinate",
    "NCPDPPharmacyAdditionalInfo",
    "NCPDPPharmacyPatientCare",
    "NCPDPPharmacyProgram",
    "NCPDPPharmacyRecertification",
]
