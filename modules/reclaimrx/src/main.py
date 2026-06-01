"""ReclaimRx FastAPI application entry point.

create_app() is the canonical application factory (LESSON-006):
all middleware, routers, and event-bus subscriptions must be mounted here
so integration tests through create_app() catch regressions.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.events.dlq import DLQService, build_dlq_router
from shared.middleware import RateLimitConfig, RateLimitMiddleware, SecurityHeadersMiddleware

from .api.router import router

logger = logging.getLogger("reclaimrx.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: wire event-bus consumers (CR-01) + scheduler jobs (D14 bindings 4-6).

    Loads all 8 reclaimrx CONSUMER_ROUTING handlers and subscribes them to
    the shared EventBus so the FWA pipeline actually receives live events.
    Starts ReclaimRxScheduler with 3 registered jobs:
      - cleanup_processed_events  (01:00 UTC daily)
      - verify_audit_hash_chain   (03:00 UTC daily)
      - check_dlq_depth           (every 15 min)
    Best-effort — a missing broker is fine in tests.
    """
    import asyncio as _asyncio  # noqa: PLC0415

    # P1-db: configure the SYNC engine the HTTP API's get_db uses. Without this the
    # _shim defaults to in-memory SQLite, so every live DB-backed endpoint 500s with
    # a detached-connection error. Tests don't set the env var (they override get_db),
    # so the SQLite default is preserved for them.
    try:
        import os as _os  # noqa: PLC0415
        from ._shim.db import configure_engine  # noqa: PLC0415
        _db_url = _os.environ.get("RECLAIMRX_DATABASE_URL") or _os.environ.get("DATABASE_URL_SYNC")
        if _db_url:
            configure_engine(_db_url)
    except Exception:  # pragma: no cover -- best-effort; tests override get_db
        logger.exception("reclaimrx.engine_config_failed")

    # P1-auth: register the auth loader before the app handles requests so
    # shared.auth.dependencies.get_current_user has a UserLoader + revoked repo.
    # Without this, every authenticated request 500s with 'auth not configured'.
    # Mirrors billing / drug-database / prescriber-directory main.py. Dev/test only:
    # configure_auth_trust_jwt() refuses to run in production (wire a real loader there).
    try:
        from shared.auth.dev_trust_jwt import configure_auth_trust_jwt  # noqa: PLC0415
        configure_auth_trust_jwt()
    except Exception:  # pragma: no cover -- best-effort; test overrides bypass this
        logger.exception("reclaimrx.auth_config_failed")

    # --- Event-bus consumer wiring ---
    try:
        from shared.events.factory import get_event_bus  # noqa: PLC0415
        from .events import wire_consumers  # noqa: PLC0415

        bus = get_event_bus()
        await bus.start()
        await wire_consumers(bus)
        app.state.event_bus = bus
    except Exception:  # pragma: no cover — best-effort
        logger.exception("reclaimrx.consumer_wiring_failed")

    # --- Scheduler (D14 bindings 4-6) ---
    from .jobs.reclaimrx_scheduler import ReclaimRxScheduler  # noqa: PLC0415

    scheduler = ReclaimRxScheduler()

    # Job: cleanup processed_events (event-bus.md: DELETE WHERE processed_at < NOW() - 7 days)
    async def _cleanup_processed_events() -> None:
        from sqlalchemy import text  # noqa: PLC0415
        from ._shim.db import get_sessionmaker  # noqa: PLC0415
        maker = get_sessionmaker()
        session = maker()
        try:
            session.execute(
                text("DELETE FROM core.processed_events WHERE processed_at < NOW() - INTERVAL '7 days'")
            )
            session.commit()
        except Exception:  # pragma: no cover
            logger.exception("reclaimrx.cleanup_processed_events.error")
        finally:
            session.close()

    # Job: verify audit hash chain (hipaa-2026.md: daily integrity check)
    async def _verify_audit_hash_chain() -> None:
        from .jobs.audit_chain_job import verify_audit_hash_chain  # noqa: PLC0415
        from ._shim.db import get_sessionmaker  # noqa: PLC0415
        maker = get_sessionmaker()
        session = maker()
        try:
            result = await _asyncio.to_thread(verify_audit_hash_chain, session, tenant_id=None)
            if result["status"] == "alert":
                logger.critical(
                    "reclaimrx.audit_chain.daily_check_failed",
                    extra={"svc_breaks": result["breaks"],
                           "audit_action": "audit_chain_daily"},
                )
        except Exception:  # pragma: no cover
            logger.exception("reclaimrx.audit_chain.daily_check_error")
        finally:
            session.close()

    # Job: DLQ depth monitor (event-bus.md: alert when > 0 for > 15 min)
    async def _check_dlq_depth() -> None:
        from .jobs.dlq_monitor import check_dlq_depth  # noqa: PLC0415
        from ._shim.db import get_async_engine_for_idempotency  # noqa: PLC0415
        try:
            await check_dlq_depth(get_async_engine_for_idempotency())
        except Exception:  # pragma: no cover
            logger.exception("reclaimrx.dlq_monitor.error")

    scheduler.register("cleanup_processed_events", _cleanup_processed_events, cron="0 1 * * *")
    scheduler.register("verify_audit_hash_chain", _verify_audit_hash_chain, cron="0 3 * * *")
    scheduler.register("check_dlq_depth", _check_dlq_depth, cron="*/15 * * * *")

    app.state.scheduler = scheduler
    sched_task = _asyncio.create_task(scheduler.start())

    yield

    await scheduler.stop()
    try:
        await _asyncio.wait_for(sched_task, timeout=5.0)
    except (_asyncio.TimeoutError, _asyncio.CancelledError):  # pragma: no cover
        pass


async def _get_dlq_service() -> DLQService:
    """Return DLQService backed by ReclaimRxDLQRepository (D14 binding 3)."""
    from .events.dlq_repository import ReclaimRxDLQRepository  # noqa: PLC0415
    from ._shim.db import get_async_engine_for_idempotency  # noqa: PLC0415
    return DLQService(repository=ReclaimRxDLQRepository(get_async_engine_for_idempotency()))


async def _get_dlq_permissions() -> set[str]:
    return set()


def create_app() -> FastAPI:
    """Application factory. Tests use this to build a fresh app per case."""
    from shared.config import get_settings  # noqa: PLC0415 — deferred to allow test override

    settings = get_settings()
    environment = getattr(settings, "ENVIRONMENT", "development")
    cors_origins = getattr(settings, "CORS_ALLOW_ORIGINS", [])

    app = FastAPI(
        lifespan=lifespan,
        title="InfinityRx ReclaimRx",
        version="1.0.0",
        description="FWA detection, ML scoring, graph analysis, and recovery estimation.",
        openapi_url="/openapi.json" if environment != "production" else None,
        docs_url="/docs" if environment != "production" else None,
        redoc_url="/redoc" if environment != "production" else None,
    )

    # LESSON-006: all middleware mounted here so integration tests catch regressions.
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.add_middleware(RateLimitMiddleware, config=RateLimitConfig())
    app.add_middleware(SecurityHeadersMiddleware)

    # SP-3: custom HTTPException handler so build_error_envelope() responses
    # are returned directly (not wrapped in {"detail": ...}).
    from fastapi import Request  # noqa: PLC0415
    from fastapi.exceptions import HTTPException as _HTTPException  # noqa: PLC0415
    from fastapi.responses import JSONResponse  # noqa: PLC0415

    @app.exception_handler(_HTTPException)
    async def _http_exception_handler(request: Request, exc: _HTTPException) -> JSONResponse:
        # If detail is a dict with an "error" key, return it directly.
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        # Otherwise use FastAPI's default {"detail": ...} format.
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    app.include_router(router)
    app.include_router(
        build_dlq_router(
            get_service=_get_dlq_service,
            get_permissions=_get_dlq_permissions,
        )
    )

    @app.get("/health")
    async def health() -> dict:
        from sqlalchemy import text  # noqa: PLC0415
        from src._shim.db import get_sessionmaker  # noqa: PLC0415
        from fastapi.responses import JSONResponse  # noqa: PLC0415

        db_status: str
        db_critical_failed: bool
        try:
            maker = get_sessionmaker()
            session = maker()
            try:
                session.execute(text("SELECT 1"))
            finally:
                session.close()
            db_status = "ok"
            db_critical_failed = False
        except Exception as exc:  # noqa: BLE001
            db_status = f"error: {type(exc).__name__}"
            db_critical_failed = True

        dependencies: dict[str, str] = {"database": db_status}

        if db_critical_failed:
            overall = "unhealthy"
        elif any(v != "ok" for v in dependencies.values()):
            overall = "degraded"
        else:
            overall = "healthy"

        status_code = 503 if db_critical_failed else 200
        return JSONResponse(
            status_code=status_code,
            content={
                "status": overall,
                "module": "reclaimrx",
                "dependencies": dependencies,
            },
        )

    return app


app = create_app()

__all__ = ["app", "create_app"]

