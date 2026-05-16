"""Integration tests for dataiq event consumer wiring.

CR-01 v2 BLOCK-1 fix: dataiq/src/main.py must call wire_consumers() with a
REAL Redis client, not None. If REDIS_URL is missing, startup must fail fast
(RuntimeError) rather than proceed with None redis silently no-opping events.

These tests verify:
1. wire_consumers(bus, redis=real_redis_mock) subscribes handlers
2. claim.ingested event causes redis.incrby to be called (real side-effect)
3. Startup fails fast when REDIS_URL is missing
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))
_PLATFORM_ROOT = _MODULE_ROOT.parent.parent
if str(_PLATFORM_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLATFORM_ROOT))

os.environ.setdefault("ENCRYPTION_KEY_ACTIVE", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXVuaXQtdGVzdHM=")
os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")
# Required by shared.config.Settings — set before any src.main import triggers create_app()
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql://test:test@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

import pytest

from shared.events import InMemoryEventBus, EventEnvelope

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
CORR = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def _make_redis_mock():
    """Return an async-compatible Redis mock."""
    redis = AsyncMock()
    redis.incrby = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    redis.hset = AsyncMock(return_value=1)
    redis.zadd = AsyncMock(return_value=1)
    return redis


@pytest.mark.asyncio
async def test_wire_consumers_subscribes_claim_ingested():
    """wire_consumers() must subscribe a handler for claim.ingested."""
    from src.events import wire_consumers

    redis = _make_redis_mock()
    bus = InMemoryEventBus()
    await bus.start()
    await wire_consumers(bus, redis=redis)
    assert any(t == "claim.ingested" for t, _ in bus._subs), "claim.ingested handler must be subscribed"
    await bus.stop()


@pytest.mark.asyncio
async def test_claim_ingested_calls_redis_incrby():
    """claim.ingested event must call redis.incrby (real side-effect verification)."""
    from src.events import wire_consumers

    redis = _make_redis_mock()
    bus = InMemoryEventBus()
    await bus.start()
    await wire_consumers(bus, redis=redis)

    envelope = EventEnvelope(
        event_type="claim.ingested",
        tenant_id=TENANT,
        correlation_id=CORR,
        source_module="billing",
        payload={
            "claim_id": str(uuid.uuid4()),
            "ndc": "12345678901",
            "paid_amount": "45.00",
            "date_of_service": "2026-05-01",
        },
    )
    await bus.publish(envelope)
    await bus.stop()

    # Redis must have been called (incrby or hset for KPI counters)
    assert redis.incrby.called or redis.hset.called, (
        "claim.ingested consumer must call redis to update KPI counters"
    )


@pytest.mark.asyncio
async def test_build_redis_or_fail_raises_without_env():
    """_build_redis_or_fail() must raise RuntimeError when REDIS_URL is missing."""
    from src.main import _build_redis_or_fail

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("REDIS_URL", None)
        with pytest.raises(RuntimeError, match="REDIS_URL"):
            await _build_redis_or_fail()
