"""Network management service — create, bulk add pharmacies, adequacy."""
from __future__ import annotations

import csv
import io
import logging
import math
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tables import Network, NetworkMembership, Pharmacy

logger = logging.getLogger("pharmacy-directory.network")

_EARTH_RADIUS_MILES = 3958.8

# CMS adequacy standards (miles) — configurable per PRD 3.5
ADEQUACY_RADII = {
    "urban": 2.0,
    "suburban": 5.0,
    "rural": 15.0,
}


class NetworkService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_network(
        self,
        tenant_id: UUID,
        name: str,
        network_code: str,
        network_type: str,
        effective_date: date,
        description: str | None = None,
        any_willing_pharmacy: bool = False,
    ) -> Network:
        network = Network(
            tenant_id=tenant_id,
            name=name,
            network_code=network_code,
            network_type=network_type,
            effective_date=effective_date,
            description=description,
            any_willing_pharmacy=any_willing_pharmacy,
        )
        self._db.add(network)
        await self._db.flush()
        return network

    async def add_pharmacy_to_network(
        self,
        tenant_id: UUID,
        network_id: UUID,
        pharmacy_id: UUID,
        effective_date: date,
        dispensing_fee: Decimal | None = None,
        brand_discount: Decimal | None = None,
        generic_discount: Decimal | None = None,
        specialty_discount: Decimal | None = None,
        admin_fee: Decimal | None = None,
        reimbursement_type: str | None = None,
        performance_tier: str | None = None,
    ) -> NetworkMembership:
        membership = NetworkMembership(
            tenant_id=tenant_id,
            pharmacy_id=pharmacy_id,
            network_id=network_id,
            effective_date=effective_date,
            status="active",
            dispensing_fee=dispensing_fee,
            brand_discount=brand_discount,
            generic_discount=generic_discount,
            specialty_discount=specialty_discount,
            admin_fee=admin_fee,
            reimbursement_type=reimbursement_type,
            performance_tier=performance_tier,
        )
        self._db.add(membership)
        await self._db.flush()
        return membership

    async def remove_pharmacy_from_network(
        self,
        tenant_id: UUID,
        network_id: UUID,
        pharmacy_id: UUID,
        termination_date: date,
        termination_reason: str | None = None,
    ) -> NetworkMembership:
        stmt = (
            select(NetworkMembership)
            .where(
                NetworkMembership.network_id == network_id,
                NetworkMembership.pharmacy_id == pharmacy_id,
                NetworkMembership.status == "active",
            )
        )
        result = await self._db.execute(stmt)
        membership = result.scalar_one()
        membership.status = "terminated"
        membership.termination_date = termination_date
        membership.termination_reason = termination_reason
        await self._db.flush()
        return membership

    async def bulk_add_from_csv(
        self,
        tenant_id: UUID,
        network_id: UUID,
        csv_content: str,
        effective_date: date,
    ) -> dict[str, Any]:
        """Bulk add pharmacies from CSV with NPI column."""
        reader = csv.DictReader(io.StringIO(csv_content))
        added, not_found, errors = 0, 0, 0
        for row in reader:
            npi = (row.get("npi") or "").strip()
            if not npi:
                errors += 1
                continue
            stmt = select(Pharmacy).where(Pharmacy.npi == npi, Pharmacy.status == "active")
            result = await self._db.execute(stmt)
            pharmacy = result.scalar_one_or_none()
            if pharmacy is None:
                not_found += 1
                continue
            membership = NetworkMembership(
                tenant_id=tenant_id,
                pharmacy_id=pharmacy.id,
                network_id=network_id,
                effective_date=effective_date,
                status="active",
            )
            self._db.add(membership)
            added += 1
        await self._db.flush()
        return {"added": added, "not_found": not_found, "errors": errors}

    async def calculate_adequacy(
        self,
        tenant_id: UUID,
        network_id: UUID,
        member_locations: list[tuple[Decimal, Decimal, str]],
        area_type: str = "urban",
    ) -> dict[str, Any]:
        """Calculate network adequacy % for given member lat/lng points.

        member_locations: list of (lat, lng, region_code) tuples.
        Avoid divide-by-zero per PRD edge case note.
        """
        if not member_locations:
            return {"adequacy_pct": None, "member_count": 0, "covered_count": 0}

        radius = ADEQUACY_RADII.get(area_type, ADEQUACY_RADII["urban"])

        # Fetch active network pharmacies with coordinates
        stmt = (
            select(Pharmacy)
            .join(NetworkMembership, NetworkMembership.pharmacy_id == Pharmacy.id)
            .where(
                NetworkMembership.network_id == network_id,
                NetworkMembership.status == "active",
                Pharmacy.latitude.is_not(None),
                Pharmacy.longitude.is_not(None),
            )
        )
        result = await self._db.execute(stmt)
        network_pharmacies = result.scalars().all()

        if not network_pharmacies:
            return {
                "adequacy_pct": Decimal("0.00"),
                "member_count": len(member_locations),
                "covered_count": 0,
            }

        covered = 0
        for m_lat, m_lng, _ in member_locations:
            for pharm in network_pharmacies:
                dist = _haversine_miles(m_lat, m_lng, pharm.latitude, pharm.longitude)
                if dist <= radius:
                    covered += 1
                    break

        total = len(member_locations)
        pct = Decimal(str(round(covered / total * 100, 2)))
        return {
            "adequacy_pct": pct,
            "member_count": total,
            "covered_count": covered,
            "radius_miles": radius,
            "area_type": area_type,
        }


def _haversine_miles(lat1: Decimal, lng1: Decimal, lat2: Decimal, lng2: Decimal) -> float:
    r = _EARTH_RADIUS_MILES
    phi1, phi2 = math.radians(float(lat1)), math.radians(float(lat2))
    dphi = math.radians(float(lat2 - lat1))
    dlambda = math.radians(float(lng2 - lng1))
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
