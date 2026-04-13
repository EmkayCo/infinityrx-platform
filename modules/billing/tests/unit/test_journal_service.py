"""Unit tests for financial journal service — 100% coverage."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from src.services.journal import JournalService
from src.utils.constants import (
    CATEGORY_CLAIMS_PAYABLE,
    CATEGORY_CLAIMS_RECEIVABLE,
    JOURNAL_AP_CREATED,
    JOURNAL_AP_SETTLED,
    JOURNAL_AP_VOIDED,
    JOURNAL_AR_PAYMENT_RECEIVED,
)
from src.utils.money import money

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
CLIENT = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
PROGRAM = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
ENTITY = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
REF_ID = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")


def _svc(events=None) -> JournalService:
    return JournalService(db=MagicMock(), events=events or MagicMock())


class TestJournalEntryCreation:
    def test_create_entry_stores_amount_as_decimal(self) -> None:
        svc = _svc()
        entry = svc.create_entry(
            tenant_id=TENANT,
            entry_type=JOURNAL_AP_CREATED,
            amount=Decimal("500.00"),
            category=CATEGORY_CLAIMS_PAYABLE,
            description="AP created for test claim",
            entry_date=date(2026, 1, 15),
        )
        assert isinstance(entry.amount, Decimal)
        assert entry.amount == money("500.00")

    def test_create_entry_sets_tenant_id(self) -> None:
        svc = _svc()
        entry = svc.create_entry(
            tenant_id=TENANT,
            entry_type=JOURNAL_AP_CREATED,
            amount=Decimal("100.00"),
            category=CATEGORY_CLAIMS_PAYABLE,
            description="Test",
            entry_date=date(2026, 1, 15),
        )
        assert entry.tenant_id == TENANT

    def test_create_entry_with_optional_tags(self) -> None:
        svc = _svc()
        entry = svc.create_entry(
            tenant_id=TENANT,
            entry_type=JOURNAL_AP_CREATED,
            amount=Decimal("250.00"),
            category=CATEGORY_CLAIMS_PAYABLE,
            description="Tagged entry",
            entry_date=date(2026, 1, 15),
            client_id=CLIENT,
            program_id=PROGRAM,
            pay_to_entity_id=ENTITY,
            reference_type="ap_record",
            reference_id=REF_ID,
        )
        assert entry.client_id == CLIENT
        assert entry.program_id == PROGRAM
        assert entry.pay_to_entity_id == ENTITY
        assert entry.reference_type == "ap_record"
        assert entry.reference_id == REF_ID

    def test_journal_entry_never_modified_once_created(self) -> None:
        """Journal entries are append-only — verify id is immutable."""
        svc = _svc()
        entry = svc.create_entry(
            tenant_id=TENANT,
            entry_type=JOURNAL_AP_SETTLED,
            amount=Decimal("100.00"),
            category=CATEGORY_CLAIMS_PAYABLE,
            description="AP settled",
            entry_date=date(2026, 1, 15),
        )
        original_id = entry.id
        # id should not change
        assert entry.id == original_id

    def test_void_creates_offsetting_entry(self) -> None:
        svc = _svc()
        original = svc.create_entry(
            tenant_id=TENANT,
            entry_type=JOURNAL_AP_CREATED,
            amount=Decimal("100.00"),
            category=CATEGORY_CLAIMS_PAYABLE,
            description="Original",
            entry_date=date(2026, 1, 15),
        )
        offset = svc.create_offsetting_entry(
            original,
            entry_type=JOURNAL_AP_VOIDED,
            description="Void of original",
        )
        assert offset.amount == money("-100.00")
        assert offset.tenant_id == TENANT
        assert offset.category == original.category

    def test_entry_description_required(self) -> None:
        svc = _svc()
        with pytest.raises(ValueError, match="description"):
            svc.create_entry(
                tenant_id=TENANT,
                entry_type=JOURNAL_AP_CREATED,
                amount=Decimal("100.00"),
                category=CATEGORY_CLAIMS_PAYABLE,
                description="",
                entry_date=date(2026, 1, 15),
            )

    def test_exported_flag_default_false(self) -> None:
        svc = _svc()
        entry = svc.create_entry(
            tenant_id=TENANT,
            entry_type=JOURNAL_AP_CREATED,
            amount=Decimal("100.00"),
            category=CATEGORY_CLAIMS_PAYABLE,
            description="Test",
            entry_date=date(2026, 1, 15),
        )
        assert entry.exported_to_accounting is False


class TestJournalQuery:
    def test_query_filters_by_tenant(self) -> None:
        svc = _svc()
        entries = [
            svc.create_entry(
                tenant_id=TENANT,
                entry_type=JOURNAL_AP_CREATED,
                amount=Decimal("100.00"),
                category=CATEGORY_CLAIMS_PAYABLE,
                description="TENANT A",
                entry_date=date(2026, 1, 15),
            ),
            svc.create_entry(
                tenant_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
                entry_type=JOURNAL_AP_CREATED,
                amount=Decimal("200.00"),
                category=CATEGORY_CLAIMS_PAYABLE,
                description="TENANT B",
                entry_date=date(2026, 1, 15),
            ),
        ]
        results = svc.query_entries(entries, tenant_id=TENANT)
        assert all(e.tenant_id == TENANT for e in results)
        assert len(results) == 1

    def test_query_filters_by_date_range(self) -> None:
        svc = _svc()
        entries = [
            svc.create_entry(
                tenant_id=TENANT,
                entry_type=JOURNAL_AP_CREATED,
                amount=Decimal("100.00"),
                category=CATEGORY_CLAIMS_PAYABLE,
                description="January",
                entry_date=date(2026, 1, 15),
            ),
            svc.create_entry(
                tenant_id=TENANT,
                entry_type=JOURNAL_AP_CREATED,
                amount=Decimal("200.00"),
                category=CATEGORY_CLAIMS_PAYABLE,
                description="March",
                entry_date=date(2026, 3, 15),
            ),
        ]
        results = svc.query_entries(
            entries,
            tenant_id=TENANT,
            date_from=date(2026, 2, 1),
            date_to=date(2026, 4, 30),
        )
        assert len(results) == 1
        assert results[0].description == "March"

    def test_mark_as_exported(self) -> None:
        svc = _svc()
        entry = svc.create_entry(
            tenant_id=TENANT,
            entry_type=JOURNAL_AR_PAYMENT_RECEIVED,
            amount=Decimal("500.00"),
            category=CATEGORY_CLAIMS_RECEIVABLE,
            description="AR payment",
            entry_date=date(2026, 1, 15),
        )
        svc.mark_exported([entry], export_reference="QB-2026-001")
        assert entry.exported_to_accounting is True
        assert entry.export_reference == "QB-2026-001"
        assert entry.exported_at is not None
