"""EventEnvelope serialization round-trips and invariants."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from shared.events import EventEnvelope, event_types


def _envelope(**overrides):
    base = dict(
        event_type=event_types.CLAIM_SUBMITTED,
        tenant_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        source_module="adjudication-engine",
        payload={"claim_id": "abc", "amount": "12.34"},
        timestamp=datetime(2026, 4, 12, 10, 30, tzinfo=UTC),
    )
    base.update(overrides)
    return EventEnvelope(**base)


def test_round_trip_through_wire_preserves_fields():
    env = _envelope()
    wire = env.to_wire()
    restored = EventEnvelope.from_wire(wire)
    assert restored == env


def test_envelope_is_immutable():
    env = _envelope()
    with pytest.raises(ValidationError):
        env.event_type = "claim.adjudicated"  # type: ignore[misc]


def test_wire_contains_iso_timestamp_and_str_uuids():
    env = _envelope()
    wire = env.to_wire()
    assert wire["timestamp"].startswith("2026-04-12T10:30:00")
    assert isinstance(wire["tenant_id"], str)
    assert isinstance(wire["correlation_id"], str)


def test_default_timestamp_is_timezone_aware():
    env = EventEnvelope(
        event_type=event_types.JOB_COMPLETED,
        tenant_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        source_module="core-platform",
    )
    assert env.timestamp.tzinfo is not None


def test_event_type_constants_are_unique_and_namespaced():
    assert len(set(event_types.ALL_EVENT_TYPES)) == len(event_types.ALL_EVENT_TYPES)
    for t in event_types.ALL_EVENT_TYPES:
        assert "." in t, f"event type {t!r} must be module.name"
