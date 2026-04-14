"""FDA Orange Book ORM models for the drug-database module.

Schema: ``drug_database`` (same schema as NDC and pricing tables, migration 0003_orange_book).

Tables:
  drug_database.drug_orange_book  — product-level records from products.txt
  drug_database.drug_patents       — patent records from patent.txt
  drug_database.drug_exclusivity   — exclusivity records from exclusivity.txt

View:
  drug_database.v_drug_orange_book — joins drugs ↔ drug_orange_book on application_number

Data rules (non-negotiable):
  - No money columns — no floats, no Decimal needed here.
  - Global reference data — no TenantScopedMixin (LESSON-011).
  - Dates: "Mmm DD, YYYY" parsed to datetime.date.
  - Y/N → Boolean True/False; empty → NULL.
  - Strip all fields. Empty string → NULL.

LESSON-004: All regex uses \\A...\\Z anchors (enforcement in service layer).
LESSON-005: All log extra keys prefixed with ingest_.

Alembic revision chain:
  0001_ndc      (T3) — drugs, packages, ingredients, pharm classes
  0002_pricing  (T4) — NADAC + ASP pricing tables
  0003_orange_book (this migration, T5) — Orange Book therapeutic equivalence overlay
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import sqlalchemy as sa
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SCHEMA = "drug_database"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OrangeBookBase(DeclarativeBase):
    """Declarative base for drug_database Orange Book tables."""


class DrugOrangeBook(OrangeBookBase):
    """Product-level Orange Book record from FDA products.txt.

    One row per (appl_type, appl_no, product_no) combination.

    application_number is a computed column "{appl_type}{appl_no:0>6}" that
    matches the format stored in drug_database.drugs.application_number (e.g.,
    "NDA019787") for Orange Book cross-reference queries.

    dosage_form and route are split from the source "DF;Route" field on semicolon.

    approved_prior_to_1982: set True when approval_date source text is
    "Approved Prior to Jan 1, 1982"; approval_date is set to 1982-01-01 in this case.

    LESSON-011: Global reference data — no TenantScopedMixin.
    LESSON-004: Regex in service layer uses \\A...\\Z anchors.
    """

    __tablename__ = "drug_orange_book"
    __table_args__ = (
        UniqueConstraint(
            "appl_type", "appl_no", "product_no",
            name="uq_orange_book_appl_product",
        ),
        Index("ix_orange_book_application_number", "application_number"),
        Index("ix_orange_book_appl_type", "appl_type"),
        Index("ix_orange_book_ingredient", "ingredient"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    ingredient: Mapped[str | None] = mapped_column(
        String(500), comment="Active ingredient(s)"
    )
    dosage_form: Mapped[str | None] = mapped_column(
        String(200), comment="Dosage form — split from 'DF;Route' on semicolon"
    )
    route: Mapped[str | None] = mapped_column(
        String(200), comment="Route of administration — split from 'DF;Route' on semicolon"
    )
    trade_name: Mapped[str | None] = mapped_column(String(500))
    applicant: Mapped[str | None] = mapped_column(
        String(100), comment="Short applicant code"
    )
    strength: Mapped[str | None] = mapped_column(String(500))
    appl_type: Mapped[str] = mapped_column(
        String(5), nullable=False, comment="N=NDA, A=ANDA, BLA"
    )
    appl_no: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="Application number digits, e.g. '019787'"
    )
    application_number: Mapped[str | None] = mapped_column(
        String(20),
        comment="Computed '{appl_type}{appl_no:0>6}' — e.g. 'NDA019787'; matches drugs.application_number",
    )
    product_no: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="Product number within the application"
    )
    te_code: Mapped[str | None] = mapped_column(
        String(10),
        comment="Therapeutic equivalence code (AA, AB, AB1, AB2, AB3, AP, AT, BC, BD, BE, BN, BP, BS, BT, BX); null for originator RX products",
    )
    approval_date: Mapped[date | None] = mapped_column(
        Date,
        comment="Approval date; 1982-01-01 when approved_prior_to_1982 is True",
    )
    approved_prior_to_1982: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="True when source text is 'Approved Prior to Jan 1, 1982'",
    )
    rld: Mapped[bool | None] = mapped_column(
        Boolean,
        comment="Reference Listed Drug: True=Yes, False=No, null=unknown",
    )
    rs: Mapped[bool | None] = mapped_column(
        Boolean,
        comment="Reference Standard: True=Yes, False=No, null=unknown",
    )
    product_type: Mapped[str | None] = mapped_column(
        String(10), comment="RX, OTC, DISCN"
    )
    applicant_full_name: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class DrugPatent(OrangeBookBase):
    """Patent record from FDA patent.txt.

    One row per (appl_type, appl_no, product_no, patent_no).

    application_number matches the format in drug_orange_book and drugs.

    LESSON-011: Global reference data — no TenantScopedMixin.
    """

    __tablename__ = "drug_patents"
    __table_args__ = (
        UniqueConstraint(
            "appl_type", "appl_no", "product_no", "patent_no",
            name="uq_drug_patents_appl_product_patent",
        ),
        Index("ix_drug_patents_application_number", "application_number"),
        Index("ix_drug_patents_patent_no", "patent_no"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    appl_type: Mapped[str] = mapped_column(String(5), nullable=False)
    appl_no: Mapped[str] = mapped_column(String(10), nullable=False)
    product_no: Mapped[str] = mapped_column(String(10), nullable=False)
    application_number: Mapped[str | None] = mapped_column(
        String(20),
        comment="Computed '{appl_type}{appl_no:0>6}' — matches drugs.application_number",
    )
    patent_no: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Patent number — can contain letters"
    )
    patent_expire_date: Mapped[date | None] = mapped_column(
        Date, comment="Patent expiration date; null if not available"
    )
    drug_substance_flag: Mapped[bool | None] = mapped_column(
        Boolean, comment="Y→True: patent covers drug substance"
    )
    drug_product_flag: Mapped[bool | None] = mapped_column(
        Boolean, comment="Y→True: patent covers drug product"
    )
    patent_use_code: Mapped[str | None] = mapped_column(
        String(20), comment="Use code (U-xxx) for method-of-use patents; null if absent"
    )
    delist_flag: Mapped[bool | None] = mapped_column(
        Boolean, comment="Y→True: patent has been delisted"
    )
    submission_date: Mapped[date | None] = mapped_column(
        Date, comment="Date patent was submitted to FDA; nullable"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class DrugExclusivity(OrangeBookBase):
    """Exclusivity record from FDA exclusivity.txt.

    One row per (appl_type, appl_no, product_no, exclusivity_code, exclusivity_date).

    application_number matches the format in drug_orange_book and drugs.

    LESSON-011: Global reference data — no TenantScopedMixin.
    """

    __tablename__ = "drug_exclusivity"
    __table_args__ = (
        UniqueConstraint(
            "appl_type", "appl_no", "product_no",
            "exclusivity_code", "exclusivity_date",
            name="uq_drug_exclusivity_appl_code_date",
        ),
        Index("ix_drug_exclusivity_application_number", "application_number"),
        Index("ix_drug_exclusivity_exclusivity_code", "exclusivity_code"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    appl_type: Mapped[str] = mapped_column(String(5), nullable=False)
    appl_no: Mapped[str] = mapped_column(String(10), nullable=False)
    product_no: Mapped[str] = mapped_column(String(10), nullable=False)
    application_number: Mapped[str | None] = mapped_column(
        String(20),
        comment="Computed '{appl_type}{appl_no:0>6}' — matches drugs.application_number",
    )
    exclusivity_code: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="NCE, ODE, PED, I, M, NP, NPP, PC, etc.",
    )
    exclusivity_date: Mapped[date] = mapped_column(
        Date, nullable=False, comment="Exclusivity expiration date"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


__all__ = [
    "DrugExclusivity",
    "DrugOrangeBook",
    "DrugPatent",
    "OrangeBookBase",
    "SCHEMA",
]
