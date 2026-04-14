"""Tests for app.py factory and lifespan startup/shutdown."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCreateApp:
    def test_create_app_returns_fastapi_instance(self) -> None:
        from fastapi import FastAPI
        from src.app import create_app
        app = create_app()
        assert isinstance(app, FastAPI)

    def test_create_app_includes_pharmacy_router(self) -> None:
        from src.app import create_app
        app = create_app()
        routes = [r.path for r in app.routes]
        assert any("/api/v1/pharmacies" in p for p in routes)

    def test_create_app_has_health_endpoint(self) -> None:
        from src.app import create_app
        app = create_app()
        routes = [r.path for r in app.routes]
        assert "/health" in routes

    def test_app_module_level_instance_is_fastapi(self) -> None:
        from fastapi import FastAPI
        from src.app import app
        assert isinstance(app, FastAPI)


class TestLifespan:
    @pytest.mark.asyncio
    async def test_lifespan_starts_and_stops_event_bus(self) -> None:
        mock_bus = AsyncMock()
        mock_engine = AsyncMock()
        mock_engine.connect = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=AsyncMock(execute=AsyncMock())),
            __aexit__=AsyncMock(return_value=None),
        ))

        with patch("src.app.get_event_bus", return_value=mock_bus), \
             patch("src.app.get_engine", return_value=mock_engine), \
             patch("src.app.reset_event_bus"), \
             patch("src.app.dispose_engine", new_callable=AsyncMock):
            from src.app import lifespan
            from fastapi import FastAPI
            mock_app = FastAPI()

            async with lifespan(mock_app):
                pass

            mock_bus.start.assert_called_once()
            mock_bus.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_database_called_on_startup(self) -> None:
        mock_bus = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_engine = MagicMock()
        mock_engine.connect = MagicMock(return_value=mock_context)

        with patch("src.app.get_engine", return_value=mock_engine), \
             patch("src.app.get_event_bus", return_value=mock_bus), \
             patch("src.app.reset_event_bus"), \
             patch("src.app.dispose_engine", new_callable=AsyncMock):
            from src.app import lifespan
            from fastapi import FastAPI
            mock_app = FastAPI()

            async with lifespan(mock_app):
                pass

            mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_dlq_repository_list_returns_empty(self) -> None:
        from src.app import _EmptyDLQRepository
        repo = _EmptyDLQRepository()
        result = await repo.list()
        assert result == []

    @pytest.mark.asyncio
    async def test_empty_dlq_repository_get_returns_none(self) -> None:
        from src.app import _EmptyDLQRepository
        import uuid
        repo = _EmptyDLQRepository()
        result = await repo.get(uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_dlq_service_returns_dlq_service(self) -> None:
        from shared.events.dlq import DLQService
        from src.app import _get_dlq_service
        result = await _get_dlq_service()
        assert isinstance(result, DLQService)

    @pytest.mark.asyncio
    async def test_get_dlq_permissions_returns_empty_set(self) -> None:
        from src.app import _get_dlq_permissions
        result = await _get_dlq_permissions()
        assert result == set()
