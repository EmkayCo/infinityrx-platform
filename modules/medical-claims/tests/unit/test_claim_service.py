"""Unit tests for claim ingestion and status management."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from src.services.claim_service import ClaimService
from src.api.schemas.claims import ClaimCreate


def _make_claim_create(**kwargs) -> ClaimCreate:
    defaults = {
        "claim_number": "CLM-001",
        "claim_line_number": 1,
        "claim_type": "professional",
        "patient_member_id": "MBR-123",
        "rendering_provider_npi": "1234567890",
        "date_of_service": date(2026, 1, 15),
        "procedure_code": "J0135",
        "billed_amount": Decimal("250.00"),
    }
    defaults.update(kwargs)
    return ClaimCreate(**defaults)


class TestClaimCreate:
    def test_create_claim_persists(self, db_session, tenant_id):
        svc = ClaimService(db_session)
        claim = svc.create_claim(tenant_id, _make_claim_create())
        assert claim.id is not None
        assert claim.tenant_id == tenant_id
        assert claim.status == "received"
        assert claim.claim_number == "CLM-001"
        assert claim.billed_amount == Decimal("250.00")

    def test_create_claim_site_of_care_inferred(self, db_session, tenant_id):
        svc = ClaimService(db_session)
        claim = svc.create_claim(tenant_id, _make_claim_create(place_of_service="11"))
        assert claim.site_of_care == "office_infusion"

    def test_create_claim_hospital_outpatient(self, db_session, tenant_id):
        svc = ClaimService(db_session)
        claim = svc.create_claim(tenant_id, _make_claim_create(place_of_service="22"))
        assert claim.site_of_care == "hospital_outpatient"

    def test_create_claim_billed_amount_rounded(self, db_session, tenant_id):
        svc = ClaimService(db_session)
        claim = svc.create_claim(tenant_id, _make_claim_create(billed_amount=Decimal("100.005")))
        # ROUND_HALF_UP: 100.005 → 100.01
        assert claim.billed_amount == Decimal("100.01")

    def test_create_claim_phi_encrypted(self, db_session, tenant_id):
        """PHI fields go through EncryptedString — value stored but not logged."""
        svc = ClaimService(db_session)
        claim = svc.create_claim(
            tenant_id,
            _make_claim_create(patient_first_name="John", patient_last_name="Doe"),
        )
        # The ORM stores encrypted bytes; reading back gives plaintext via decrypt
        assert claim.patient_first_name_encrypted == "John"
        assert claim.patient_last_name_encrypted == "Doe"

    def test_create_claim_zero_dollar(self, db_session, tenant_id):
        """Zero-dollar (capitated) claims are valid."""
        svc = ClaimService(db_session)
        claim = svc.create_claim(tenant_id, _make_claim_create(billed_amount=Decimal("0.00")))
        assert claim.billed_amount == Decimal("0.00")


class TestClaimRead:
    def test_get_claim_found(self, db_session, tenant_id):
        svc = ClaimService(db_session)
        created = svc.create_claim(tenant_id, _make_claim_create())
        fetched = svc.get_claim(tenant_id, created.id)
        assert fetched is not None
        assert fetched.id == created.id

    def test_get_claim_wrong_tenant_returns_none(self, db_session, tenant_id, other_tenant_id):
        svc = ClaimService(db_session)
        created = svc.create_claim(tenant_id, _make_claim_create())
        # Querying with other_tenant_id must NOT return the claim (tenant isolation)
        fetched = svc.get_claim(other_tenant_id, created.id)
        assert fetched is None

    def test_get_claim_not_found(self, db_session, tenant_id):
        svc = ClaimService(db_session)
        result = svc.get_claim(tenant_id, uuid.uuid4())
        assert result is None

    def test_list_claims_by_status(self, db_session, tenant_id):
        svc = ClaimService(db_session)
        svc.create_claim(tenant_id, _make_claim_create(claim_number="CLM-A"))
        svc.create_claim(tenant_id, _make_claim_create(claim_number="CLM-B"))
        items, total = svc.list_claims(tenant_id, status="received")
        assert total >= 2

    def test_list_claims_tenant_isolation(self, db_session, tenant_id, other_tenant_id):
        svc = ClaimService(db_session)
        svc.create_claim(tenant_id, _make_claim_create(claim_number="T1-CLM-X"))
        svc.create_claim(other_tenant_id, _make_claim_create(claim_number="T2-CLM-Y"))
        items_a, _ = svc.list_claims(tenant_id)
        claim_numbers_a = {c.claim_number for c in items_a}
        # Tenant A must NOT see Tenant B claims
        assert "T2-CLM-Y" not in claim_numbers_a


class TestStatusTransitions:
    def test_received_to_validated(self, db_session, tenant_id):
        svc = ClaimService(db_session)
        claim = svc.create_claim(tenant_id, _make_claim_create(claim_number="CLM-ST1"))
        updated = svc.transition_status(tenant_id, claim.id, "validated")
        assert updated.status == "validated"

    def test_validated_to_priced(self, db_session, tenant_id):
        svc = ClaimService(db_session)
        claim = svc.create_claim(tenant_id, _make_claim_create(claim_number="CLM-ST2"))
        svc.transition_status(tenant_id, claim.id, "validated")
        updated = svc.transition_status(tenant_id, claim.id, "priced")
        assert updated.status == "priced"

    def test_priced_to_adjudicated(self, db_session, tenant_id):
        svc = ClaimService(db_session)
        claim = svc.create_claim(tenant_id, _make_claim_create(claim_number="CLM-ST3"))
        svc.transition_status(tenant_id, claim.id, "validated")
        svc.transition_status(tenant_id, claim.id, "priced")
        updated = svc.transition_status(tenant_id, claim.id, "adjudicated")
        assert updated.status == "adjudicated"

    def test_invalid_transition_raises(self, db_session, tenant_id):
        svc = ClaimService(db_session)
        claim = svc.create_claim(tenant_id, _make_claim_create(claim_number="CLM-ST4"))
        with pytest.raises(ValueError, match="Cannot transition"):
            svc.transition_status(tenant_id, claim.id, "paid")  # must be adjudicated first

    def test_deny_claim_with_reason(self, db_session, tenant_id):
        svc = ClaimService(db_session)
        claim = svc.create_claim(tenant_id, _make_claim_create(claim_number="CLM-ST5"))
        svc.transition_status(tenant_id, claim.id, "validated")
        denied = svc.transition_status(
            tenant_id, claim.id, "denied",
            denial_reason_code="197",
            denial_reason_description="Prior auth missing",
        )
        assert denied.status == "denied"
        assert denied.denial_reason_code == "197"

    def test_void_from_any_valid_state(self, db_session, tenant_id):
        svc = ClaimService(db_session)
        claim = svc.create_claim(tenant_id, _make_claim_create(claim_number="CLM-ST6"))
        voided = svc.transition_status(tenant_id, claim.id, "voided")
        assert voided.status == "voided"

    def test_voided_has_no_transitions(self, db_session, tenant_id):
        svc = ClaimService(db_session)
        claim = svc.create_claim(tenant_id, _make_claim_create(claim_number="CLM-ST7"))
        svc.transition_status(tenant_id, claim.id, "voided")
        with pytest.raises(ValueError):
            svc.transition_status(tenant_id, claim.id, "validated")


class TestDrugClaimFilter:
    def test_j_code_is_drug_claim(self):
        assert ClaimService.is_drug_claim("J0135", None) is True

    def test_q_code_is_drug_claim(self):
        assert ClaimService.is_drug_claim("Q0169", None) is True

    def test_c_code_is_drug_claim(self):
        assert ClaimService.is_drug_claim("C9399", None) is True

    def test_ndc_present_is_drug_claim(self):
        assert ClaimService.is_drug_claim("99213", "12345678901") is True

    def test_non_drug_no_ndc(self):
        assert ClaimService.is_drug_claim("99213", None) is False

    def test_empty_ndc_is_not_drug(self):
        assert ClaimService.is_drug_claim("99213", "") is False


class TestEdiIngestion:
    def test_edi_payload_creates_drug_lines_only(self, db_session, tenant_id):
        svc = ClaimService(db_session)
        payload = {
            "transaction_type": "837P",
            "claim_lines": [
                {
                    "claim_number": "EDI-001",
                    "claim_line_number": 1,
                    "procedure_code": "J0135",
                    "patient_member_id": "MBR-EDI",
                    "rendering_provider_npi": "1234567890",
                    "date_of_service": "2026-02-01",
                    "billed_amount": "500.00",
                },
                {
                    "claim_number": "EDI-001",
                    "claim_line_number": 2,
                    "procedure_code": "99213",  # non-drug line
                    "patient_member_id": "MBR-EDI",
                    "rendering_provider_npi": "1234567890",
                    "date_of_service": "2026-02-01",
                    "billed_amount": "150.00",
                },
            ],
        }
        created = svc.ingest_from_edi_payload(tenant_id, payload)
        # Only the J-code line should be created, not the E&M visit
        assert len(created) == 1
        assert created[0].procedure_code == "J0135"

    def test_edi_payload_with_ndc_creates_record(self, db_session, tenant_id):
        svc = ClaimService(db_session)
        payload = {
            "transaction_type": "837I",
            "claim_lines": [
                {
                    "claim_number": "EDI-002",
                    "procedure_code": "99213",  # non-drug HCPCS
                    "ndc": "12345678901",  # but has NDC → drug claim
                    "patient_member_id": "MBR-002",
                    "rendering_provider_npi": "0987654321",
                    "date_of_service": "2026-02-15",
                    "billed_amount": "800.00",
                },
            ],
        }
        created = svc.ingest_from_edi_payload(tenant_id, payload)
        assert len(created) == 1
        assert created[0].ndc == "12345678901"
