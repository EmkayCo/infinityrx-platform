from __future__ import annotations

import pytest

from src.health.api import ServiceStatus, get_registry


def test_liveness(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_detailed_healthy(client, platform_admin):
    resp = client.get("/api/v1/health/detailed")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"
    names = [s["name"] for s in resp.json()["services"]]
    assert "database" in names


def test_detailed_requires_platform_admin(client, tenant_admin_a):
    resp = client.get("/api/v1/health/detailed")
    assert resp.status_code == 403


def test_detailed_db_down_returns_503(client, platform_admin, monkeypatch):
    from src.health import api as hmod

    async def bad_db():
        return ServiceStatus(name="database", ok=False, latency_ms=1.0, critical=True, detail="conn refused")

    reg = get_registry()
    original = list(reg.checks)
    reg.clear()
    reg.register(bad_db)
    try:
        resp = client.get("/api/v1/health/detailed")
        assert resp.status_code == 503
        assert resp.json()["detail"]["status"] == "unhealthy"
    finally:
        reg.clear()
        for c in original:
            reg.register(c)


def test_detailed_non_critical_down_is_degraded(client, platform_admin):
    reg = get_registry()
    original = list(reg.checks)

    async def ok_db():
        return ServiceStatus(name="database", ok=True, latency_ms=0.5, critical=True)

    async def bad_redis():
        return ServiceStatus(name="redis", ok=False, latency_ms=0.5, critical=False, detail="down")

    reg.clear()
    reg.register(ok_db)
    reg.register(bad_redis)
    try:
        resp = client.get("/api/v1/health/detailed")
        assert resp.status_code == 200
        assert resp.json()["status"] == "degraded"
    finally:
        reg.clear()
        for c in original:
            reg.register(c)


async def test_check_db_captures_error(monkeypatch):
    from src.health import api as hmod

    def boom():
        raise RuntimeError("no engine")

    monkeypatch.setattr(hmod, "get_engine", boom)
    status = await hmod._check_db()
    assert status.ok is False
    assert "RuntimeError" in (status.detail or "")


async def test_check_db_success():
    from src.health import api as hmod

    status = await hmod._check_db()
    assert status.ok is True
