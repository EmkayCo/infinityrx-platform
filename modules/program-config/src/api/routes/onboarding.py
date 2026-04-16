"""Onboarding workflow routes.

Endpoints:
  POST  /onboarding/{program_id} — create workflow for a program
  GET   /onboarding/{program_id} — get workflow status
  POST  /onboarding/{program_id}/steps — complete a step
  GET   /onboarding/dashboard — aggregate dashboard
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from shared.auth.dependencies import CurrentUser, get_current_user
from shared.events.in_memory_bus import InMemoryEventBus

from src.api.schemas.programs import (
    OnboardingDashboardEntry,
    OnboardingStepCompleteRequest,
    OnboardingWorkflowResponse,
)
from src.events.publishers import onboarding_go_live_event, onboarding_step_completed_event
from src.models.tables import (
    OnboardingStepLog,
    OnboardingWorkflow,
    Program,
    ProgramActivityLog,
)
from src.services.onboarding import (
    OnboardingError,
    advance_step,
    build_default_steps,
    identify_bottlenecks,
    is_onboarding_complete,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

_event_bus = InMemoryEventBus()


def _get_db():  # pragma: no cover
    from shared.db.session import get_db
    yield from get_db()


def _get_event_bus():
    return _event_bus


@router.post("/{program_id}", response_model=OnboardingWorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_onboarding_workflow(
    program_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
) -> Any:
    correlation_id = str(uuid.uuid4())

    program = db.query(Program).filter_by(
        id=program_id, tenant_id=current_user.tenant_id
    ).first()
    if not program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "PROGRAM_NOT_FOUND", "message": f"Program {program_id} not found", "correlation_id": correlation_id}},
        )

    existing = db.query(OnboardingWorkflow).filter_by(
        program_id=program_id, tenant_id=current_user.tenant_id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "WORKFLOW_EXISTS", "message": "Onboarding workflow already exists for this program", "correlation_id": correlation_id}},
        )

    workflow = OnboardingWorkflow(
        tenant_id=current_user.tenant_id,
        program_id=program_id,
        status="in_progress",
        steps=build_default_steps(),
    )
    db.add(workflow)

    log_entry = ProgramActivityLog(
        tenant_id=current_user.tenant_id,
        program_id=program_id,
        entity_type="onboarding_workflow",
        entity_id=workflow.id,
        action="created",
        performed_by=current_user.id,
        before_state=None,
        after_state={"status": "in_progress"},
        correlation_id=uuid.UUID(correlation_id),
    )
    db.add(log_entry)
    db.commit()
    db.refresh(workflow)
    return workflow


@router.get("/dashboard", response_model=list[OnboardingDashboardEntry])
async def get_onboarding_dashboard(
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
) -> Any:
    """Aggregate dashboard: all programs in onboarding with status per step."""
    workflows = db.query(OnboardingWorkflow).filter(
        OnboardingWorkflow.tenant_id == current_user.tenant_id,
        OnboardingWorkflow.status.in_(["in_progress", "not_started", "blocked"]),
    ).all()

    entries = []
    for wf in workflows:
        program = db.query(Program).filter_by(
            id=wf.program_id, tenant_id=current_user.tenant_id
        ).first()
        if not program:
            continue

        steps = wf.steps or []
        total = len(steps)
        completed = sum(1 for s in steps if s.get("status") == "completed")
        pct = (completed / total * 100) if total > 0 else 0.0
        bottlenecks = identify_bottlenecks(steps)

        entries.append(
            OnboardingDashboardEntry(
                program_id=program.id,
                program_name=program.name,
                workflow_id=wf.id,
                status=wf.status,
                current_step=wf.current_step,
                total_steps=total,
                bottlenecks=bottlenecks,
                percent_complete=round(pct, 1),
            )
        )
    return entries


@router.get("/{program_id}", response_model=OnboardingWorkflowResponse)
async def get_onboarding_workflow(
    program_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
) -> Any:
    correlation_id = str(uuid.uuid4())
    workflow = db.query(OnboardingWorkflow).filter_by(
        program_id=program_id, tenant_id=current_user.tenant_id
    ).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "WORKFLOW_NOT_FOUND", "message": f"No workflow found for program {program_id}", "correlation_id": correlation_id}},
        )
    return workflow


@router.post("/{program_id}/steps", response_model=OnboardingWorkflowResponse)
async def complete_onboarding_step(
    program_id: uuid.UUID,
    body: OnboardingStepCompleteRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
    event_bus=Depends(_get_event_bus),
) -> Any:
    correlation_id = str(uuid.uuid4())
    workflow = db.query(OnboardingWorkflow).filter_by(
        program_id=program_id, tenant_id=current_user.tenant_id
    ).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "WORKFLOW_NOT_FOUND", "message": f"No workflow found for program {program_id}", "correlation_id": correlation_id}},
        )

    try:
        updated_steps, new_current = advance_step(
            workflow.steps, body.step_number, body.action, body.notes
        )
    except OnboardingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "ONBOARDING_ERROR", "message": str(exc), "correlation_id": correlation_id}},
        ) from exc

    # Find completed step details
    completed_step = next(
        (s for s in workflow.steps if s["step_number"] == body.step_number), {}
    )

    workflow.steps = updated_steps
    workflow.current_step = new_current

    # Check if go-live step completed
    is_go_live = completed_step.get("name") == "go_live_confirmed"
    if is_go_live:
        from datetime import UTC, datetime
        workflow.go_live_date = datetime.now(UTC)

    # Check if all required steps complete → mark workflow done
    if is_onboarding_complete(updated_steps):
        workflow.status = "completed"

    # Log the step
    step_log = OnboardingStepLog(
        tenant_id=current_user.tenant_id,
        workflow_id=workflow.id,
        step_number=body.step_number,
        step_name=completed_step.get("name", f"step_{body.step_number}"),
        action=body.action,
        performed_by=current_user.id,
        notes=body.notes,
    )
    db.add(step_log)
    db.commit()
    db.refresh(workflow)

    # Publish events
    await event_bus.publish(
        onboarding_step_completed_event(
            workflow_id=workflow.id,
            program_id=program_id,
            tenant_id=current_user.tenant_id,
            step_number=body.step_number,
            step_name=completed_step.get("name", f"step_{body.step_number}"),
            correlation_id=uuid.UUID(correlation_id),
        )
    )

    if is_go_live and workflow.go_live_date:
        await event_bus.publish(
            onboarding_go_live_event(
                workflow_id=workflow.id,
                program_id=program_id,
                tenant_id=current_user.tenant_id,
                go_live_date=workflow.go_live_date.isoformat(),
                correlation_id=uuid.UUID(correlation_id),
            )
        )

    return workflow
