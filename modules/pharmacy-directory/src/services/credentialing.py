"""Credentialing workflow service.

Application → automated verification → risk-based routing → review → decision.
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tables import CredentialingApplication

logger = logging.getLogger("pharmacy-directory.credentialing")


# Risk thresholds per PRD 3.4
_LOW_RISK_MAX = 25
_MEDIUM_RISK_MAX = 50


def determine_risk_queue(
    risk_score: int | None,
    all_automated_pass: bool,
    recent_ownership_change: bool = False,
    prior_fraud_flags: bool = False,
) -> str:
    """Return routing queue: fast_track, standard, or enhanced."""
    if recent_ownership_change or prior_fraud_flags:
        return "enhanced"
    if risk_score is None:
        return "standard"
    if risk_score > _MEDIUM_RISK_MAX:
        return "enhanced"
    if risk_score <= _LOW_RISK_MAX and all_automated_pass:
        return "fast_track"
    return "standard"


class CredentialingService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def submit_application(
        self,
        tenant_id: UUID,
        applicant_npi: str,
        applicant_name: str,
        network_id: UUID,
        pharmacy_id: UUID | None = None,
        applicant_address: str | None = None,
    ) -> CredentialingApplication:
        app = CredentialingApplication(
            tenant_id=tenant_id,
            pharmacy_id=pharmacy_id,
            applicant_npi=applicant_npi,
            applicant_name=applicant_name,
            applicant_address=applicant_address,
            network_id=network_id,
            application_date=date.today(),
            status="submitted",
        )
        self._db.add(app)
        await self._db.flush()
        logger.info(
            "credentialing.application_submitted",
            extra={
                "svc_name": "credentialing",
                "credentialing_application_id": str(app.id),
                "pharmacy_npi": applicant_npi,
            },
        )
        return app

    async def run_automated_checks(
        self,
        application_id: UUID,
        npi_valid: bool = True,
        state_license_valid: bool = True,
        state_license_expiry: date | None = None,
        dea_valid: bool = True,
        dea_expiry: date | None = None,
        oig_sam_clear: bool = True,
    ) -> CredentialingApplication:
        stmt = select(CredentialingApplication).where(
            CredentialingApplication.id == application_id
        )
        result = await self._db.execute(stmt)
        app = result.scalar_one()

        app.npi_verified = npi_valid
        app.state_license_verified = state_license_valid
        app.state_license_expiry = state_license_expiry
        app.dea_verified = dea_valid
        app.dea_expiry = dea_expiry
        app.oig_sam_screened = True
        app.oig_sam_clear = oig_sam_clear
        app.status = "under_review"
        app.updated_at = datetime.now(UTC)

        await self._db.flush()
        return app

    async def update_risk_score(
        self,
        application_id: UUID,
        risk_score: int,
        risk_factors: dict[str, Any] | None = None,
    ) -> CredentialingApplication:
        stmt = select(CredentialingApplication).where(
            CredentialingApplication.id == application_id
        )
        result = await self._db.execute(stmt)
        app = result.scalar_one()
        app.credentialing_risk_score = risk_score
        app.risk_score_factors = risk_factors or {}
        app.updated_at = datetime.now(UTC)
        await self._db.flush()
        return app

    async def approve(
        self,
        application_id: UUID,
        reviewed_by: UUID,
        review_notes: str | None = None,
    ) -> CredentialingApplication:
        stmt = select(CredentialingApplication).where(
            CredentialingApplication.id == application_id
        )
        result = await self._db.execute(stmt)
        app = result.scalar_one()
        app.status = "approved"
        app.reviewed_by = reviewed_by
        app.reviewed_at = datetime.now(UTC)
        app.review_notes = review_notes
        app.updated_at = datetime.now(UTC)
        await self._db.flush()
        return app

    async def deny(
        self,
        application_id: UUID,
        reviewed_by: UUID,
        denial_reason: str,
        review_notes: str | None = None,
    ) -> CredentialingApplication:
        stmt = select(CredentialingApplication).where(
            CredentialingApplication.id == application_id
        )
        result = await self._db.execute(stmt)
        app = result.scalar_one()
        app.status = "denied"
        app.reviewed_by = reviewed_by
        app.reviewed_at = datetime.now(UTC)
        app.denial_reason = denial_reason
        app.review_notes = review_notes
        app.updated_at = datetime.now(UTC)
        await self._db.flush()
        return app
