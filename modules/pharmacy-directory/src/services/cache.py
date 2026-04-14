"""Redis cache layer for pharmacy lookups.

All keys prefixed tenant:{tenant_id}: per tenant-isolation rules.
Pharmacies themselves are shared-directory (no tenant scope), but reads
are always associated with a requesting tenant for audit/cache-key purposes.
"""
from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

logger = logging.getLogger("pharmacy-directory.cache")

_PHARMACY_CACHE_TTL = 86400  # 24 hours per PRD 3.2


class PharmacyCache:
    """Thin wrapper over a redis-like async client."""

    def __init__(self, redis: Any) -> None:
        self._redis = redis

    def _npi_key(self, tenant_id: UUID, npi: str) -> str:
        return f"tenant:{tenant_id}:pharmacy:npi:{npi}"

    def _nabp_key(self, tenant_id: UUID, nabp: str) -> str:
        return f"tenant:{tenant_id}:pharmacy:nabp:{nabp}"

    async def get_by_npi(self, tenant_id: UUID, npi: str) -> dict[str, Any] | None:
        raw = await self._redis.get(self._npi_key(tenant_id, npi))
        if raw is None:
            return None
        return json.loads(raw)  # type: ignore[no-any-return]

    async def set_by_npi(
        self, tenant_id: UUID, npi: str, data: dict[str, Any]
    ) -> None:
        await self._redis.set(
            self._npi_key(tenant_id, npi),
            json.dumps(data),
            ex=_PHARMACY_CACHE_TTL,
        )

    async def invalidate_npi(self, tenant_id: UUID, npi: str) -> None:
        await self._redis.delete(self._npi_key(tenant_id, npi))

    async def get_by_nabp(self, tenant_id: UUID, nabp: str) -> dict[str, Any] | None:
        raw = await self._redis.get(self._nabp_key(tenant_id, nabp))
        if raw is None:
            return None
        return json.loads(raw)  # type: ignore[no-any-return]

    async def set_by_nabp(
        self, tenant_id: UUID, nabp: str, data: dict[str, Any]
    ) -> None:
        await self._redis.set(
            self._nabp_key(tenant_id, nabp),
            json.dumps(data),
            ex=_PHARMACY_CACHE_TTL,
        )

    async def invalidate_nabp(self, tenant_id: UUID, nabp: str) -> None:
        await self._redis.delete(self._nabp_key(tenant_id, nabp))
