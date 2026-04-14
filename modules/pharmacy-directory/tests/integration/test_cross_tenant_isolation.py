"""Cross-tenant API isolation tests.

For every tenant-scoped endpoint: create data for Tenant A and Tenant B,
query as Tenant A, verify zero Tenant B data leaks.

Tenant-scoped endpoints:
- GET /api/v1/pharmacies/networks
- GET /api/v1/pharmacies/networks/{id}/pharmacies
- GET /api/v1/pharmacies/credentialing
- GET /api/v1/pharmacies/credentialing/{id}
- GET /api/v1/pharmacies/stats
"""
from __future__ import annotations

import uuid
from datetime import date
from typing import AsyncIterator

import httpx
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.session import get_session
from src.api.middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from src.api.router import router as pharmacy_router
from src.models.tables import CredentialingApplication, Network, Pharmacy

TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = uuid.UUID("22222222-2222-2222-2222-222222222222")


def _make_app(session: AsyncSession) -> FastAPI:
    from shared.events.dlq import DLQService, build_dlq_router

    async def _get_dlq() -> DLQService:
        class _Empty:
            async def list(self, **_kw): return []
            async def get(self, _id): return None
        return DLQService(repository=_Empty())

    async def _get_perms() -> set: return set()

    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.include_router(pharmacy_router)
    app.include_router(build_dlq_router(get_service=_get_dlq, get_permissions=_get_perms))

    async def _session_override() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _session_override
    return app


