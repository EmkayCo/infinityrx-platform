"""Idempotent consumer support.

Prevents duplicate processing when the event bus delivers the same message
more than once (at-least-once delivery guarantee).  This path is
correctness-critical: duplicates in financial message handlers can corrupt
ledger data.  100% coverage required (see testing.md).

Usage
-----
Decorate any async event handler::

    store = InMemoryIdempotencyStore()           # or PostgresIdempotencyStore(engine)
    handler = idempotent_handler(store, consumer_name="billing", ttl_seconds=86400)(
        my_actual_handler
    )

The decorated handler receives the same arguments as the original but
skips execution (silently) when the idempotency key has already been
processed by this consumer within the TTL window.

The idempotency key is the first positional argument to the wrapped
function.  Callers typically pass the ``EventEnvelope.idempotency_key``
string.
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, runtime_checkable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@runtime_checkable
class IdempotencyStore(Protocol):
    """Protocol for idempotency back-ends."""

    async def seen(self, key: str, *, consumer_name: str = "") -> bool:
        """Return True if *key* has already been processed by *consumer_name*."""
        ...

    async def mark(self, key: str, *, consumer_name: str = "", ttl_seconds: int = 86400) -> None:
        """Record that *key* has been processed by *consumer_name*."""
        ...


class InMemoryIdempotencyStore:
    """Thread-safe in-process store — test double with TTL support.

    The ``now`` callable is injected so tests can freeze/advance time without
    monkeypatching the stdlib (freezegun-compatible but not required).
    """

    def __init__(self, now: Callable[[], datetime] | None = None) -> None:
        self._now: Callable[[], datetime] = now or (lambda: datetime.now(UTC))
        # key → (consumer_name, expires_at)
        self._store: dict[str, datetime] = {}

    def _namespaced(self, key: str, consumer_name: str) -> str:
        return f"{consumer_name}::{key}"

    async def seen(self, key: str, *, consumer_name: str = "") -> bool:
        ns_key = self._namespaced(key, consumer_name)
        expires_at = self._store.get(ns_key)
        if expires_at is None:
            return False
        if self._now() >= expires_at:
            del self._store[ns_key]
            return False
        return True

    async def mark(self, key: str, *, consumer_name: str = "", ttl_seconds: int = 86400) -> None:
        ns_key = self._namespaced(key, consumer_name)
        self._store[ns_key] = self._now() + timedelta(seconds=ttl_seconds)


class PostgresIdempotencyStore:
    """Persistent idempotency store backed by the ``core.processed_events`` table.

    Uses ``INSERT ... ON CONFLICT DO NOTHING`` so concurrent consumers racing
    on the same key are safe — only the first INSERT wins; subsequent calls
    are silently ignored.

    Call ``await store.ensure_table()`` once at startup to create the table
    if it does not exist (idempotent DDL).
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def ensure_table(self) -> None:
        """Create the processed_events table if it does not exist (idempotent)."""
        async with self._engine.begin() as conn:
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS core"))
        async with self._engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS core.processed_events (
                        idempotency_key TEXT NOT NULL,
                        consumer_name   TEXT NOT NULL DEFAULT '',
                        processed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        PRIMARY KEY (idempotency_key, consumer_name)
                    )
                    """
                )
            )

    async def seen(self, key: str, *, consumer_name: str = "") -> bool:
        """Return True if this (key, consumer_name) pair is in the table."""
        async with self._engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT 1 FROM core.processed_events "
                    "WHERE idempotency_key = :key AND consumer_name = :cn "
                    "LIMIT 1"
                ),
                {"key": key, "cn": consumer_name},
            )
            return result.fetchone() is not None

    async def mark(self, key: str, *, consumer_name: str = "", ttl_seconds: int = 86400) -> None:
        """Insert (key, consumer_name) — silently ignores conflicts.

        ``ttl_seconds`` is retained for API compatibility but is NOT
        enforced per-row (Postgres does not have native row TTL).
        Bulk expiration is handled by :meth:`purge_expired` which the
        scheduled-jobs framework calls once per day. Callers that need
        a different retention than the default MUST invoke
        ``purge_expired`` with their own cutoff.
        """
        async with self._engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO core.processed_events (idempotency_key, consumer_name) "
                    "VALUES (:key, :cn) "
                    "ON CONFLICT DO NOTHING"
                ),
                {"key": key, "cn": consumer_name},
            )

    async def purge_expired(self, *, older_than_seconds: int = 7 * 86400) -> int:
        """Delete processed_events rows older than the cutoff.

        Default retention is 7 days, which is long enough to cover any
        reasonable consumer retry window (RabbitMQ retries run on the
        order of minutes) while keeping the table small enough to index
        efficiently at 100M+ events/year throughput.

        Returns the number of rows deleted so the scheduled job can log
        operational metrics.
        """
        async with self._engine.begin() as conn:
            result = await conn.execute(
                text(
                    "DELETE FROM core.processed_events "
                    "WHERE processed_at < NOW() - (:secs || ' seconds')::interval"
                ),
                {"secs": str(older_than_seconds)},
            )
            return result.rowcount or 0


def idempotent_handler(
    store: InMemoryIdempotencyStore | PostgresIdempotencyStore,
    *,
    consumer_name: str,
    ttl_seconds: int = 86400,
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """Decorator factory that wraps an async handler with idempotency checks.

    The wrapped function must accept the idempotency key as its **first
    positional argument**.  Any remaining args/kwargs are forwarded unchanged.

    Behaviour:
    - ``store.seen(key)`` → already processed → return silently (no-op).
    - Otherwise → call inner handler → on success → ``store.mark(key)``.
    - If the inner handler raises, the key is NOT marked so the caller can retry.
    """

    def decorator(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(fn)
        async def wrapper(key: str, *args: Any, **kwargs: Any) -> Any:
            if await store.seen(key, consumer_name=consumer_name):
                return None
            result = await fn(key, *args, **kwargs)
            await store.mark(key, consumer_name=consumer_name, ttl_seconds=ttl_seconds)
            return result

        return wrapper

    return decorator
