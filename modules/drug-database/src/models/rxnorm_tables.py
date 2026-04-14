"""RxNorm ORM models for the drug-database module.

Schema: ``drug_database``

Tables:
  rxnorm_concepts          — RXNCONSO.RRF (all 18 fields)
  rxnorm_relationships     — RXNREL.RRF   (all 16 fields)
  rxnorm_attributes        — RXNSAT.RRF   (all 13 fields)
  rxnorm_semantic_types    — RXNSTY.RRF   (all 6 fields)
  rxnorm_ndc_crosswalk     — derived from RXNSAT where ATN='NDC'
  rxnorm_atc_crosswalk     — derived from RXNSAT where ATN='ATC' or SAB='ATC'

LESSON-011: Global reference data — no TenantScopedMixin.
No floats, no Float columns — per financial-precision.md.
"""

from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy import (
    BigInteger,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SCHEMA = "drug_database"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RxNormBase(DeclarativeBase):
    """Declarative base for drug_database RxNorm tables."""


class RxNormConcept(RxNormBase):
    """RXNCONSO.RRF — all 18 fields.

    PK is composite (rxcui, rxaui) because RXCUI alone is not unique;
    a concept can have multiple atoms (different SABs, TTYs).
    """

    __tablename__ = "rxnorm_concepts"
    __table_args__ = (
        Index("ix_rxnorm_concepts_rxcui", "rxcui"),
        Index("ix_rxnorm_concepts_tty", "tty"),
        Index("ix_rxnorm_concepts_sab", "sab"),
        UniqueConstraint("rxcui", "rxaui", name="uq_rxnorm_concepts_rxcui_rxaui"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    rxcui: Mapped[str] = mapped_column(String(20), nullable=False)
    lat: Mapped[str | None] = mapped_column(String(3))
    ts: Mapped[str | None] = mapped_column(String(3))
    lui: Mapped[str | None] = mapped_column(String(20))
    stt: Mapped[str | None] = mapped_column(String(3))
    sui: Mapped[str | None] = mapped_column(String(20))
    ispref: Mapped[str | None] = mapped_column(String(1))
    rxaui: Mapped[str] = mapped_column(String(20), nullable=False)
    saui: Mapped[str | None] = mapped_column(String(50))
    scui: Mapped[str | None] = mapped_column(String(100))
    sdui: Mapped[str | None] = mapped_column(String(100))
    sab: Mapped[str | None] = mapped_column(String(40))
    tty: Mapped[str | None] = mapped_column(String(20))
    code: Mapped[str | None] = mapped_column(String(100))
    str_: Mapped[str | None] = mapped_column("str", Text)
    srl: Mapped[str | None] = mapped_column(String(10))
    suppress: Mapped[str | None] = mapped_column(String(1))
    cvf: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class RxNormRelationship(RxNormBase):
    """RXNREL.RRF — all 16 fields. PK: rui."""

    __tablename__ = "rxnorm_relationships"
    __table_args__ = (
        Index("ix_rxnorm_relationships_rxcui1", "rxcui1"),
        Index("ix_rxnorm_relationships_rxcui2", "rxcui2"),
        Index("ix_rxnorm_relationships_rel", "rel"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    rxcui1: Mapped[str | None] = mapped_column(String(20))
    rxaui1: Mapped[str | None] = mapped_column(String(20))
    stype1: Mapped[str | None] = mapped_column(String(50))
    rel: Mapped[str | None] = mapped_column(String(4))
    rxcui2: Mapped[str | None] = mapped_column(String(20))
    rxaui2: Mapped[str | None] = mapped_column(String(20))
    stype2: Mapped[str | None] = mapped_column(String(50))
    rela: Mapped[str | None] = mapped_column(String(100))
    rui: Mapped[str | None] = mapped_column(String(20), unique=True)
    srui: Mapped[str | None] = mapped_column(String(50))
    sab: Mapped[str | None] = mapped_column(String(40))
    sl: Mapped[str | None] = mapped_column(String(1000))
    rg: Mapped[str | None] = mapped_column(String(10))
    dir: Mapped[str | None] = mapped_column(String(1))
    suppress: Mapped[str | None] = mapped_column(String(1))
    cvf: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class RxNormAttribute(RxNormBase):
    """RXNSAT.RRF — all 13 fields. PK: atui."""

    __tablename__ = "rxnorm_attributes"
    __table_args__ = (
        Index("ix_rxnorm_attributes_rxcui_atn", "rxcui", "atn"),
        Index("ix_rxnorm_attributes_rxaui", "rxaui"),
        Index("ix_rxnorm_attributes_atn", "atn"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    rxcui: Mapped[str | None] = mapped_column(String(20))
    lui: Mapped[str | None] = mapped_column(String(20))
    sui: Mapped[str | None] = mapped_column(String(20))
    rxaui: Mapped[str | None] = mapped_column(String(20))
    stype: Mapped[str | None] = mapped_column(String(50))
    code: Mapped[str | None] = mapped_column(String(100))
    atui: Mapped[str | None] = mapped_column(String(20), unique=True)
    satui: Mapped[str | None] = mapped_column(String(50))
    atn: Mapped[str | None] = mapped_column(String(100))
    sab: Mapped[str | None] = mapped_column(String(40))
    atv: Mapped[str | None] = mapped_column(Text)
    suppress: Mapped[str | None] = mapped_column(String(1))
    cvf: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class RxNormSemanticType(RxNormBase):
    """RXNSTY.RRF — all 6 fields. Surrogate int PK."""

    __tablename__ = "rxnorm_semantic_types"
    __table_args__ = (
        Index("ix_rxnorm_semantic_types_rxcui", "rxcui"),
        Index("ix_rxnorm_semantic_types_tui", "tui"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    rxcui: Mapped[str | None] = mapped_column(String(20))
    tui: Mapped[str | None] = mapped_column(String(10))
    stn: Mapped[str | None] = mapped_column(String(100))
    sty: Mapped[str | None] = mapped_column(String(100))
    atui: Mapped[str | None] = mapped_column(String(20), unique=True)
    cvf: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class RxNormNDCCrosswalk(RxNormBase):
    """NDC ↔ RxCUI crosswalk derived from RXNSAT where ATN='NDC'.

    PK: ndc_11. One row per 11-digit NDC mapped to its canonical RxCUI.
    drug_name and tty come from the preferred atom in RXNCONSO.
    """

    __tablename__ = "rxnorm_ndc_crosswalk"
    __table_args__ = (
        {"schema": SCHEMA},
    )

    ndc_11: Mapped[str] = mapped_column(String(11), primary_key=True)
    rxcui: Mapped[str | None] = mapped_column(String(20))
    drug_name: Mapped[str | None] = mapped_column(Text)
    tty: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class RxNormATCCrosswalk(RxNormBase):
    """RxCUI ↔ ATC crosswalk derived from RXNSAT where ATN='ATC' or SAB='ATC'.

    PK: (rxcui, atc_code).
    """

    __tablename__ = "rxnorm_atc_crosswalk"
    __table_args__ = (
        Index("ix_rxnorm_atc_crosswalk_atc_code", "atc_code"),
        UniqueConstraint("rxcui", "atc_code", name="uq_rxnorm_atc_crosswalk"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rxcui: Mapped[str] = mapped_column(String(20), nullable=False)
    atc_code: Mapped[str] = mapped_column(String(10), nullable=False)
    atc_level: Mapped[str | None] = mapped_column(String(10))
    atc_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


__all__ = [
    "RxNormBase",
    "RxNormConcept",
    "RxNormRelationship",
    "RxNormAttribute",
    "RxNormSemanticType",
    "RxNormNDCCrosswalk",
    "RxNormATCCrosswalk",
    "SCHEMA",
]
