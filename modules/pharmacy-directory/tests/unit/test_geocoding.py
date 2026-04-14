"""RED tests: geocoding adapter interface."""
from __future__ import annotations

import pytest

from src.services.geocoding import GeocodingResult, MockGeocodingAdapter


class TestMockGeocodingAdapter:
    @pytest.mark.asyncio
    async def test_geocode_returns_lat_lng(self) -> None:
        adapter = MockGeocodingAdapter()
        result = await adapter.geocode("123 Main St, Springfield, IL 62701")
        assert isinstance(result, GeocodingResult)
        assert result.latitude is not None
        assert result.longitude is not None

    @pytest.mark.asyncio
    async def test_geocode_unknown_address_returns_none(self) -> None:
        adapter = MockGeocodingAdapter()
        result = await adapter.geocode("")
        assert result is None

    @pytest.mark.asyncio
    async def test_geocode_result_has_valid_decimal_precision(self) -> None:
        adapter = MockGeocodingAdapter()
        result = await adapter.geocode("100 Test Ave, Boston, MA 02101")
        assert result is not None
        # lat/lng stored as Decimal with 7dp precision
        lat_str = str(result.latitude)
        assert "." in lat_str
