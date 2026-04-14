"""Integration tests for the pharmacy-directory API router (LESSON-006).

Uses httpx.AsyncClient + ASGITransport so that coverage.py can trace
async route handlers (TestClient runs ASGI in a separate thread where
coverage cannot follow; httpx.AsyncClient runs in the same asyncio loop).

IMPORTANT: Uses router_session (no SAVEPOINT event listener) instead of
db_session. The SAVEPOINT event listener interferes with coverage.py's
C tracer because it executes synchronous code from within async context,
breaking the tracer's coroutine tracking. Routes call flush() not commit()
so SAVEPOINT restart is unnecessary.
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
from src.models.tables import Network, Pharmacy

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

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "module": "pharmacy-directory"}

    return app


@pytest_asyncio.fixture
async def client(router_session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    app = _make_app(router_session)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def pharmacy_a_rs(router_session: AsyncSession) -> Pharmacy:
    """pharmacy_a using router_session (no SAVEPOINT listener)."""
    p = Pharmacy(
        npi=str(uuid.uuid4().int)[:10],
        nabp_number=str(uuid.uuid4().int)[:7],
        legal_name="Test Pharmacy A",
        display_name="Test Pharmacy A",
        pharmacy_type="retail",
        address_line_1="100 Main St",
        city="Springfield",
        state="IL",
        zip_code="62701",
        status="active",
    )
    router_session.add(p)
    await router_session.flush()
    return p


@pytest_asyncio.fixture
async def network_a_rs(router_session: AsyncSession) -> Network:
    """network_a using router_session (no SAVEPOINT listener)."""
    n = Network(
        tenant_id=TENANT_A,
        name="Retail Network A",
        network_code=f"RET-{uuid.uuid4().hex[:4].upper()}",
        network_type="retail",
        effective_date=date(2024, 1, 1),
    )
    router_session.add(n)
    await router_session.flush()
    return n


class TestLookupEndpoints:
    async def test_get_by_npi_returns_pharmacy(
        self, client: httpx.AsyncClient, pharmacy_a_rs: Pharmacy
    ) -> None:
        resp = await client.get(f"/api/v1/pharmacies/lookup/{pharmacy_a_rs.npi}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["npi"] == pharmacy_a_rs.npi
        assert body["display_name"] == pharmacy_a_rs.display_name

    async def test_get_by_npi_invalid_format_returns_400(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/api/v1/pharmacies/lookup/NOTANNPI")
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"]["code"] == "INVALID_NPI"

    async def test_get_by_npi_not_found_returns_404(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/api/v1/pharmacies/lookup/9999999999")
        assert resp.status_code == 404
        assert resp.json()["detail"]["error"]["code"] == "PHARMACY_NOT_FOUND"

    async def test_get_by_nabp_returns_pharmacy(
        self, client: httpx.AsyncClient, pharmacy_a_rs: Pharmacy
    ) -> None:
        resp = await client.get(f"/api/v1/pharmacies/lookup/nabp/{pharmacy_a_rs.nabp_number}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["nabp_number"] == pharmacy_a_rs.nabp_number

    async def test_get_by_nabp_not_found_returns_404(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/api/v1/pharmacies/lookup/nabp/9999999")
        assert resp.status_code == 404
        assert resp.json()["detail"]["error"]["code"] == "PHARMACY_NOT_FOUND"

    async def test_search_returns_results(
        self, client: httpx.AsyncClient, pharmacy_a_rs: Pharmacy
    ) -> None:
        resp = await client.get("/api/v1/pharmacies/search?q=Test")
        assert resp.status_code == 200
        body = resp.json()
        assert "pharmacies" in body
        assert body["total"] >= 1

    async def test_nearby_returns_results(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/api/v1/pharmacies/nearby?lat=39.0&lng=-89.0&radius_miles=5.0")
        assert resp.status_code == 200
        assert "pharmacies" in resp.json()

    async def test_batch_lookup_returns_dict(
        self, client: httpx.AsyncClient, pharmacy_a_rs: Pharmacy
    ) -> None:
        resp = await client.post(
            "/api/v1/pharmacies/batch",
            json={"npis": [pharmacy_a_rs.npi, "0000000000"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body[pharmacy_a_rs.npi] is not None
        assert body["0000000000"] is None

    async def test_batch_lookup_empty_list_returns_422(self, client: httpx.AsyncClient) -> None:
        resp = await client.post("/api/v1/pharmacies/batch", json={"npis": []})
        assert resp.status_code == 422


class TestNetworkEndpoints:
    async def test_list_networks_empty_initially(self, client: httpx.AsyncClient) -> None:
        tid = uuid.uuid4()
        resp = await client.get(f"/api/v1/pharmacies/networks?x-tenant-id={tid}")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_network_returns_201_with_schema(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            f"/api/v1/pharmacies/networks?x-tenant-id={TENANT_A}",
            json={
                "name": "Test Network",
                "network_code": "TST-NET-1",
                "network_type": "retail",
                "effective_date": "2024-01-01",
                "description": "Test desc",
                "any_willing_pharmacy": False,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Test Network"
        assert body["tenant_id"] == str(TENANT_A)
        assert body["network_code"] == "TST-NET-1"
        assert "id" in body

    async def test_list_networks_returns_created_network(
        self, client: httpx.AsyncClient, network_a_rs: Network
    ) -> None:
        resp = await client.get(f"/api/v1/pharmacies/networks?x-tenant-id={TENANT_A}")
        assert resp.status_code == 200
        names = [n["name"] for n in resp.json()]
        assert "Retail Network A" in names

    async def test_list_network_pharmacies_empty(
        self, client: httpx.AsyncClient, network_a_rs: Network
    ) -> None:
        resp = await client.get(
            f"/api/v1/pharmacies/networks/{network_a_rs.id}/pharmacies?x-tenant-id={TENANT_A}"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0

    async def test_add_pharmacy_to_network_returns_201(
        self, client: httpx.AsyncClient, pharmacy_a_rs: Pharmacy, network_a_rs: Network
    ) -> None:
        resp = await client.post(
            f"/api/v1/pharmacies/networks/{network_a_rs.id}/pharmacies?x-tenant-id={TENANT_A}",
            json={
                "pharmacy_id": str(pharmacy_a_rs.id),
                "effective_date": "2024-01-01",
                "dispensing_fee": "1.50",
                "brand_discount": None,
                "generic_discount": None,
                "specialty_discount": None,
                "admin_fee": None,
                "reimbursement_type": None,
                "performance_tier": None,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "active"
        assert body["pharmacy_id"] == str(pharmacy_a_rs.id)

    async def test_list_network_pharmacies_with_member(
        self, client: httpx.AsyncClient, pharmacy_a_rs: Pharmacy, network_a_rs: Network
    ) -> None:
        await client.post(
            f"/api/v1/pharmacies/networks/{network_a_rs.id}/pharmacies?x-tenant-id={TENANT_A}",
            json={
                "pharmacy_id": str(pharmacy_a_rs.id),
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
        resp = await client.get(
            f"/api/v1/pharmacies/networks/{network_a_rs.id}/pharmacies?x-tenant-id={TENANT_A}"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        assert body["pharmacies"][0]["npi"] == pharmacy_a_rs.npi

    async def test_network_adequacy_returns_result(
        self, client: httpx.AsyncClient, network_a_rs: Network
    ) -> None:
        resp = await client.get(
            f"/api/v1/pharmacies/networks/{network_a_rs.id}/adequacy?x-tenant-id={TENANT_A}&area_type=urban"
        )
        assert resp.status_code == 200
        assert "adequacy_pct" in resp.json()

    async def test_bulk_add_pharmacies_returns_result(
        self, client: httpx.AsyncClient, pharmacy_a_rs: Pharmacy, network_a_rs: Network
    ) -> None:
        csv_content = f"npi\n{pharmacy_a_rs.npi}\n"
        resp = await client.post(
            f"/api/v1/pharmacies/networks/{network_a_rs.id}/bulk-add"
            f"?x-tenant-id={TENANT_A}&effective_date=2024-01-01",
            files={"file": ("pharmacies.csv", csv_content.encode("utf-8"), "text/csv")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "added" in body or "errors" in body


class TestCredentialingEndpoints:
    async def test_submit_credentialing_returns_201(
        self, client: httpx.AsyncClient, pharmacy_a_rs: Pharmacy, network_a_rs: Network
    ) -> None:
        resp = await client.post(
            f"/api/v1/pharmacies/credentialing?x-tenant-id={TENANT_A}",
            json={
                "applicant_npi": pharmacy_a_rs.npi,
                "applicant_name": "Test Pharmacy A",
                "network_id": str(network_a_rs.id),
                "pharmacy_id": str(pharmacy_a_rs.id),
                "applicant_address": None,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "submitted"
        assert body["applicant_npi"] == pharmacy_a_rs.npi
        assert "id" in body

    async def test_submit_credentialing_invalid_npi_returns_400(
        self, client: httpx.AsyncClient, network_a_rs: Network
    ) -> None:
        resp = await client.post(
            f"/api/v1/pharmacies/credentialing?x-tenant-id={TENANT_A}",
            json={
                "applicant_npi": "INVALID",
                "applicant_name": "Test",
                "network_id": str(network_a_rs.id),
                "pharmacy_id": None,
                "applicant_address": None,
            },
        )
        assert resp.status_code == 400

    async def test_list_credentialing_includes_submitted(
        self, client: httpx.AsyncClient, pharmacy_a_rs: Pharmacy, network_a_rs: Network
    ) -> None:
        await client.post(
            f"/api/v1/pharmacies/credentialing?x-tenant-id={TENANT_A}",
            json={
                "applicant_npi": pharmacy_a_rs.npi,
                "applicant_name": "Pharm A",
                "network_id": str(network_a_rs.id),
                "pharmacy_id": None,
                "applicant_address": None,
            },
        )
        resp = await client.get(f"/api/v1/pharmacies/credentialing?x-tenant-id={TENANT_A}")
        assert resp.status_code == 200
        statuses = [a["status"] for a in resp.json()]
        assert "submitted" in statuses

    async def test_get_credentialing_application_returns_schema(
        self, client: httpx.AsyncClient, pharmacy_a_rs: Pharmacy, network_a_rs: Network
    ) -> None:
        create_resp = await client.post(
            f"/api/v1/pharmacies/credentialing?x-tenant-id={TENANT_A}",
            json={
                "applicant_npi": pharmacy_a_rs.npi,
                "applicant_name": "Test",
                "network_id": str(network_a_rs.id),
                "pharmacy_id": None,
                "applicant_address": None,
            },
        )
        app_id = create_resp.json()["id"]
        resp = await client.get(
            f"/api/v1/pharmacies/credentialing/{app_id}?x-tenant-id={TENANT_A}"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == app_id
        assert body["status"] == "submitted"

    async def test_get_credentialing_not_found_returns_404(self, client: httpx.AsyncClient) -> None:
        fake_id = uuid.uuid4()
        resp = await client.get(
            f"/api/v1/pharmacies/credentialing/{fake_id}?x-tenant-id={TENANT_A}"
        )
        assert resp.status_code == 404

    async def test_approve_credentialing_returns_approved(
        self, client: httpx.AsyncClient, pharmacy_a_rs: Pharmacy, network_a_rs: Network
    ) -> None:
        create_resp = await client.post(
            f"/api/v1/pharmacies/credentialing?x-tenant-id={TENANT_A}",
            json={
                "applicant_npi": pharmacy_a_rs.npi,
                "applicant_name": "Test",
                "network_id": str(network_a_rs.id),
                "pharmacy_id": None,
                "applicant_address": None,
            },
        )
        app_id = create_resp.json()["id"]
        resp = await client.post(
            f"/api/v1/pharmacies/credentialing/{app_id}/approve?x-tenant-id={TENANT_A}",
            json={"review_notes": "All clear", "denial_reason": None},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "approved"
        assert body["id"] == app_id

    async def test_deny_without_reason_returns_422(
        self, client: httpx.AsyncClient, pharmacy_a_rs: Pharmacy, network_a_rs: Network
    ) -> None:
        create_resp = await client.post(
            f"/api/v1/pharmacies/credentialing?x-tenant-id={TENANT_A}",
            json={
                "applicant_npi": pharmacy_a_rs.npi,
                "applicant_name": "Test",
                "network_id": str(network_a_rs.id),
                "pharmacy_id": None,
                "applicant_address": None,
            },
        )
        app_id = create_resp.json()["id"]
        resp = await client.post(
            f"/api/v1/pharmacies/credentialing/{app_id}/deny?x-tenant-id={TENANT_A}",
            json={"review_notes": None, "denial_reason": None},
        )
        assert resp.status_code == 422

    async def test_deny_with_reason_returns_denied(
        self, client: httpx.AsyncClient, pharmacy_a_rs: Pharmacy, network_a_rs: Network
    ) -> None:
        create_resp = await client.post(
            f"/api/v1/pharmacies/credentialing?x-tenant-id={TENANT_A}",
            json={
                "applicant_npi": pharmacy_a_rs.npi,
                "applicant_name": "Test",
                "network_id": str(network_a_rs.id),
                "pharmacy_id": None,
                "applicant_address": None,
            },
        )
        app_id = create_resp.json()["id"]
        resp = await client.post(
            f"/api/v1/pharmacies/credentialing/{app_id}/deny?x-tenant-id={TENANT_A}",
            json={"review_notes": "See notes", "denial_reason": "OIG exclusion found"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "denied"
        assert body["id"] == app_id


class TestPsaoEndpoints:
    async def test_create_psao_returns_201_with_schema(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/pharmacies/psaos",
            json={
                "name": "Test PSAO",
                "psao_id": "PSAO-001",
                "npi": None,
                "contact_name": "Jane Doe",
                "contact_email": "jane@psao.com",
                "contact_phone": None,
                "payment_consolidated": True,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Test PSAO"
        assert body["payment_consolidated"] is True
        assert "id" in body

    async def test_list_psaos_includes_created(self, client: httpx.AsyncClient) -> None:
        await client.post(
            "/api/v1/pharmacies/psaos",
            json={
                "name": "Listed PSAO",
                "psao_id": None,
                "npi": None,
                "contact_name": None,
                "contact_email": None,
                "contact_phone": None,
                "payment_consolidated": False,
            },
        )
        resp = await client.get("/api/v1/pharmacies/psaos")
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()]
        assert "Listed PSAO" in names

    async def test_list_psao_pharmacies_empty(self, client: httpx.AsyncClient) -> None:
        create_resp = await client.post(
            "/api/v1/pharmacies/psaos",
            json={
                "name": "PSAO No Pharmacies",
                "psao_id": None,
                "npi": None,
                "contact_name": None,
                "contact_email": None,
                "contact_phone": None,
                "payment_consolidated": False,
            },
        )
        psao_id = create_resp.json()["id"]
        resp = await client.get(f"/api/v1/pharmacies/psaos/{psao_id}/pharmacies")
        assert resp.status_code == 200
        assert resp.json()["pharmacies"] == []


class TestStatsEndpoint:
    async def test_stats_returns_all_fields(
        self, client: httpx.AsyncClient, pharmacy_a_rs: Pharmacy
    ) -> None:
        resp = await client.get(f"/api/v1/pharmacies/stats?x-tenant-id={TENANT_A}")
        assert resp.status_code == 200
        body = resp.json()
        assert "total_pharmacies" in body
        assert "active_pharmacies" in body
        assert "total_networks" in body
        assert "pending_credentialing" in body
        assert body["total_pharmacies"] >= 1


class TestCreateAppHealthEndpoint:
    """Verify health endpoint works through create_app() factory (app.py LESSON-006)."""

    async def test_health_endpoint_via_create_app(self) -> None:
        from unittest.mock import AsyncMock, MagicMock, patch
        from src.app import create_app

        mock_bus = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_engine = MagicMock()
        mock_engine.connect = MagicMock(return_value=mock_ctx)

        with patch("src.app.get_engine", return_value=mock_engine), \
             patch("src.app.get_event_bus", return_value=mock_bus), \
             patch("src.app.reset_event_bus"), \
             patch("src.app.dispose_engine", new_callable=AsyncMock):
            app = create_app()
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/health")
                assert resp.status_code == 200
                assert resp.json()["module"] == "pharmacy-directory"


class TestRateLimitThroughCreateApp:
    """429 rate-limit path tested through create_app() (LESSON-006)."""

    async def test_rate_limit_exceeded_returns_429(self) -> None:
        from unittest.mock import AsyncMock, MagicMock, patch
        from src.app import create_app
        from src.api.middleware import _Bucket

        mock_bus = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_engine = MagicMock()
        mock_engine.connect = MagicMock(return_value=mock_ctx)

        with patch("src.app.get_engine", return_value=mock_engine), \
             patch("src.app.get_event_bus", return_value=mock_bus), \
             patch("src.app.reset_event_bus"), \
             patch("src.app.dispose_engine", new_callable=AsyncMock):
            app = create_app()
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp_ok = await client.get("/health")
                assert resp_ok.status_code == 200

                with patch.object(_Bucket, "consume", return_value=False):
                    resp_429 = await client.get("/health")
                    assert resp_429.status_code == 429
                    assert "Retry-After" in resp_429.headers
