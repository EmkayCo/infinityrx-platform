"""Tests for COB (Coordination of Benefits) service.

RED tests written before implementation (TDD).
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest

from src.services.cob_service import (
    CobSequence,
    CobService,
    CobServiceError,
    PayerRecord,
)

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
MEMBER_UUID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


# ---------------------------------------------------------------------------
# PayerRecord
# ---------------------------------------------------------------------------

class TestPayerRecord:
    def test_valid_payer_record(self):
        pr = PayerRecord(
            sequence=CobSequence.PRIMARY,
            other_payer_name="BlueCross",
            other_payer_bin="600428",
            other_payer_type="commercial",
            effective_date=date(2026, 1, 1),
        )
        assert pr.sequence == CobSequence.PRIMARY

    def test_secondary_sequence(self):
        pr = PayerRecord(
            sequence=CobSequence.SECONDARY,
            other_payer_name="Medicare",
            other_payer_type="medicare",
            effective_date=date(2026, 1, 1),
        )
        assert pr.sequence == CobSequence.SECONDARY


# ---------------------------------------------------------------------------
# CobSequence ordering
# ---------------------------------------------------------------------------

class TestCobSequenceOrdering:
    def test_sequence_values(self):
        assert CobSequence.PRIMARY.value == "primary"
        assert CobSequence.SECONDARY.value == "secondary"
        assert CobSequence.TERTIARY.value == "tertiary"


# ---------------------------------------------------------------------------
# CobService.sort_payers — ordering logic
# ---------------------------------------------------------------------------

class TestCobServiceSortPayers:
    def setup_method(self):
        self.svc = CobService()

    def test_primary_comes_first(self):
        payers = [
            PayerRecord(sequence=CobSequence.SECONDARY, other_payer_name="B", effective_date=date(2026, 1, 1)),
            PayerRecord(sequence=CobSequence.PRIMARY, other_payer_name="A", effective_date=date(2026, 1, 1)),
        ]
        sorted_payers = self.svc.sort_payers(payers)
        assert sorted_payers[0].sequence == CobSequence.PRIMARY
        assert sorted_payers[1].sequence == CobSequence.SECONDARY

    def test_tertiary_comes_last(self):
        payers = [
            PayerRecord(sequence=CobSequence.TERTIARY, other_payer_name="C", effective_date=date(2026, 1, 1)),
            PayerRecord(sequence=CobSequence.PRIMARY, other_payer_name="A", effective_date=date(2026, 1, 1)),
            PayerRecord(sequence=CobSequence.SECONDARY, other_payer_name="B", effective_date=date(2026, 1, 1)),
        ]
        sorted_payers = self.svc.sort_payers(payers)
        assert sorted_payers[0].sequence == CobSequence.PRIMARY
        assert sorted_payers[2].sequence == CobSequence.TERTIARY

    def test_empty_list_returns_empty(self):
        assert self.svc.sort_payers([]) == []

    def test_single_payer_returns_single(self):
        payers = [PayerRecord(sequence=CobSequence.PRIMARY, other_payer_name="A", effective_date=date(2026, 1, 1))]
        assert len(self.svc.sort_payers(payers)) == 1


# ---------------------------------------------------------------------------
# CobService.get_active_payers — filters by date
# ---------------------------------------------------------------------------

class TestCobServiceGetActivePayers:
    def setup_method(self):
        self.svc = CobService()

    def test_active_payer_included(self):
        payers = [
            PayerRecord(
                sequence=CobSequence.PRIMARY,
                other_payer_name="A",
                effective_date=date(2026, 1, 1),
                termination_date=None,
            )
        ]
        active = self.svc.get_active_payers(payers, as_of=date(2026, 4, 13))
        assert len(active) == 1

    def test_terminated_payer_excluded(self):
        payers = [
            PayerRecord(
                sequence=CobSequence.PRIMARY,
                other_payer_name="A",
                effective_date=date(2026, 1, 1),
                termination_date=date(2026, 3, 31),
            )
        ]
        active = self.svc.get_active_payers(payers, as_of=date(2026, 4, 13))
        assert len(active) == 0

    def test_payer_termination_on_same_day_is_still_active(self):
        """Termination date inclusive."""
        payers = [
            PayerRecord(
                sequence=CobSequence.PRIMARY,
                other_payer_name="A",
                effective_date=date(2026, 1, 1),
                termination_date=date(2026, 4, 13),
            )
        ]
        active = self.svc.get_active_payers(payers, as_of=date(2026, 4, 13))
        assert len(active) == 1

    def test_future_payer_excluded(self):
        payers = [
            PayerRecord(
                sequence=CobSequence.PRIMARY,
                other_payer_name="A",
                effective_date=date(2026, 5, 1),
                termination_date=None,
            )
        ]
        active = self.svc.get_active_payers(payers, as_of=date(2026, 4, 13))
        assert len(active) == 0

    def test_multiple_payers_filtered_correctly(self):
        payers = [
            PayerRecord(sequence=CobSequence.PRIMARY, other_payer_name="A",
                        effective_date=date(2026, 1, 1), termination_date=None),
            PayerRecord(sequence=CobSequence.SECONDARY, other_payer_name="B",
                        effective_date=date(2026, 1, 1), termination_date=date(2026, 2, 28)),
        ]
        active = self.svc.get_active_payers(payers, as_of=date(2026, 4, 13))
        assert len(active) == 1
        assert active[0].other_payer_name == "A"


# ---------------------------------------------------------------------------
# CobService.validate_sequence — duplicate sequence detection
# ---------------------------------------------------------------------------

class TestCobServiceValidateSequence:
    def setup_method(self):
        self.svc = CobService()

    def test_no_duplicates_passes(self):
        payers = [
            PayerRecord(sequence=CobSequence.PRIMARY, other_payer_name="A", effective_date=date(2026, 1, 1)),
            PayerRecord(sequence=CobSequence.SECONDARY, other_payer_name="B", effective_date=date(2026, 1, 1)),
        ]
        self.svc.validate_sequence(payers)  # should not raise

    def test_duplicate_primary_raises(self):
        payers = [
            PayerRecord(sequence=CobSequence.PRIMARY, other_payer_name="A", effective_date=date(2026, 1, 1)),
            PayerRecord(sequence=CobSequence.PRIMARY, other_payer_name="B", effective_date=date(2026, 1, 1)),
        ]
        with pytest.raises(CobServiceError, match="duplicate"):
            self.svc.validate_sequence(payers)

    def test_empty_list_passes(self):
        self.svc.validate_sequence([])  # should not raise
