"""Tests for the Redis and RabbitMQ health check callables."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.health import api as hmod


# ---------------------------------------------------------------------------
# _check_redis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redis_check_reports_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    status = await hmod._check_redis()
    assert status.name == "redis"
    assert status.ok is True  # non-failure when absent by design
    assert status.detail == "not configured"
    assert status.critical is False


@pytest.mark.asyncio
async def test_redis_check_empty_url_is_not_configured(monkeypatch) -> None:
    monkeypatch.setenv("REDIS_URL", "   ")
    status = await hmod._check_redis()
    assert status.ok is True
    assert status.detail == "not configured"


@pytest.mark.asyncio
async def test_redis_check_ping_success(monkeypatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://fake:6379")
    fake_client = MagicMock()
    fake_client.ping.return_value = True
    fake_redis = MagicMock()
    fake_redis.Redis.from_url.return_value = fake_client
    with patch.dict(sys.modules, {"redis": fake_redis}):
        status = await hmod._check_redis()
    assert status.ok is True
    assert status.name == "redis"
    assert status.critical is False
    fake_redis.Redis.from_url.assert_called_once()
    fake_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_redis_check_ping_falsy(monkeypatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://fake:6379")
    fake_client = MagicMock()
    fake_client.ping.return_value = False
    fake_redis = MagicMock()
    fake_redis.Redis.from_url.return_value = fake_client
    with patch.dict(sys.modules, {"redis": fake_redis}):
        status = await hmod._check_redis()
    assert status.ok is False
    assert status.detail == "ping returned falsy"


@pytest.mark.asyncio
async def test_redis_check_exception(monkeypatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://unreachable:6379")
    fake_redis = MagicMock()
    fake_redis.Redis.from_url.side_effect = ConnectionError("timeout")
    with patch.dict(sys.modules, {"redis": fake_redis}):
        status = await hmod._check_redis()
    assert status.ok is False
    assert "ConnectionError" in status.detail
    assert "timeout" in status.detail


# ---------------------------------------------------------------------------
# _check_rabbitmq
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rabbitmq_check_reports_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("RABBITMQ_URL", raising=False)
    status = await hmod._check_rabbitmq()
    assert status.name == "rabbitmq"
    assert status.ok is True
    assert status.detail == "not configured"


@pytest.mark.asyncio
async def test_rabbitmq_check_connects_ok(monkeypatch) -> None:
    monkeypatch.setenv("RABBITMQ_URL", "amqp://u:p@fake:5672/")
    fake_conn = MagicMock()
    fake_conn.is_closed = False
    fake_conn.close = AsyncMock()
    fake_aio_pika = MagicMock()
    fake_aio_pika.connect_robust = AsyncMock(return_value=fake_conn)
    with patch.dict(sys.modules, {"aio_pika": fake_aio_pika}):
        status = await hmod._check_rabbitmq()
    assert status.ok is True
    fake_aio_pika.connect_robust.assert_awaited_once()
    fake_conn.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_rabbitmq_check_reports_closed(monkeypatch) -> None:
    monkeypatch.setenv("RABBITMQ_URL", "amqp://u:p@fake:5672/")
    fake_conn = MagicMock()
    fake_conn.is_closed = True
    fake_conn.close = AsyncMock()
    fake_aio_pika = MagicMock()
    fake_aio_pika.connect_robust = AsyncMock(return_value=fake_conn)
    with patch.dict(sys.modules, {"aio_pika": fake_aio_pika}):
        status = await hmod._check_rabbitmq()
    assert status.ok is False


@pytest.mark.asyncio
async def test_rabbitmq_check_exception(monkeypatch) -> None:
    monkeypatch.setenv("RABBITMQ_URL", "amqp://unreachable:5672/")
    fake_aio_pika = MagicMock()
    fake_aio_pika.connect_robust = AsyncMock(side_effect=ConnectionError("refused"))
    with patch.dict(sys.modules, {"aio_pika": fake_aio_pika}):
        status = await hmod._check_rabbitmq()
    assert status.ok is False
    assert "ConnectionError" in status.detail
    assert "refused" in status.detail


# ---------------------------------------------------------------------------
# Registry contains the new checks
# ---------------------------------------------------------------------------


def test_registry_includes_all_three_checks() -> None:
    names = {c.__name__ for c in hmod._registry.checks}
    assert "_check_db" in names
    assert "_check_redis" in names
    assert "_check_rabbitmq" in names
