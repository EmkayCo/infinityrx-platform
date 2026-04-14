"""Integration tests for the /health endpoint in the billing module.

Verifies real dependency checks through create_app() per LESSON-006.
Database is a critical dependency — 503 when down.
Billing uses a sync SQLAlchemy engine (src.db.session).
Billing does not use Redis, so no redis dependency check.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


def _make_engine_ok() -> MagicMock:
    """Return a mock engine whose connect() context manager executes cleanly."""
    mock_conn = MagicMock()
    mock_conn.execute = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)

    mock_engine = MagicMock()
    mock_engine.connect = MagicMock(return_value=mock_conn)
    return mock_engine


def _make_engine_fail() -> MagicMock:
    """Return a mock engine whose connect() raises."""
    mock_engine = MagicMock()
    mock_engine.connect = MagicMock(side_effect=OSError("connection refused"))
    return mock_engine


class TestHealthEndpoint:
    def test_health_returns_healthy_when_all_deps_up(self, client: TestClient) -> None:
        """When DB ping succeeds, health returns 200 healthy."""
        with patch("src.db.session._get_engine", return_value=_make_engine_ok()):
            resp = client.get("/health")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["module"] == "billing"
        assert body["dependencies"]["database"] == "ok"

    def test_health_returns_unhealthy_503_when_db_down(self, client: TestClient) -> None:
        """When DB ping raises, health returns 503 unhealthy."""
        with patch("src.db.session._get_engine", return_value=_make_engine_fail()):
            resp = client.get("/health")

        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "unhealthy"
        assert body["module"] == "billing"
        assert body["dependencies"]["database"].startswith("error:")
