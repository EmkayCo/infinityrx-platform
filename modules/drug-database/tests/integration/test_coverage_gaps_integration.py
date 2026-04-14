"""Integration tests filling remaining coverage gaps.

Targets: router search filters, rate limiter 429, pricing invalid NDC,
mac list success delete, schema validator error paths.
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.dependencies import get_db
from src.infrastructure.rate_limiter import InMemoryBucketStore, RateLimitConfig, RateLimitMiddleware
from src.main import create_app
from src.models.tables import DrugBase, DrugProduct, TenantPricingOverride

TENANT_A = "11111111-1111-1111-1111-111111111111"
_NOW = datetime.now(timezone.utc)


@pytest.fixture(scope="module")
def _engine():
    engine = create_engine(
        "sqlite:///file:drug_test_cov_gaps?mode=memory&cache=shared&uri=true",
        connect_args={"check_same_thread": False},
    )
    for table in DrugBase.metadata.tables.values():
        table.schema = None
    DrugBase.metadata.create_all(engine)
    yield engine
    DrugBase.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="module")
def client(_engine) -> TestClient:
    app = create_app()
    _Factory = sessionmaker(bind=_engine, autocommit=False, autoflush=False)

    def _override_db():
        s = _Factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override_db
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def seed_db(_engine):
    Factory = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    session = Factory()

    d1 = DrugProduct(
        ndc_11="00093314905",
        ndc_formatted="00093-3149-05",
        labeler_code="00093",
        product_code="3149",
        package_code="05",
        drug_name_display="Metformin",
        nonproprietary_name="metformin",
        drug_type="generic",
        marketing_status="active",
        is_active=True,
        is_specialty=False,
        is_biosimilar=False,
        is_glp1=False,
        unit_dose=False,
        is_limited_distribution=False,
        data_source="fda_ndc",
        last_updated_at=_NOW,
        created_at=_NOW,
        updated_at=_NOW,
    )
    session.add(d1)

    # Override for delete test
    override_for_delete = TenantPricingOverride(
        id=uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
        tenant_id=uuid.UUID(TENANT_A),
        ndc_11="00093314905",
        price_type="MAC",
        price_per_unit=Decimal("0.020000"),
        effective_date=datetime.now(timezone.utc).date(),
        data_source="tenant_mac",
        created_at=_NOW,
        updated_at=_NOW,
    )
    session.add(override_for_delete)

    session.commit()
    session.close()


class TestSearchFilters:
    def test_search_with_drug_type_filter(self, client, seed_db) -> None:
        resp = client.get(
            "/api/v1/drugs/search?q=metformin&drug_type=generic",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200
        data = resp.json()
        for r in data["results"]:
            assert r["drug_type"] == "generic"

    def test_search_with_marketing_status_filter(self, client, seed_db) -> None:
        resp = client.get(
            "/api/v1/drugs/search?q=metformin&marketing_status=active",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200

    def test_pricing_invalid_ndc(self, client, seed_db) -> None:
        resp = client.get(
            "/api/v1/drugs/pricing/BADINPUT",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 400


class TestDeleteOverrideSuccess:
    def test_delete_own_override_succeeds(self, client, seed_db) -> None:
        resp = client.delete(
            "/api/v1/drugs/overrides/dddddddd-dddd-dddd-dddd-dddddddddddd",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 204


class TestRateLimiter429:
    def test_rate_limiter_returns_429_when_bucket_exhausted(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient as TC

        app = FastAPI()
        store = InMemoryBucketStore()
        # Pre-create bucket with 0 tokens and 0 refill
        b = store.get_or_create("tenant:exhausted-tenant", 1.0, 0.0)
        b.tokens = 0.0

        app.add_middleware(
            RateLimitMiddleware,
            config=RateLimitConfig(tenant_rpm=1),
            store=store,
        )

        from starlette.requests import Request as Req

        @app.get("/test-rate")
        async def _endpoint(req: Req) -> dict:
            return {"ok": True}

        # Inject tenant_id into state via another middleware
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.responses import Response

        class InjectTenantMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request: Req, call_next) -> Response:
                request.state.tenant_id = "exhausted-tenant"
                return await call_next(request)

        app.add_middleware(InjectTenantMiddleware)
        tc = TC(app, raise_server_exceptions=False)
        resp = tc.get("/test-rate")
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
