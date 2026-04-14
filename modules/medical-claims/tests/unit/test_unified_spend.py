"""Unit tests for unified drug spend — critical financial path, 100% coverage."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from src.services.unified_spend_service import UnifiedDrugSpendService
from src.models.tables import ClaimRecord, UnifiedDrugSpend


def _make_claim(db, tenant_id, claim_num, ndc=None, member_id=None, payer_seq=None, paid=None):
    claim = ClaimRecord(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        claim_number=claim_num,
        claim_line_number=1,
        claim_type="professional",
        patient_member_id="MBR-1",
        rendering_provider_npi="1234567890",
        date_of_service=date(2026, 3, 1),
        procedure_code="J0135",
        billed_amount=Decimal("200.00"),
        paid_amount=paid,
        status="adjudicated",
        ndc=ndc,
        member_id=member_id,
        payer_sequence=payer_seq,
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim


class TestRecordMedicalClaim:
    def test_record_creates_unified_spend(self, db_session, tenant_id, member_id):
        svc = UnifiedDrugSpendService(db_session)
        claim = _make_claim(db_session, tenant_id, "UNI-001", ndc="12345678901", member_id=member_id)
        record = svc.record_medical_claim(claim)
        assert record.benefit_type == "medical"
        assert record.medical_claim_id == claim.id
        assert record.tenant_id == tenant_id

    def test_record_pharmacy_claim(self, db_session, tenant_id, member_id):
        svc = UnifiedDrugSpendService(db_session)
        pharm_id = uuid.uuid4()
        record = svc.record_pharmacy_claim(
            tenant_id=tenant_id,
            pharmacy_claim_id=pharm_id,
            member_id=member_id,
            member_id_display="MBR-1",
            ndc="12345678901",
            drug_name="Adalimumab",
            dos=date(2026, 3, 1),
            billed_amount=Decimal("500.00"),
            allowed_amount=Decimal("450.00"),
            paid_amount=Decimal("400.00"),
            patient_pay=Decimal("50.00"),
            quantity=Decimal("1.000"),
            days_supply=30,
        )
        assert record.benefit_type == "pharmacy"
        assert record.pharmacy_claim_id == pharm_id
        assert record.paid_amount == Decimal("400.00")

    def test_no_double_count_cob(self, db_session, tenant_id, member_id):
        """COB scenario: primary + secondary medical claim for same member/drug/date.
        They must produce 2 rows with DIFFERENT payer sequences, not count as duplication.
        """
        svc = UnifiedDrugSpendService(db_session)
        ndc = "55555555555"

        # Primary medical claim
        primary = _make_claim(
            db_session, tenant_id, "COB-MED-P", ndc=ndc, member_id=member_id,
            payer_seq="primary", paid=Decimal("400.00")
        )
        # Secondary medical claim (COB)
        secondary = _make_claim(
            db_session, tenant_id, "COB-MED-S", ndc=ndc, member_id=member_id,
            payer_seq="secondary", paid=Decimal("50.00")
        )

        r1 = svc.record_medical_claim(primary)
        r2 = svc.record_medical_claim(secondary)

        # Two rows in unified spend (both are legitimate COB records)
        assert r1.id != r2.id
        assert r1.benefit_type == "medical"
        assert r2.benefit_type == "medical"

    def test_cob_not_flagged_as_duplication(self, db_session, tenant_id, member_id):
        """Pharmacy + COB medical claim for same member/ndc/date must NOT flag as duplication."""
        svc = UnifiedDrugSpendService(db_session)
        ndc = "66666666666"

        # Pharmacy claim
        pharm_id = uuid.uuid4()
        svc.record_pharmacy_claim(
            tenant_id=tenant_id,
            pharmacy_claim_id=pharm_id,
            member_id=member_id,
            member_id_display="MBR-1",
            ndc=ndc,
            drug_name="Drug X",
            dos=date(2026, 3, 5),
            billed_amount=Decimal("300.00"),
            allowed_amount=Decimal("280.00"),
            paid_amount=Decimal("250.00"),
            patient_pay=Decimal("30.00"),
            quantity=None,
            days_supply=None,
        )

        # Medical COB claim (secondary payer)
        cob_claim = _make_claim(
            db_session, tenant_id, "COB-DUP-TEST", ndc=ndc, member_id=member_id,
            payer_seq="secondary",
        )
        cob_claim.date_of_service = date(2026, 3, 5)
        db_session.commit()
        svc.record_medical_claim(cob_claim)

        duplications = svc.detect_therapeutic_duplications(tenant_id)
        dup_ndcs = {d["ndc"] for d in duplications}
        assert ndc not in dup_ndcs

    def test_true_duplication_detected(self, db_session, tenant_id, member_id):
        """Same drug on pharmacy and medical (no COB) → duplication flagged."""
        svc = UnifiedDrugSpendService(db_session)
        ndc = "77777777777"

        pharm_id = uuid.uuid4()
        svc.record_pharmacy_claim(
            tenant_id=tenant_id,
            pharmacy_claim_id=pharm_id,
            member_id=member_id,
            member_id_display="MBR-1",
            ndc=ndc,
            drug_name="Drug Y",
            dos=date(2026, 4, 1),
            billed_amount=Decimal("200.00"),
            allowed_amount=None,
            paid_amount=None,
            patient_pay=None,
            quantity=None,
            days_supply=None,
        )

        # Medical claim with NO payer_sequence (not COB)
        med_claim = _make_claim(
            db_session, tenant_id, "DUP-MED-001", ndc=ndc, member_id=member_id,
            payer_seq=None,
        )
        med_claim.date_of_service = date(2026, 4, 1)
        db_session.commit()
        svc.record_medical_claim(med_claim)

        duplications = svc.detect_therapeutic_duplications(tenant_id)
        dup_ndcs = {d["ndc"] for d in duplications}
        assert ndc in dup_ndcs


class TestUnifiedSpendAmounts:
    def test_all_amounts_are_decimal(self, db_session, tenant_id, member_id):
        svc = UnifiedDrugSpendService(db_session)
        pharm_id = uuid.uuid4()
        record = svc.record_pharmacy_claim(
            tenant_id=tenant_id,
            pharmacy_claim_id=pharm_id,
            member_id=member_id,
            member_id_display="MBR-1",
            ndc="99999999999",
            drug_name="Test",
            dos=date(2026, 1, 1),
            billed_amount=Decimal("100.555"),
            allowed_amount=Decimal("90.001"),
            paid_amount=Decimal("85.005"),
            patient_pay=Decimal("5.005"),
            quantity=Decimal("1.000"),
            days_supply=30,
        )
        # All should be Decimal
        for attr in ("billed_amount", "allowed_amount", "paid_amount", "patient_pay"):
            val = getattr(record, attr)
            assert isinstance(val, Decimal), f"{attr} should be Decimal"
        # Should be rounded to 2dp
        assert record.billed_amount == Decimal("100.56")  # ROUND_HALF_UP
