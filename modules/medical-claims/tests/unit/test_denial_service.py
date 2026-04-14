"""Unit tests for denial management service."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.services.denial_service import DenialService
from src.services.claim_service import ClaimService
from src.api.schemas.claims import ClaimCreate


def _create_claim(db, tenant_id, claim_num="DEN-001") -> object:
    svc = ClaimService(db)
    return svc.create_claim(
        tenant_id,
        ClaimCreate(
            claim_number=claim_num,
            claim_type="professional",
            patient_member_id="MBR-1",
            rendering_provider_npi="1234567890",
            date_of_service=date(2026, 1, 10),
            procedure_code="J0135",
            billed_amount=Decimal("300.00"),
        ),
    )


class TestDenyAndAppeal:
    def test_deny_claim_transitions_status(self, db_session, tenant_id):
        claim = _create_claim(db_session, tenant_id, "DEN-A")
        # Must validate first
        ClaimService(db_session).transition_status(tenant_id, claim.id, "validated")
        svc = DenialService(db_session)
        denied = svc.deny_claim(tenant_id, claim.id, "197")
        assert denied.status == "denied"
        assert denied.denial_reason_code == "197"

    def test_deny_uses_known_carc_description(self, db_session, tenant_id):
        claim = _create_claim(db_session, tenant_id, "DEN-B")
        ClaimService(db_session).transition_status(tenant_id, claim.id, "validated")
        svc = DenialService(db_session)
        denied = svc.deny_claim(tenant_id, claim.id, "197")
        assert "precertification" in denied.denial_reason_description.lower()

    def test_appeal_denied_claim(self, db_session, tenant_id):
        claim = _create_claim(db_session, tenant_id, "DEN-C")
        ClaimService(db_session).transition_status(tenant_id, claim.id, "validated")
        svc = DenialService(db_session)
        svc.deny_claim(tenant_id, claim.id, "50")
        appealed = svc.initiate_appeal(tenant_id, claim.id, "Medical necessity documented")
        assert appealed.status == "appealed"

    def test_cannot_appeal_non_denied_claim(self, db_session, tenant_id):
        claim = _create_claim(db_session, tenant_id, "DEN-D")
        svc = DenialService(db_session)
        with pytest.raises(ValueError, match="only appeal denied"):
            svc.initiate_appeal(tenant_id, claim.id, "reason here too long enough")

    def test_list_denied_claims(self, db_session, tenant_id):
        claim = _create_claim(db_session, tenant_id, "DEN-E")
        ClaimService(db_session).transition_status(tenant_id, claim.id, "validated")
        svc = DenialService(db_session)
        svc.deny_claim(tenant_id, claim.id, "96")

        items, total = svc.list_denied_claims(tenant_id)
        ids = {c.id for c in items}
        assert claim.id in ids

    def test_denial_analytics_rates(self, db_session, tenant_id):
        claim = _create_claim(db_session, tenant_id, "DEN-F")
        ClaimService(db_session).transition_status(tenant_id, claim.id, "validated")
        svc = DenialService(db_session)
        svc.deny_claim(tenant_id, claim.id, "197")

        analytics = svc.get_denial_analytics(
            tenant_id, date(2026, 1, 1), date(2026, 12, 31)
        )
        assert analytics["total_denied"] >= 1
        assert isinstance(analytics["denial_rate"], Decimal)
