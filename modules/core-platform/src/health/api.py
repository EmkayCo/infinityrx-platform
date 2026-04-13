"""Liveness + detailed health endpoints."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from .._shim.auth import CurrentUser, current_user, require_role
from .._shim.db import get_engine

router = APIRouter(prefix="/health", tags=["health"])

ServiceCheck = Callable[[], Awaitable["ServiceStatus"]]


@dataclass
class ServiceStatus:
    name: str
    ok: bool
    latency_ms: float
    critical: bool = False
    detail: Optional[str] = None


@dataclass
class HealthRegistry:
    checks: List[ServiceCheck] = field(default_factory=list)

    def register(self, check: ServiceCheck) -> None:
        self.checks.append(check)

    def clear(self) -> None:
        self.checks.clear()


_registry = HealthRegistry()


def get_registry() -> HealthRegistry:
    return _registry


async def _check_db() -> ServiceStatus:
    start = time.perf_counter()
    try:
        engine = get_engine()
        with engine.connect() as conn:
            from sqlalchemy import text

            conn.execute(text("SELECT 1"))
        return ServiceStatus(name="database", ok=True, latency_ms=(time.perf_counter() - start) * 1000, critical=True)
    except Exception as exc:  # noqa: BLE001
        return ServiceStatus(
            name="database",
            ok=False,
            latency_ms=(time.perf_counter() - start) * 1000,
            critical=True,
            detail=f"{type(exc).__name__}: {exc}",
        )


async def _check_redis() -> ServiceStatus:
    """Ping Redis. Critical=False: stale auth/session caches degrade but
    don't break writes — app can limp along with direct-to-DB reads while
    Redis recovers. Probe uses a fresh connection per call so the check
    notices broker restarts without a retry from stale pool entries.
    """
    start = time.perf_counter()
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        # No Redis configured — don't invent a failure; report as OK w/ detail.
        return ServiceStatus(
            name="redis", ok=True, latency_ms=0.0, critical=False, detail="not configured"
        )
    try:
        import redis  # imported lazily so tests without redis installed don't crash

        client = redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
        try:
            pong = client.ping()
        finally:
            client.close()
        return ServiceStatus(
            name="redis",
            ok=bool(pong),
            latency_ms=(time.perf_counter() - start) * 1000,
            critical=False,
            detail=None if pong else "ping returned falsy",
        )
    except Exception as exc:  # noqa: BLE001
        return ServiceStatus(
            name="redis",
            ok=False,
            latency_ms=(time.perf_counter() - start) * 1000,
            critical=False,
            detail=f"{type(exc).__name__}: {exc}",
        )


async def _check_rabbitmq() -> ServiceStatus:
    """Open a short-lived AMQP connection and close it. Critical=False:
    event-bus downtime means messages queue at the publisher or defer via
    the outbox — degraded, not unhealthy. Kubernetes readiness probe
    should NOT use this to flip pods out of rotation; the app serves
    reads + writes without RabbitMQ."""
    start = time.perf_counter()
    url = os.getenv("RABBITMQ_URL", "").strip()
    if not url:
        return ServiceStatus(
            name="rabbitmq", ok=True, latency_ms=0.0, critical=False, detail="not configured"
        )
    try:
        import aio_pika  # imported lazily

        connection = await aio_pika.connect_robust(url, timeout=2.0)
        try:
            is_closed = connection.is_closed
        finally:
            await connection.close()
        return ServiceStatus(
            name="rabbitmq",
            ok=not is_closed,
            latency_ms=(time.perf_counter() - start) * 1000,
            critical=False,
        )
    except Exception as exc:  # noqa: BLE001
        return ServiceStatus(
            name="rabbitmq",
            ok=False,
            latency_ms=(time.perf_counter() - start) * 1000,
            critical=False,
            detail=f"{type(exc).__name__}: {exc}",
        )


_registry.register(_check_db)
_registry.register(_check_redis)
_registry.register(_check_rabbitmq)


@router.get("")
async def liveness() -> Dict[str, str]:
    return {
        "status": "ok",
        "version": os.getenv("APP_VERSION", "0.1.0"),
        "commit_sha": os.getenv("APP_COMMIT_SHA", "dev"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/detailed", dependencies=[Depends(require_role("platform_admin"))])
async def detailed(_user: CurrentUser = Depends(current_user)) -> Dict:
    statuses: List[ServiceStatus] = []
    for check in _registry.checks:
        statuses.append(await check())
    critical_failure = any(s.critical and not s.ok for s in statuses)
    degraded = any(not s.ok for s in statuses) and not critical_failure

    body = {
        "status": "unhealthy" if critical_failure else ("degraded" if degraded else "healthy"),
        "version": os.getenv("APP_VERSION", "0.1.0"),
        "commit_sha": os.getenv("APP_COMMIT_SHA", "dev"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": [
            {
                "name": s.name,
                "ok": s.ok,
                "latency_ms": round(s.latency_ms, 3),
                "critical": s.critical,
                "detail": s.detail,
            }
            for s in statuses
        ],
    }
    if critical_failure:
        raise HTTPException(status_code=503, detail=body)
    return body
