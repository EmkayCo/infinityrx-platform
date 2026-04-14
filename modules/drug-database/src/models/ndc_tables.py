"""FDA NDC Directory ORM models for the drug-database module.

Schema: ``drug_database`` (separate from ``drug_db`` used by the legacy
DrugProduct/DrugPricing models in tables.py).

Tables:
  drug_database.drugs                   — product-level records from product.txt
  drug_database.drug_packages           — package-level records from package.txt
  drug_database.drug_active_ingredients — exploded from SUBSTANCENAME/STRENGTH/UNIT
  drug_database.drug_pharm_classes      — exploded from PHARM_CLASSES

LESSON-011: Global reference data — no TenantScopedMixin.
LESSON-004: All regex uses \\A...\\Z anchors (enforcement in service layer).
Financial precision: Decimal(18,6) with ROUND_HALF_UP for numerator_strength.
No floats anywhere.

Alembic revision chain:
  0001_ndc    (this migration — drugs, packages, ingredients, pharm classes)
  0002        reserved for pricing data by Teammate 4
  0003        reserved for Orange Book cross-ref by Teammate 5
"""

from __future__ import annotations

import uuid as _uuid_module
from datetime import date, datetime, timezone
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

SCHEMA = "drug_database"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NDCBase(DeclarativeBase):
    """Declarative base for drug_database NDC tables."""


class Drug(NDCBase):
    """Product-level drug record from FDA product.txt.

    One row per PRODUCTID (a labeler-product pair like "0069-4200").
    The ndc_11 column stores the 5-4-2 normalized NDC using "00" as the
    package segment placeholder for the product-level row; true per-package
    NDC-11s live in DrugPackage.ndc_package_code_11.

    Cross-reference for Teammate 5 (Orange Book):
        application_number — maps to Orange Book NDA/ANDA numbers.
        Indexed for fast lookup.
    """

    __tablename__ = "drugs"
    __table_args__ = (
        Index("ix_drugs_product_ndc", "product_ndc"),
        Index("ix_drugs_ndc_11", "ndc_11"),
        Index("ix_drugs_application_number", "application_number"),
        Index("ix_drugs_dea_schedule", "dea_schedule"),
        UniqueConstraint("ndc_11", name="uq_drugs_ndc_11"),
        {"schema": SCHEMA},
    )

    product_id: Mapped[str] = mapped_column(
        String(50), primary_key=True, comment="PRODUCTID from FDA (labeler-product)"
    )
    product_ndc: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="PRODUCTNDC in 5-4 format"
    )
    ndc_11: Mapped[str] = mapped_column(
        String(11), nullable=False,
        comment="11-digit normalized NDC (5-4-2); package segment is '00' at product level"
    )
    product_type_name: Mapped[str | None] = mapped_column(String(100))
    proprietary_name: Mapped[str | None] = mapped_column(String(500))
    proprietary_name_suffix: Mapped[str | None] = mapped_column(String(255))
    non_proprietary_name: Mapped[str | None] = mapped_column(String(500))
    dosage_form_name: Mapped[str | None] = mapped_column(String(100))
    route_name: Mapped[str | None] = mapped_column(String(255))
    start_marketing_date: Mapped[date | None] = mapped_column(Date)
    end_marketing_date: Mapped[date | None] = mapped_column(Date)
    marketing_category_name: Mapped[str | None] = mapped_column(String(255))
    application_number: Mapped[str | None] = mapped_column(
        String(20), comment="Orange Book NDA/ANDA number — cross-ref for T5"
    )
    labeler_name: Mapped[str | None] = mapped_column(String(500))
    substance_name: Mapped[str | None] = mapped_column(
        Text, comment="Raw semicolon-separated substance names"
    )
    active_numerator_strength: Mapped[str | None] = mapped_column(
        Text, comment="Raw semicolon-separated strength values"
    )
    active_ingred_unit: Mapped[str | None] = mapped_column(
        Text, comment="Raw semicolon-separated unit strings"
    )
    pharm_classes: Mapped[str | None] = mapped_column(
        Text, comment="Raw comma-separated pharmacological classes with [TYPE] markers"
    )
    dea_schedule: Mapped[str | None] = mapped_column(String(5))
    ndc_exclude_flag: Mapped[str | None] = mapped_column(String(1))
    listing_record_certified_through: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    packages: Mapped[list[DrugPackage]] = relationship(
        "DrugPackage", back_populates="drug", cascade="all, delete-orphan"
    )
    active_ingredients: Mapped[list[DrugActiveIngredient]] = relationship(
        "DrugActiveIngredient", back_populates="drug", cascade="all, delete-orphan"
    )
    pharm_class_entries: Mapped[list[DrugPharmClass]] = relationship(
        "DrugPharmClass", back_populates="drug", cascade="all, delete-orphan"
    )


