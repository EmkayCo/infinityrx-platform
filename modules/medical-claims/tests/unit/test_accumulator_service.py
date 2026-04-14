"""Unit tests for accumulator integration service."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from src.services.accumulator_service import AccumulatorService
from src.models.tables import ClaimRecord


class TestAccumulatorService:
    def _make_claim(self, db, tenant_id, copay=None, coinsurance=None, deductible=None, member_id=None):
        claim = ClaimRecord(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            claim_number=f"ACC-{uuid.uuid4().hex[:6]}",
            claim_line_number=1,
            claim_type="professional",
            patient_member_id="MBR-1",
            rendering_provider_npi="1234567890",
            date_of_service=date(2026, 3, 1),
            procedure_code="J0135",
            billed_amount=Decimal("500.00"),
            patient_responsibility=Decimal("100.00"),
            copay_amount=copay,
            coinsurance_amount=coinsurance,
            deductible_amount=deductible,
            status="adjudicated",
            member_id=member_id,
        )
        db.add(claim)
        db.commit()
        db.refresh(claim)
        return claim

    def test_apply_accumulator_persists(self, db_session, tenant_id, member_id):
        from src.clients.member_management_client import MemberManagementClient
        client = MemberManagementClient()
        svc = AccumulatorService(db_session, client)

        claim = self._make_claim(
            db_session, tenant_id,
            copay=Decimal("20.00"),
            coinsurance=Decimal("30.00"),
            deductible=Decimal("50.00"),
            member_id=member_id,
        )
        updated = svc.apply_accumulator(tenant_id, claim.id)
        assert updated.applied_to_deductible is not None
        assert updated.applied_to_oop is not None
        assert isinstance(updated.applied_to_deductible, Decimal)
        assert isinstance(updated.applied_to_oop, Decimal)

    def test_deductible_applied_correctly(self, db_session, tenant_id, member_id):
        from src.clients.member_management_client import MemberManagementClient
        client = MemberManagementClient()
        svc = AccumulatorService(db_session, client)

        claim = self._make_claim(
            db_session, tenant_id,
            deductible=Decimal("100.00"),
            coinsurance=Decimal("0.00"),
            member_id=member_id,
        )
        updated = svc.apply_accumulator(tenant_id, claim.id)
        assert updated.applied_to_deductible == Decimal("100.00")

    def test_oop_includes_deductible_and_coinsurance(self, db_session, tenant_id, member_id):
        from src.clients.member_management_client import MemberManagementClient
        client = MemberManagementClient()
        svc = AccumulatorService(db_session, client)

        claim = self._make_claim(
            db_session, tenant_id,
            deductible=Decimal("75.00"),
            coinsurance=Decimal("25.00"),
            member_id=member_id,
        )
        updated = svc.apply_accumulator(tenant_id, claim.id)
        # OOP = deductible + coinsurance
        assert updated.applied_to_oop == Decimal("100.00")

    def test_unknown_claim_returns_none(self, db_session, tenant_id):
        from src.clients.member_management_client import MemberManagementClient
        svc = AccumulatorService(db_session, MemberManagementClient())
        result = svc.apply_accumulator(tenant_id, uuid.uuid4())
        assert result is None

    def test_transient_error_is_swallowed_uses_local_calc(self, db_session, tenant_id):
        """ConnectionError (transient) is caught; local calculation is used (H-14)."""
        from unittest.mock import MagicMock

        client = MagicMock()
        client.apply_claim_accumulator.side_effect = ConnectionError("connection refused")
        svc = AccumulatorService(db_session, client)

        claim = self._make_claim(
            db_session, tenant_id,
            deductible=Decimal("50.00"),
            coinsurance=Decimal("10.00"),
        )
        # Should NOT raise — transient error is swallowed and local calc is used
        updated = svc.apply_accumulator(tenant_id, claim.id)
        assert updated is not None
        assert updated.applied_to_deductible == Decimal("50.00")

    def test_non_transient_error_propagates(self, db_session, tenant_id):
        """ValueError (non-transient) propagates out of apply_accumulator (H-14 fix)."""
        from unittest.mock import MagicMock

        client = MagicMock()
        client.apply_claim_accumulator.side_effect = ValueError("bad data")
        svc = AccumulatorService(db_session, client)

        claim = self._make_claim(
            db_session, tenant_id,
            deductible=Decimal("50.00"),
        )
        with pytest.raises(ValueError, match="bad data"):
            svc.apply_accumulator(tenant_id, claim.id)
