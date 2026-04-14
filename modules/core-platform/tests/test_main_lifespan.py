"""Tests for the graceful-shutdown lifespan in src.main.

These tests verify the contract, not uvicorn's internals. We drive the
lifespan context manager directly and assert that:
    * DB verification runs on startup (SELECT 1 against the engine)
    * Event bus start() is called on startup
    * Event bus stop() is called on shutdown
    * dispose_engine() is called on shutdown
    * Exceptions during shutdown drains are swallowed (best-effort)
    * shutting_down flag flips True at shutdown
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src import main as main_module


@pytest.mark.asyncio
async def test_lifespan_startup_and_shutdown_in_order() -> None:
    app = main_module.create_app()
    calls: list[str] = []

    async def fake_verify() -> None:
        calls.append("verify_db")

    bus = AsyncMock()
    bus.start = AsyncMock(side_effect=lambda: calls.append("bus_start"))
    bus.stop = AsyncMock(side_effect=lambda: calls.append("bus_stop"))

    async def fake_dispose() -> None:
        calls.append("dispose")

    with (
        patch.object(main_module, "_verify_database", fake_verify),
        patch.object(main_module, "get_event_bus", return_value=bus),
        patch.object(main_module, "dispose_engine", fake_dispose),
        patch.object(main_module, "reset_event_bus"),
    ):
        async with main_module.lifespan(app):
            assert app.state.shutting_down is False
            assert calls == ["verify_db", "bus_start"]
        assert app.state.shutting_down is True

    assert calls == ["verify_db", "bus_start", "bus_stop", "dispose"]


@pytest.mark.asyncio
async def test_lifespan_shutdown_tolerates_bus_failure() -> None:
    app = main_module.create_app()
    bus = AsyncMock()
    bus.stop = AsyncMock(side_effect=RuntimeError("broker gone"))
    disposed = []

    async def fake_dispose() -> None:
        disposed.append(True)

    with (
        patch.object(main_module, "_verify_database", AsyncMock()),
        patch.object(main_module, "get_event_bus", return_value=bus),
        patch.object(main_module, "dispose_engine", fake_dispose),
        patch.object(main_module, "reset_event_bus"),
    ):
        async with main_module.lifespan(app):
            pass

    # Engine was disposed even though bus.stop raised
    assert disposed == [True]


@pytest.mark.asyncio
async def test_lifespan_shutdown_tolerates_engine_failure() -> None:
    app = main_module.create_app()
    bus = AsyncMock()

    async def bad_dispose() -> None:
        raise RuntimeError("engine hosed")

    with (
        patch.object(main_module, "_verify_database", AsyncMock()),
        patch.object(main_module, "get_event_bus", return_value=bus),
        patch.object(main_module, "dispose_engine", bad_dispose),
        patch.object(main_module, "reset_event_bus"),
    ):
        async with main_module.lifespan(app):
            pass  # Should not raise

    bus.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_lifespan_startup_db_failure_aborts() -> None:
    """If DB verification fails, bus.start() must NOT be called and the
    lifespan enter must raise — we fail fast rather than serve traffic
    against a broken DB."""
    app = main_module.create_app()
    bus = AsyncMock()

    async def bad_verify() -> None:
        raise ConnectionError("db down")

    with (
        patch.object(main_module, "_verify_database", bad_verify),
        patch.object(main_module, "get_event_bus", return_value=bus),
        patch.object(main_module, "dispose_engine", AsyncMock()),
        patch.object(main_module, "reset_event_bus"),
        pytest.raises(ConnectionError),
    ):
        async with main_module.lifespan(app):
            pass

    bus.start.assert_not_awaited()


def test_create_app_returns_fastapi_with_router() -> None:
    app = main_module.create_app()
    # Router should be mounted (health path among others)
    paths = {route.path for route in app.routes}
    assert any(p.startswith("/health") for p in paths), f"No /health route: {paths}"


def test_install_signal_handlers_handles_no_loop() -> None:
    """Should silently no-op if add_signal_handler is unsupported."""

    app = main_module.create_app()

    class _FakeLoop:
        def add_signal_handler(self, *args, **kwargs):
            raise NotImplementedError

    main_module._install_signal_handlers(_FakeLoop(), app)  # type: ignore[arg-type]


def test_install_signal_handlers_runtime_error_swallowed() -> None:
    app = main_module.create_app()

    class _FakeLoop:
        def add_signal_handler(self, *args, **kwargs):
            raise RuntimeError("not main thread")

    main_module._install_signal_handlers(_FakeLoop(), app)  # type: ignore[arg-type]


def test_install_signal_handlers_handler_body_flips_flag() -> None:
    """Exercise the inner _handler callback directly so coverage records it."""
    app = main_module.create_app()
    app.state.shutting_down = False
    captured: dict = {}

    class _Loop:
        def add_signal_handler(self, sig, handler, signame):
            captured["handler"] = handler
            captured["signame"] = signame

    main_module._install_signal_handlers(_Loop(), app)  # type: ignore[arg-type]
    # Invoke the captured handler — it should flip shutting_down
    captured["handler"](captured["signame"])
    assert app.state.shutting_down is True


@pytest.mark.asyncio
async def test_lifespan_handles_no_running_loop() -> None:
    """If asyncio.get_running_loop() raises RuntimeError, startup continues."""
    app = main_module.create_app()
    bus = AsyncMock()

    with (
        patch.object(main_module.asyncio, "get_running_loop", side_effect=RuntimeError),
        patch.object(main_module, "_verify_database", AsyncMock()),
        patch.object(main_module, "get_event_bus", return_value=bus),
        patch.object(main_module, "dispose_engine", AsyncMock()),
        patch.object(main_module, "reset_event_bus"),
    ):
        async with main_module.lifespan(app):
            pass
    bus.start.assert_awaited_once()


@pytest.mark.asyncio
async def test_verify_database_executes_select_1() -> None:
    """Cover the _verify_database body by patching get_engine with a fake."""

    executed: list[str] = []

    class _FakeConn:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def execute(self, stmt):
            executed.append(str(stmt))

    class _FakeEngine:
        def connect(self):
            return _FakeConn()

    with patch.object(main_module, "get_engine", return_value=_FakeEngine()):
        await main_module._verify_database()

    assert len(executed) == 1
    assert "SELECT 1" in executed[0]