class DrugPackage(NDCBase):
    """Package-level record from FDA package.txt.

    One row per NDCPACKAGECODE (full 11-digit NDC including package segment).
    ndc_package_code_11 is the normalized 5-4-2 form.
    """

    __tablename__ = "drug_packages"
    __table_args__ = (
        Index("ix_drug_packages_product_ndc", "product_ndc"),
        Index("ix_drug_packages_ndc_package_code", "ndc_package_code"),
        Index("ix_drug_packages_ndc_package_code_11", "ndc_package_code_11"),
        UniqueConstraint("ndc_package_code_11", name="uq_drug_packages_ndc_11"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey(f"{SCHEMA}.drugs.product_id", ondelete="CASCADE"),
        nullable=False,
    )
    product_ndc: Mapped[str | None] = mapped_column(
        String(20), comment="Denormalized PRODUCTNDC for convenience"
    )
    ndc_package_code: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="Raw NDCPACKAGECODE from FDA"
    )
    ndc_package_code_11: Mapped[str] = mapped_column(
        String(11), nullable=False, comment="Normalized 11-digit NDC (5-4-2)"
    )
    package_description: Mapped[str | None] = mapped_column(Text)
    start_marketing_date: Mapped[date | None] = mapped_column(Date)
    end_marketing_date: Mapped[date | None] = mapped_column(Date)
    ndc_exclude_flag: Mapped[str | None] = mapped_column(String(1))
    sample_package: Mapped[str | None] = mapped_column(String(1))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    drug: Mapped[Drug] = relationship("Drug", back_populates="packages")


class DrugActiveIngredient(NDCBase):
    """Exploded active ingredient rows.

    One row per ingredient per drug, derived by zipping the semicolon-
    separated SUBSTANCENAME, ACTIVE_NUMERATOR_STRENGTH, and ACTIVE_INGRED_UNIT
    fields from product.txt.

    numerator_strength is Decimal(18,6) ROUND_HALF_UP per financial-precision
    rules (even though this is a pharmacological quantity, we apply the same
    rule to prevent float contamination in the data pipeline).

    Non-numeric strength values (e.g. "q.s.") are stored as NULL — never 0.
    """

    __tablename__ = "drug_active_ingredients"
    __table_args__ = (
        Index("ix_drug_active_ingredients_drug_id", "drug_id"),
        Index("ix_drug_active_ingredients_substance_name", "substance_name"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    drug_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey(f"{SCHEMA}.drugs.product_id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="0-indexed position within the drug's ingredient list"
    )
    substance_name: Mapped[str] = mapped_column(String(500), nullable=False)
    numerator_strength: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6), comment="Decimal(18,6) ROUND_HALF_UP; NULL for non-numeric values like q.s."
    )
    unit: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    drug: Mapped[Drug] = relationship("Drug", back_populates="active_ingredients")


class DrugPharmClass(NDCBase):
    """Exploded pharmacological class entries.

    One row per class per drug, derived by splitting the comma-separated
    PHARM_CLASSES field from product.txt.

    class_type is extracted from a trailing ``[TYPE]`` marker (e.g., EPC, MoA,
    PE, CS). Rows without a marker have class_type=None.
    """

    __tablename__ = "drug_pharm_classes"
    __table_args__ = (
        Index("ix_drug_pharm_classes_drug_id", "drug_id"),
        Index("ix_drug_pharm_classes_class_type", "class_type"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    drug_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey(f"{SCHEMA}.drugs.product_id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="0-indexed position within the drug's class list"
    )
    pharm_class: Mapped[str] = mapped_column(Text, nullable=False)
    class_type: Mapped[str | None] = mapped_column(
        String(10), comment="EPC, MoA, PE, CS — extracted from [TYPE] marker; null if absent"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    drug: Mapped[Drug] = relationship("Drug", back_populates="pharm_class_entries")


__all__ = [
    "Drug",
    "DrugActiveIngredient",
    "DrugPackage",
    "DrugPharmClass",
    "NDCBase",
    "SCHEMA",
]
