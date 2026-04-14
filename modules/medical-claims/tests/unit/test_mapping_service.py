"""Unit tests for HCPCS-NDC mapping service."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from src.services.mapping_service import MappingService, _MANY_NDCS_THRESHOLD
from src.models.tables import ClaimRecord


def _seed_crosswalk(svc: MappingService, hcpcs: str, ndcs: list[str], eff: date = date(2026, 1, 1)):
    for ndc in ndcs:
        svc.upsert_crosswalk_entry(hcpcs_code=hcpcs, ndc=ndc, effective_date=eff)


class TestCrosswalkLookup:
    def test_no_crosswalk_returns_manual(self, db_session):
        svc = MappingService(db_session)
        result = svc.lookup_crosswalk("J9999", as_of=date(2026, 1, 1))
        assert result.confidence == "manual"
        assert result.requires_manual_review is True
        assert result.matches == []

    def test_single_ndc_returns_high(self, db_session):
        svc = MappingService(db_session)
        _seed_crosswalk(svc, "J0135A", ["12345678901"])
        result = svc.lookup_crosswalk("J0135A", as_of=date(2026, 1, 1))
        assert result.confidence == "high"
        assert result.requires_manual_review is False
        assert len(result.matches) == 1

    def test_few_ndcs_returns_medium(self, db_session):
        svc = MappingService(db_session)
        _seed_crosswalk(svc, "J0136A", ["1" * 11, "2" * 11, "3" * 11])
        result = svc.lookup_crosswalk("J0136A", as_of=date(2026, 1, 1))
        assert result.confidence == "medium"
        assert result.requires_manual_review is False

    def test_many_ndcs_returns_low_with_manual_flag(self, db_session):
        """50+ NDCs → LOW confidence, requires manual review."""
        svc = MappingService(db_session)
        # Seed more than _MANY_NDCS_THRESHOLD entries
        ndcs = [str(i).zfill(11) for i in range(_MANY_NDCS_THRESHOLD + 1)]
        _seed_crosswalk(svc, "J0137A", ndcs)
        result = svc.lookup_crosswalk("J0137A", as_of=date(2026, 1, 1))
        assert result.confidence == "low"
        assert result.requires_manual_review is True
        assert len(result.matches) == _MANY_NDCS_THRESHOLD + 1

    def test_terminated_entry_excluded(self, db_session):
        svc = MappingService(db_session)
        svc.upsert_crosswalk_entry(
            hcpcs_code="J0138A",
            ndc="11111111111",
            effective_date=date(2025, 1, 1),
            termination_date=date(2025, 12, 31),
        )
        result = svc.lookup_crosswalk("J0138A", as_of=date(2026, 1, 1))
        assert len(result.matches) == 0
        assert result.confidence == "manual"


class TestClaimMapping:
    def test_direct_ndc_returns_exact(self, db_session, tenant_id):
        svc = MappingService(db_session)
        from tests.conftest import TENANT_A
        claim = ClaimRecord(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            claim_number="MAP-001",
            claim_line_number=1,
            claim_type="professional",
            patient_member_id="MBR-1",
            rendering_provider_npi="1234567890",
            date_of_service=date(2026, 1, 15),
            procedure_code="J0135",
            billed_amount=Decimal("100.00"),
            status="received",
            ndc="99999999999",
        )
        db_session.add(claim)
        db_session.commit()

        mapped_ndc, confidence = svc.map_claim(claim)
        assert mapped_ndc == "99999999999"
        assert confidence == "exact"

    def test_hcpcs_single_ndc_high_confidence(self, db_session, tenant_id):
        svc = MappingService(db_session)
        _seed_crosswalk(svc, "J0200A", ["88888888888"])
        claim = ClaimRecord(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            claim_number="MAP-002",
            claim_line_number=1,
            claim_type="professional",
            patient_member_id="MBR-1",
            rendering_provider_npi="1234567890",
            date_of_service=date(2026, 1, 15),
            procedure_code="J0200A",
            billed_amount=Decimal("100.00"),
            status="received",
            ndc=None,
        )
        db_session.add(claim)
        db_session.commit()

        mapped_ndc, confidence = svc.map_claim(claim)
        assert mapped_ndc == "88888888888"
        assert confidence == "high"

    def test_manual_override_sets_manual_confidence(self, db_session, tenant_id):
        svc = MappingService(db_session)
        claim = ClaimRecord(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            claim_number="MAP-003",
            claim_line_number=1,
            claim_type="professional",
            patient_member_id="MBR-1",
            rendering_provider_npi="1234567890",
            date_of_service=date(2026, 1, 15),
            procedure_code="J9999",
            billed_amount=Decimal("100.00"),
            status="received",
        )
        db_session.add(claim)
        db_session.commit()

        updated = svc.set_manual_mapping(tenant_id, claim.id, "77777777777")
        assert updated.mapped_ndc == "77777777777"
        assert updated.mapping_confidence == "manual"

    def test_unmapped_claims_list(self, db_session, tenant_id):
        svc = MappingService(db_session)
        claim = ClaimRecord(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            claim_number="MAP-004",
            claim_line_number=1,
            claim_type="professional",
            patient_member_id="MBR-1",
            rendering_provider_npi="1234567890",
            date_of_service=date(2026, 1, 15),
            procedure_code="J8888",
            billed_amount=Decimal("100.00"),
            status="received",
            mapping_confidence="manual",
            mapped_ndc=None,
        )
        db_session.add(claim)
        db_session.commit()

        unmapped = svc.list_unmapped_claims(tenant_id)
        ids = {c.id for c in unmapped}
        assert claim.id in ids
