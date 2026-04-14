"""Integration tests for the /health endpoint in the payment-processing module.

Verifies real dependency checks through create_app() per LESSON-006.
Database is a critical dependency — 503 when down.
Payment-processing does not use Redis, so no redis dependency check.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.app import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


def _make_sessionmaker_ok() -> MagicMock:
    """Return a mock sessionmaker whose session executes cleanly."""
    mock_session = MagicMock()
    mock_session.execute = MagicMock()
    mock_session.close = MagicMock()

    mock_maker = MagicMock(return_value=mock_session)
    return mock_maker


def _make_sessionmaker_fail() -> MagicMock:
    """Return a mock sessionmaker whose session raises on execute."""
    mock_session = MagicMock()
    mock_session.execute = MagicMock(side_effect=OSError("connection refused"))
    mock_session.close = MagicMock()

    mock_maker = MagicMock(return_value=mock_session)
    return mock_maker


class TestHealthEndpoint:
    def test_health_returns_healthy_when_all_deps_up(self, client: TestClient) -> None:
        """When DB ping succeeds, health returns 200 healthy."""
        with patch("src._shim.db.get_sessionmaker", return_value=_make_sessionmaker_ok()):
            resp = client.get("/health")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["module"] == "payment-processing"
        assert body["dependencies"]["database"] == "ok"

    def test_health_returns_unhealthy_503_when_db_down(self, client: TestClient) -> None:
        """When DB ping raises, health returns 503 unhealthy."""
        with patch("src._shim.db.get_sessionmaker", return_value=_make_sessionmaker_fail()):
            resp = client.get("/health")

        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "unhealthy"
        assert body["module"] == "payment-processing"
        assert body["dependencies"]["database"].startswith("error:")
