"""Tests for PharmacyCache Redis key naming and tenant isolation."""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.cache import PharmacyCache


TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = uuid.UUID("22222222-2222-2222-2222-222222222222")

_SAMPLE = {"npi": "1234567890", "display_name": "Test Pharmacy"}


@pytest.fixture
def mock_redis() -> MagicMock:
    r = MagicMock()
    r.get = AsyncMock(return_value=None)
    r.set = AsyncMock()
    r.delete = AsyncMock()
    return r


class TestPharmacyCache:
    @pytest.mark.asyncio
    async def test_get_by_npi_returns_none_on_cache_miss(self, mock_redis: MagicMock) -> None:
        cache = PharmacyCache(mock_redis)
        result = await cache.get_by_npi(TENANT_A, "1234567890")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_npi_returns_parsed_json_on_hit(self, mock_redis: MagicMock) -> None:
        mock_redis.get = AsyncMock(return_value=json.dumps(_SAMPLE))
        cache = PharmacyCache(mock_redis)
        result = await cache.get_by_npi(TENANT_A, "1234567890")
        assert result == _SAMPLE

    @pytest.mark.asyncio
    async def test_set_by_npi_uses_tenant_prefixed_key(self, mock_redis: MagicMock) -> None:
        cache = PharmacyCache(mock_redis)
        await cache.set_by_npi(TENANT_A, "1234567890", _SAMPLE)
        call_args = mock_redis.set.call_args
        key = call_args[0][0]
        assert f"tenant:{TENANT_A}" in key
        assert "1234567890" in key

    @pytest.mark.asyncio
    async def test_tenant_a_and_b_have_different_keys(self, mock_redis: MagicMock) -> None:
        cache = PharmacyCache(mock_redis)
        await cache.set_by_npi(TENANT_A, "1234567890", _SAMPLE)
        key_a = mock_redis.set.call_args[0][0]
        await cache.set_by_npi(TENANT_B, "1234567890", _SAMPLE)
        key_b = mock_redis.set.call_args[0][0]
        assert key_a != key_b

    @pytest.mark.asyncio
    async def test_invalidate_npi_calls_delete(self, mock_redis: MagicMock) -> None:
        cache = PharmacyCache(mock_redis)
        await cache.invalidate_npi(TENANT_A, "1234567890")
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_by_nabp_uses_tenant_prefixed_key(self, mock_redis: MagicMock) -> None:
        cache = PharmacyCache(mock_redis)
        await cache.set_by_nabp(TENANT_A, "1234567", _SAMPLE)
        key = mock_redis.set.call_args[0][0]
        assert f"tenant:{TENANT_A}" in key
        assert "1234567" in key

    @pytest.mark.asyncio
    async def test_get_by_nabp_returns_none_on_miss(self, mock_redis: MagicMock) -> None:
        cache = PharmacyCache(mock_redis)
        result = await cache.get_by_nabp(TENANT_A, "1234567")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_nabp_returns_parsed_json_on_hit(self, mock_redis: MagicMock) -> None:
        mock_redis.get = AsyncMock(return_value=json.dumps(_SAMPLE))
        cache = PharmacyCache(mock_redis)
        result = await cache.get_by_nabp(TENANT_A, "1234567")
        assert result == _SAMPLE

    @pytest.mark.asyncio
    async def test_invalidate_nabp_calls_delete(self, mock_redis: MagicMock) -> None:
        cache = PharmacyCache(mock_redis)
        await cache.invalidate_nabp(TENANT_A, "1234567")
        mock_redis.delete.assert_called_once()
