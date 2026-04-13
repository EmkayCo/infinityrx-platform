"""Financial journal service — append-only, tenant-scoped.

Every financial event writes a journal entry. Entries are never modified
or deleted. Export tracking is the only mutation allowed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from src.utils.money import money


@dataclass
class JournalEntryData:
    id: uuid.UUID
    tenant_id: uuid.UUID
    entry_date: date
    entry_timestamp: datetime
    entry_type: str
    amount: Decimal
    category: str
    description: str
    client_id: uuid.UUID | None = None
    client_name: str | None = None
    program_id: uuid.UUID | None = None
    program_name: str | None = None
    pay_to_entity_id: uuid.UUID | None = None
    pay_to_entity_name: str | None = None
    gl_account_code: str | None = None
    gl_class: str | None = None
    reference_type: str | None = None
    reference_id: uuid.UUID | None = None
    exported_to_accounting: bool = False
    exported_at: datetime | None = None
    export_reference: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class JournalService:
    def __init__(self, db: Any, events: Any) -> None:
        self._db = db
        self._events = events

    def create_entry(
        self,
        tenant_id: uuid.UUID,
        entry_type: str,
        amount: Decimal,
        category: str,
        description: str,
        entry_date: date,
        client_id: uuid.UUID | None = None,
        client_name: str | None = None,
        program_id: uuid.UUID | None = None,
        program_name: str | None = None,
        pay_to_entity_id: uuid.UUID | None = None,
        pay_to_entity_name: str | None = None,
        gl_account_code: str | None = None,
        gl_class: str | None = None,
        reference_type: str | None = None,
        reference_id: uuid.UUID | None = None,
    ) -> JournalEntryData:
        if not description:
            raise ValueError("Journal entry description is required")
        now = datetime.now(UTC)
        return JournalEntryData(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            entry_date=entry_date,
            entry_timestamp=now,
            entry_type=entry_type,
            amount=money(amount),
            category=category,
            description=description,
            client_id=client_id,
            client_name=client_name,
            program_id=program_id,
            program_name=program_name,
            pay_to_entity_id=pay_to_entity_id,
            pay_to_entity_name=pay_to_entity_name,
            gl_account_code=gl_account_code,
            gl_class=gl_class,
            reference_type=reference_type,
            reference_id=reference_id,
            created_at=now,
        )

    def create_offsetting_entry(
        self,
        original: JournalEntryData,
        entry_type: str,
        description: str,
    ) -> JournalEntryData:
        """Create an entry that offsets (negates) an original entry."""
        now = datetime.now(UTC)
        return JournalEntryData(
            id=uuid.uuid4(),
            tenant_id=original.tenant_id,
            entry_date=original.entry_date,
            entry_timestamp=now,
            entry_type=entry_type,
            amount=money(-original.amount),
            category=original.category,
            description=description,
            client_id=original.client_id,
            client_name=original.client_name,
            program_id=original.program_id,
            program_name=original.program_name,
            pay_to_entity_id=original.pay_to_entity_id,
            pay_to_entity_name=original.pay_to_entity_name,
            reference_type=original.reference_type,
            reference_id=original.reference_id,
            created_at=now,
        )

    def query_entries(
        self,
        entries: list[JournalEntryData],
        tenant_id: uuid.UUID,
        date_from: date | None = None,
        date_to: date | None = None,
        client_id: uuid.UUID | None = None,
        program_id: uuid.UUID | None = None,
        category: str | None = None,
        entry_type: str | None = None,
        unexported_only: bool = False,
    ) -> list[JournalEntryData]:
        """Filter in-memory journal entries (used in unit tests; DB layer for production)."""
        result = [e for e in entries if e.tenant_id == tenant_id]
        if date_from is not None:
            result = [e for e in result if e.entry_date >= date_from]
        if date_to is not None:
            result = [e for e in result if e.entry_date <= date_to]
        if client_id is not None:
            result = [e for e in result if e.client_id == client_id]
        if program_id is not None:
            result = [e for e in result if e.program_id == program_id]
        if category is not None:
            result = [e for e in result if e.category == category]
        if entry_type is not None:
            result = [e for e in result if e.entry_type == entry_type]
        if unexported_only:
            result = [e for e in result if not e.exported_to_accounting]
        return result

    def mark_exported(self, entries: list[JournalEntryData], export_reference: str) -> None:
        now = datetime.now(UTC)
        for entry in entries:
            entry.exported_to_accounting = True
            entry.exported_at = now
            entry.export_reference = export_reference
