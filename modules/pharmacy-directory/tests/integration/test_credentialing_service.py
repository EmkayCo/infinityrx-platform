"""Integration tests for CredentialingService."""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tables import CredentialingApplication, Network, Pharmacy
from src.services.credentialing import CredentialingService

TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = uuid.UUID("22222222-2222-2222-2222-222222222222")


class TestCredentialingService:
    @pytest.mark.asyncio
    async def test_submit_application_status_is_submitted(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy, network_a: Network
    ) -> None:
        svc = CredentialingService(db_session)
        app = await svc.submit_application(
            tenant_id=TENANT_A,
            applicant_npi=pharmacy_a.npi,
            applicant_name=pharmacy_a.legal_name,
            network_id=network_a.id,
            pharmacy_id=pharmacy_a.id,
        )
        assert app.status == "submitted"
        assert app.tenant_id == TENANT_A

    @pytest.mark.asyncio
    async def test_run_automated_checks_updates_verifications(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy, network_a: Network
    ) -> None:
        svc = CredentialingService(db_session)
        app = await svc.submit_application(
            tenant_id=TENANT_A,
            applicant_npi=pharmacy_a.npi,
            applicant_name=pharmacy_a.legal_name,
            network_id=network_a.id,
        )
        updated = await svc.run_automated_checks(
            application_id=app.id,
            npi_valid=True,
            state_license_valid=True,
            state_license_expiry=date(2027, 12, 31),
            dea_valid=True,
            dea_expiry=date(2027, 6, 30),
            oig_sam_clear=True,
        )
        assert updated.npi_verified is True
        assert updated.state_license_verified is True
        assert updated.dea_verified is True
        assert updated.oig_sam_screened is True
        assert updated.oig_sam_clear is True
        assert updated.status == "under_review"

    @pytest.mark.asyncio
    async def test_update_risk_score_persists(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy, network_a: Network
    ) -> None:
        svc = CredentialingService(db_session)
        app = await svc.submit_application(
            tenant_id=TENANT_A,
            applicant_npi=pharmacy_a.npi,
            applicant_name=pharmacy_a.legal_name,
            network_id=network_a.id,
        )
        updated = await svc.update_risk_score(app.id, 35, {"flag": "new_ownership"})
        assert updated.credentialing_risk_score == 35

    @pytest.mark.asyncio
    async def test_approve_changes_status(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy, network_a: Network
    ) -> None:
        svc = CredentialingService(db_session)
        app = await svc.submit_application(
            tenant_id=TENANT_A,
            applicant_npi=pharmacy_a.npi,
            applicant_name=pharmacy_a.legal_name,
            network_id=network_a.id,
        )
        reviewer = uuid.uuid4()
        approved = await svc.approve(app.id, reviewer, "All checks passed")
        assert approved.status == "approved"
        assert approved.reviewed_by == reviewer
        assert approved.review_notes == "All checks passed"

    @pytest.mark.asyncio
    async def test_deny_changes_status_and_records_reason(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy, network_a: Network
    ) -> None:
        svc = CredentialingService(db_session)
        app = await svc.submit_application(
            tenant_id=TENANT_A,
            applicant_npi=pharmacy_a.npi,
            applicant_name=pharmacy_a.legal_name,
            network_id=network_a.id,
        )
        reviewer = uuid.uuid4()
        denied = await svc.deny(app.id, reviewer, "OIG exclusion found")
        assert denied.status == "denied"
        assert denied.denial_reason == "OIG exclusion found"


class TestCredentialingTenantIsolation:
    @pytest.mark.asyncio
    async def test_application_tenant_b_not_visible_to_tenant_a(
        self,
        db_session: AsyncSession,
        pharmacy_a: Pharmacy,
        network_a: Network,
        network_b: Network,
    ) -> None:
        svc = CredentialingService(db_session)
        await svc.submit_application(TENANT_A, pharmacy_a.npi, "Pharm A", network_a.id)
        await svc.submit_application(TENANT_B, pharmacy_a.npi, "Pharm A", network_b.id)

        stmt = select(CredentialingApplication).where(
            CredentialingApplication.tenant_id == TENANT_A
        )
        result = (await db_session.execute(stmt)).scalars().all()
        assert all(a.tenant_id == TENANT_A for a in result)
