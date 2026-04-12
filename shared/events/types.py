"""Event envelope type (PRD 4.2 message format)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _utc_now() -> datetime:
    return datetime.now(UTC)


class EventEnvelope(BaseModel):
    """Standard envelope for every event on the bus.

    Matches PRD 4.2:
        {
            "event_type": "claim.adjudicated",
            "tenant_id": "uuid",
            "correlation_id": "uuid",
            "timestamp": "2026-04-12T10:30:00Z",
            "source_module": "adjudication-engine",
            "payload": { ... }
        }
    """

    model_config = ConfigDict(frozen=True)

    event_type: str
    tenant_id: uuid.UUID
    correlation_id: uuid.UUID
    source_module: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=_utc_now)

    def to_wire(self) -> dict[str, Any]:
        """Serialize for transport. ISO-8601 timestamps, UUIDs stringified."""
        return {
            "event_type": self.event_type,
            "tenant_id": str(self.tenant_id),
            "correlation_id": str(self.correlation_id),
            "source_module": self.source_module,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_wire(cls, data: dict[str, Any]) -> EventEnvelope:
        return cls(
            event_type=data["event_type"],
            tenant_id=uuid.UUID(data["tenant_id"]),
            correlation_id=uuid.UUID(data["correlation_id"]),
            source_module=data["source_module"],
            payload=data.get("payload", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )
