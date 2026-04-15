"""Contract management routes.

Endpoints:
  POST/GET  /contracts
  GET/PATCH  /contracts/{id}
  POST  /contracts/{id}/amendments
  GET   /contracts/renewal-alerts
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from shared.auth.dependencies import CurrentUser, get_current_user
from shared.events.in_memory_bus import InMemoryEventBus

from src.api.schemas.programs import (
    ContractAmendmentRequest,
    ContractCreateRequest,
    ContractResponse,
)
from src.events.publishers import contract_expiring_soon_event
from src.models.tables import Contract, ProgramActivityLog

router = APIRouter(prefix="/contracts", tags=["contracts"])

_event_bus = InMemoryEventBus()


def _get_db():  # pragma: no cover
    from shared.db.session import get_db
    yield from get_db()


def _get_event_bus():
    return _event_bus


def _not_found(contract_id: uuid.UUID, corr: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": {"code": "CONTRACT_NOT_FOUND", "message": f"Contract {contract_id} not found", "correlation_id": corr}},
    )


@router.post("", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
async def create_contract(
    body: ContractCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
) -> Any:
    correlation_id = str(uuid.uuid4())

    # Compute auto-renewal date if auto_renewal enabled
    auto_renewal_date = None
    if body.auto_renewal and body.termination_date:
        notice_before = timedelta(days=body.renewal_notice_days)
        auto_renewal_date = body.termination_date - notice_before

    contract = Contract(
        tenant_id=current_user.tenant_id,
        program_id=body.program_id,
        client_id=body.client_id,
        effective_date=body.effective_date,
        termination_date=body.termination_date,
        auto_renewal=body.auto_renewal,
        auto_renewal_date=auto_renewal_date,
        renewal_notice_days=body.renewal_notice_days,
        sla=body.sla,
        fees=body.fees,
        spend_cap_config=body.spend_cap_config,
        bfsf_documentation=body.bfsf_documentation,
        created_by=current_user.id,
    )
    db.add(contract)

    log_entry = ProgramActivityLog(
        tenant_id=current_user.tenant_id,
        program_id=body.program_id,
        entity_type="contract",
        entity_id=contract.id,
        action="created",
        performed_by=current_user.id,
        before_state=None,
        after_state={"status": "draft"},
        correlation_id=uuid.UUID(correlation_id),
    )
    db.add(log_entry)
    db.commit()
    db.refresh(contract)
    return contract


@router.get("", response_model=list[ContractResponse])
async def list_contracts(
    program_id: uuid.UUID | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
) -> Any:
    query = db.query(Contract).filter_by(tenant_id=current_user.tenant_id)
    if program_id:
        query = query.filter(Contract.program_id == program_id)
    return query.order_by(Contract.created_at.desc()).all()


@router.get("/renewal-alerts", response_model=list[ContractResponse])
async def get_renewal_alerts(
    days_ahead: int = Query(default=90, ge=1, le=365),
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
    event_bus=Depends(_get_event_bus),
) -> Any:
    """Return contracts whose auto-renewal date is within the next N days."""
    now = datetime.now(UTC)
    alert_cutoff = now + timedelta(days=days_ahead)

    contracts = (
        db.query(Contract)
        .filter(
            Contract.tenant_id == current_user.tenant_id,
            Contract.auto_renewal.is_(True),
            Contract.auto_renewal_date.isnot(None),
            Contract.auto_renewal_date <= alert_cutoff,
            Contract.auto_renewal_date >= now,
            Contract.status.in_(["active", "draft"]),
        )
        .all()
    )

    # Publish expiry events for each
    for contract in contracts:
        days_until = (contract.auto_renewal_date - now).days
        await event_bus.publish(
            contract_expiring_soon_event(
                contract_id=contract.id,
                program_id=contract.program_id,
                tenant_id=current_user.tenant_id,
                renewal_date=contract.auto_renewal_date.isoformat(),
                days_until_renewal=days_until,
            )
        )

    return contracts


@router.get("/{contract_id}", response_model=ContractResponse)
async def get_contract(
    contract_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
) -> Any:
    correlation_id = str(uuid.uuid4())
    contract = db.query(Contract).filter_by(id=contract_id, tenant_id=current_user.tenant_id).first()
    if not contract:
        raise _not_found(contract_id, correlation_id)
    return contract


@router.post("/{contract_id}/amendments", response_model=ContractResponse)
async def add_amendment(
    contract_id: uuid.UUID,
    body: ContractAmendmentRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
) -> Any:
    """Append an amendment to a contract. Preserves amendment history."""
    correlation_id = str(uuid.uuid4())
    contract = db.query(Contract).filter_by(id=contract_id, tenant_id=current_user.tenant_id).first()
    if not contract:
        raise _not_found(contract_id, correlation_id)

    amendment = {
        "amendment_id": str(uuid.uuid4()),
        "effective_date": body.effective_date.isoformat(),
        "changes": body.changes,
        "reason": body.reason,
        "approved_by": str(current_user.id),
        "created_at": datetime.now(UTC).isoformat(),
    }

    # JSONB list — build new list to trigger SQLAlchemy dirty tracking
    amendments = list(contract.amendments) if contract.amendments else []
    amendments.append(amendment)
    contract.amendments = amendments

    log_entry = ProgramActivityLog(
        tenant_id=current_user.tenant_id,
        program_id=contract.program_id,
        entity_type="contract",
        entity_id=contract.id,
        action="amendment_added",
        performed_by=current_user.id,
        before_state=None,
        after_state=amendment,
        correlation_id=uuid.UUID(correlation_id),
    )
    db.add(log_entry)
    db.commit()
    db.refresh(contract)
    return contract
