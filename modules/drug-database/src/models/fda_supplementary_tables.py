"""FDA supplementary ORM models: REMS, Drug Shortages, Purple Book.

Schema: ``drug_database`` (same schema as all other drug-database tables).

Tables:
  drug_database.drug_rems             — REMS program registry
  drug_database.drug_rems_ndc         — NDC ↔ REMS cross-reference (side table)
  drug_database.drug_shortages        — Current drug shortage state
  drug_database.drug_shortages_history — Append-only shortage snapshots
  drug_database.drug_purple_book      — FDA-licensed biologics/biosimilars

Alembic revision chain:
  0001_ndc          — drugs, packages, ingredients, pharm classes
  0002_pricing      — NADAC + ASP pricing tables
  0003_orange_book  — Orange Book therapeutic equivalence
  0004_supplementary — This migration: REMS, shortages, Purple Book

Data rules (non-negotiable):
  - Global reference data — no TenantScopedMixin (LESSON-011).
  - No float columns (no money here; enforced globally per project rules).
  - Dates: sa.Date columns. Booleans: sa.Boolean.
  - JSONB for array/complex fields (ndc_codes, etasu_requirements, manufacturers, etc.).
  - raw_payload JSONB on each table captures all extra source fields.

LESSON-011: Global reference data — no TenantScopedMixin.
LESSON-004: Regex anchors enforced in service layer.
LESSON-005: Log extra keys prefixed with ingest_ in services.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import sqlalchemy as sa
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SCHEMA = "drug_database"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SupplementaryBase(DeclarativeBase):
    """Declarative base for drug_database supplementary tables."""


# ---------------------------------------------------------------------------
# REMS tables
# ---------------------------------------------------------------------------


class DrugRems(SupplementaryBase):
    """REMS program registry.

    PK: (application_number, rems_program_name).
    One REMS program can cover many NDCs — stored in ndc_codes JSONB and
    also materialized in the drug_rems_ndc side table for indexed lookup.
    """

    __tablename__ = "drug_rems"
    __table_args__ = (
        UniqueConstraint("application_number", "rems_program_name", name="uq_drug_rems_pk"),
        Index("ix_drug_rems_app_number", "application_number"),
        Index("ix_drug_rems_ndc_codes_gin", "ndc_codes", postgresql_using="gin"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    application_number: Mapped[str] = mapped_column(String(20), nullable=False)
    rems_program_name: Mapped[str] = mapped_column(String(255), nullable=False)
    drug_name_brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    drug_name_generic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ndc_codes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    rems_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    etasu_requirements: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    initial_approval_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    most_recent_modification_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    shared_system_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class DrugRemsNdc(SupplementaryBase):
    """NDC ↔ REMS cross-reference side table.

    Materialized from DrugRems.ndc_codes for indexed NDC lookups.
    FK to drug_rems.id.
    """

    __tablename__ = "drug_rems_ndc"
    __table_args__ = (
        Index("ix_drug_rems_ndc_ndc11", "ndc_11"),
        Index("ix_drug_rems_ndc_rems_id", "rems_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    rems_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    ndc_11: Mapped[str] = mapped_column(String(11), nullable=False)
    application_number: Mapped[str] = mapped_column(String(20), nullable=False)


# ---------------------------------------------------------------------------
# Drug Shortages tables
# ---------------------------------------------------------------------------


class DrugShortage(SupplementaryBase):
    """Current drug shortage state.

    PK: (drug_name_generic, application_number).
    Updated in-place on each run — history is preserved in DrugShortageHistory.
    """

    __tablename__ = "drug_shortages"
    __table_args__ = (
        UniqueConstraint(
            "drug_name_generic", "application_number", name="uq_drug_shortages_pk"
        ),
        Index("ix_drug_shortages_status", "status"),
        Index("ix_drug_shortages_ndc_codes_gin", "ndc_codes", postgresql_using="gin"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    drug_name_generic: Mapped[str] = mapped_column(String(255), nullable=False)
    application_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ndc_codes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    shortage_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    date_first_posted: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_last_updated: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_resolved: Mapped[date | None] = mapped_column(Date, nullable=True)
    manufacturers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    therapeutic_category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    estimated_resupply_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    alternative_therapies: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class DrugShortageHistory(SupplementaryBase):
    """Append-only drug shortage snapshots.

    Every ingestion run inserts a new row — never updates or deletes.
    Preserves full history for trend analysis.
    """

    __tablename__ = "drug_shortages_history"
    __table_args__ = (
        Index("ix_drug_shortages_history_generic", "drug_name_generic"),
        Index("ix_drug_shortages_history_snapshot", "snapshot_date"),
        Index("ix_drug_shortages_history_status", "status"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    drug_name_generic: Mapped[str] = mapped_column(String(255), nullable=False)
    application_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ndc_codes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    shortage_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    date_first_posted: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_last_updated: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_resolved: Mapped[date | None] = mapped_column(Date, nullable=True)
    manufacturers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    therapeutic_category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    estimated_resupply_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    alternative_therapies: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


# ---------------------------------------------------------------------------
# Purple Book (Biologics)
# ---------------------------------------------------------------------------


class DrugPurpleBook(SupplementaryBase):
    """FDA-licensed biologics and biosimilars from the Purple Book.

    PK: bla_number (BLA application number).
    interchangeable flag is CRITICAL for formulary substitution logic.
    """

    __tablename__ = "drug_purple_book"
    __table_args__ = (
        Index("ix_drug_purple_book_proprietary_name", "proprietary_name"),
        Index("ix_drug_purple_book_proper_name", "proper_name"),
        Index("ix_drug_purple_book_reference_bla", "reference_product_bla"),
        Index("ix_drug_purple_book_interchangeable", "interchangeable"),
        {"schema": SCHEMA},
    )

    bla_number: Mapped[str] = mapped_column(String(20), primary_key=True)
    proprietary_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    proper_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bla_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    applicant: Mapped[str | None] = mapped_column(String(255), nullable=True)
    strength: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dosage_form: Mapped[str | None] = mapped_column(String(100), nullable=True)
    route: Mapped[str | None] = mapped_column(String(100), nullable=True)
    product_presentation: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    licensure_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    interchangeable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    reference_product_bla: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reference_product_proper_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    exclusivity_expiration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


__all__ = [
    "SupplementaryBase",
    "DrugRems",
    "DrugRemsNdc",
    "DrugShortage",
    "DrugShortageHistory",
    "DrugPurpleBook",
    "SCHEMA",
]
