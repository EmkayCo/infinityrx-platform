"""ORM models for OFAC SDN (Specially Designated Nationals) reference tables.

Schema: shared
Tables: ofac_sdn, ofac_sdn_addresses, ofac_sdn_aliases, ofac_sdn_comments

Parent keyed on ent_num (from sdn.csv), three CASCADE children mirror the
relational structure of the OFAC CSV distribution. All four carry
raw_payload jsonb so the ingester's "-0- " -> NULL normalisation doesn't
lose source information.

LESSON-011: Global reference data — no TenantScopedMixin.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.db.base import Base

SCHEMA = "shared"


class OfacSdn(Base):
    """Parent row — one per OFAC-listed entity (ent_num)."""

    __tablename__ = "ofac_sdn"
    __table_args__ = (
        Index("idx_ofac_sdn_name", "sdn_name"),
        Index("idx_ofac_sdn_type", "sdn_type"),
        Index("idx_ofac_sdn_program", "program"),
        {"schema": SCHEMA},
    )

    ent_num: Mapped[int] = mapped_column(Integer, primary_key=True)
    sdn_name: Mapped[str | None] = mapped_column(Text)
    sdn_type: Mapped[str | None] = mapped_column(String(50))
    program: Mapped[str | None] = mapped_column(String(500))
    title: Mapped[str | None] = mapped_column(Text)
    call_sign: Mapped[str | None] = mapped_column(String(100))
    vess_type: Mapped[str | None] = mapped_column(String(100))
    tonnage: Mapped[str | None] = mapped_column(String(50))
    grt: Mapped[str | None] = mapped_column(String(50))
    vess_flag: Mapped[str | None] = mapped_column(String(100))
    vess_owner: Mapped[str | None] = mapped_column(Text)
    remarks: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    addresses: Mapped[list[OfacSdnAddress]] = relationship(
        "OfacSdnAddress", back_populates="sdn",
        cascade="all, delete-orphan",
    )
    aliases: Mapped[list[OfacSdnAlias]] = relationship(
        "OfacSdnAlias", back_populates="sdn",
        cascade="all, delete-orphan",
    )
    comments: Mapped[list[OfacSdnComment]] = relationship(
        "OfacSdnComment", back_populates="sdn",
        cascade="all, delete-orphan",
    )


class OfacSdnAddress(Base):
    __tablename__ = "ofac_sdn_addresses"
    __table_args__ = (
        UniqueConstraint("ent_num", "add_num",
                         name="uq_ofac_sdn_addresses_ent_add"),
        Index("idx_ofac_sdn_addresses_ent_num", "ent_num"),
        Index("idx_ofac_sdn_addresses_country", "country"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ent_num: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{SCHEMA}.ofac_sdn.ent_num", ondelete="CASCADE"),
        nullable=False,
    )
    add_num: Mapped[int] = mapped_column(Integer, nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    city_state_zip: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(String(100))
    add_remarks: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sdn: Mapped[OfacSdn] = relationship("OfacSdn", back_populates="addresses")


class OfacSdnAlias(Base):
    __tablename__ = "ofac_sdn_aliases"
    __table_args__ = (
        UniqueConstraint("ent_num", "alt_num",
                         name="uq_ofac_sdn_aliases_ent_alt"),
        Index("idx_ofac_sdn_aliases_ent_num", "ent_num"),
        Index("idx_ofac_sdn_aliases_name", "alt_name"),
        Index("idx_ofac_sdn_aliases_type", "alt_type"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ent_num: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{SCHEMA}.ofac_sdn.ent_num", ondelete="CASCADE"),
        nullable=False,
    )
    alt_num: Mapped[int] = mapped_column(Integer, nullable=False)
    alt_type: Mapped[str | None] = mapped_column(String(20))
    alt_name: Mapped[str | None] = mapped_column(Text)
    alt_remarks: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sdn: Mapped[OfacSdn] = relationship("OfacSdn", back_populates="aliases")


class OfacSdnComment(Base):
    __tablename__ = "ofac_sdn_comments"
    __table_args__ = (
        UniqueConstraint("ent_num", name="uq_ofac_sdn_comments_ent_num"),
        Index("idx_ofac_sdn_comments_ent_num", "ent_num"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ent_num: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{SCHEMA}.ofac_sdn.ent_num", ondelete="CASCADE"),
        nullable=False,
    )
    remarks3: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sdn: Mapped[OfacSdn] = relationship("OfacSdn", back_populates="comments")


__all__ = [
    "SCHEMA",
    "OfacSdn",
    "OfacSdnAddress",
    "OfacSdnAlias",
    "OfacSdnComment",
]
