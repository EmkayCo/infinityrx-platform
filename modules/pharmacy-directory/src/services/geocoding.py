"""Geocoding adapter — mockable interface for Azure Maps / Google."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class GeocodingResult:
    latitude: Decimal
    longitude: Decimal
    confidence: str = "high"


class GeocodingAdapter(ABC):
    @abstractmethod
    async def geocode(self, address: str) -> GeocodingResult | None:
        """Geocode an address string to lat/lng. Returns None if not found."""


class MockGeocodingAdapter(GeocodingAdapter):
    """Deterministic stub used in tests and local dev."""

    async def geocode(self, address: str) -> GeocodingResult | None:
        if not address.strip():
            return None
        # Deterministic offset based on address length for test variety
        base_lat = Decimal("41.8781136")
        base_lng = Decimal("-87.6297982")
        offset = Decimal(str(len(address) % 100)) * Decimal("0.0001000")
        return GeocodingResult(
            latitude=(base_lat + offset).quantize(Decimal("0.0000001")),
            longitude=(base_lng - offset).quantize(Decimal("0.0000001")),
        )
