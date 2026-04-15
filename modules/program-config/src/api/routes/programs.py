"""Program CRUD routes + status transition + wizard endpoints.

All routes use:
  - async def handlers
  - router-level Depends(get_current_user) for JWT auth
  - Structured error responses
  - Tenant-scoped DB queries (via TenantScopedMixin + tenant context set by auth)
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from shared.auth.dependencies import CurrentUser, get_current_user
from shared.events.in_memory_bus import InMemoryEventBus

from src.api.schemas.programs import (
    ProgramCreateRequest,
    ProgramDrugAddRequest,
    ProgramDrugResponse,
    ProgramResponse,
    ProgramStatusTransitionRequest,
    ProgramUpdateRequest,
)
from src.events.publishers import (
    program_activated_event,
    program_created_event,
    program_suspended_event,
    program_terminated_event,
)
from src.models.tables import Program, ProgramActivityLog, ProgramDrug
from src.services.program_service import (
    BinPcnConflictError,
    OnboardingIncompleteError,
    ProgramStateError,
    apply_brd_to_program,
    check_bin_pcn_conflict,
    transition_program_status,
)

router = APIRouter(prefix="/programs", tags=["programs"])

# Module-level event bus (injected for tests via dependency_overrides)
_event_bus = InMemoryEventBus()


def _get_db():  # pragma: no cover — overridden in tests
    from shared.db.session import get_db
    yield from get_db()


def _get_event_bus():
    return _event_bus


def _not_found(program_id: uuid.UUID, correlation_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": {"code": "PROGRAM_NOT_FOUND", "message": f"Program {program_id} not found", "correlation_id": correlation_id}},
    )


@router.post("", response_model=ProgramResponse, status_code=status.HTTP_201_CREATED)
async def create_program(
    body: ProgramCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
    event_bus=Depends(_get_event_bus),
) -> Any:
    correlation_id = str(uuid.uuid4())

    # BIN/PCN conflict check
    if body.bin_number:
        conflict = check_bin_pcn_conflict(
            current_user.tenant_id, body.bin_number, body.pcn, None, db
        )
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "BIN_PCN_CONFLICT", "message": f"BIN/PCN already in use by program {conflict}", "correlation_id": correlation_id}},
            )

    program = Program(
        tenant_id=current_user.tenant_id,
        name=body.name,
        program_type=body.program_type,
        client_id=body.client_id,
        bin_number=body.bin_number,
        pcn=body.pcn,
        group_id=body.group_id,
        effective_date=body.effective_date,
        termination_date=body.termination_date,
        created_by=current_user.id,
    )
    db.add(program)

    log_entry = ProgramActivityLog(
        tenant_id=current_user.tenant_id,
        program_id=program.id,
        entity_type="program",
        entity_id=program.id,
        action="created",
        performed_by=current_user.id,
        before_state=None,
        after_state={"status": "draft", "name": body.name},
        correlation_id=uuid.UUID(correlation_id),
    )
    db.add(log_entry)
    db.commit()
    db.refresh(program)

    await event_bus.publish(
        program_created_event(
            program_id=program.id,
            tenant_id=current_user.tenant_id,
            program_name=program.name,
            program_type=program.program_type,
            client_id=program.client_id,
            correlation_id=uuid.UUID(correlation_id),
        )
    )

    return program


@router.get("", response_model=list[ProgramResponse])
async def list_programs(
    status_filter: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
) -> Any:
    query = db.query(Program).filter(Program.tenant_id == current_user.tenant_id)
    if status_filter:
        query = query.filter(Program.status == status_filter)
    return query.order_by(Program.created_at.desc()).all()


@router.get("/{program_id}", response_model=ProgramResponse)
async def get_program(
    program_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
) -> Any:
    correlation_id = str(uuid.uuid4())
    program = db.query(Program).filter_by(id=program_id, tenant_id=current_user.tenant_id).first()
    if not program:
        raise _not_found(program_id, correlation_id)
    return program


@router.patch("/{program_id}", response_model=ProgramResponse)
async def update_program(
    program_id: uuid.UUID,
    body: ProgramUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
) -> Any:
    correlation_id = str(uuid.uuid4())
    program = db.query(Program).filter_by(id=program_id, tenant_id=current_user.tenant_id).first()
    if not program:
        raise _not_found(program_id, correlation_id)

    update_data = body.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(program, key, value)

    log_entry = ProgramActivityLog(
        tenant_id=current_user.tenant_id,
        program_id=program.id,
        entity_type="program",
        entity_id=program.id,
        action="updated",
        performed_by=current_user.id,
        before_state=None,
        after_state=update_data,
        correlation_id=uuid.UUID(correlation_id),
    )
    db.add(log_entry)
    db.commit()
    db.refresh(program)
    return program


@router.post("/{program_id}/status", response_model=ProgramResponse)
async def transition_status(
    program_id: uuid.UUID,
    body: ProgramStatusTransitionRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
    event_bus=Depends(_get_event_bus),
) -> Any:
    correlation_id = str(uuid.uuid4())
    program = db.query(Program).filter_by(id=program_id, tenant_id=current_user.tenant_id).first()
    if not program:
        raise _not_found(program_id, correlation_id)

    try:
        program = transition_program_status(
            program, body.new_status, current_user.id, db,
            correlation_id=uuid.UUID(correlation_id)
        )
    except ProgramStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_TRANSITION", "message": str(exc), "correlation_id": correlation_id}},
        ) from exc
    except OnboardingIncompleteError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "ONBOARDING_INCOMPLETE", "message": str(exc), "correlation_id": correlation_id}},
        ) from exc

    db.commit()
    db.refresh(program)

    # Publish status events
    reason = body.reason or ""
    if body.new_status == "active":
        await event_bus.publish(program_activated_event(program.id, current_user.tenant_id, correlation_id=uuid.UUID(correlation_id)))
    elif body.new_status == "suspended":
        await event_bus.publish(program_suspended_event(program.id, current_user.tenant_id, reason, correlation_id=uuid.UUID(correlation_id)))
    elif body.new_status == "terminated":
        await event_bus.publish(program_terminated_event(program.id, current_user.tenant_id, reason, correlation_id=uuid.UUID(correlation_id)))

    return program


# ---------------------------------------------------------------------------
# Program Drugs
# ---------------------------------------------------------------------------


@router.post("/{program_id}/drugs", response_model=ProgramDrugResponse, status_code=status.HTTP_201_CREATED)
async def add_program_drug(
    program_id: uuid.UUID,
    body: ProgramDrugAddRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
) -> Any:
    correlation_id = str(uuid.uuid4())
    program = db.query(Program).filter_by(id=program_id, tenant_id=current_user.tenant_id).first()
    if not program:
        raise _not_found(program_id, correlation_id)

    # Check for duplicate NDC
    existing = db.query(ProgramDrug).filter_by(
        program_id=program_id, tenant_id=current_user.tenant_id, ndc=body.ndc
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "DUPLICATE_NDC", "message": f"NDC {body.ndc} already in program", "correlation_id": correlation_id}},
        )

    from decimal import ROUND_HALF_UP, Decimal

    def _dec(v: str | None):
        if v is None:
            return None
        return Decimal(v).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    drug = ProgramDrug(
        tenant_id=current_user.tenant_id,
        program_id=program_id,
        ndc=body.ndc,
        gpi=body.gpi,
        drug_name=body.drug_name,
        copay_amount=_dec(body.copay_amount),
        per_fill_cap=_dec(body.per_fill_cap),
        annual_max=_dec(body.annual_max),
    )
    db.add(drug)
    db.commit()
    db.refresh(drug)
    return drug


@router.get("/{program_id}/drugs", response_model=list[ProgramDrugResponse])
async def list_program_drugs(
    program_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
) -> Any:
    correlation_id = str(uuid.uuid4())
    program = db.query(Program).filter_by(id=program_id, tenant_id=current_user.tenant_id).first()
    if not program:
        raise _not_found(program_id, correlation_id)
    return (
        db.query(ProgramDrug)
        .filter_by(program_id=program_id, tenant_id=current_user.tenant_id)
        .all()
    )


@router.delete("/{program_id}/drugs/{ndc}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_program_drug(
    program_id: uuid.UUID,
    ndc: str,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
) -> None:
    correlation_id = str(uuid.uuid4())
    program = db.query(Program).filter_by(id=program_id, tenant_id=current_user.tenant_id).first()
    if not program:
        raise _not_found(program_id, correlation_id)
    drug = db.query(ProgramDrug).filter_by(
        program_id=program_id, tenant_id=current_user.tenant_id, ndc=ndc
    ).first()
    if not drug:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "DRUG_NOT_FOUND", "message": f"NDC {ndc} not in program {program_id}", "correlation_id": correlation_id}},
        )
    db.delete(drug)
    db.commit()
