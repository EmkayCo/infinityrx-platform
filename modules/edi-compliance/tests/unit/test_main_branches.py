"""Tests for main.py branch coverage — lifespan and middleware registration."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_MODULE_ROOT = Path(__file__).resolve().parents[2]
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))


def test_create_app_returns_fastapi():
    """create_app always returns a FastAPI application."""
    from src.main import create_app
    from fastapi import FastAPI
    app = create_app()
    assert isinstance(app, FastAPI)


def test_create_app_health_endpoint():
    """create_app mounts /health endpoint."""
    from fastapi.testclient import TestClient
    from src.main import create_app
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_create_app_with_security_middleware_mocked():
    """Security middleware try/except block is covered when imports succeed."""
    mock_middleware = MagicMock()
    mock_rate_config = MagicMock()
    mock_rate_middleware = MagicMock()

    with patch.dict("sys.modules", {
        "modules": MagicMock(),
        "modules.core_platform": MagicMock(),
        "modules.core_platform.src": MagicMock(),
        "modules.core_platform.src.infrastructure": MagicMock(),
        "modules.core_platform.src.infrastructure.security_headers": MagicMock(
            SecurityHeadersMiddleware=mock_middleware
        ),
        "modules.core_platform.src.infrastructure.rate_limiter": MagicMock(
            RateLimitConfig=mock_rate_config,
            RateLimitMiddleware=mock_rate_middleware,
        ),
    }):
        # Re-import to force new execution through create_app
        import importlib
        import src.main as main_module
        importlib.reload(main_module)
        app = main_module.create_app()
        from fastapi import FastAPI
        assert isinstance(app, FastAPI)


def test_create_app_with_dlq_router_mocked():
    """DLQ router try/except block is covered when shared.events.dlq is available."""
    mock_router = MagicMock()
    mock_build_dlq = MagicMock(return_value=mock_router)

    with patch.dict("sys.modules", {
        "shared": MagicMock(),
        "shared.events": MagicMock(),
        "shared.events.dlq": MagicMock(build_dlq_router=mock_build_dlq),
    }):
        import importlib
        import src.main as main_module
        importlib.reload(main_module)
        app = main_module.create_app()
        from fastapi import FastAPI
        assert isinstance(app, FastAPI)


@pytest.mark.asyncio
async def test_lifespan_runs():
    """Lifespan async context manager executes without error (shared imports fail gracefully)."""
    from src.main import lifespan, create_app
    app = create_app()
    async with lifespan(app):
        pass  # Just verify it completes


@pytest.mark.asyncio
async def test_lifespan_with_shared_db_mocked():
    """Lifespan exercises DB connectivity check when shared.db.engine is available."""
    mock_conn = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)
    mock_conn.execute = AsyncMock()

    mock_engine = MagicMock()
    mock_engine.connect = MagicMock(return_value=mock_conn)

    mock_db_engine = MagicMock()
    mock_db_engine.get_engine = MagicMock(return_value=mock_engine)
    mock_db_engine.dispose_engine = AsyncMock()

    mock_bus = AsyncMock()
    mock_bus.start = AsyncMock()
    mock_bus.stop = AsyncMock()

    mock_events_factory = MagicMock()
    mock_events_factory.get_event_bus = MagicMock(return_value=mock_bus)
    mock_events_factory.reset_event_bus = MagicMock()

    with patch.dict("sys.modules", {
        "shared": MagicMock(),
        "shared.db": MagicMock(),
        "shared.db.engine": mock_db_engine,
        "shared.events": MagicMock(),
        "shared.events.factory": mock_events_factory,
    }):
        import importlib
        import src.main as main_module
        importlib.reload(main_module)

        app = main_module.create_app()
        async with main_module.lifespan(app):
            pass

    # Reload original
    importlib.reload(main_module)
