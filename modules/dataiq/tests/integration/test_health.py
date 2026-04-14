"""Integration tests for the /health endpoint in the dataiq module.

Verifies real dependency checks through create_app() per LESSON-006.
Database is a critical dependency — 503 when down.
Redis is critical for dataiq (used for KPI counters) — degraded when down.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


def _make_db_ok():
    """Return a mock sessionmaker whose context manager executes cleanly."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_maker = MagicMock()
    mock_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_maker.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_maker


def _make_db_fail():
    """Return a mock sessionmaker that raises on __aenter__."""
    mock_maker = MagicMock()
    mock_maker.return_value.__aenter__ = AsyncMock(
        side_effect=OSError("connection refused")
    )
    mock_maker.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_maker


def _make_redis_ok():
    """Return an async Redis mock that responds to ping."""
    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)
    mock_redis.aclose = AsyncMock()
    return mock_redis


def _make_redis_fail():
    """Return an async Redis mock that raises on ping."""
    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(side_effect=OSError("redis refused"))
    mock_redis.aclose = AsyncMock()
    return mock_redis


class TestHealthEndpoint:
    def test_health_returns_healthy_when_all_deps_up(self, client: TestClient) -> None:
        """When DB and Redis are both up, health returns 200 healthy."""
        with (
            patch("shared.db.session.get_sessionmaker", return_value=_make_db_ok()),
            patch("redis.asyncio.from_url", return_value=_make_redis_ok()),
        ):
            resp = client.get("/health")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["module"] == "dataiq"
        assert body["dependencies"]["database"] == "ok"
        assert body["dependencies"]["redis"] == "ok"

    def test_health_returns_unhealthy_503_when_db_down(self, client: TestClient) -> None:
        """When DB ping raises, health returns 503 unhealthy even if Redis is up."""
        with (
            patch("shared.db.session.get_sessionmaker", return_value=_make_db_fail()),
            patch("redis.asyncio.from_url", return_value=_make_redis_ok()),
        ):
            resp = client.get("/health")

        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "unhealthy"
        assert body["module"] == "dataiq"
        assert body["dependencies"]["database"].startswith("error:")

    def test_health_returns_degraded_when_redis_down(self, client: TestClient) -> None:
        """When Redis ping raises but DB is up, health returns 200 degraded."""
        with (
            patch("shared.db.session.get_sessionmaker", return_value=_make_db_ok()),
            patch("redis.asyncio.from_url", return_value=_make_redis_fail()),
        ):
            resp = client.get("/health")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "degraded"
        assert body["module"] == "dataiq"
        assert body["dependencies"]["database"] == "ok"
        assert body["dependencies"]["redis"].startswith("error:")
