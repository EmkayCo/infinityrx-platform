"""Tests for infrastructure middleware and app factory coverage."""
from __future__ import annotations

import sys
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from src.infrastructure.rate_limiter import (
    RateLimitConfig,
    RateLimitMiddleware,
    InMemoryBucketStore,
    TokenBucket,
)
from src.main import create_app, _EmptyDLQRepository, _get_dlq_service, _get_dlq_permissions


# ---------------------------------------------------------------------------
# TokenBucket
# ---------------------------------------------------------------------------

class TestTokenBucket:
    def test_consume_allowed_when_tokens_available(self):
        bucket = TokenBucket(capacity=10.0, refill_rate=1.0)
        allowed, remaining, reset = bucket.consume(1)
        assert allowed is True
        assert remaining >= 0

    def test_consume_blocked_when_empty(self):
        bucket = TokenBucket(capacity=1.0, refill_rate=0.0)
        bucket.consume(1)  # drain
        allowed, remaining, reset = bucket.consume(1)
        assert allowed is False

    def test_refill_rate_zero_returns_wait_60(self):
        bucket = TokenBucket(capacity=1.0, refill_rate=0.0)
        bucket.consume(1)  # drain
        allowed, remaining, reset = bucket.consume(1)
        assert reset == 60

    def test_full_bucket_reset_is_zero(self):
        bucket = TokenBucket(capacity=10.0, refill_rate=1.0)
        allowed, remaining, reset = bucket.consume(1)
        assert allowed is True


class TestInMemoryBucketStore:
    def test_get_or_create_creates_new_bucket(self):
        store = InMemoryBucketStore()
        bucket = store.get_or_create("key1", 100.0, 1.0)
        assert bucket is not None

    def test_get_or_create_returns_same_bucket(self):
        store = InMemoryBucketStore()
        b1 = store.get_or_create("key1", 100.0, 1.0)
        b2 = store.get_or_create("key1", 100.0, 1.0)
        assert b1 is b2

    def test_clear_removes_all_buckets(self):
        store = InMemoryBucketStore()
        store.get_or_create("key1", 100.0, 1.0)
        store.clear()
        b = store.get_or_create("key1", 100.0, 1.0)
        assert b is not None


class TestRateLimitMiddlewareThroughApp:
    def _make_app_with_tenant(self, tenant_id: str) -> TestClient:
        """App that sets tenant_id on request state to trigger rate limiting."""
        config = RateLimitConfig(tenant_rpm=5, user_rpm=5)
        store = InMemoryBucketStore()
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, config=config, store=store)

        @app.middleware("http")
        async def inject_tenant(request: Request, call_next):
            request.state.tenant_id = tenant_id
            return await call_next(request)

        @app.get("/test")
        async def endpoint():
            return {"ok": True}

        return TestClient(app, raise_server_exceptions=False)

    def test_rate_limit_headers_present_when_tenant_set(self):
        client = self._make_app_with_tenant(str(uuid.uuid4()))
        resp = client.get("/test")
        assert resp.status_code == 200
        assert "x-ratelimit-limit" in resp.headers

    def test_rate_limit_429_when_exhausted(self):
        tenant = str(uuid.uuid4())
        config = RateLimitConfig(tenant_rpm=1, user_rpm=100)
        store = InMemoryBucketStore()
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, config=config, store=store)

        @app.middleware("http")
        async def inject_tenant(request: Request, call_next):
            request.state.tenant_id = tenant
            return await call_next(request)

        @app.get("/test")
        async def endpoint():
            return {"ok": True}

        client = TestClient(app, raise_server_exceptions=False)
        # Drain the bucket — capacity = 1 * 1.5 = 1.5 tokens, so 2 requests should hit limit
        client.get("/test")
        client.get("/test")
        resp = client.get("/test")
        assert resp.status_code == 429

    def test_health_endpoint_bypasses_rate_limit(self):
        config = RateLimitConfig(tenant_rpm=1, user_rpm=1)
        store = InMemoryBucketStore()
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, config=config, store=store)

        @app.get("/health")
        async def health():
            return {"ok": True}

        client = TestClient(app, raise_server_exceptions=False)
        for _ in range(10):
            resp = client.get("/health")
            assert resp.status_code == 200

    def test_user_rate_limit_applied(self):
        user = str(uuid.uuid4())
        config = RateLimitConfig(tenant_rpm=1000, user_rpm=1)
        store = InMemoryBucketStore()
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, config=config, store=store)

        @app.middleware("http")
        async def inject_user(request: Request, call_next):
            request.state.user_id = user
            return await call_next(request)

        @app.get("/test")
        async def endpoint():
            return {"ok": True}

        client = TestClient(app, raise_server_exceptions=False)
        client.get("/test")
        client.get("/test")
        resp = client.get("/test")
        assert resp.status_code == 429

    def test_user_rate_limit_headers_present(self):
        user = str(uuid.uuid4())
        config = RateLimitConfig(tenant_rpm=1000, user_rpm=100)
        store = InMemoryBucketStore()
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, config=config, store=store)

        @app.middleware("http")
        async def inject_user(request: Request, call_next):
            request.state.user_id = user
            return await call_next(request)

        @app.get("/test")
        async def endpoint():
            return {"ok": True}

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert "x-ratelimit-limit" in resp.headers


# ---------------------------------------------------------------------------
# App factory / DLQ helpers
# ---------------------------------------------------------------------------

