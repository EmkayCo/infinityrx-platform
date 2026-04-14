"""Pharmacy lookup service — NPI, NABP, name (full-text), geographic."""
from __future__ import annotations

import logging
import math
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tables import Pharmacy
from src.services.cache import PharmacyCache

logger = logging.getLogger("pharmacy-directory.lookup")

_EARTH_RADIUS_MILES = 3958.8


def _haversine_miles(lat1: Decimal, lng1: Decimal, lat2: Decimal, lng2: Decimal) -> float:
    """Fallback haversine distance in miles when PostGIS is unavailable."""
    r = _EARTH_RADIUS_MILES
    phi1, phi2 = math.radians(float(lat1)), math.radians(float(lat2))
    dphi = math.radians(float(lat2 - lat1))
    dlambda = math.radians(float(lng2 - lng1))
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class PharmacyLookupService:
    def __init__(self, db: AsyncSession, cache: PharmacyCache | None = None) -> None:
        self._db = db
        self._cache = cache

    async def get_by_npi(self, tenant_id: UUID, npi: str) -> dict[str, Any] | None:
        if self._cache:
            cached = await self._cache.get_by_npi(tenant_id, npi)
            if cached is not None:
                return cached

        stmt = select(Pharmacy).where(Pharmacy.npi == npi)
        result = await self._db.execute(stmt)
        pharmacy = result.scalar_one_or_none()
        if pharmacy is None:
            return None

        data = _pharmacy_to_dict(pharmacy)
        if self._cache:
            await self._cache.set_by_npi(tenant_id, npi, data)
        return data

    async def get_by_nabp(self, tenant_id: UUID, nabp: str) -> dict[str, Any] | None:
        if self._cache:
            cached = await self._cache.get_by_nabp(tenant_id, nabp)
            if cached is not None:
                return cached

        stmt = select(Pharmacy).where(Pharmacy.nabp_number == nabp)
        result = await self._db.execute(stmt)
        pharmacy = result.scalar_one_or_none()
        if pharmacy is None:
            return None

        data = _pharmacy_to_dict(pharmacy)
        if self._cache:
            await self._cache.set_by_nabp(tenant_id, nabp, data)
        return data

    async def search_by_name(
        self, query: str, limit: int = 20, offset: int = 0
    ) -> list[dict[str, Any]]:
        stmt = (
            select(Pharmacy)
            .where(
                Pharmacy.display_name.ilike(f"%{query}%")
            )
            .where(Pharmacy.status == "active")
            .order_by(Pharmacy.display_name)
            .limit(limit)
            .offset(offset)
        )
        result = await self._db.execute(stmt)
        return [_pharmacy_to_dict(p) for p in result.scalars().all()]

    async def search_nearby(
        self,
        lat: Decimal,
        lng: Decimal,
        radius_miles: float,
        pharmacy_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Geographic search using haversine distance (PostGIS fallback)."""
        # Bounding box pre-filter to reduce scan
        lat_delta = Decimal(str(radius_miles / _EARTH_RADIUS_MILES * 57.2958))
        lng_delta = lat_delta / Decimal(str(max(math.cos(math.radians(float(lat))), 0.001)))

        stmt = select(Pharmacy).where(
            Pharmacy.latitude.is_not(None),
            Pharmacy.longitude.is_not(None),
            Pharmacy.latitude.between(lat - lat_delta, lat + lat_delta),
            Pharmacy.longitude.between(lng - lng_delta, lng + lng_delta),
            Pharmacy.status == "active",
        )
        if pharmacy_type:
            stmt = stmt.where(Pharmacy.pharmacy_type == pharmacy_type)

        result = await self._db.execute(stmt)
        candidates = result.scalars().all()

        # Exact haversine filter (bounding box above already excludes null coords)
        matches: list[tuple[float, dict[str, Any]]] = []
        for p in candidates:
            dist = _haversine_miles(lat, lng, p.latitude, p.longitude)
            if dist <= radius_miles:
                data = _pharmacy_to_dict(p)
                data["distance_miles"] = round(dist, 2)
                matches.append((dist, data))

        matches.sort(key=lambda x: x[0])
        return [m[1] for m in matches[:limit]]

    async def batch_lookup(
        self, tenant_id: UUID, npis: list[str]
    ) -> dict[str, dict[str, Any] | None]:
        if not npis:
            return {}
        stmt = select(Pharmacy).where(Pharmacy.npi.in_(npis))
        result = await self._db.execute(stmt)
        found = {p.npi: _pharmacy_to_dict(p) for p in result.scalars().all()}
        return {npi: found.get(npi) for npi in npis}


def _pharmacy_to_dict(p: Pharmacy) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "npi": p.npi,
        "nabp_number": p.nabp_number,
        "ncpdp_id": p.ncpdp_id,
        "legal_name": p.legal_name,
        "dba_name": p.dba_name,
        "display_name": p.display_name,
        "pharmacy_type": p.pharmacy_type,
        "chain_name": p.chain_name,
        "chain_code": p.chain_code,
        "store_number": p.store_number,
        "address_line_1": p.address_line_1,
        "address_line_2": p.address_line_2,
        "city": p.city,
        "state": p.state,
        "zip_code": p.zip_code,
        "county": p.county,
        "country": p.country,
        "latitude": str(p.latitude) if p.latitude is not None else None,
        "longitude": str(p.longitude) if p.longitude is not None else None,
        "phone": p.phone,
        "fax": p.fax,
        "email": p.email,
        "website": p.website,
        "is_24_hour": p.is_24_hour,
        "accepts_electronic_rx": p.accepts_electronic_rx,
        "dispenses_controlled": p.dispenses_controlled,
        "offers_delivery": p.offers_delivery,
        "offers_compounding": p.offers_compounding,
        "offers_specialty": p.offers_specialty,
        "offers_340b": p.offers_340b,
        "offers_immunizations": p.offers_immunizations,
        "offers_mtm": p.offers_mtm,
        "status": p.status,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }
