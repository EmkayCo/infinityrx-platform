"""Core-platform FastAPI entry point with graceful-shutdown lifespan.

Ensures in-flight DB transactions and in-flight event-bus messages are
flushed before the process exits. Without this, pod termination
(SIGTERM Ã¢â€ â€™ 30s grace Ã¢â€ â€™ SIGKILL) can corrupt PHI/audit data Ã¢â‚¬â€ HIPAA
Ã‚Â§164.308(a)(1) availability + Ã‚Â§164.308(a)(7) contingency.

On startup:
    - Verify the database is reachable (SELECT 1).
    - Start the event bus (opens connection, spins consumers).
    - Log "service started" with correlation metadata.

On shutdown (lifespan exit OR SIGTERM OR SIGINT):
    - Stop the event bus (drains in-flight deliveries, closes channel).
    - Dispose the SQLAlchemy engine (returns pooled connections).
    - Log "service stopped".

The SIGTERM/SIGINT handler forwards to the lifespan by raising an
asyncio CancelledError in uvicorn's main loop Ã¢â‚¬â€ uvicorn then triggers
the normal lifespan shutdown path. We only install the handler when
running under an event loop (skipped in TestClient).
"""

from __future__ import annotations

import asyncio
import logging
import signal
import uuid
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from sqlalchemy import text

from shared.db.engine import dispose_engine, get_engine
from shared.events.dlq import DLQService, build_dlq_router
from shared.events.factory import get_event_bus, reset_event_bus
from shared.observability import configure_logging
from shared.observability.slow_query import install_slow_query_logger

from ._shim import db as db_shim
from .api import router as api_router
from .jobs.seed import ensure_audit_chain_job
from .audit.middleware import AuditContext, AuditMiddleware
from .auth import auth_api_router, configure_core_auth
from .auth._db import get_session as auth_get_session
from .auth.deps import configure_audit_sink
from .infrastructure.rate_limiter import RateLimitConfig, RateLimitMiddleware
from .infrastructure.security_headers import SecurityHeadersMiddleware
from .infrastructure.tenant_middleware import AuthContext, AuthResolver, TenantIsolationMiddleware

logger = logging.getLogger("core-platform.main")


async def _verify_database() -> None:
    """Fail-fast on startup if the DB is not reachable."""
    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


