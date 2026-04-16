"""Rebate contract management API routes."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.dependencies import get_db, get_tenant_id
from src.api.schemas.contracts import (
    ContractAmendRequest,
    ContractCreateRequest,
    ContractResponse,
    ContractStatusTransition,
    NDCTermCreate,
    TierCreate,
)
from src.services.contracts import ContractLifecycleError, ContractService

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.post("", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
async def create_contract(
    body: ContractCreateRequest,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
) -> Any:
    svc = ContractService(db)
    contract = svc.create_contract(
        tenant_id=tenant_id,
        manufacturer_id=body.manufacturer_id,
        manufacturer_name=body.manufacturer_name,
        contract_number=body.contract_number,
        contract_type=body.contract_type,
        effective_date=body.effective_date,
        payment_frequency=body.payment_frequency,
        termination_date=body.termination_date,
        minimum_volume_threshold=body.minimum_volume_threshold,
        bfsf_only=body.bfsf_only,
        notes=body.notes,
    )
    for ndc in body.ndc_terms:
        svc.add_ndc_term(
            tenant_id=tenant_id,
            contract_id=contract.id,
            ndc11=ndc.ndc11,
            rebate_type=ndc.rebate_type,
            effective_date=ndc.effective_date,
            rebate_percent=ndc.rebate_percent,
            rebate_per_unit=ndc.rebate_per_unit,
            drug_name=ndc.drug_name,
            formulary_position=ndc.formulary_position,
            formulary_position_bonus_percent=ndc.formulary_position_bonus_percent,
            growth_bonus_percent=ndc.growth_bonus_percent,
            termination_date=ndc.termination_date,
        )
    for tier in body.tiers:
        svc.add_tier(
            tenant_id=tenant_id,
            contract_id=contract.id,
            tier_name=tier.tier_name,
            tier_type=tier.tier_type,
            threshold_value=tier.threshold_value,
            rebate_percent=tier.rebate_percent,
        )
    db.commit()
    return contract


@router.get("", response_model=list[ContractResponse])
async def list_contracts(
    contract_status: str | None = None,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
) -> Any:
    svc = ContractService(db)
    return svc.list_contracts(tenant_id, status=contract_status)


@router.get("/{contract_id}", response_model=ContractResponse)
async def get_contract(
    contract_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
) -> Any:
    svc = ContractService(db)
    contract = svc.get_contract(tenant_id, contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="Contract not found")
    return contract


@router.post("/{contract_id}/transition", response_model=ContractResponse)
async def transition_contract(
    contract_id: uuid.UUID,
    body: ContractStatusTransition,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
) -> Any:
    svc = ContractService(db)
    try:
        contract = svc.transition_status(
            tenant_id, contract_id, body.new_status, body.approved_by
        )
        db.commit()
        return contract
    except ContractLifecycleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{contract_id}/amend", response_model=ContractResponse)
async def amend_contract(
    contract_id: uuid.UUID,
    body: ContractAmendRequest,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
) -> Any:
    svc = ContractService(db)
    try:
        contract = svc.amend_contract(tenant_id, contract_id, body.updates)
        db.commit()
        return contract
    except ContractLifecycleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{contract_id}/ndc-terms")
async def add_ndc_term(
    contract_id: uuid.UUID,
    body: NDCTermCreate,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
) -> dict[str, str]:
    svc = ContractService(db)
    term = svc.add_ndc_term(
        tenant_id=tenant_id,
        contract_id=contract_id,
        ndc11=body.ndc11,
        rebate_type=body.rebate_type,
        effective_date=body.effective_date,
        rebate_percent=body.rebate_percent,
        rebate_per_unit=body.rebate_per_unit,
        drug_name=body.drug_name,
        formulary_position=body.formulary_position,
        formulary_position_bonus_percent=body.formulary_position_bonus_percent,
        growth_bonus_percent=body.growth_bonus_percent,
        termination_date=body.termination_date,
    )
    db.commit()
    return {"id": str(term.id)}


@router.post("/{contract_id}/tiers")
async def add_tier(
    contract_id: uuid.UUID,
    body: TierCreate,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
) -> dict[str, str]:
    svc = ContractService(db)
    tier = svc.add_tier(
        tenant_id=tenant_id,
        contract_id=contract_id,
        tier_name=body.tier_name,
        tier_type=body.tier_type,
        threshold_value=body.threshold_value,
        rebate_percent=body.rebate_percent,
    )
    db.commit()
    return {"id": str(tier.id)}
