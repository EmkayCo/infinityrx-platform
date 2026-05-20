"""Integration tests filling remaining coverage gaps.

Targets: router search filters, rate limiter 429, pricing invalid NDC,
mac list success delete, schema validator error paths.
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal
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
from src.models.ndc_tables import Drug, NDCBase
from src.models.pricing_tables import PricingBase
from src.models.tables import DrugBase, TenantPricingOverride

TENANT_A = "11111111-1111-1111-1111-111111111111"
_NOW = datetime.now(timezone.utc)

# Unique product_id for this test module to avoid SQLite shared-memory conflicts
_COV_ID = "00093-3149-gaps"


@pytest.fixture(scope="module")
def _engine():
    engine = create_engine(
        "sqlite:///file:drug_test_cov_gaps?mode=memory&cache=shared&uri=true",
        connect_args={"check_same_thread": False},
    )
    for table in DrugBase.metadata.tables.values():
        table.schema = None
    for table in NDCBase.metadata.tables.values():
        table.schema = None
    for table in PricingBase.metadata.tables.values():
        table.schema = None

    DrugBase.metadata.create_all(engine)
    NDCBase.metadata.create_all(engine)
    PricingBase.metadata.create_all(engine)
    yield engine
    PricingBase.metadata.drop_all(engine)
    NDCBase.metadata.drop_all(engine)
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

    # Use Drug (seeded schema) — marketing_category_name is the drug_type equivalent
    d1 = Drug(
        product_id=_COV_ID,
        product_ndc="00093-3149",
        ndc_11="00093314906",
        non_proprietary_name="metformin hydrochloride",
        labeler_name="Teva Pharmaceuticals",
        marketing_category_name="ANDA",  # maps to drug_type in response
        ndc_exclude_flag=None,
        created_at=_NOW,
        updated_at=_NOW,
    )
    session.add(d1)

    # Override for delete test
    override_for_delete = TenantPricingOverride(
        id=uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
        tenant_id=uuid.UUID(TENANT_A),
        ndc_11="00093314906",
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
    def test_search_with_drug_type_filter_anda(self, client, seed_db) -> None:
        """drug_type filter now maps to marketing_category_name (ANDA/NDA/OTC)."""
        resp = client.get(
            "/api/v1/drugs/search?q=metformin&drug_type=ANDA",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200
        data = resp.json()
        for r in data["results"]:
            # drug_type field in response reflects marketing_category_name
            assert r["drug_type"] == "ANDA"

    def test_search_marketing_status_filter_ignored(self, client, seed_db) -> None:
        """marketing_status has no seeded column — filter is silently skipped, returns results."""
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
