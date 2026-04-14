"""Unit tests for DataIQ event consumers.

Tests verify:
1. Claim ingested → Redis counters incremented with tenant-scoped keys.
2. FWA flagged → FWA counter incremented.
3. Payment settled → financial counter incremented.
4. Idempotency: second call with same key is a no-op.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from src.events.consumers import (
    make_claim_ingested_handler,
    make_fwa_flagged_handler,
    make_payment_settled_handler,
)

from shared.events.idempotency import InMemoryIdempotencyStore
from shared.events.types import EventEnvelope


def make_envelope(
    event_type: str,
    tenant_id: uuid.UUID,
    payload: dict | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        event_type=event_type,
        tenant_id=tenant_id,
        correlation_id=uuid.uuid4(),
        source_module="billing",
        payload=payload or {},
    )


@pytest.fixture()
def mock_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.incrby = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    redis.hincrbyfloat = AsyncMock(return_value="100.00")
    return redis


class TestClaimIngestedHandler:
    @pytest.mark.asyncio
    async def test_increments_claim_count_counters(self, mock_redis: AsyncMock) -> None:
        store = InMemoryIdempotencyStore()
        handler = make_claim_ingested_handler(mock_redis, store)
        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        envelope = make_envelope("claim.ingested", tenant_id)

        await handler(envelope.idempotency_key, envelope)

        assert mock_redis.incrby.call_count == 3  # minute + hour + day

    @pytest.mark.asyncio
    async def test_redis_keys_contain_tenant_prefix(self, mock_redis: AsyncMock) -> None:
        store = InMemoryIdempotencyStore()
        handler = make_claim_ingested_handler(mock_redis, store)
        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        envelope = make_envelope("claim.ingested", tenant_id)

        await handler(envelope.idempotency_key, envelope)

        for call in mock_redis.incrby.call_args_list:
            key = call[0][0]
            assert key.startswith(f"tenant:{tenant_id}:"), (
                f"Redis key {key!r} does not start with tenant prefix"
            )

    @pytest.mark.asyncio
    async def test_increments_financial_counter_when_amount_present(
        self, mock_redis: AsyncMock
    ) -> None:
        store = InMemoryIdempotencyStore()
        handler = make_claim_ingested_handler(mock_redis, store)
        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        envelope = make_envelope("claim.ingested", tenant_id, {"amount": "150.00"})

        await handler(envelope.idempotency_key, envelope)

        mock_redis.hincrbyfloat.assert_called_once()
        key = mock_redis.hincrbyfloat.call_args[0][0]
        assert key.startswith(f"tenant:{tenant_id}:")

    @pytest.mark.asyncio
    async def test_idempotent_second_call_is_noop(self, mock_redis: AsyncMock) -> None:
        store = InMemoryIdempotencyStore()
        handler = make_claim_ingested_handler(mock_redis, store)
        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        envelope = make_envelope("claim.ingested", tenant_id)

        await handler(envelope.idempotency_key, envelope)
        first_count = mock_redis.incrby.call_count

        await handler(envelope.idempotency_key, envelope)
        second_count = mock_redis.incrby.call_count

        assert second_count == first_count  # no additional calls

    @pytest.mark.asyncio
    async def test_different_envelopes_both_processed(self, mock_redis: AsyncMock) -> None:
        store = InMemoryIdempotencyStore()
        handler = make_claim_ingested_handler(mock_redis, store)
        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        env1 = make_envelope("claim.ingested", tenant_id)
        env2 = make_envelope("claim.ingested", tenant_id)

        await handler(env1.idempotency_key, env1)
        await handler(env2.idempotency_key, env2)

        assert mock_redis.incrby.call_count == 6  # 3 per envelope


class TestPaymentSettledHandlerNoAmount:
    @pytest.mark.asyncio
    async def test_no_amount_in_payload_no_financial_counter(self, mock_redis: AsyncMock) -> None:
        store = InMemoryIdempotencyStore()
        handler = make_payment_settled_handler(mock_redis, store)
        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        # No amount in payload
        envelope = make_envelope("payment.settled", tenant_id, {})

        await handler(envelope.idempotency_key, envelope)

        mock_redis.hincrbyfloat.assert_not_called()


class TestFwaFlaggedHandler:
    @pytest.mark.asyncio
    async def test_increments_fwa_flag_count(self, mock_redis: AsyncMock) -> None:
        store = InMemoryIdempotencyStore()
        handler = make_fwa_flagged_handler(mock_redis, store)
        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        envelope = make_envelope("fwa.claim_flagged", tenant_id)

        await handler(envelope.idempotency_key, envelope)

        assert mock_redis.incrby.call_count == 1
        key = mock_redis.incrby.call_args[0][0]
        assert key.startswith(f"tenant:{tenant_id}:")
        assert "fwa_flag_count" in key


class TestPaymentSettledHandler:
    @pytest.mark.asyncio
    async def test_increments_financial_counter_for_settled_amount(
        self, mock_redis: AsyncMock
    ) -> None:
        store = InMemoryIdempotencyStore()
        handler = make_payment_settled_handler(mock_redis, store)
        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        envelope = make_envelope("payment.settled", tenant_id, {"amount": "5000.00"})

        await handler(envelope.idempotency_key, envelope)

        mock_redis.hincrbyfloat.assert_called_once()
        key = mock_redis.hincrbyfloat.call_args[0][0]
        assert key.startswith(f"tenant:{tenant_id}:")
        assert "payments_settled" in key
