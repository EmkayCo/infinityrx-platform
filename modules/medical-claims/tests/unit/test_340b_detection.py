"""Unit tests for 340B detection — security path, 100% coverage."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal


from src.services.detection_340b_service import Detection340bService
from src.clients.pharmacy_directory_client import PharmacyDirectoryClient
from src.models.tables import ClaimRecord


def _make_claim(db, tenant_id, npi_billing, ndc=None, modifiers=None):
    m = modifiers or {}
    claim = ClaimRecord(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        claim_number=f"340B-{uuid.uuid4().hex[:6]}",
        claim_line_number=1,
        claim_type="professional",
        patient_member_id="MBR-1",
        rendering_provider_npi="1234567890",
        billing_provider_npi=npi_billing,
        date_of_service=date(2026, 2, 1),
        procedure_code="J0135",
        billed_amount=Decimal("500.00"),
        status="received",
        ndc=ndc,
        modifier_1=m.get("m1"),
        modifier_2=m.get("m2"),
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim


class TestDetection340b:
    def test_billing_npi_in_list_and_ndc_present_flagged(self, db_session, tenant_id):
        client = PharmacyDirectoryClient()
        client.register_stub_entity("3401234567", True)
        svc = Detection340bService(db_session, client)

        claim = _make_claim(db_session, tenant_id, "3401234567", ndc="12345678901")
        is_340b, entity_id = svc.evaluate_claim(claim)
        assert is_340b is True
        assert entity_id is not None

    def test_billing_npi_not_in_list_not_flagged(self, db_session, tenant_id):
        client = PharmacyDirectoryClient()  # empty list
        svc = Detection340bService(db_session, client)

        claim = _make_claim(db_session, tenant_id, "9999999999", ndc="12345678901")
        is_340b, entity_id = svc.evaluate_claim(claim)
        assert is_340b is False

    def test_340b_entity_but_no_ndc_not_flagged(self, db_session, tenant_id):
        """Conservative: must have both entity in list AND NDC."""
        client = PharmacyDirectoryClient()
        client.register_stub_entity("3401234568", True)
        svc = Detection340bService(db_session, client)

        claim = _make_claim(db_session, tenant_id, "3401234568", ndc=None)
        is_340b, entity_id = svc.evaluate_claim(claim)
        assert is_340b is False

    def test_no_billing_npi_not_flagged(self, db_session, tenant_id):
        client = PharmacyDirectoryClient()
        svc = Detection340bService(db_session, client)

        claim = ClaimRecord(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            claim_number="340B-NOBILE",
            claim_line_number=1,
            claim_type="professional",
            patient_member_id="MBR-1",
            rendering_provider_npi="1234567890",
            billing_provider_npi=None,  # No billing NPI
            date_of_service=date(2026, 2, 1),
            procedure_code="J0135",
            billed_amount=Decimal("500.00"),
            status="received",
            ndc="12345678901",
        )
        db_session.add(claim)
        db_session.commit()

        is_340b, entity_id = svc.evaluate_claim(claim)
        assert is_340b is False

    def test_jg_modifier_alone_not_sufficient(self, db_session, tenant_id):
        """JG modifier is a signal, not a determinant. If NPI not in list → not flagged."""
        client = PharmacyDirectoryClient()  # empty
        svc = Detection340bService(db_session, client)

        claim = _make_claim(
            db_session, tenant_id, "5556667777", ndc="12345678901",
            modifiers={"m1": "JG"}
        )
        is_340b, entity_id = svc.evaluate_claim(claim)
        assert is_340b is False

    def test_apply_340b_persists_result(self, db_session, tenant_id):
        client = PharmacyDirectoryClient()
        client.register_stub_entity("3401234569", True)
        svc = Detection340bService(db_session, client)

        claim = _make_claim(db_session, tenant_id, "3401234569", ndc="12345678901")
        updated = svc.apply_340b_detection(tenant_id, claim.id)
        assert updated.is_340b is True
        assert updated.entity_340b_id is not None

    def test_apply_340b_not_in_list_stores_false(self, db_session, tenant_id):
        client = PharmacyDirectoryClient()
        svc = Detection340bService(db_session, client)

        claim = _make_claim(db_session, tenant_id, "9998887776", ndc="12345678901")
        updated = svc.apply_340b_detection(tenant_id, claim.id)
        assert updated.is_340b is False

    def test_apply_340b_unknown_claim_returns_none(self, db_session, tenant_id):
        client = PharmacyDirectoryClient()
        svc = Detection340bService(db_session, client)

        result = svc.apply_340b_detection(tenant_id, uuid.uuid4())
        assert result is None
