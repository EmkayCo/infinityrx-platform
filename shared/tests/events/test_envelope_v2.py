"""Tests for extended EventEnvelope fields (event_id, schema_version, idempotency_key, ordering_key)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from shared.events.types import EventEnvelope


def _base_kwargs() -> dict:
    return dict(
        event_type="claim.submitted",
        tenant_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        source_module="test-module",
    )


# ---------------------------------------------------------------------------
# Default field values
# ---------------------------------------------------------------------------


def test_event_id_auto_generated_as_uuid():
    env = EventEnvelope(**_base_kwargs())
    assert isinstance(env.event_id, uuid.UUID)


def test_event_id_is_unique_per_instance():
    env1 = EventEnvelope(**_base_kwargs())
    env2 = EventEnvelope(**_base_kwargs())
    assert env1.event_id != env2.event_id


def test_schema_version_defaults_to_1_0():
    env = EventEnvelope(**_base_kwargs())
    assert env.schema_version == "1.0"


def test_idempotency_key_defaults_to_str_event_id():
    env = EventEnvelope(**_base_kwargs())
    assert env.idempotency_key == str(env.event_id)


def test_ordering_key_defaults_to_none():
    env = EventEnvelope(**_base_kwargs())
    assert env.ordering_key is None


# ---------------------------------------------------------------------------
# Explicit overrides
# ---------------------------------------------------------------------------


def test_explicit_event_id_accepted():
    eid = uuid.uuid4()
    env = EventEnvelope(**_base_kwargs(), event_id=eid)
    assert env.event_id == eid


def test_explicit_schema_version_accepted():
    env = EventEnvelope(**_base_kwargs(), schema_version="2.0")
    assert env.schema_version == "2.0"


def test_explicit_idempotency_key_overrides_default():
    env = EventEnvelope(**_base_kwargs(), idempotency_key="payment_batch:abc-123")
    assert env.idempotency_key == "payment_batch:abc-123"


def test_explicit_ordering_key_accepted():
    env = EventEnvelope(**_base_kwargs(), ordering_key="batch-456")
    assert env.ordering_key == "batch-456"


# ---------------------------------------------------------------------------
# Wire serialization round-trips
# ---------------------------------------------------------------------------


def test_new_fields_included_in_to_wire():
    env = EventEnvelope(**_base_kwargs(), ordering_key="batch-1")
    wire = env.to_wire()
    assert "event_id" in wire
    assert "schema_version" in wire
    assert "idempotency_key" in wire
    assert "ordering_key" in wire
    assert wire["schema_version"] == "1.0"
    assert wire["ordering_key"] == "batch-1"
    assert wire["event_id"] == str(env.event_id)
    assert wire["idempotency_key"] == str(env.event_id)


def test_from_wire_round_trip_preserves_new_fields():
    env = EventEnvelope(
        **_base_kwargs(),
        idempotency_key="custom-key",
        ordering_key="entity-99",
        schema_version="1.1",
    )
    restored = EventEnvelope.from_wire(env.to_wire())
    assert restored.event_id == env.event_id
    assert restored.schema_version == "1.1"
    assert restored.idempotency_key == "custom-key"
    assert restored.ordering_key == "entity-99"
    assert restored == env


def test_ordering_key_none_serialises_as_none():
    env = EventEnvelope(**_base_kwargs())
    wire = env.to_wire()
    assert wire["ordering_key"] is None
    restored = EventEnvelope.from_wire(wire)
    assert restored.ordering_key is None


# ---------------------------------------------------------------------------
# Backwards compatibility: callers without new fields still work
# ---------------------------------------------------------------------------


def test_legacy_caller_without_new_fields_still_constructs():
    """Existing callers that don't pass event_id, schema_version, etc. still work."""
    env = EventEnvelope(
        event_type="claim.adjudicated",
        tenant_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        source_module="legacy-module",
        payload={"claim_id": "xyz"},
        timestamp=datetime(2026, 4, 12, 10, 30, tzinfo=UTC),
    )
    assert env.schema_version == "1.0"
    assert env.ordering_key is None
    assert env.idempotency_key == str(env.event_id)


def test_from_wire_ignores_unknown_fields():
    """Forward-compatible parse: consumer on old schema ignores new fields from producer."""
    env = EventEnvelope(**_base_kwargs())
    wire = env.to_wire()
    wire["future_field"] = "some_value"  # new field from future schema version
    # Should not raise
    restored = EventEnvelope.from_wire(wire)
    assert restored.event_type == env.event_type


def test_from_wire_old_message_without_new_fields():
    """Old messages without event_id/schema_version parsed by new consumer still work."""
    old_wire = {
        "event_type": "claim.submitted",
        "tenant_id": str(uuid.uuid4()),
        "correlation_id": str(uuid.uuid4()),
        "source_module": "old-module",
        "payload": {},
        "timestamp": "2026-04-12T10:30:00+00:00",
    }
    env = EventEnvelope.from_wire(old_wire)
    assert env.schema_version == "1.0"
    assert env.ordering_key is None
    assert isinstance(env.event_id, uuid.UUID)


# ---------------------------------------------------------------------------
# Immutability check still passes with new fields
# ---------------------------------------------------------------------------


def test_envelope_with_new_fields_is_immutable():
    env = EventEnvelope(**_base_kwargs())
    with pytest.raises(ValidationError):
        env.schema_version = "9.9"  # type: ignore[misc]
