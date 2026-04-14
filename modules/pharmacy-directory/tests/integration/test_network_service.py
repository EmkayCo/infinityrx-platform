"""Integration tests for NetworkService — tenant isolation, adequacy."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tables import Network, NetworkMembership, Pharmacy
from src.services.network import NetworkService

TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = uuid.UUID("22222222-2222-2222-2222-222222222222")


class TestNetworkService:
    @pytest.mark.asyncio
    async def test_create_network_stores_tenant_id(self, db_session: AsyncSession) -> None:
        svc = NetworkService(db_session)
        network = await svc.create_network(
            tenant_id=TENANT_A,
            name="Test Net",
            network_code="TST-1",
            network_type="retail",
            effective_date=date(2024, 1, 1),
        )
        assert network.tenant_id == TENANT_A

    @pytest.mark.asyncio
    async def test_add_pharmacy_to_network_creates_membership(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy, network_a: Network
    ) -> None:
        svc = NetworkService(db_session)
        membership = await svc.add_pharmacy_to_network(
            tenant_id=TENANT_A,
            network_id=network_a.id,
            pharmacy_id=pharmacy_a.id,
            effective_date=date(2024, 1, 1),
            dispensing_fee=Decimal("1.50"),
            brand_discount=Decimal("0.1500"),
        )
        assert membership.status == "active"
        assert membership.dispensing_fee == Decimal("1.50")

    @pytest.mark.asyncio
    async def test_remove_pharmacy_terminates_membership(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy, network_a: Network
    ) -> None:
        svc = NetworkService(db_session)
        await svc.add_pharmacy_to_network(
            tenant_id=TENANT_A,
            network_id=network_a.id,
            pharmacy_id=pharmacy_a.id,
            effective_date=date(2024, 1, 1),
        )
        membership = await svc.remove_pharmacy_from_network(
            tenant_id=TENANT_A,
            network_id=network_a.id,
            pharmacy_id=pharmacy_a.id,
            termination_date=date(2025, 12, 31),
            termination_reason="Contract expired",
        )
        assert membership.status == "terminated"
        assert membership.termination_reason == "Contract expired"

    @pytest.mark.asyncio
    async def test_bulk_add_from_csv_adds_pharmacies(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy, network_a: Network
    ) -> None:
        csv_content = f"npi\n{pharmacy_a.npi}\n"
        svc = NetworkService(db_session)
        result = await svc.bulk_add_from_csv(
            TENANT_A, network_a.id, csv_content, date(2024, 1, 1)
        )
        assert result["added"] == 1
        assert result["not_found"] == 0

    @pytest.mark.asyncio
    async def test_bulk_add_unknown_npi_counted_as_not_found(
        self, db_session: AsyncSession, network_a: Network
    ) -> None:
        csv_content = "npi\n0000000000\n"
        svc = NetworkService(db_session)
        result = await svc.bulk_add_from_csv(
            TENANT_A, network_a.id, csv_content, date(2024, 1, 1)
        )
        assert result["not_found"] == 1

    @pytest.mark.asyncio
    async def test_adequacy_with_zero_members_returns_none(
        self, db_session: AsyncSession, network_a: Network
    ) -> None:
        svc = NetworkService(db_session)
        result = await svc.calculate_adequacy(TENANT_A, network_a.id, [])
        assert result["member_count"] == 0
        assert result["adequacy_pct"] is None

    @pytest.mark.asyncio
    async def test_bulk_add_empty_npi_row_counted_as_error(
        self, db_session: AsyncSession, network_a: Network
    ) -> None:
        # A row with whitespace-only NPI triggers the errors branch
        csv_content = "npi\n   \n"
        svc = NetworkService(db_session)
        result = await svc.bulk_add_from_csv(TENANT_A, network_a.id, csv_content, date(2024, 1, 1))
        assert result["errors"] == 1
        assert result["added"] == 0

    @pytest.mark.asyncio
    async def test_adequacy_with_members_but_no_network_pharmacies_returns_zero(
        self, db_session: AsyncSession, network_a: Network
    ) -> None:
        svc = NetworkService(db_session)
        member_locations = [(Decimal("41.8781136"), Decimal("-87.6297982"), "REGION_1")]
        result = await svc.calculate_adequacy(TENANT_A, network_a.id, member_locations, "urban")
        assert result["adequacy_pct"] == Decimal("0.00")
        assert result["member_count"] == 1
        assert result["covered_count"] == 0

    @pytest.mark.asyncio
    async def test_adequacy_member_outside_radius_not_covered(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy, network_a: Network
    ) -> None:
        pharmacy_a.latitude = Decimal("41.8781136")
        pharmacy_a.longitude = Decimal("-87.6297982")
        await db_session.flush()

        svc = NetworkService(db_session)
        await svc.add_pharmacy_to_network(
            TENANT_A, network_a.id, pharmacy_a.id, date(2024, 1, 1)
        )

        member_locations = [
            (Decimal("34.0522342"), Decimal("-118.2436849"), "LA"),  # far from Chicago pharmacy
        ]
        result = await svc.calculate_adequacy(TENANT_A, network_a.id, member_locations, "urban")
        assert result["adequacy_pct"] == Decimal("0.0")
        assert result["covered_count"] == 0

    @pytest.mark.asyncio
    async def test_adequacy_all_covered_returns_100(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy, network_a: Network
    ) -> None:
        pharmacy_a.latitude = Decimal("41.8781136")
        pharmacy_a.longitude = Decimal("-87.6297982")
        await db_session.flush()

        svc = NetworkService(db_session)
        await svc.add_pharmacy_to_network(
            TENANT_A, network_a.id, pharmacy_a.id, date(2024, 1, 1)
        )

        member_locations = [
            (Decimal("41.8781136"), Decimal("-87.6297982"), "REGION_1"),
        ]
        result = await svc.calculate_adequacy(TENANT_A, network_a.id, member_locations, "urban")
        assert result["adequacy_pct"] == Decimal("100.0")


class TestNetworkTenantIsolation:
    @pytest.mark.asyncio
    async def test_tenant_b_network_not_visible_to_tenant_a(
        self, db_session: AsyncSession, network_a: Network, network_b: Network
    ) -> None:
        stmt = select(Network).where(Network.tenant_id == TENANT_A)
        result = await db_session.execute(stmt)
        networks = result.scalars().all()
        network_ids = [n.id for n in networks]
        assert network_a.id in network_ids
        assert network_b.id not in network_ids

    @pytest.mark.asyncio
    async def test_membership_tenant_scoping(
        self,
        db_session: AsyncSession,
        pharmacy_a: Pharmacy,
        network_a: Network,
        network_b: Network,
    ) -> None:
        svc = NetworkService(db_session)
        await svc.add_pharmacy_to_network(TENANT_A, network_a.id, pharmacy_a.id, date(2024, 1, 1))
        await svc.add_pharmacy_to_network(TENANT_B, network_b.id, pharmacy_a.id, date(2024, 1, 1))

        stmt_a = select(NetworkMembership).where(NetworkMembership.tenant_id == TENANT_A)
        result_a = (await db_session.execute(stmt_a)).scalars().all()
        assert all(m.tenant_id == TENANT_A for m in result_a)

        stmt_b = select(NetworkMembership).where(NetworkMembership.tenant_id == TENANT_B)
        result_b = (await db_session.execute(stmt_b)).scalars().all()
        assert all(m.tenant_id == TENANT_B for m in result_b)

        a_ids = {m.id for m in result_a}
        b_ids = {m.id for m in result_b}
        assert a_ids.isdisjoint(b_ids)
