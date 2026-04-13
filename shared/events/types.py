"""Event envelope type (PRD 4.3 message format)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _new_uuid() -> uuid.UUID:
    return uuid.uuid4()


class EventEnvelope(BaseModel):
    """Standard envelope for every event on the bus.

    Matches PRD 4.3 message format:
        {
            "event_id": "uuid",
            "event_type": "claim.adjudicated",
            "schema_version": "1.0",
            "tenant_id": "uuid",
            "correlation_id": "uuid",
            "timestamp": "2026-04-12T10:30:00Z",
            "source_module": "adjudication-engine",
            "idempotency_key": "uuid",
            "ordering_key": null,
            "payload": { ... }
        }

    Backwards-compatible: callers that don't pass the new fields get safe defaults.
    Consumers ignore unknown fields in from_wire (forward-compatible).
    """

    model_config = ConfigDict(frozen=True)

    event_type: str
    tenant_id: uuid.UUID
    correlation_id: uuid.UUID
    source_module: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=_utc_now)

    # --- Phase 2 reliability fields ---
    event_id: uuid.UUID = Field(default_factory=_new_uuid)
    schema_version: str = "1.0"
    # idempotency_key defaults to str(event_id); publishers may override for
    # business-level dedup (e.g., "payment_batch:{batch_id}").
    idempotency_key: str = Field(default="")
    # ordering_key drives per-entity queue sharding; None means unordered.
    ordering_key: str | None = None

    def model_post_init(self, __context: Any) -> None:
        """Set idempotency_key default after event_id is known."""
        if not self.idempotency_key:
            object.__setattr__(self, "idempotency_key", str(self.event_id))

    def to_wire(self) -> dict[str, Any]:
        """Serialize for transport. ISO-8601 timestamps, UUIDs stringified."""
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "schema_version": self.schema_version,
            "tenant_id": str(self.tenant_id),
            "correlation_id": str(self.correlation_id),
            "source_module": self.source_module,
            "idempotency_key": self.idempotency_key,
            "ordering_key": self.ordering_key,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_wire(cls, data: dict[str, Any]) -> EventEnvelope:
        """Deserialize from transport dict.

        Forward-compatible: unknown keys are silently ignored so new schema
        versions don't break old consumers.
        """
        kwargs: dict[str, Any] = {
            "event_type": data["event_type"],
            "tenant_id": uuid.UUID(data["tenant_id"]),
            "correlation_id": uuid.UUID(data["correlation_id"]),
            "source_module": data["source_module"],
            "payload": data.get("payload", {}),
            "timestamp": datetime.fromisoformat(data["timestamp"]),
        }
        if "event_id" in data:
            kwargs["event_id"] = uuid.UUID(data["event_id"])
        if "schema_version" in data:
            kwargs["schema_version"] = data["schema_version"]
        if "idempotency_key" in data:
            kwargs["idempotency_key"] = data["idempotency_key"]
        if "ordering_key" in data:
            kwargs["ordering_key"] = data["ordering_key"]
        return cls(**kwargs)
