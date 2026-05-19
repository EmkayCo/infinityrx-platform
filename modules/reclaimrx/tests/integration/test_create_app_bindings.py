"""CR-02 / D14: create_app() must wire all 6 required bindings.

D14 checklist:
  1. SecurityHeadersMiddleware mounted
  2. RateLimitMiddleware mounted
  3. DLQ router backed by ReclaimRxDLQRepository (not _EmptyDLQRepository)
  4. Lifespan registers cleanup_processed_events scheduler job
  5. Lifespan registers check_dlq_depth scheduler job
  6. Lifespan registers verify_audit_hash_chain scheduler job

Each test is independent -- tests fail individually so CI pinpoints the gap.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _make_app():
    from src.main import create_app  # noqa: PLC0415
    return create_app()


# ---------------------------------------------------------------------------
# Binding 1 -- SecurityHeadersMiddleware
# ---------------------------------------------------------------------------

def test_security_headers_middleware_mounted():
    """HSTS + X-Frame-Options headers prove SecurityHeadersMiddleware is mounted."""
    with TestClient(_make_app()) as client:
        resp = client.get("/health")
    assert resp.headers.get("Strict-Transport-Security") is not None, (
        "SecurityHeadersMiddleware not mounted"
    )
    assert resp.headers.get("X-Frame-Options") == "DENY"


# ---------------------------------------------------------------------------
# Binding 2 -- RateLimitMiddleware present in middleware stack
# ---------------------------------------------------------------------------

def test_rate_limit_middleware_mounted():
    """RateLimitMiddleware must appear in app.user_middleware."""
    from shared.middleware import RateLimitMiddleware  # noqa: PLC0415

    app = _make_app()
    middleware_classes = [
        m.cls if hasattr(m, "cls") else type(m)
        for m in app.user_middleware
    ]
    assert RateLimitMiddleware in middleware_classes, (
        f"RateLimitMiddleware not in middleware stack: {middleware_classes}"
    )


# ---------------------------------------------------------------------------
# Binding 3 -- DLQ router uses ReclaimRxDLQRepository (not _EmptyDLQRepository)
# ---------------------------------------------------------------------------

def test_dlq_router_uses_real_repository():
    """_get_dlq_service() must return DLQService backed by ReclaimRxDLQRepository."""
    import asyncio  # noqa: PLC0415
    from src.events.dlq_repository import ReclaimRxDLQRepository  # noqa: PLC0415
    from src.main import _get_dlq_service  # noqa: PLC0415

    svc = asyncio.run(_get_dlq_service())
    assert isinstance(svc._repo, ReclaimRxDLQRepository), (
        f"DLQ router still uses stub repository: {type(svc._repo).__name__}"
    )


# ---------------------------------------------------------------------------
# Binding 4, 5, 6 -- Scheduler jobs registered during lifespan startup
# ---------------------------------------------------------------------------

def test_lifespan_registers_cleanup_processed_events_job():
    """Scheduler must have cleanup_processed_events job after lifespan startup."""
    app = _make_app()
    with TestClient(app) as _client:
        scheduler = getattr(app.state, "scheduler", None)
    assert scheduler is not None, "app.state.scheduler not set during lifespan"
    assert "cleanup_processed_events" in scheduler._jobs, (
        "cleanup_processed_events job not registered"
    )


def test_lifespan_registers_check_dlq_depth_job():
    """Scheduler must have check_dlq_depth job after lifespan startup."""
    app = _make_app()
    with TestClient(app) as _client:
        scheduler = getattr(app.state, "scheduler", None)
    assert scheduler is not None, "app.state.scheduler not set during lifespan"
    assert "check_dlq_depth" in scheduler._jobs, (
        "check_dlq_depth job not registered"
    )


def test_lifespan_registers_verify_audit_hash_chain_job():
    """Scheduler must have verify_audit_hash_chain job after lifespan startup."""
    app = _make_app()
    with TestClient(app) as _client:
        scheduler = getattr(app.state, "scheduler", None)
    assert scheduler is not None, "app.state.scheduler not set during lifespan"
    assert "verify_audit_hash_chain" in scheduler._jobs, (
        "verify_audit_hash_chain job not registered"
    )
