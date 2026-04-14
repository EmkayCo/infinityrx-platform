"""ORM model for the OIG LEIE federal exclusion list.

Schema: shared
Table: oig_leie_exclusions

Global reference data — no TenantScopedMixin (LESSON-011).
Published by OIG as public data — names/DOB are NOT PHI in this context (LESSON-010).
NPI plaintext — public registry identifier (LESSON-010).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Date,
    DateTime,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base

SCHEMA = "shared"


class OigLeieExclusion(Base):
    """One row per excluded individual or entity in the OIG LEIE database.

    The LEIE has no natural single-column PK; NPI is optional. The composite
    (lastname, firstname, busname, excldate) is used as the deduplication key.
    """

    __tablename__ = "oig_leie_exclusions"
    __table_args__ = (
        UniqueConstraint(
            "lastname", "firstname", "busname", "excldate",
            name="uq_oig_leie_exclusions_natural_key",
        ),
        Index("ix_oig_leie_npi", "npi"),
        Index("ix_oig_leie_name_dob", "lastname", "firstname", "dob"),
        Index("ix_oig_leie_excldate", "excldate"),
        Index("ix_oig_leie_reindate", "reindate"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Individual name fields
    lastname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    firstname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    midname: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Business name (for entities)
    busname: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Provider type and specialty
    general: Mapped[str | None] = mapped_column(String(255), nullable=True)
    specialty: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Identifiers — public; do NOT log name+DOB together for audit (only NPI)
    upin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    npi: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # DOB: LEIE is public federal data — plaintext OK (not PHI in this context)
    dob: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Address
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    zip: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Exclusion details
    excltype: Mapped[str | None] = mapped_column(String(50), nullable=True)
    excldate: Mapped[date | None] = mapped_column(Date, nullable=True)
    reindate: Mapped[date | None] = mapped_column(Date, nullable=True)
    waiverdate: Mapped[date | None] = mapped_column(Date, nullable=True)
    waiverstate: Mapped[str | None] = mapped_column(String(2), nullable=True)

    # Raw payload for forward-compatibility
    raw_payload: Mapped[Any] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = ["OigLeieExclusion"]
