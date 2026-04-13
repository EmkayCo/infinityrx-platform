"""DLQ sink abstractions.

A DLQSink receives dead-letter entries and persists them.  The Protocol
allows the RabbitMQ bus to be tested without a real database.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from shared.db.models.events import EventDLQEntry


@runtime_checkable
class DLQSink(Protocol):
    """Protocol for DLQ persistence backends."""

    async def write(self, entry: "EventDLQEntry") -> None:
        """Persist a dead-letter entry."""
        ...


class InMemoryDLQSink:
    """In-process DLQ sink for tests.

    Stores entries in memory.  Call ``reset()`` between test cases.
    """

    def __init__(self) -> None:
        self._entries: list[EventDLQEntry] = []

    @property
    def entries(self) -> list[EventDLQEntry]:
        return list(self._entries)

    async def write(self, entry: EventDLQEntry) -> None:
        self._entries.append(entry)

    def reset(self) -> None:
        self._entries.clear()


class PostgresDLQSink:
    """Persists dead-letter entries to the ``core.event_dlq`` table.

    Requires an async SQLAlchemy session factory.
    """

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    async def write(self, entry: EventDLQEntry) -> None:
        async with self._session_factory() as session:
            session.add(entry)
            await session.commit()
