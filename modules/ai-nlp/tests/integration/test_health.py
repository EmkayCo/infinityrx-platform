"""Integration tests for the /health endpoint in the ai-nlp module.

Verifies real dependency checks through create_app() per LESSON-006.
Database is a critical dependency — 503 when down.
ai-nlp does not use Redis, so no redis dependency check.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.app import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


class TestHealthEndpoint:
    def test_health_returns_healthy_when_all_deps_up(self, client: TestClient) -> None:
        """When DB ping succeeds, health returns 200 healthy."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()

        mock_maker = MagicMock()
        mock_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("shared.db.session.get_sessionmaker", return_value=mock_maker):
            resp = client.get("/health")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["module"] == "ai-nlp"
        assert body["dependencies"]["database"] == "ok"

    def test_health_returns_unhealthy_503_when_db_down(self, client: TestClient) -> None:
        """When DB ping raises, health returns 503 unhealthy."""
        mock_maker = MagicMock()
        mock_maker.return_value.__aenter__ = AsyncMock(
            side_effect=OSError("connection refused")
        )
        mock_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("shared.db.session.get_sessionmaker", return_value=mock_maker):
            resp = client.get("/health")

        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "unhealthy"
        assert body["module"] == "ai-nlp"
        assert body["dependencies"]["database"].startswith("error:")
