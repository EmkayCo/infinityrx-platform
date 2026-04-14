"""PostGIS geo analytics service.

Provides network adequacy calculations and drug desert detection.
Uses haversine formula for in-memory calculations; production will
use ST_DWithin + ST_Distance PostGIS queries.

All distances returned as Decimal (miles).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

_MILES_PER_METER = Decimal("0.000621371")
_METERS_PER_MILE = Decimal("1609.344").quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
_EARTH_RADIUS_MILES = Decimal("3958.8")

# CMS drug desert threshold: < 1 pharmacy per 10,000 members
_PHARMACY_PER_10K_THRESHOLD = Decimal("1")


@dataclass(frozen=True)
class MemberLocation:
    member_id: str
    lat: Decimal
    lon: Decimal


@dataclass(frozen=True)
class PharmacyLocation:
    pharmacy_id: str
    lat: Decimal
    lon: Decimal
    is_in_network: bool


@dataclass(frozen=True)
class NetworkAdequacyResult:
    total_members: int
    covered_members: int
    pct_members_covered: Decimal
    radius_miles: Decimal


def miles_to_meters(miles: Decimal) -> Decimal:
    """Convert miles to meters (CMS standard conversion)."""
    result = miles * Decimal("1609.34")
    return result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _haversine_miles(lat1: Decimal, lon1: Decimal, lat2: Decimal, lon2: Decimal) -> Decimal:
    """Calculate great-circle distance in miles using haversine formula."""
    r = float(_EARTH_RADIUS_MILES)
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    dphi = math.radians(float(lat2 - lat1))
    dlambda = math.radians(float(lon2 - lon1))

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return Decimal(str(round(r * c, 6)))


def calculate_network_adequacy(
    members: list[MemberLocation],
    pharmacies: list[PharmacyLocation],
    radius_miles: Decimal,
) -> NetworkAdequacyResult:
    """Calculate % of members within radius_miles of an in-network pharmacy.

    Uses haversine for in-memory testing; production uses ST_DWithin.
    Only in-network pharmacies count toward coverage.
    """
    if not members:
        return NetworkAdequacyResult(
            total_members=0,
            covered_members=0,
            pct_members_covered=Decimal("0.00"),
            radius_miles=radius_miles,
        )

    in_network = [p for p in pharmacies if p.is_in_network]

    if not in_network:
        return NetworkAdequacyResult(
            total_members=len(members),
            covered_members=0,
            pct_members_covered=Decimal("0.00"),
            radius_miles=radius_miles,
        )

    covered = 0
    for member in members:
        for pharmacy in in_network:
            dist = _haversine_miles(member.lat, member.lon, pharmacy.lat, pharmacy.lon)
            if dist <= radius_miles:
                covered += 1
                break

    total = len(members)
    pct = (Decimal(str(covered)) / Decimal(str(total)) * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    return NetworkAdequacyResult(
        total_members=total,
        covered_members=covered,
        pct_members_covered=pct,
        radius_miles=radius_miles,
    )


def is_drug_desert(pharmacies: int, population: int) -> bool:
    """Return True if area has < 1 pharmacy per 10,000 members (drug desert).

    Raises:
        ValueError: If population is zero.
    """
    if population == 0:
        raise ValueError("population must be > 0")
    rate_per_10k = Decimal(str(pharmacies)) / Decimal(str(population)) * Decimal("10000")
    return rate_per_10k < _PHARMACY_PER_10K_THRESHOLD
