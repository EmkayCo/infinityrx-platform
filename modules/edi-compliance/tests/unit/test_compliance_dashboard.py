"""Tests for compliance dashboard DB path."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

_MODULE_ROOT = Path(__file__).resolve().parents[2]
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

import os
os.environ.setdefault("ENCRYPTION_KEY_ACTIVE", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXVuaXQtdGVzdHM=")
os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")

import pytest

TENANT_ID = "11111111-1111-1111-1111-111111111111"
TENANT_UUID = uuid.UUID(TENANT_ID)


class _FakeRow:
    def __init__(self, total=10, pending=2, accepted=8, rejected=0):
        self.total = total
        self.pending = pending
        self.accepted = accepted
        self.rejected = rejected


class _FakeResult:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeDB:
    def __init__(self, row=None):
        self._row = row

    async def execute(self, *args, **kwargs):
        return _FakeResult(row=self._row)


def test_compliance_dashboard_direct_with_data():
    """Directly test get_compliance_dashboard with populated DB."""
    import asyncio
    from src.api.compliance import get_compliance_dashboard

    row = _FakeRow(total=10, pending=2, accepted=8, rejected=0)
    fake_db = _FakeDB(row=row)

    async def run():
        with patch("src.api.compliance.set_tenant_context"):
            return await get_compliance_dashboard(tenant_id=TENANT_UUID, db=fake_db)

    result = asyncio.get_event_loop().run_until_complete(run())
    assert result.total_files == 10
    assert result.pending_transmission == 2
    assert result.acknowledged == 8
    assert result.rejected == 0
    assert result.acceptance_rate_pct == 80.0


def test_compliance_dashboard_direct_no_data():
    """Directly test get_compliance_dashboard with empty DB (row=None)."""
    import asyncio
    from src.api.compliance import get_compliance_dashboard

    fake_db = _FakeDB(row=None)

    async def run():
        with patch("src.api.compliance.set_tenant_context"):
            return await get_compliance_dashboard(tenant_id=TENANT_UUID, db=fake_db)

    result = asyncio.get_event_loop().run_until_complete(run())
    assert result.total_files == 0
    assert result.acceptance_rate_pct == 0.0


def test_compliance_dashboard_direct_zero_total_no_division_by_zero():
    """Directly test acceptance_rate_pct=0 when total=0."""
    import asyncio
    from src.api.compliance import get_compliance_dashboard

    row = _FakeRow(total=0, pending=0, accepted=0, rejected=0)
    fake_db = _FakeDB(row=row)

    async def run():
        with patch("src.api.compliance.set_tenant_context"):
            return await get_compliance_dashboard(tenant_id=TENANT_UUID, db=fake_db)

    result = asyncio.get_event_loop().run_until_complete(run())
    assert result.acceptance_rate_pct == 0.0