def _install_signal_handlers(loop: asyncio.AbstractEventLoop, app: FastAPI) -> None:
    """Forward SIGTERM/SIGINT to the uvicorn shutdown path.

    Setting ``app.state.shutting_down`` lets health checks report 503 while
    the lifespan shutdown tasks drain.
    """

    def _handler(signame: str) -> None:
        logger.info("signal_received", extra={"signal": signame})
        app.state.shutting_down = True
        # Uvicorn installs its own handler; we only flip the flag so the
        # readiness probe starts failing immediately. Uvicorn drives the
        # actual lifespan shutdown when its server loop unwinds.

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _handler, sig.name)
        except (NotImplementedError, RuntimeError):
            # Windows / test environments may not support add_signal_handler
            pass


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI lifespan: startup + graceful shutdown."""
    # --- startup ---
    # Structured logging must be configured BEFORE any other startup step
    # so their log lines land as JSON too (otherwise the first few events
    # escape the formatter).
    import os

    configure_logging(
        level=os.getenv("LOG_LEVEL", "INFO"),
        mode=os.getenv("LOG_MODE", "json"),
    )
    app.state.shutting_down = False
    try:
        loop = asyncio.get_running_loop()
        _install_signal_handlers(loop, app)
    except RuntimeError:
        pass  # No running loop (shouldn't happen under uvicorn)

    await _verify_database()
    # Attach slow-query logger to the sync side of the engine so any query
    # over SLOW_QUERY_THRESHOLD_MS (default 1000) is logged at WARNING with
    # elapsed_ms, statement (truncated, no params), and the request context
    # injected by ContextFilter.
    threshold = int(os.getenv("SLOW_QUERY_THRESHOLD_MS", "1000"))
    try:
        install_slow_query_logger(get_engine().sync_engine, threshold_ms=threshold)
    except Exception:  # pragma: no cover - best-effort
        logger.exception("slow_query_logger_install_failed")
    bus = get_event_bus()
    await bus.start()

    # H-07: seed the daily audit chain verification job row if absent.
    # Uses the sync shim session so this works in both test and prod mode.
    try:
        SessionLocal = db_shim.get_sessionmaker()
        with SessionLocal() as _seed_db:
            ensure_audit_chain_job(_seed_db)
    except Exception:  # pragma: no cover - best-effort; job row missing != broken startup
        logger.exception("audit_chain_job_seed_failed")
    # CONCERN-3 fix (P0a v2): seed system jobs (exclusion_refresh, etc.)
    # into core_jobs so the scheduler picks them up.  Also import the
    # exclusion job handler to trigger its self-registration on
    # default_registry (import side-effect at module load time).
    try:
        from .exclusions import job_handler as _excl_handler  # noqa: F401 Ã¢â‚¬â€ side-effect import
        from .jobs.seed import seed_system_jobs
        _seed_session = db_shim.get_sessionmaker()()
        try:
            seeded = seed_system_jobs(_seed_session)
            _seed_session.commit()
            if seeded > 0:
                logger.info("excl_jobs_seeded excl_count=%d", seeded)
        except Exception:  # pragma: no cover - best-effort, non-fatal
            logger.exception("excl_jobs_seed_failed")
            _seed_session.rollback()
        finally:
            _seed_session.close()
    except Exception:  # pragma: no cover - best-effort, non-fatal
        logger.exception("excl_jobs_seed_import_failed")


    logger.info("service_started", extra={"service": "core-platform"})

    try:
        yield
    finally:
        # --- shutdown ---
        app.state.shutting_down = True
        logger.info("service_stopping", extra={"service": "core-platform"})
        try:
            await bus.stop()
        except Exception:  # pragma: no cover - best-effort drain
            logger.exception("event_bus_stop_failed")
        reset_event_bus()
        try:
            await dispose_engine()
        except Exception:  # pragma: no cover - best-effort drain
            logger.exception("engine_dispose_failed")
        logger.info("service_stopped", extra={"service": "core-platform"})


class _EmptyDLQRepository:
    """Placeholder DLQ repository mounted before the Postgres-backed repo
    is wired through the shared async engine. Returns no entries so list
    operations are honest ("nothing is queued") rather than stubbed."""

    async def list(self, **_kwargs):
        return []

    async def get(self, _entry_id):
        return None

    async def save(self, _entry) -> None:  # pragma: no cover - write path unused
        return None


async def _get_dlq_service() -> DLQService:
    return DLQService(repository=_EmptyDLQRepository())


async def _get_dlq_permissions() -> set[str]:
    # Deny by default. The real permission resolver will pull from the
    # authenticated user's JWT once the auth dependency lands on this app.
    return set()


def _audit_session_factory():
    """Return a context-manager-compatible sync session for the audit middleware.

    Uses the shim's session factory so this works in both test and production
    mode (the shim uses SQLite in tests, Postgres in production).
    """
    from .._shim import db as db_shim  # noqa: PLC0415 Ã¢â‚¬â€ deferred to avoid circular import

    @contextmanager
    def _cm():
        SessionLocal = db_shim.get_sessionmaker()
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    return _cm()


def _audit_user_resolver(request: Request) -> AuditContext | None:
    """Resolve tenant/user from bearer token for audit logging.

    Uses the same ``get_current_user`` path as the request auth stack so
    audit context reflects the same user the auth decision would accept â€”
    revoked tokens and inactive users yield None (no attribution) rather
    than being incorrectly attributed.

    MEDIUM-1 fix (B12-S1 v2): v1 called ``decode_token()`` directly, which
    would attribute audit entries to callers whose tokens the auth path
    rejects (revoked or for inactive users).

    Gracefully falls back to None (unauthenticated) when no valid JWT is
    present â€” AuditMiddleware skips the audit write for unauthenticated
    calls (e.g., /auth/login itself). Returns None rather than raising so
    that the middleware never fails a request due to resolver errors.

    """
    try:
        from shared.auth.dependencies import get_current_user  # noqa: PLC0415
        from fastapi.security.utils import get_authorization_scheme_param  # noqa: PLC0415

        auth_header = request.headers.get("Authorization", "")
        scheme, token = get_authorization_scheme_param(auth_header)
        if scheme.lower() != "bearer" or not token:
            return None
        # Route through the full auth stack (decode + revocation + inactive check).
        # Any rejection (401) is caught below and maps to None.
        user = get_current_user(token=token)
        return AuditContext(
            tenant_id=user.tenant_id,
            user_id=user.id,
        )
    except Exception:  # noqa: BLE001 Ã¢â‚¬â€ best-effort; never fail the request
        return None


class _TenantResolver:
    """Resolve auth context from bearer JWT for TenantIsolationMiddleware.

    Returns None for requests without a valid bearer token so that
    unauthenticated routes (health, /auth/login) can be made explicitly
    exempt via the ``@tenant_exempt_route`` decorator without breaking the
    middleware chain.
    """

    def __call__(self, request: Request) -> AuthContext | None:
        try:
            from shared.auth.jwt_tokens import decode_token  # noqa: PLC0415
            from fastapi.security.utils import get_authorization_scheme_param  # noqa: PLC0415

            auth_header = request.headers.get("Authorization", "")
            scheme, token = get_authorization_scheme_param(auth_header)
            if scheme.lower() != "bearer" or not token:
                return None
            claims = decode_token(token)
            roles: frozenset[str] = frozenset()
            return AuthContext(
                user_id=claims.user_id,
                tenant_id=claims.tenant_id,
                roles=roles,
            )
        except Exception:  # noqa: BLE001 Ã¢â‚¬â€ best-effort resolver
            return None


def create_app() -> FastAPI:
    """Application factory. Tests use this to build a fresh app per case."""
    app = FastAPI(
        title="InfinityRx Core Platform",
        version="1.0.0",
        description="Tenants, auth, RBAC, audit, jobs, files, notifications.",
        lifespan=lifespan,
    )
    # Middleware ordering note: Starlette applies middleware in LIFO order
    # (last add_middleware call = outermost layer). The desired request flow:
    #
    #   SecurityHeaders Ã¢â€ â€™ RateLimit Ã¢â€ â€™ TenantIsolation Ã¢â€ â€™ Audit Ã¢â€ â€™ routes
    #
    # So we add them in the reverse order (innermost first):
    #   AuditMiddleware (innermost, closest to routes)
    #   TenantIsolationMiddleware (pure ASGI, runs before routes)
    #   RateLimitMiddleware
    #   SecurityHeadersMiddleware (outermost Ã¢â‚¬â€ headers on ALL responses)
    app.add_middleware(
        AuditMiddleware,
        session_factory=_audit_session_factory,
        user_resolver=_audit_user_resolver,
        event_bus=get_event_bus(),
    )
    # Allowlist of anonymous endpoints that must bypass the tenant auth
    # check. Login, refresh, and MFA verify all run without a caller token
    # (that's the whole point); health probes come from Kubernetes which
    # never carries an auth header. Everything else still requires a valid
    # JWT. Paths must match `scope["path"]` exactly.
    _UNAUTH_PATHS: frozenset[str] = frozenset(
        {
            "/api/v1/auth/login",
            "/api/v1/auth/token/refresh",
            "/api/v1/auth/mfa/verify",
            "/health",
        }
    )
    app.add_middleware(
        TenantIsolationMiddleware,
        resolver=_TenantResolver(),
        unauthenticated_paths=_UNAUTH_PATHS,
    )
    app.add_middleware(RateLimitMiddleware, config=RateLimitConfig())
    app.add_middleware(SecurityHeadersMiddleware)

    app.include_router(api_router)
    app.include_router(auth_api_router)
    app.include_router(
        build_dlq_router(
            get_service=_get_dlq_service,
            get_permissions=_get_dlq_permissions,
        )
    )

    # Wire auth session + user loader + audit sink against the shim's
    # sessionmaker. The auth routers declare `Depends(auth_get_session)`
    # which resolves to the placeholder in `src.auth._db`; without this
    # override the first live request 500s with "must be overridden".
    # `configure_core_auth` installs the shared `CurrentUser` loader so
    # `tenant_admin_only` and peers can resolve roles/permissions from
    # the real ORM. `configure_audit_sink` swaps the process-wide
    # InMemoryAuditSink fallback for a DB-backed sink. LESSON-006 applies:
    # the integration test in tests/test_main_auth_wired.py hits a real
    # HTTP request through this wiring Ã¢â‚¬â€ unit tests on the router alone
    # do not prove it's mounted.
    SessionLocal = db_shim.get_sessionmaker()

    def _auth_session_dep():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[auth_get_session] = _auth_session_dep
    configure_core_auth(SessionLocal)
    configure_audit_sink(SessionLocal)

    return app


app = create_app()


__all__ = ["app", "create_app", "lifespan"]