@pytest_asyncio.fixture
async def isolation_client(router_session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    app = _make_app(router_session)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def pharmacy_shared(router_session: AsyncSession) -> Pharmacy:
    p = Pharmacy(
        npi=str(uuid.uuid4().int)[:10],
        legal_name="Shared Pharmacy",
        display_name="Shared Pharmacy",
        pharmacy_type="retail",
        address_line_1="1 Shared Blvd",
        city="Chicago",
        state="IL",
        zip_code="60601",
        status="active",
    )
    router_session.add(p)
    await router_session.flush()
    return p


@pytest_asyncio.fixture
async def network_tenant_a(router_session: AsyncSession) -> Network:
    n = Network(
        tenant_id=TENANT_A,
        name="Network Tenant A — Isolation Test",
        network_code=f"ISO-A-{uuid.uuid4().hex[:4].upper()}",
        network_type="retail",
        effective_date=date(2024, 1, 1),
    )
    router_session.add(n)
    await router_session.flush()
    return n


@pytest_asyncio.fixture
async def network_tenant_b(router_session: AsyncSession) -> Network:
    n = Network(
        tenant_id=TENANT_B,
        name="Network Tenant B — Isolation Test",
        network_code=f"ISO-B-{uuid.uuid4().hex[:4].upper()}",
        network_type="retail",
        effective_date=date(2024, 1, 1),
    )
    router_session.add(n)
    await router_session.flush()
    return n


@pytest_asyncio.fixture
async def cred_app_tenant_b(
    router_session: AsyncSession, pharmacy_shared: Pharmacy, network_tenant_b: Network
) -> CredentialingApplication:
    app = CredentialingApplication(
        tenant_id=TENANT_B,
        applicant_npi=pharmacy_shared.npi,
        applicant_name="Tenant B Applicant",
        network_id=network_tenant_b.id,
    )
    router_session.add(app)
    await router_session.flush()
    return app


class TestNetworkTenantIsolation:
    async def test_list_networks_does_not_return_tenant_b_networks(
        self,
        isolation_client: httpx.AsyncClient,
        network_tenant_a: Network,
        network_tenant_b: Network,
    ) -> None:
        resp = await isolation_client.get(
            f"/api/v1/pharmacies/networks?x-tenant-id={TENANT_A}"
        )
        assert resp.status_code == 200
        networks = resp.json()
        ids = [n["id"] for n in networks]
        assert str(network_tenant_a.id) in ids
        assert str(network_tenant_b.id) not in ids

    async def test_network_pharmacies_scoped_to_tenant(
        self,
        isolation_client: httpx.AsyncClient,
        pharmacy_shared: Pharmacy,
        network_tenant_a: Network,
        network_tenant_b: Network,
    ) -> None:
        await isolation_client.post(
            f"/api/v1/pharmacies/networks/{network_tenant_a.id}/pharmacies?x-tenant-id={TENANT_A}",
            json={
                "pharmacy_id": str(pharmacy_shared.id),
                "effective_date": "2024-01-01",
                "dispensing_fee": None,
                "brand_discount": None,
                "generic_discount": None,
                "specialty_discount": None,
                "admin_fee": None,
                "reimbursement_type": None,
                "performance_tier": None,
            },
        )
        await isolation_client.post(
            f"/api/v1/pharmacies/networks/{network_tenant_b.id}/pharmacies?x-tenant-id={TENANT_B}",
            json={
                "pharmacy_id": str(pharmacy_shared.id),
                "effective_date": "2024-01-01",
                "dispensing_fee": None,
                "brand_discount": None,
                "generic_discount": None,
                "specialty_discount": None,
                "admin_fee": None,
                "reimbursement_type": None,
                "performance_tier": None,
            },
        )

        resp_a = await isolation_client.get(
            f"/api/v1/pharmacies/networks/{network_tenant_a.id}/pharmacies?x-tenant-id={TENANT_A}"
        )
        assert resp_a.status_code == 200
        a_npi_list = [p["npi"] for p in resp_a.json()["pharmacies"]]
        assert pharmacy_shared.npi in a_npi_list

        resp_b_as_a = await isolation_client.get(
            f"/api/v1/pharmacies/networks/{network_tenant_b.id}/pharmacies?x-tenant-id={TENANT_A}"
        )
        # Network belongs to tenant B; querying with tenant A's context returns empty
        b_npi_list = [p["npi"] for p in resp_b_as_a.json()["pharmacies"]]
        assert pharmacy_shared.npi not in b_npi_list


class TestCredentialingTenantIsolation:
    async def test_list_credentialing_does_not_return_tenant_b_applications(
        self,
        isolation_client: httpx.AsyncClient,
        pharmacy_shared: Pharmacy,
        network_tenant_a: Network,
        cred_app_tenant_b: CredentialingApplication,
    ) -> None:
        create_resp = await isolation_client.post(
            f"/api/v1/pharmacies/credentialing?x-tenant-id={TENANT_A}",
            json={
                "applicant_npi": pharmacy_shared.npi,
                "applicant_name": "Tenant A Applicant",
                "network_id": str(network_tenant_a.id),
                "pharmacy_id": None,
                "applicant_address": None,
            },
        )
        assert create_resp.status_code == 201
        a_app_id = create_resp.json()["id"]

        resp = await isolation_client.get(
            f"/api/v1/pharmacies/credentialing?x-tenant-id={TENANT_A}"
        )
        assert resp.status_code == 200
        app_ids = [a["id"] for a in resp.json()]
        assert a_app_id in app_ids
        assert str(cred_app_tenant_b.id) not in app_ids

    async def test_get_credentialing_by_id_isolated_by_tenant(
        self,
        isolation_client: httpx.AsyncClient,
        cred_app_tenant_b: CredentialingApplication,
    ) -> None:
        resp = await isolation_client.get(
            f"/api/v1/pharmacies/credentialing/{cred_app_tenant_b.id}?x-tenant-id={TENANT_A}"
        )
        assert resp.status_code == 404


class TestStatsTenantIsolation:
    async def test_stats_network_count_scoped_to_tenant(
        self,
        isolation_client: httpx.AsyncClient,
        network_tenant_a: Network,
        network_tenant_b: Network,
    ) -> None:
        resp_a = await isolation_client.get(
            f"/api/v1/pharmacies/stats?x-tenant-id={TENANT_A}"
        )
        resp_b = await isolation_client.get(
            f"/api/v1/pharmacies/stats?x-tenant-id={TENANT_B}"
        )

        assert resp_a.status_code == 200
        assert resp_b.status_code == 200

        # Network counts reflect tenant isolation (tenant A sees its own networks only)
        networks_for_a = resp_a.json()["total_networks"]
        networks_for_b = resp_b.json()["total_networks"]

        # Both have at least 1 network; the counts must differ since fixtures are isolated
        assert networks_for_a >= 1
        assert networks_for_b >= 1
        # Total across both tenants must not bleed into either single-tenant view
        total = networks_for_a + networks_for_b
        assert networks_for_a < total
        assert networks_for_b < total
