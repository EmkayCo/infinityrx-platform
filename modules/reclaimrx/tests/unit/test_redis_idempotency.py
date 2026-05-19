"""Tests for tenant-prefixed Redis idempotency key isolation.

Verifies the key format: tenant:{tenant_id}:reclaimrx:idempotency:{key}
per .claude/rules/tenant-isolation.md (Redis must use tenant-prefixed keys).
"""
from __future__ import annotations

import uuid
import pytest


class TestTenantPrefixedIdempotencyKeys:
    """Redis idempotency keys must be prefixed tenant:{tenant_id}:reclaimrx:idempotency:{key}."""

    def test_build_redis_key_format(self):
        """build_reclaimrx_idempotency_key() returns correctly prefixed key."""
        from src.events.idempotency_keys import build_reclaimrx_idempotency_key

        tenant_id = uuid.UUID("12345678-1234-1234-1234-123456789012")
        raw_key = "hold:release:abc"
        result = build_reclaimrx_idempotency_key(tenant_id, raw_key)
        assert result == f"tenant:{tenant_id}:reclaimrx:idempotency:{raw_key}"

    def test_different_tenants_produce_different_keys(self):
        """Two tenants with same raw_key produce different Redis keys (isolation)."""
        from src.events.idempotency_keys import build_reclaimrx_idempotency_key

        t1 = uuid.uuid4()
        t2 = uuid.uuid4()
        key1 = build_reclaimrx_idempotency_key(t1, "hold:release:abc")
        key2 = build_reclaimrx_idempotency_key(t2, "hold:release:abc")
        assert key1 != key2
        assert str(t1) in key1
        assert str(t2) in key2
