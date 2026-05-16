"""Integration tests for ai-nlp event consumer wiring.

CR-01 v2 BLOCK-3 fix: ai-nlp/src/app.py must call wire_consumers() with a
REAL OpenAI client, not None. With None, idempotency marks events as
processed even though the handler silently no-ops — producing data loss
(an FWA flag that should trigger NLP analysis is forever skipped).

These tests verify:
1. wire_consumers() with a real openai_client mock subscribes handlers
2. fwa.claim_flagged event reaches AiNlpEventConsumer.handle_fwa_claim_flagged
3. Startup fails fast when AZURE_OPENAI_ENDPOINT or API_KEY is missing
4. Idempotency: duplicate events are not re-processed
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
# Required by shared.config.Settings — set before any src.app import triggers create_app()
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql://test:test@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

import pytest

from shared.events import InMemoryEventBus, EventEnvelope
from shared.events.idempotency import InMemoryIdempotencyStore

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
CORR = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def _make_openai_mock():
    """Return a mock OpenAIClient with async complete()."""
    client = MagicMock()
    client.complete = AsyncMock(return_value="Mock AI analysis complete.")
    return client


@pytest.mark.asyncio
async def test_wire_consumers_subscribes_fwa_claim_flagged():
    """wire_consumers() must subscribe a handler for fwa.claim_flagged."""
    from src.events import wire_consumers

    openai_client = _make_openai_mock()
    bus = InMemoryEventBus()
    await bus.start()
    await wire_consumers(bus, openai_client=openai_client, db_factory=None)
    assert any(t == "fwa.claim_flagged" for t, _ in bus._subs), "fwa.claim_flagged must be subscribed"
    await bus.stop()


@pytest.mark.asyncio
async def test_fwa_claim_flagged_calls_openai_complete():
    """fwa.claim_flagged event must call openai_client.complete() (real side-effect)."""
    from src.events import wire_consumers

    openai_client = _make_openai_mock()
    bus = InMemoryEventBus()
    await bus.start()
    await wire_consumers(
        bus,
        openai_client=openai_client,
        db_factory=None,
        idempotency_store=InMemoryIdempotencyStore(),
    )

    envelope = EventEnvelope(
        event_type="fwa.claim_flagged",
        tenant_id=TENANT,
        correlation_id=CORR,
        source_module="reclaimrx",
        payload={
            "claim_id": str(uuid.uuid4()),
            "flag_reason": "unusual_billing_pattern",
            "risk_score": "0.92",
        },
    )
    await bus.publish(envelope)
    await bus.stop()

    assert openai_client.complete.called, (
        "openai_client.complete() must be called when fwa.claim_flagged is received"
    )


@pytest.mark.asyncio
async def test_idempotency_fwa_claim_not_reprocessed():
    """Duplicate fwa.claim_flagged envelopes must not call openai_client twice."""
    from src.events import wire_consumers

    openai_client = _make_openai_mock()
    store = InMemoryIdempotencyStore()
    bus = InMemoryEventBus()
    await bus.start()
    await wire_consumers(bus, openai_client=openai_client, db_factory=None, idempotency_store=store)

    idem_key = f"fwa.claim_flagged:dedup-{uuid.uuid4()}"
    envelope = EventEnvelope(
        event_type="fwa.claim_flagged",
        tenant_id=TENANT,
        correlation_id=CORR,
        source_module="reclaimrx",
        idempotency_key=idem_key,
        payload={"claim_id": str(uuid.uuid4()), "flag_reason": "test"},
    )
    # Publish twice
    await bus.publish(envelope)
    await bus.publish(envelope)
    await bus.stop()

    assert openai_client.complete.call_count == 1, (
        "Duplicate fwa.claim_flagged must call openai_client.complete() exactly once"
    )


@pytest.mark.asyncio
async def test_build_openai_client_or_fail_raises_without_endpoint():
    """_build_openai_client_or_fail() must raise RuntimeError when endpoint missing."""
    from src.app import _build_openai_client_or_fail

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("AZURE_OPENAI_ENDPOINT", None)
        os.environ.pop("AZURE_OPENAI_API_KEY", None)
        with pytest.raises(RuntimeError, match="AZURE_OPENAI"):
            await _build_openai_client_or_fail()


@pytest.mark.asyncio
async def test_build_openai_client_or_fail_raises_missing_api_key():
    """_build_openai_client_or_fail() must raise RuntimeError when API key missing."""
    from src.app import _build_openai_client_or_fail

    with patch.dict(os.environ, {"AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com"}, clear=False):
        os.environ.pop("AZURE_OPENAI_API_KEY", None)
        with pytest.raises(RuntimeError, match="AZURE_OPENAI"):
            await _build_openai_client_or_fail()
