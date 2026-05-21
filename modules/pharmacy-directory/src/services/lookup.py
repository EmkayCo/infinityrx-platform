"""Pharmacy lookup service — NPI, name search backed by dataq_master.

Repointed from the unmigrated pharmacy_dir.pharmacies to pharmacy_dir.dataq_master
(82,643 seeded rows) as Option A per docs/audit/pharmacy-drug-dataflow-fix-plan.md
(2026-05-20). Nearby search is not supported from dataq_master (no lat/lon columns)
and returns an empty list until geocoding data is available.
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tables import DataqMaster
from src.services.cache import PharmacyCache

logger = logging.getLogger("pharmacy-directory.lookup")


class PharmacyLookupService:
    def __init__(self, db: AsyncSession, cache: PharmacyCache | None = None) -> None:
        self._db = db
        self._cache = cache

    async def get_by_npi(self, tenant_id: UUID, npi: str) -> dict[str, Any] | None:
        if self._cache:
            cached = await self._cache.get_by_npi(tenant_id, npi)
            if cached is not None:
                return cached

        stmt = select(DataqMaster).where(DataqMaster.npi == npi)
        result = await self._db.execute(stmt)
        pharmacy = result.scalar_one_or_none()
        if pharmacy is None:
            return None

        data = _dataq_to_dict(pharmacy)
        if self._cache:
            await self._cache.set_by_npi(tenant_id, npi, data)
        return data

    async def get_by_nabp(self, tenant_id: UUID, nabp: str) -> dict[str, Any] | None:
        """NABP lookup is not available in dataq_master; always returns None."""
        if self._cache:
            cached = await self._cache.get_by_nabp(tenant_id, nabp)
            if cached is not None:
                return cached
        # dataq_master has no nabp_number column — return None (caller raises 404)
        return None

    async def search_by_name(
        self, query: str, limit: int = 20, offset: int = 0
    ) -> list[dict[str, Any]]:
        stmt = (
            select(DataqMaster)
            .where(
                DataqMaster.deactivation_code.is_(None),
                or_(
                    DataqMaster.name.ilike(f"%{query}%"),
                    DataqMaster.legal_business_name.ilike(f"%{query}%"),
                ),
            )
            .order_by(DataqMaster.name, DataqMaster.legal_business_name)
            .limit(limit)
            .offset(offset)
        )
        result = await self._db.execute(stmt)
        return [_dataq_to_dict(p) for p in result.scalars().all()]

    async def search_nearby(
        self,
        lat: Any,
        lng: Any,
        radius_miles: float,
        pharmacy_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Geographic search — not supported from dataq_master (no lat/lon).

        Returns empty list. Callers handle this gracefully via PharmacyListResponse.
        """
        logger.warning(
            "search_nearby called but dataq_master has no lat/lon columns — returning empty list",
            extra={"svc_name": "pharmacy-directory"},
        )
        return []

    async def batch_lookup(
        self, tenant_id: UUID, npis: list[str]
    ) -> dict[str, dict[str, Any] | None]:
        if not npis:
            return {}
        stmt = select(DataqMaster).where(DataqMaster.npi.in_(npis))
        result = await self._db.execute(stmt)
        found = {p.npi: _dataq_to_dict(p) for p in result.scalars().all()}
        return {npi: found.get(npi) for npi in npis}


def _dataq_to_dict(p: DataqMaster) -> dict[str, Any]:
    """Serialize a DataqMaster row to the PharmacyResponse-compatible dict.

    Fields absent from dataq_master are nulled. The surrogate id is the
    7-char ncpdp_provider_id (satisfies the str type in PharmacyResponse).
    """
    return {
        "id": p.ncpdp_provider_id,
        "npi": p.npi or "",
        "nabp_number": None,                        # not in dataq_master
        "ncpdp_id": p.ncpdp_provider_id,
        "legal_name": p.legal_business_name or "",
        "dba_name": p.name,
        "display_name": p.name or p.legal_business_name or "",
        "pharmacy_type": p.primary_provider_type_code or "01",
        "chain_name": None,
        "chain_code": None,
        "store_number": p.store_number,
        "address_line_1": p.physical_location_address_1 or "",
        "address_line_2": p.physical_location_address_2,
        "city": p.physical_location_city or "",
        "state": p.physical_location_state_code or "",
        "zip_code": p.physical_location_zip_code or "",
        "county": p.physical_location_county_parish,
        "country": "US",
        "latitude": None,                           # not in dataq_master
        "longitude": None,                          # not in dataq_master
        "phone": p.physical_location_phone_number,
        "fax": p.physical_location_fax,
        "email": p.physical_location_email_address,
        "website": None,
        "is_24_hour": p.physical_location_24_hour_operation_flag or False,
        "accepts_electronic_rx": None,
        "dispenses_controlled": None,
        "offers_delivery": None,
        "offers_compounding": None,
        "offers_specialty": None,
        "offers_340b": None,
        "offers_immunizations": None,
        "offers_mtm": None,
        "status": "inactive" if p.deactivation_code else "active",
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }
