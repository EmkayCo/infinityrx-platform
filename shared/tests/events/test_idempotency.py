"""Tests for idempotent consumer wrapper — 100% coverage required (financial path)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from shared.events.idempotency import (
    InMemoryIdempotencyStore,
    idempotent_handler,
)


# ---------------------------------------------------------------------------
# InMemoryIdempotencyStore — TTL behaviour
# ---------------------------------------------------------------------------


async def test_unseen_key_returns_false():
    store = InMemoryIdempotencyStore()
    assert await store.seen("key-1") is False


async def test_seen_returns_true_after_mark():
    store = InMemoryIdempotencyStore()
    await store.mark("key-1", ttl_seconds=300)
    assert await store.seen("key-1") is True


async def test_ttl_expiry_clears_key():
    """After TTL expires the key should be unseen again."""
    base_time = datetime(2026, 4, 12, 10, 0, 0, tzinfo=UTC)

    fixed_now = base_time

    def _now() -> datetime:
        return fixed_now

    store = InMemoryIdempotencyStore(now=_now)
    await store.mark("key-1", ttl_seconds=60)
    assert await store.seen("key-1") is True

    # Advance time past TTL
    fixed_now = base_time + timedelta(seconds=61)
    assert await store.seen("key-1") is False


async def test_key_still_seen_just_before_expiry():
    base_time = datetime(2026, 4, 12, 10, 0, 0, tzinfo=UTC)
    fixed_now = base_time

    def _now() -> datetime:
        return fixed_now

    store = InMemoryIdempotencyStore(now=_now)
    await store.mark("key-1", ttl_seconds=60)

    fixed_now = base_time + timedelta(seconds=59)
    assert await store.seen("key-1") is True


async def test_multiple_keys_independent():
    store = InMemoryIdempotencyStore()
    await store.mark("key-a", ttl_seconds=300)
    assert await store.seen("key-a") is True
    assert await store.seen("key-b") is False


async def test_remark_extends_ttl():
    """Re-marking a key resets its TTL."""
    base_time = datetime(2026, 4, 12, 10, 0, 0, tzinfo=UTC)
    fixed_now = base_time

    def _now() -> datetime:
        return fixed_now

    store = InMemoryIdempotencyStore(now=_now)
    await store.mark("key-1", ttl_seconds=60)

    # Advance to 50 seconds, re-mark
    fixed_now = base_time + timedelta(seconds=50)
    await store.mark("key-1", ttl_seconds=60)

    # At original +70s (which is new_mark+20s) — should still be seen
    fixed_now = base_time + timedelta(seconds=70)
    assert await store.seen("key-1") is True

    # At new_mark+61s (original+111s) — expired
    fixed_now = base_time + timedelta(seconds=50 + 61)
    assert await store.seen("key-1") is False


# ---------------------------------------------------------------------------
# idempotent_handler decorator
# ---------------------------------------------------------------------------


async def test_first_call_invokes_inner_handler():
    store = InMemoryIdempotencyStore()
    calls: list[str] = []

    async def inner(key: str) -> None:
        calls.append(key)

    wrapped = idempotent_handler(store, consumer_name="test-consumer", ttl_seconds=300)(inner)
    await wrapped("key-1")
    assert calls == ["key-1"]


async def test_second_call_with_same_key_skips_inner():
    store = InMemoryIdempotencyStore()
    calls: list[str] = []

    async def inner(key: str) -> None:
        calls.append(key)

    wrapped = idempotent_handler(store, consumer_name="test-consumer", ttl_seconds=300)(inner)
    await wrapped("key-1")
    await wrapped("key-1")
    assert calls == ["key-1"]  # only called once


async def test_different_keys_each_invoke_inner():
    store = InMemoryIdempotencyStore()
    calls: list[str] = []

    async def inner(key: str) -> None:
        calls.append(key)

    wrapped = idempotent_handler(store, consumer_name="test-consumer", ttl_seconds=300)(inner)
    await wrapped("key-1")
    await wrapped("key-2")
    assert calls == ["key-1", "key-2"]


async def test_after_ttl_expiry_handler_invoked_again():
    base_time = datetime(2026, 4, 12, 10, 0, 0, tzinfo=UTC)
    fixed_now = base_time

    def _now() -> datetime:
        return fixed_now

    store = InMemoryIdempotencyStore(now=_now)
    calls: list[str] = []

    async def inner(key: str) -> None:
        calls.append(key)

    wrapped = idempotent_handler(store, consumer_name="test-consumer", ttl_seconds=60)(inner)
    await wrapped("key-1")
    assert calls == ["key-1"]

    fixed_now = base_time + timedelta(seconds=61)
    await wrapped("key-1")
    assert calls == ["key-1", "key-1"]  # called again after expiry


async def test_different_consumers_process_same_key_independently():
    """Consumer name scoping: consumer-A and consumer-B are independent."""
    store = InMemoryIdempotencyStore()
    calls_a: list[str] = []
    calls_b: list[str] = []

    async def handler_a(key: str) -> None:
        calls_a.append(key)

    async def handler_b(key: str) -> None:
        calls_b.append(key)

    wrapped_a = idempotent_handler(store, consumer_name="consumer-A", ttl_seconds=300)(handler_a)
    wrapped_b = idempotent_handler(store, consumer_name="consumer-B", ttl_seconds=300)(handler_b)

    # Both consumers process the same idempotency key
    await wrapped_a("shared-key")
    await wrapped_b("shared-key")

    assert calls_a == ["shared-key"]
    assert calls_b == ["shared-key"]

    # Second calls for both are idempotent
    await wrapped_a("shared-key")
    await wrapped_b("shared-key")
    assert calls_a == ["shared-key"]
    assert calls_b == ["shared-key"]


async def test_inner_exception_propagates_and_does_not_mark():
    """If handler raises, key should not be marked (so retry is possible)."""
    store = InMemoryIdempotencyStore()
    call_count = 0

    async def failing(key: str) -> None:
        nonlocal call_count
        call_count += 1
        raise ValueError("downstream error")

    wrapped = idempotent_handler(store, consumer_name="test-consumer", ttl_seconds=300)(failing)

    with pytest.raises(ValueError, match="downstream error"):
        await wrapped("key-1")

    assert call_count == 1
    # Key was NOT marked — second call should try again
    with pytest.raises(ValueError, match="downstream error"):
        await wrapped("key-1")

    assert call_count == 2


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


def test_in_memory_store_implements_protocol():
    """Runtime check that InMemoryIdempotencyStore satisfies IdempotencyStore Protocol."""
    store = InMemoryIdempotencyStore()
    assert hasattr(store, "seen")
    assert hasattr(store, "mark")
    assert asyncio.iscoroutinefunction(store.seen)
    assert asyncio.iscoroutinefunction(store.mark)


# ---------------------------------------------------------------------------
# PostgresIdempotencyStore — tested via testcontainers
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_postgres_store_first_seen_returns_false(pg_engine):
    """First-time key is not seen."""
    from shared.events.idempotency import PostgresIdempotencyStore

    store = PostgresIdempotencyStore(pg_engine)
    await store.ensure_table()
    assert await store.seen("pg-key-1", consumer_name="consumer-X") is False


@pytest.mark.integration
async def test_postgres_store_mark_then_seen(pg_engine):
    from shared.events.idempotency import PostgresIdempotencyStore

    store = PostgresIdempotencyStore(pg_engine)
    await store.ensure_table()
    await store.mark("pg-key-2", consumer_name="consumer-X")
    assert await store.seen("pg-key-2", consumer_name="consumer-X") is True


@pytest.mark.integration
async def test_postgres_store_insert_on_conflict_is_idempotent(pg_engine):
    """Marking the same key twice should not raise."""
    from shared.events.idempotency import PostgresIdempotencyStore

    store = PostgresIdempotencyStore(pg_engine)
    await store.ensure_table()
    await store.mark("pg-key-3", consumer_name="consumer-X")
    await store.mark("pg-key-3", consumer_name="consumer-X")  # no error
    assert await store.seen("pg-key-3", consumer_name="consumer-X") is True


@pytest.mark.integration
async def test_postgres_store_consumer_scoping(pg_engine):
    """Different consumer_name values are independent for the same key."""
    from shared.events.idempotency import PostgresIdempotencyStore

    store = PostgresIdempotencyStore(pg_engine)
    await store.ensure_table()
    await store.mark("pg-key-4", consumer_name="consumer-A")
    assert await store.seen("pg-key-4", consumer_name="consumer-A") is True
    assert await store.seen("pg-key-4", consumer_name="consumer-B") is False
