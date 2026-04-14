"""UUID validation tests for reporting tenant header dependency.

P1 Item 4 (partial) of the emergency wiring pass: reporting accepts
``X-Tenant-ID`` as a raw string, so a manipulated header can propagate
directly into WHERE clauses. Billing validates the header as a UUID
(``modules/billing/src/api/dependencies.py:22``); reporting must match.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from src.api.dependencies import get_current_tenant_id


@pytest.mark.asyncio
async def test_accepts_valid_uuid() -> None:
    result = await get_current_tenant_id(
        x_tenant_id="11111111-1111-1111-1111-111111111111"
    )
    # Accepts valid UUIDs (returns as string or UUID — don't over-constrain).
    assert str(result) == "11111111-1111-1111-1111-111111111111"


@pytest.mark.asyncio
async def test_rejects_non_uuid_string() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await get_current_tenant_id(x_tenant_id="not-a-uuid")
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_rejects_empty_string() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await get_current_tenant_id(x_tenant_id="")
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_rejects_sql_injection_attempt() -> None:
    with pytest.raises(HTTPException):
        await get_current_tenant_id(x_tenant_id="' OR 1=1 --")
