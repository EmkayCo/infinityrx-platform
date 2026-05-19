"""Tenant-prefixed Redis idempotency key builder for ReclaimRx.

Per .claude/rules/tenant-isolation.md:
    Redis keys MUST be prefixed: tenant:{tenant_id}:
Per spec D8 binding:
    Full prefix: tenant:{tenant_id}:reclaimrx:idempotency:{raw_key}
"""
from __future__ import annotations

import uuid


def build_reclaimrx_idempotency_key(tenant_id: uuid.UUID, raw_key: str) -> str:
    """Build a tenant-scoped Redis idempotency key for ReclaimRx consumers.

    Args:
        tenant_id: The tenant UUID. Used as the first segment to ensure
            zero cross-tenant key collision per tenant-isolation.md.
        raw_key: The business-level idempotency key
            (e.g. 'hold:release:{hold_id}').

    Returns:
        'tenant:{tenant_id}:reclaimrx:idempotency:{raw_key}'
    """
    return f"tenant:{tenant_id}:reclaimrx:idempotency:{raw_key}"
