"""Tests for rebate contract lifecycle service."""

from __future__ import annotations

import uuid
from datetime import date, datetime, UTC
from decimal import Decimal

import pytest

from src.services.contracts import ContractService, ContractLifecycleError


class FakeDB:
    def __init__(self):
        self._store = []

    def add(self, obj):
        self._store.append(obj)

    def flush(self):
        pass

    def query(self, model):
        return FakeContractQuery(self._store, model)


class FakeContractQuery:
    def __init__(self, store, model):
        self._store = store
        self._model = model
        self._filters = {}

    def filter(self, *args):
        return self

    def first(self):
        return self._store[-1] if self._store else None

    def all(self):
        return list(self._store)


class TestContractLifecycle:
    def test_create_contract_defaults_to_draft(self):
        db = FakeDB()
        svc = ContractService(db)
        contract = svc.create_contract(
            tenant_id=uuid.uuid4(),
            manufacturer_id=uuid.uuid4(),
            manufacturer_name="Acme Pharma",
            contract_number="RC-2026-001",
            contract_type="formulary_access",
            effective_date=date(2026, 1, 1),
        )
        assert contract.status == "draft"
        assert contract.version == 1

    def test_valid_transitions(self):
        db = FakeDB()
        svc = ContractService(db)
        tid = uuid.uuid4()
        contract = svc.create_contract(
            tenant_id=tid,
            manufacturer_id=uuid.uuid4(),
            manufacturer_name="Test",
            contract_number="RC-001",
            contract_type="volume",
            effective_date=date(2026, 1, 1),
        )
        # draft → negotiated
        contract = svc.transition_status(tid, contract.id, "negotiated")
        assert contract.status == "negotiated"
        # negotiated → executed
        approver = uuid.uuid4()
        contract = svc.transition_status(tid, contract.id, "executed", approved_by=approver)
        assert contract.status == "executed"
        assert contract.approved_by == approver
        # executed → active
        contract = svc.transition_status(tid, contract.id, "active")
        assert contract.status == "active"

    def test_invalid_transition_raises(self):
        db = FakeDB()
        svc = ContractService(db)
        tid = uuid.uuid4()
        contract = svc.create_contract(
            tenant_id=tid,
            manufacturer_id=uuid.uuid4(),
            manufacturer_name="Test",
            contract_number="RC-002",
            contract_type="admin_fee",
            effective_date=date(2026, 1, 1),
        )
        # draft → active is not valid (must go through negotiated → executed first)
        with pytest.raises(ContractLifecycleError, match="Cannot transition"):
            svc.transition_status(tid, contract.id, "active")

    def test_terminated_is_final(self):
        db = FakeDB()
        svc = ContractService(db)
        tid = uuid.uuid4()
        contract = svc.create_contract(
            tenant_id=tid,
            manufacturer_id=uuid.uuid4(),
            manufacturer_name="Test",
            contract_number="RC-003",
            contract_type="volume",
            effective_date=date(2026, 1, 1),
        )
        svc.transition_status(tid, contract.id, "terminated")
        with pytest.raises(ContractLifecycleError, match="Cannot transition"):
            svc.transition_status(tid, contract.id, "draft")

    def test_amend_increments_version(self):
        db = FakeDB()
        svc = ContractService(db)
        tid = uuid.uuid4()
        contract = svc.create_contract(
            tenant_id=tid,
            manufacturer_id=uuid.uuid4(),
            manufacturer_name="Test",
            contract_number="RC-004",
            contract_type="formulary_access",
            effective_date=date(2026, 1, 1),
        )
        # Move to active
        svc.transition_status(tid, contract.id, "negotiated")
        svc.transition_status(tid, contract.id, "executed")
        svc.transition_status(tid, contract.id, "active")
        # Amend
        amended = svc.amend_contract(tid, contract.id, {"payment_frequency": "monthly"})
        assert amended.version == 2
        assert amended.status == "amended"
        assert amended.payment_frequency == "monthly"

    def test_cannot_amend_non_active(self):
        db = FakeDB()
        svc = ContractService(db)
        tid = uuid.uuid4()
        contract = svc.create_contract(
            tenant_id=tid,
            manufacturer_id=uuid.uuid4(),
            manufacturer_name="Test",
            contract_number="RC-005",
            contract_type="volume",
            effective_date=date(2026, 1, 1),
        )
        with pytest.raises(ContractLifecycleError, match="Only active"):
            svc.amend_contract(tid, contract.id, {"notes": "changed"})


class TestNDCTerms:
    def test_add_ndc_term(self):
        db = FakeDB()
        svc = ContractService(db)
        tid = uuid.uuid4()
        cid = uuid.uuid4()
        term = svc.add_ndc_term(
            tenant_id=tid,
            contract_id=cid,
            ndc11="12345678901",
            rebate_type="percent_wac",
            effective_date=date(2026, 1, 1),
            rebate_percent=Decimal("12.5000"),
        )
        assert term.ndc11 == "12345678901"
        assert term.rebate_type == "percent_wac"
        assert term.rebate_percent == Decimal("12.5000")

    def test_add_tier(self):
        db = FakeDB()
        svc = ContractService(db)
        tier = svc.add_tier(
            tenant_id=uuid.uuid4(),
            contract_id=uuid.uuid4(),
            tier_name="Gold",
            tier_type="volume",
            threshold_value=Decimal("1000"),
            rebate_percent=Decimal("5.0000"),
        )
        assert tier.tier_name == "Gold"
        assert tier.rebate_percent == Decimal("5.0000")
