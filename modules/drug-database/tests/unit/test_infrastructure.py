"""Unit tests for infrastructure middleware (rate limiter, security headers)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.dependencies import get_db
from src.infrastructure.rate_limiter import (
    InMemoryBucketStore,
    RateLimitConfig,
    RateLimitMiddleware,
    TokenBucket,
)
from src.main import create_app
from src.models.tables import DrugBase

_TEST_TENANT = "11111111-1111-1111-1111-111111111111"


@pytest.fixture(scope="module")
def _engine():
    engine = create_engine(
        "sqlite:///file:drug_test_infra?mode=memory&cache=shared&uri=true",
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


class TestTokenBucket:
    def test_full_bucket_allows_consume(self) -> None:
        bucket = TokenBucket(capacity=10.0, refill_rate=1.0)
        allowed, remaining, reset = bucket.consume()
        assert allowed is True
        assert remaining < 10.0

    def test_empty_bucket_denies_consume(self) -> None:
        bucket = TokenBucket(capacity=1.0, refill_rate=0.0)
        bucket.consume()  # Take the last token
        bucket.tokens = 0.0  # Force empty
        allowed, remaining, reset = bucket.consume()
        assert allowed is False
        assert remaining == 0.0

    def test_refill_rate_zero_gives_max_wait(self) -> None:
        bucket = TokenBucket(capacity=1.0, refill_rate=0.0)
        bucket.tokens = 0.0
        allowed, remaining, reset = bucket.consume()
        assert allowed is False
        assert reset == 60  # Max wait when refill_rate=0


class TestInMemoryBucketStore:
    def test_get_or_create_returns_bucket(self) -> None:
        store = InMemoryBucketStore()
        bucket = store.get_or_create("test_key", 100.0, 10.0)
        assert bucket.capacity == 100.0

    def test_get_or_create_returns_same_instance(self) -> None:
        store = InMemoryBucketStore()
        b1 = store.get_or_create("key", 100.0, 10.0)
        b2 = store.get_or_create("key", 100.0, 10.0)
        assert b1 is b2

    def test_clear_removes_all_buckets(self) -> None:
        store = InMemoryBucketStore()
        store.get_or_create("key1", 100.0, 10.0)
        store.get_or_create("key2", 100.0, 10.0)
        store.clear()
        # After clear, new bucket is created (not the old one)
        b = store.get_or_create("key1", 50.0, 5.0)
        assert b.capacity == 50.0


class TestRateLimitMiddlewareIntegration:
    def test_health_endpoint_not_rate_limited(self, client: TestClient) -> None:
        resp = client.get("/api/v1/drugs/health", headers={"X-Tenant-Id": _TEST_TENANT})
        assert resp.status_code == 200

    def test_normal_request_passes_rate_limit(self, client: TestClient) -> None:
        resp = client.get("/api/v1/drugs/search?q=metformin", headers={"X-Tenant-Id": _TEST_TENANT})
        assert resp.status_code in (200, 404)  # not 429

    def test_rate_limit_config_defaults(self) -> None:
        config = RateLimitConfig()
        assert config.tenant_rpm == 1000
        assert config.user_rpm == 100
        assert config.burst_multiplier == 1.5

    def test_rate_limit_config_custom(self) -> None:
        config = RateLimitConfig(tenant_rpm=500)
        assert config.tenant_rpm == 500
