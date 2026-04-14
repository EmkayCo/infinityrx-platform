"""Pharmacy upsert service for NCPDP and NPPES refresh pipelines."""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tables import Pharmacy
from src.services.ncpdp_parser import NcpdpRecord
from src.services.nppes_parser import NppesRecord

logger = logging.getLogger("pharmacy-directory.upsert")


class PharmacyUpsertService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def upsert_from_ncpdp(self, record: NcpdpRecord) -> tuple[Pharmacy, bool]:
        """Upsert a pharmacy from an NCPDP record. Returns (pharmacy, created)."""
        stmt = select(Pharmacy).where(Pharmacy.npi == record.npi)
        result = await self._db.execute(stmt)
        pharmacy = result.scalar_one_or_none()
        created = pharmacy is None

        if created:
            pharmacy = Pharmacy(
                npi=record.npi,
                display_name=record.dba_name or record.legal_name,
            )
            self._db.add(pharmacy)

        pharmacy.nabp_number = record.nabp_number or pharmacy.nabp_number if not created else record.nabp_number
        pharmacy.ncpdp_id = record.ncpdp_id or None
        pharmacy.legal_name = record.legal_name
        pharmacy.dba_name = record.dba_name or None
        pharmacy.display_name = record.dba_name or record.legal_name
        pharmacy.pharmacy_type = record.pharmacy_type
        pharmacy.chain_name = record.chain_name or None
        pharmacy.chain_code = record.chain_code or None
        pharmacy.store_number = record.store_number or None
        pharmacy.address_line_1 = record.address_line_1
        pharmacy.address_line_2 = record.address_line_2 or None
        pharmacy.city = record.city
        pharmacy.state = record.state
        pharmacy.zip_code = record.zip_code
        pharmacy.phone = record.phone or None
        pharmacy.fax = record.fax or None
        pharmacy.hours_monday = record.hours_monday or None
        pharmacy.hours_tuesday = record.hours_tuesday or None
        pharmacy.hours_wednesday = record.hours_wednesday or None
        pharmacy.hours_thursday = record.hours_thursday or None
        pharmacy.hours_friday = record.hours_friday or None
        pharmacy.hours_saturday = record.hours_saturday or None
        pharmacy.hours_sunday = record.hours_sunday or None
        pharmacy.is_24_hour = record.is_24_hour
        pharmacy.accepts_electronic_rx = record.accepts_electronic_rx
        pharmacy.dispenses_controlled = record.dispenses_controlled
        pharmacy.offers_delivery = record.offers_delivery
        pharmacy.offers_compounding = record.offers_compounding
        pharmacy.offers_specialty = record.offers_specialty
        pharmacy.offers_340b = record.offers_340b
        pharmacy.status = record.status
        pharmacy.ncpdp_last_updated = datetime.now(UTC)

        await self._db.flush()
        return pharmacy, created

    async def upsert_from_nppes(self, record: NppesRecord) -> tuple[Pharmacy, bool]:
        """Upsert from an NPPES record. NCPDP data takes precedence when available."""
        stmt = select(Pharmacy).where(Pharmacy.npi == record.npi)
        result = await self._db.execute(stmt)
        pharmacy = result.scalar_one_or_none()
        created = pharmacy is None

        if created:
            pharmacy = Pharmacy(
                npi=record.npi,
                legal_name=record.organization_name or record.npi,
                display_name=record.organization_name or record.npi,
                pharmacy_type=record.pharmacy_type,
                address_line_1=record.address_line_1 or "Unknown",
                city=record.city or "Unknown",
                state=record.state or "XX",
                zip_code=record.zip_code or "00000",
                phone=record.phone or None,
            )
            self._db.add(pharmacy)
        else:
            # Only update address/phone if NCPDP hasn't set them
            if not pharmacy.ncpdp_last_updated:
                pharmacy.pharmacy_type = record.pharmacy_type
                pharmacy.address_line_1 = record.address_line_1 or pharmacy.address_line_1
                pharmacy.city = record.city or pharmacy.city
                pharmacy.state = record.state or pharmacy.state
                pharmacy.zip_code = record.zip_code or pharmacy.zip_code
                pharmacy.phone = record.phone or pharmacy.phone

        if not record.is_active:
            pharmacy.status = "inactive"

        pharmacy.nppes_last_updated = datetime.now(UTC)
        await self._db.flush()
        return pharmacy, created