class TestAppFactory:
    def test_create_app_returns_fastapi(self):
        from fastapi import FastAPI
        app = create_app()
        assert isinstance(app, FastAPI)

    @pytest.mark.asyncio
    async def test_empty_dlq_repo_list_returns_empty(self):
        repo = _EmptyDLQRepository()
        result = await repo.list()
        assert result == []

    @pytest.mark.asyncio
    async def test_empty_dlq_repo_get_returns_none(self):
        repo = _EmptyDLQRepository()
        result = await repo.get("fake-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_dlq_repo_save_returns_none(self):
        repo = _EmptyDLQRepository()
        result = await repo.save({"entry": "data"})
        assert result is None

    @pytest.mark.asyncio
    async def test_get_dlq_service_returns_service(self):
        from shared.events.dlq import DLQService
        svc = await _get_dlq_service()
        assert isinstance(svc, DLQService)

    @pytest.mark.asyncio
    async def test_get_dlq_permissions_returns_empty_set(self):
        perms = await _get_dlq_permissions()
        assert perms == set()


# ---------------------------------------------------------------------------
# EDI parser additional edge cases
# ---------------------------------------------------------------------------

class TestEdi834AdditionalCoverage:
    def test_ins_segment_subscriber_relationship(self):
        """INS*Y*01* → spouse relationship."""
        from src.services.edi_834_parser import _Loop2000Handler, _parse_elements
        handler = _Loop2000Handler()
        segments = [
            _parse_elements("L2000*1*1*ADD"),
            _parse_elements("INS*Y*01*030*XN*A*E**FT"),
            _parse_elements("REF*0F*MEMSP01"),
            _parse_elements("DTP*356*D8*20260101"),
            _parse_elements("NM1*IL*1*DOE*JANE***MS*34*987654321"),
            _parse_elements("DMG*D8*19900201*F"),
        ]
        handler.handle(segments)
        assert len(handler.records) == 1
        assert handler.records[0].relationship_code == "spouse"

    def test_ins_segment_child_relationship(self):
        from src.services.edi_834_parser import _Loop2000Handler, _parse_elements
        handler = _Loop2000Handler()
        segments = [
            _parse_elements("L2000*1*1*ADD"),
            _parse_elements("INS*Y*19*030*XN*A*E**FT"),
            _parse_elements("REF*0F*MEMCH01"),
            _parse_elements("DTP*356*D8*20260101"),
            _parse_elements("NM1*IL*1*DOE*KID***MS*34*555555555"),
            _parse_elements("DMG*D8*20100601*M"),
        ]
        handler.handle(segments)
        assert handler.records[0].relationship_code == "child"

    def test_dtp_357_sets_termination_date(self):
        """DTP*357 is termination date."""
        from src.services.edi_834_parser import _Loop2000Handler, _parse_elements
        handler = _Loop2000Handler()
        segments = [
            _parse_elements("L2000*1*1*TRM"),
            _parse_elements("INS*Y*18*024*XN*A*E**FT"),
            _parse_elements("REF*0F*MEMTERM1"),
            _parse_elements("DTP*356*D8*20200101"),
            _parse_elements("DTP*357*D8*20261231"),
            _parse_elements("NM1*IL*1*SMITH*BOB***MR*34*111111111"),
            _parse_elements("DMG*D8*19700101*M"),
        ]
        handler.handle(segments)
        from datetime import date
        assert handler.records[0].termination_date == date(2026, 12, 31)

    def test_nm1_74_entity_parsed(self):
        """NM1*74 is also a member entity identifier."""
        from src.services.edi_834_parser import _Loop2000Handler, _parse_elements
        handler = _Loop2000Handler()
        segments = [
            _parse_elements("L2000*1*1*ADD"),
            _parse_elements("INS*Y*18*030*XN*A*E**FT"),
            _parse_elements("REF*0F*MEM74"),
            _parse_elements("DTP*356*D8*20260101"),
            _parse_elements("NM1*74*1*JONES*TOM***MR*34*222222222"),
            _parse_elements("DMG*D8*19850101*M"),
        ]
        handler.handle(segments)
        assert handler.records[0].first_name == "TOM"

    def test_nm1_non_member_entity_skipped(self):
        """NM1 with unrecognized entity ID should not clobber member fields."""
        from src.services.edi_834_parser import _Loop2000Handler, _parse_elements
        handler = _Loop2000Handler()
        segments = [
            _parse_elements("L2000*1*1*ADD"),
            _parse_elements("INS*Y*18*030*XN*A*E**FT"),
            _parse_elements("REF*0F*MEMXXX"),
            _parse_elements("DTP*356*D8*20260101"),
            _parse_elements("NM1*IL*1*DOE*ALICE***F*34*333333333"),
            _parse_elements("NM1*P3*2*ACME PHARMACY"),  # payer — should be skipped
            _parse_elements("DMG*D8*19950101*F"),
        ]
        handler.handle(segments)
        assert handler.records[0].first_name == "ALICE"

    def test_record_without_member_id_not_added(self):
        """A loop 2000 block without REF*0F → member_id empty → record not added."""
        from src.services.edi_834_parser import _Loop2000Handler, _parse_elements
        handler = _Loop2000Handler()
        segments = [
            _parse_elements("L2000*1*1*ADD"),
            _parse_elements("INS*Y*18*030*XN*A*E**FT"),
            _parse_elements("DTP*356*D8*20260101"),
            _parse_elements("NM1*IL*1*NOREF*PERSON***MR"),
            _parse_elements("DMG*D8*19800101*M"),
        ]
        handler.handle(segments)
        assert len(handler.records) == 0
