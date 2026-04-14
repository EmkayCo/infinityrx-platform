"""Tests for shared.auth.mfa.challenge."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from shared.auth.mfa.challenge import (
    ChallengeClaims,
    InMemoryChallengeStore,
    RedisChallengeStore,
    consume_challenge,
    create_challenge,
)

_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


# ---------------------------------------------------------------------------
# ChallengeClaims
# ---------------------------------------------------------------------------


def test_claims_frozen() -> None:
    claims = ChallengeClaims(user_id=_USER_ID, tenant_id=_TENANT_ID, method="totp")
    with pytest.raises(AttributeError):
        claims.method = "fido2"  # type: ignore[misc]


def test_claims_defaults() -> None:
    claims = ChallengeClaims(user_id=_USER_ID, tenant_id=_TENANT_ID, method="totp")
    assert claims.enrollment_required is False


# ---------------------------------------------------------------------------
# InMemoryChallengeStore
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inmemory_put_get_roundtrip() -> None:
    store = InMemoryChallengeStore()
    claims = ChallengeClaims(user_id=_USER_ID, tenant_id=_TENANT_ID, method="totp")
    await store.put("tok1", claims, ttl=300)
    result = await store.get("tok1")
    assert result == claims


@pytest.mark.asyncio
async def test_inmemory_get_missing_returns_none() -> None:
    store = InMemoryChallengeStore()
    assert await store.get("nonexistent") is None


@pytest.mark.asyncio
async def test_inmemory_delete() -> None:
    store = InMemoryChallengeStore()
    claims = ChallengeClaims(user_id=_USER_ID, tenant_id=_TENANT_ID, method="fido2")
    await store.put("tok2", claims, ttl=300)
    await store.delete("tok2")
    assert await store.get("tok2") is None


@pytest.mark.asyncio
async def test_inmemory_delete_missing_no_error() -> None:
    store = InMemoryChallengeStore()
    await store.delete("no-such-token")  # Should not raise


@pytest.mark.asyncio
async def test_inmemory_expired_returns_none() -> None:
    store = InMemoryChallengeStore()
    claims = ChallengeClaims(user_id=_USER_ID, tenant_id=_TENANT_ID, method="totp")
    await store.put("tok3", claims, ttl=1)
    # Manually expire the entry
    token_entry = store._store["tok3"]
    store._store["tok3"] = (token_entry[0], datetime.now(tz=timezone.utc) - timedelta(seconds=1))
    assert await store.get("tok3") is None


@pytest.mark.asyncio
async def test_inmemory_clear() -> None:
    store = InMemoryChallengeStore()
    claims = ChallengeClaims(user_id=_USER_ID, tenant_id=_TENANT_ID, method="totp")
    await store.put("a", claims, ttl=300)
    await store.put("b", claims, ttl=300)
    store.clear()
    assert await store.get("a") is None
    assert await store.get("b") is None


# ---------------------------------------------------------------------------
# RedisChallengeStore
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redis_put_calls_setex() -> None:
    redis = AsyncMock()
    store = RedisChallengeStore(redis)
    claims = ChallengeClaims(
        user_id=_USER_ID, tenant_id=_TENANT_ID, method="totp", enrollment_required=True
    )
    await store.put("tok", claims, ttl=300)
    redis.setex.assert_awaited_once()
    args = redis.setex.call_args
    assert args[0][0] == "mfa:challenge:tok"
    assert args[0][1] == 300


@pytest.mark.asyncio
async def test_redis_get_returns_claims() -> None:
    import json

    redis = AsyncMock()
    redis.get.return_value = json.dumps(
        {
            "user_id": str(_USER_ID),
            "tenant_id": str(_TENANT_ID),
            "method": "fido2",
            "enrollment_required": True,
        }
    )
    store = RedisChallengeStore(redis)
    result = await store.get("tok")
    assert result is not None
    assert result.user_id == _USER_ID
    assert result.tenant_id == _TENANT_ID
    assert result.method == "fido2"
    assert result.enrollment_required is True
    redis.get.assert_awaited_once_with("mfa:challenge:tok")


@pytest.mark.asyncio
async def test_redis_get_missing_returns_none() -> None:
    redis = AsyncMock()
    redis.get.return_value = None
    store = RedisChallengeStore(redis)
    assert await store.get("missing") is None


@pytest.mark.asyncio
async def test_redis_get_enrollment_required_default() -> None:
    import json

    redis = AsyncMock()
    redis.get.return_value = json.dumps(
        {
            "user_id": str(_USER_ID),
            "tenant_id": str(_TENANT_ID),
            "method": "totp",
        }
    )
    store = RedisChallengeStore(redis)
    result = await store.get("tok")
    assert result is not None
    assert result.enrollment_required is False


@pytest.mark.asyncio
async def test_redis_delete() -> None:
    redis = AsyncMock()
    store = RedisChallengeStore(redis)
    await store.delete("tok")
    redis.delete.assert_awaited_once_with("mfa:challenge:tok")


# ---------------------------------------------------------------------------
# create_challenge
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_challenge_returns_token() -> None:
    store = InMemoryChallengeStore()
    token = await create_challenge(
        store, user_id=_USER_ID, tenant_id=_TENANT_ID, method="totp"
    )
    assert isinstance(token, str)
    assert len(token) > 20  # 32 bytes of entropy → ~43 chars base64url


@pytest.mark.asyncio
async def test_create_challenge_stores_claims() -> None:
    store = InMemoryChallengeStore()
    token = await create_challenge(
        store, user_id=_USER_ID, tenant_id=_TENANT_ID, method="fido2", enrollment_required=True
    )
    claims = await store.get(token)
    assert claims is not None
    assert claims.user_id == _USER_ID
    assert claims.tenant_id == _TENANT_ID
    assert claims.method == "fido2"
    assert claims.enrollment_required is True


@pytest.mark.asyncio
async def test_create_challenge_unique_tokens() -> None:
    store = InMemoryChallengeStore()
    tokens = set()
    for _ in range(20):
        t = await create_challenge(store, user_id=_USER_ID, tenant_id=_TENANT_ID, method="totp")
        tokens.add(t)
    assert len(tokens) == 20


# ---------------------------------------------------------------------------
# consume_challenge
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_consume_valid_challenge() -> None:
    store = InMemoryChallengeStore()
    token = await create_challenge(
        store, user_id=_USER_ID, tenant_id=_TENANT_ID, method="totp"
    )
    claims = await consume_challenge(store, token)
    assert claims is not None
    assert claims.user_id == _USER_ID


@pytest.mark.asyncio
async def test_consume_deletes_token() -> None:
    store = InMemoryChallengeStore()
    token = await create_challenge(
        store, user_id=_USER_ID, tenant_id=_TENANT_ID, method="totp"
    )
    await consume_challenge(store, token)
    # Second consume should return None (single-use)
    assert await consume_challenge(store, token) is None


@pytest.mark.asyncio
async def test_consume_nonexistent_returns_none() -> None:
    store = InMemoryChallengeStore()
    assert await consume_challenge(store, "does-not-exist") is None


@pytest.mark.asyncio
async def test_consume_expired_returns_none() -> None:
    store = InMemoryChallengeStore()
    token = await create_challenge(
        store, user_id=_USER_ID, tenant_id=_TENANT_ID, method="totp", ttl=1
    )
    # Manually expire
    entry = store._store[token]
    store._store[token] = (entry[0], datetime.now(tz=timezone.utc) - timedelta(seconds=1))
    assert await consume_challenge(store, token) is None
