"""Compliance monitoring and reporting API endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.session import get_session
from shared.db.tenant_context import set_tenant_context

from ..models.edi_models import TransactionFile

router = APIRouter(prefix="/compliance", tags=["compliance"])


def _require_tenant(x_tenant_id: Annotated[Optional[str], Header()] = None) -> uuid.UUID:
    if not x_tenant_id:
        raise HTTPException(status_code=401, detail={"error": {"code": "MISSING_TENANT", "message": "x-tenant-id header required"}})
    try:
        return uuid.UUID(x_tenant_id)
    except ValueError:
        raise HTTPException(status_code=403, detail={"error": {"code": "INVALID_TENANT", "message": "x-tenant-id must be a valid UUID"}})


class ComplianceDashboard(BaseModel):
    tenant_id: str
    total_files: int
    pending_transmission: int
    acknowledged: int
    rejected: int
    acceptance_rate_pct: float


@router.get("", response_model=ComplianceDashboard)
async def get_compliance_dashboard(
    tenant_id: uuid.UUID = Depends(_require_tenant),
    db: AsyncSession = Depends(get_session),
) -> ComplianceDashboard:
    set_tenant_context(tenant_id)
    result = await db.execute(
        select(
            func.count(TransactionFile.id).label("total"),
            func.count(TransactionFile.id).filter(TransactionFile.transmission_status == "pending").label("pending"),
            func.count(TransactionFile.id).filter(TransactionFile.ack_status == "accepted").label("accepted"),
            func.count(TransactionFile.id).filter(TransactionFile.ack_status == "rejected").label("rejected"),
        ).where(TransactionFile.tenant_id == tenant_id)
    )
    row = result.fetchone()
    total = row.total if row else 0
    pending = row.pending if row else 0
    accepted = row.accepted if row else 0
    rejected = row.rejected if row else 0
    acceptance_rate = (accepted / total * 100.0) if total > 0 else 0.0
    return ComplianceDashboard(
        tenant_id=str(tenant_id),
        total_files=total,
        pending_transmission=pending,
        acknowledged=accepted,
        rejected=rejected,
        acceptance_rate_pct=round(acceptance_rate, 2),
    )
