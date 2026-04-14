"""H-08: Business Associate Agreement / Trading Partner Agreement tracking.

Implements PRD §3.20 — every trading partner must have a BAA on file before
any PHI flows through that partner. This service manages agreement lifecycle
and surfaces expiry alerts to the compliance dashboard.

Persistence: ``TradingPartnerAgreement`` model in ``models/edi_models.py``.

Date inputs and outputs are ISO ``YYYY-MM-DD`` strings — the model column is
``String(10)`` to keep the schema lossless when partners send
non-ISO dates from upstream systems and to avoid timezone ambiguity for
contract dates.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.edi_models import TradingPartnerAgreement

VALID_AGREEMENT_TYPES: frozenset[str] = frozenset({"BAA", "TPA", "NDA"})


class InvalidAgreementType(ValueError):
    """Raised when agreement_type is not BAA/TPA/NDA."""


@dataclass(slots=True)
class AgreementInput:
    trading_partner_id: uuid.UUID
    agreement_type: str
    executed_date: Optional[str] = None
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None
    renewal_date: Optional[str] = None
    signatory_name: Optional[str] = None
    signatory_title: Optional[str] = None


def _validate_type(agreement_type: str) -> str:
    upper = agreement_type.upper()
    if upper not in VALID_AGREEMENT_TYPES:
        raise InvalidAgreementType(
            f"agreement_type must be one of {sorted(VALID_AGREEMENT_TYPES)}, got {agreement_type!r}"
        )
    return upper


def _parse_iso_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


async def create_agreement(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    payload: AgreementInput,
) -> TradingPartnerAgreement:
    """Persist a new BAA/TPA/NDA agreement for a trading partner."""
    agreement_type = _validate_type(payload.agreement_type)
    _parse_iso_date(payload.executed_date)
    _parse_iso_date(payload.effective_date)
    _parse_iso_date(payload.expiry_date)
    _parse_iso_date(payload.renewal_date)

    row = TradingPartnerAgreement(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        trading_partner_id=payload.trading_partner_id,
        agreement_type=agreement_type,
        executed_date=payload.executed_date,
        effective_date=payload.effective_date,
        expiry_date=payload.expiry_date,
        renewal_date=payload.renewal_date,
        signatory_name=payload.signatory_name,
        signatory_title=payload.signatory_title,
    )
    db.add(row)
    await db.commit()
    return row


async def get_agreements_by_partner(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    trading_partner_id: uuid.UUID,
) -> list[TradingPartnerAgreement]:
    result = await db.execute(
        select(TradingPartnerAgreement).where(
            TradingPartnerAgreement.tenant_id == tenant_id,
            TradingPartnerAgreement.trading_partner_id == trading_partner_id,
        )
    )
    return list(result.scalars().all())


async def get_expiring_agreements(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    days_ahead: int = 90,
    today: Optional[date] = None,
) -> list[TradingPartnerAgreement]:
    """Return agreements whose ``expiry_date`` falls inside the alert window.

    Includes anything already expired so compliance can chase late renewals.
    Skips rows with no ``expiry_date`` (e.g. evergreen NDAs).
    """
    if days_ahead < 0:
        raise ValueError("days_ahead must be non-negative")

    today = today or date.today()
    cutoff = today + timedelta(days=days_ahead)

    result = await db.execute(
        select(TradingPartnerAgreement).where(
            TradingPartnerAgreement.tenant_id == tenant_id,
            TradingPartnerAgreement.expiry_date.is_not(None),
        )
    )
    rows: Iterable[TradingPartnerAgreement] = result.scalars().all()
    return [
        r
        for r in rows
        if (parsed := _parse_iso_date(r.expiry_date)) is not None and parsed <= cutoff
    ]


async def check_baa_valid(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    trading_partner_id: uuid.UUID,
    today: Optional[date] = None,
) -> bool:
    """Return True iff at least one BAA covers ``today`` for the given partner.

    A BAA covers ``today`` when:
      - ``effective_date`` is null or ``<= today``
      - ``expiry_date`` is null (evergreen) or ``>= today``
    Only ``agreement_type == "BAA"`` rows count — TPAs and NDAs do not
    satisfy HIPAA's BAA requirement.
    """
    today = today or date.today()
    result = await db.execute(
        select(TradingPartnerAgreement).where(
            TradingPartnerAgreement.tenant_id == tenant_id,
            TradingPartnerAgreement.trading_partner_id == trading_partner_id,
            TradingPartnerAgreement.agreement_type == "BAA",
        )
    )
    for row in result.scalars().all():
        effective = _parse_iso_date(row.effective_date)
        expiry = _parse_iso_date(row.expiry_date)
        if effective is not None and effective > today:
            continue
        if expiry is not None and expiry < today:
            continue
        return True
    return False
