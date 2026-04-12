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


_registry.register(_check_db)


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
