"""Trading partner management API."""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth.dependencies import get_current_user  # CR-03
from shared.db.session import get_session
from shared.db.tenant_context import set_tenant_context

from ..models.edi_models import TradingPartner
from ..services.baa_tracking import (
    AgreementInput,
    InvalidAgreementType,
    check_baa_valid,
    create_agreement,
    get_agreements_by_partner,
    get_expiring_agreements,
)

router = APIRouter(
    prefix="/trading-partners",
    tags=["trading-partners"],
    dependencies=[Depends(get_current_user)],  # CR-03: require JWT auth on all routes
)


def _require_tenant(x_tenant_id: Annotated[Optional[str], Header()] = None) -> uuid.UUID:
    if not x_tenant_id:
        raise HTTPException(status_code=401, detail={"error": {"code": "MISSING_TENANT", "message": "x-tenant-id header required"}})
    try:
        return uuid.UUID(x_tenant_id)
    except ValueError:
        raise HTTPException(status_code=403, detail={"error": {"code": "INVALID_TENANT", "message": "x-tenant-id must be a valid UUID"}})


class TradingPartnerCreate(BaseModel):
    name: str
    partner_type: str
    isa_qualifier: str
    isa_id: str
    gs_id: Optional[str] = None
    supported_transactions: list[str]
    transport_type: str
    transport_config: dict[str, Any]
    test_mode: bool = True
    companion_guide_ref: Optional[str] = None


class TradingPartnerResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    partner_type: str
    isa_qualifier: str
    isa_id: str
    supported_transactions: list[str]
    transport_type: str
    test_mode: bool
    is_active: bool


@router.get("", response_model=list[TradingPartnerResponse])
async def list_trading_partners(
    tenant_id: uuid.UUID = Depends(_require_tenant),
    db: AsyncSession = Depends(get_session),
) -> list[TradingPartnerResponse]:
    set_tenant_context(tenant_id)
    result = await db.execute(
        select(TradingPartner).where(
            TradingPartner.tenant_id == tenant_id,
            TradingPartner.is_active.is_(True),
        )
    )
    partners = result.scalars().all()
    return [
        TradingPartnerResponse(
            id=str(p.id),
            tenant_id=str(p.tenant_id),
            name=p.name,
            partner_type=p.partner_type,
            isa_qualifier=p.isa_qualifier,
            isa_id=p.isa_id,
            supported_transactions=p.supported_transactions,
            transport_type=p.transport_type,
            test_mode=p.test_mode,
            is_active=p.is_active,
        )
        for p in partners
    ]


@router.post("", response_model=TradingPartnerResponse, status_code=201)
async def create_trading_partner(
    body: TradingPartnerCreate,
    tenant_id: uuid.UUID = Depends(_require_tenant),
    db: AsyncSession = Depends(get_session),
) -> TradingPartnerResponse:
    set_tenant_context(tenant_id)
    partner = TradingPartner(
        tenant_id=tenant_id,
        name=body.name,
        partner_type=body.partner_type,
        isa_qualifier=body.isa_qualifier,
        isa_id=body.isa_id,
        gs_id=body.gs_id,
        supported_transactions=body.supported_transactions,
        transport_type=body.transport_type,
        transport_config=body.transport_config,
        test_mode=body.test_mode,
        companion_guide_ref=body.companion_guide_ref,
        is_active=True,
    )
    db.add(partner)
    await db.commit()
    await db.refresh(partner)
    return TradingPartnerResponse(
        id=str(partner.id),
        tenant_id=str(partner.tenant_id),
        name=partner.name,
        partner_type=partner.partner_type,
        isa_qualifier=partner.isa_qualifier,
        isa_id=partner.isa_id,
        supported_transactions=partner.supported_transactions,
        transport_type=partner.transport_type,
        test_mode=partner.test_mode,
        is_active=partner.is_active,
    )


# ---- H-08: Trading Partner Agreement (BAA/TPA/NDA) tracking ----


class AgreementCreate(BaseModel):
    agreement_type: str
    executed_date: Optional[str] = None
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None
    renewal_date: Optional[str] = None
    signatory_name: Optional[str] = None
    signatory_title: Optional[str] = None


class AgreementResponse(BaseModel):
    id: str
    trading_partner_id: str
    agreement_type: str
    executed_date: Optional[str] = None
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None
    renewal_date: Optional[str] = None
    signatory_name: Optional[str] = None
    signatory_title: Optional[str] = None


def _agreement_to_response(row: Any) -> AgreementResponse:
    return AgreementResponse(
        id=str(row.id),
        trading_partner_id=str(row.trading_partner_id),
        agreement_type=row.agreement_type,
        executed_date=row.executed_date,
        effective_date=row.effective_date,
        expiry_date=row.expiry_date,
        renewal_date=row.renewal_date,
        signatory_name=row.signatory_name,
        signatory_title=row.signatory_title,
    )


@router.get("/{partner_id}/agreements", response_model=list[AgreementResponse])
async def list_agreements(
    partner_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(_require_tenant),
    db: AsyncSession = Depends(get_session),
) -> list[AgreementResponse]:
    set_tenant_context(tenant_id)
    rows = await get_agreements_by_partner(
        db, tenant_id=tenant_id, trading_partner_id=partner_id
    )
    return [_agreement_to_response(r) for r in rows]


@router.post("/{partner_id}/agreements", response_model=AgreementResponse, status_code=201)
async def create_agreement_endpoint(
    partner_id: uuid.UUID,
    body: AgreementCreate,
    tenant_id: uuid.UUID = Depends(_require_tenant),
    db: AsyncSession = Depends(get_session),
) -> AgreementResponse:
    set_tenant_context(tenant_id)
    try:
        row = await create_agreement(
            db,
            tenant_id=tenant_id,
            payload=AgreementInput(
                trading_partner_id=partner_id,
                agreement_type=body.agreement_type,
                executed_date=body.executed_date,
                effective_date=body.effective_date,
                expiry_date=body.expiry_date,
                renewal_date=body.renewal_date,
                signatory_name=body.signatory_name,
                signatory_title=body.signatory_title,
            ),
        )
    except InvalidAgreementType as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "INVALID_AGREEMENT_TYPE", "message": str(exc)}},
        )
    return _agreement_to_response(row)


@router.get("/agreements/expiring", response_model=list[AgreementResponse])
async def list_expiring_agreements(
    days_ahead: int = 90,
    tenant_id: uuid.UUID = Depends(_require_tenant),
    db: AsyncSession = Depends(get_session),
) -> list[AgreementResponse]:
    set_tenant_context(tenant_id)
    rows = await get_expiring_agreements(db, tenant_id=tenant_id, days_ahead=days_ahead)
    return [_agreement_to_response(r) for r in rows]


@router.get("/{partner_id}/baa-valid")
async def check_baa(
    partner_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(_require_tenant),
    db: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    set_tenant_context(tenant_id)
    valid = await check_baa_valid(
        db, tenant_id=tenant_id, trading_partner_id=partner_id
    )
    return {"valid": valid}
