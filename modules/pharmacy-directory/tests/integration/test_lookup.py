"""Integration tests for PharmacyLookupService."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tables import Pharmacy
from src.services.lookup import PharmacyLookupService

TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")


class TestPharmacyLookupService:
    @pytest.mark.asyncio
    async def test_get_by_npi_returns_pharmacy(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy
    ) -> None:
        svc = PharmacyLookupService(db_session)
        result = await svc.get_by_npi(TENANT_A, pharmacy_a.npi)
        assert result is not None
        assert result["npi"] == pharmacy_a.npi

    @pytest.mark.asyncio
    async def test_get_by_npi_returns_none_for_unknown(self, db_session: AsyncSession) -> None:
        svc = PharmacyLookupService(db_session)
        result = await svc.get_by_npi(TENANT_A, "0000000000")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_nabp_returns_pharmacy(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy
    ) -> None:
        svc = PharmacyLookupService(db_session)
        result = await svc.get_by_nabp(TENANT_A, pharmacy_a.nabp_number)
        assert result is not None
        assert result["nabp_number"] == pharmacy_a.nabp_number

    @pytest.mark.asyncio
    async def test_get_by_nabp_returns_none_for_unknown(self, db_session: AsyncSession) -> None:
        svc = PharmacyLookupService(db_session)
        result = await svc.get_by_nabp(TENANT_A, "0000000")
        assert result is None

    @pytest.mark.asyncio
    async def test_search_by_name_finds_partial_match(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy
    ) -> None:
        svc = PharmacyLookupService(db_session)
        results = await svc.search_by_name("Test")
        npis = [r["npi"] for r in results]
        assert pharmacy_a.npi in npis

    @pytest.mark.asyncio
    async def test_search_by_name_returns_empty_for_no_match(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy
    ) -> None:
        svc = PharmacyLookupService(db_session)
        results = await svc.search_by_name("ZZZZNONEXISTENT")
        assert results == []

    @pytest.mark.asyncio
    async def test_batch_lookup_returns_all_npis(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy, pharmacy_b: Pharmacy
    ) -> None:
        svc = PharmacyLookupService(db_session)
        result = await svc.batch_lookup(TENANT_A, [pharmacy_a.npi, pharmacy_b.npi, "0000000000"])
        assert result[pharmacy_a.npi] is not None
        assert result[pharmacy_b.npi] is not None
        assert result["0000000000"] is None

    @pytest.mark.asyncio
    async def test_batch_lookup_empty_list_returns_empty_dict(
        self, db_session: AsyncSession
    ) -> None:
        svc = PharmacyLookupService(db_session)
        result = await svc.batch_lookup(TENANT_A, [])
        assert result == {}

    @pytest.mark.asyncio
    async def test_search_nearby_returns_pharmacies_within_radius(
        self, db_session: AsyncSession
    ) -> None:
        p = Pharmacy(
            npi="5555555555",
            legal_name="Geo Pharmacy",
            display_name="Geo Pharmacy",
            pharmacy_type="retail",
            address_line_1="1 Geo St",
            city="Chicago",
            state="IL",
            zip_code="60601",
            status="active",
            latitude=Decimal("41.8781136"),
            longitude=Decimal("-87.6297982"),
        )
        db_session.add(p)
        await db_session.flush()

        svc = PharmacyLookupService(db_session)
        results = await svc.search_nearby(
            lat=Decimal("41.8781136"),
            lng=Decimal("-87.6297982"),
            radius_miles=1.0,
        )
        npis = [r["npi"] for r in results]
        assert "5555555555" in npis

    @pytest.mark.asyncio
    async def test_search_nearby_with_pharmacy_type_filter(
        self, db_session: AsyncSession
    ) -> None:
        p = Pharmacy(
            npi="7777777770",
            legal_name="Specialty Geo",
            display_name="Specialty Geo",
            pharmacy_type="specialty",
            address_line_1="2 Geo St",
            city="Chicago",
            state="IL",
            zip_code="60601",
            status="active",
            latitude=Decimal("41.8781136"),
            longitude=Decimal("-87.6297982"),
        )
        db_session.add(p)
        await db_session.flush()

        svc = PharmacyLookupService(db_session)
        results = await svc.search_nearby(
            lat=Decimal("41.8781136"),
            lng=Decimal("-87.6297982"),
            radius_miles=1.0,
            pharmacy_type="retail",
        )
        npis = [r["npi"] for r in results]
        assert "7777777770" not in npis

    @pytest.mark.asyncio
    async def test_get_by_npi_with_cache_uses_cache_on_hit(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy
    ) -> None:
        from unittest.mock import AsyncMock
        from src.services.cache import PharmacyCache

        mock_redis = type("R", (), {
            "get": AsyncMock(return_value='{"npi": "cached-npi", "display_name": "Cached"}'),
            "set": AsyncMock(),
        })()
        cache = PharmacyCache(mock_redis)
        svc = PharmacyLookupService(db_session, cache=cache)
        result = await svc.get_by_npi(TENANT_A, pharmacy_a.npi)
        assert result["npi"] == "cached-npi"

    @pytest.mark.asyncio
    async def test_get_by_npi_with_cache_stores_result(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy
    ) -> None:
        from unittest.mock import AsyncMock
        from src.services.cache import PharmacyCache

        mock_redis = type("R", (), {
            "get": AsyncMock(return_value=None),
            "set": AsyncMock(),
        })()
        cache = PharmacyCache(mock_redis)
        svc = PharmacyLookupService(db_session, cache=cache)
        result = await svc.get_by_npi(TENANT_A, pharmacy_a.npi)
        assert result is not None
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_nabp_with_cache_uses_cache_on_hit(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy
    ) -> None:
        from unittest.mock import AsyncMock
        from src.services.cache import PharmacyCache

        mock_redis = type("R", (), {
            "get": AsyncMock(return_value='{"npi": "cached-npi", "display_name": "Cached"}'),
            "set": AsyncMock(),
        })()
        cache = PharmacyCache(mock_redis)
        svc = PharmacyLookupService(db_session, cache=cache)
        result = await svc.get_by_nabp(TENANT_A, pharmacy_a.nabp_number)
        assert result["npi"] == "cached-npi"

    @pytest.mark.asyncio
    async def test_get_by_nabp_with_cache_stores_result(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy
    ) -> None:
        from unittest.mock import AsyncMock
        from src.services.cache import PharmacyCache

        mock_redis = type("R", (), {
            "get": AsyncMock(return_value=None),
            "set": AsyncMock(),
        })()
        cache = PharmacyCache(mock_redis)
        svc = PharmacyLookupService(db_session, cache=cache)
        result = await svc.get_by_nabp(TENANT_A, pharmacy_a.nabp_number)
        assert result is not None
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_nearby_excludes_pharmacy_outside_exact_radius(
        self, db_session: AsyncSession
    ) -> None:
        """Pharmacy is inside bounding box but outside exact haversine radius.

        The bounding box pre-filter is a square; a pharmacy at the diagonal corner
        passes the box check but fails the true circular distance check.
        At 41.878°N, 5-mile box half-widths: lat_delta≈0.0723°, lng_delta≈0.0972°.
        Placing pharmacy at (+0.07°N, -0.09°E) puts it inside the box (~6.8 mi away).
        """
        p = Pharmacy(
            npi="8888888880",
            legal_name="Near Miss Pharmacy",
            display_name="Near Miss Pharmacy",
            pharmacy_type="retail",
            address_line_1="1 Near St",
            city="Chicago",
            state="IL",
            zip_code="60601",
            status="active",
            latitude=Decimal("41.9481136"),   # +0.07° N inside bounding box
            longitude=Decimal("-87.7197982"),  # -0.09° W inside bounding box
        )
        db_session.add(p)
        await db_session.flush()

        svc = PharmacyLookupService(db_session)
        # Search with 5 mile radius — pharmacy is ~6.8 miles away (outside circle)
        results = await svc.search_nearby(
            lat=Decimal("41.8781136"),
            lng=Decimal("-87.6297982"),
            radius_miles=5.0,
        )
        npis = [r["npi"] for r in results]
        assert "8888888880" not in npis

    @pytest.mark.asyncio
    async def test_search_nearby_excludes_pharmacies_outside_radius(
        self, db_session: AsyncSession
    ) -> None:
        p = Pharmacy(
            npi="6666666666",
            legal_name="Far Pharmacy",
            display_name="Far Pharmacy",
            pharmacy_type="retail",
            address_line_1="1 Far St",
            city="Los Angeles",
            state="CA",
            zip_code="90001",
            status="active",
            latitude=Decimal("34.0522342"),
            longitude=Decimal("-118.2437486"),
        )
        db_session.add(p)
        await db_session.flush()

        svc = PharmacyLookupService(db_session)
        results = await svc.search_nearby(
            lat=Decimal("41.8781136"),  # Chicago
            lng=Decimal("-87.6297982"),
            radius_miles=10.0,
        )
        npis = [r["npi"] for r in results]
        assert "6666666666" not in npis
