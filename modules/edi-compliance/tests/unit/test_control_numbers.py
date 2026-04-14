"""Tests for atomic control number generation."""

from __future__ import annotations

import uuid

import pytest

from src.x12.control_numbers import SequenceType, next_control_number


TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
PARTNER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


class _FakeResult:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeSession:
    """Minimal async session mock that simulates control number table access."""

    def __init__(self, existing_value=None):
        self._existing_value = existing_value
        self._executed = []
        self._execute_call_count = 0

    async def execute(self, stmt, params=None):
        self._execute_call_count += 1
        if self._execute_call_count == 1:
            # First call: SELECT FOR UPDATE
            if self._existing_value is not None:
                # Return an existing row: (id, current_value, max_value)
                row = (str(uuid.uuid4()), self._existing_value, 999999999)
                return _FakeResult(row)
            else:
                return _FakeResult(None)
        else:
            # Subsequent calls: INSERT or UPDATE
            return _FakeResult(None)


@pytest.mark.asyncio
async def test_next_control_number_creates_new_sequence():
    """When no sequence row exists, creates one and returns 1."""
    session = _FakeSession(existing_value=None)
    result = await next_control_number(session, TENANT_ID, PARTNER_ID, SequenceType.ISA)
    assert result == 1


@pytest.mark.asyncio
async def test_next_control_number_increments():
    """When sequence exists at N, returns N+1."""
    session = _FakeSession(existing_value=5)
    result = await next_control_number(session, TENANT_ID, PARTNER_ID, SequenceType.ISA)
    assert result == 6


@pytest.mark.asyncio
async def test_next_control_number_wraps_at_max():
    """When at max_value, wraps back to 1."""
    session = _FakeSession(existing_value=999999999)
    result = await next_control_number(session, TENANT_ID, PARTNER_ID, SequenceType.GS)
    assert result == 1


@pytest.mark.asyncio
async def test_next_control_number_st_type():
    session = _FakeSession(existing_value=100)
    result = await next_control_number(session, TENANT_ID, PARTNER_ID, SequenceType.ST)
    assert result == 101


def test_sequence_type_values():
    assert SequenceType.ISA.value == "isa"
    assert SequenceType.GS.value == "gs"
    assert SequenceType.ST.value == "st"
