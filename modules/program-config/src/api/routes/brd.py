"""BRD Template + Submission routes.

Endpoints:
  GET/POST/PATCH  /brd-templates
  POST  /brd-submissions (upload/submit)
  GET   /brd-submissions/{id}
  POST  /brd-submissions/{id}/validate
  POST  /brd-submissions/{id}/review
  POST  /brd-submissions/{id}/sign
  GET   /brd-submissions/{id}/diff
  POST  /brd-submissions/{id}/apply
  POST  /brd-submissions/{id}/rollback
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from shared.auth.dependencies import CurrentUser, get_current_user
from shared.events.in_memory_bus import InMemoryEventBus

from src.api.schemas.programs import (
    BrdDiffResponse,
    BrdReviewRequest,
    BrdSignRequest,
    BrdSubmissionResponse,
    BrdSubmitRequest,
    BrdTemplateCreateRequest,
    BrdTemplateResponse,
    BrdValidationResponse,
)
from src.events.publishers import brd_approved_event, brd_applied_event, brd_submitted_event
from src.models.tables import BrdSubmission, BrdTemplate, Program, ProgramActivityLog
from src.services.brd_engine import (
    build_default_template_schema,
    compute_brd_diff,
    compute_brd_signature_hash,
    parse_brd_into_config,
    validate_brd_submission,
)
from src.services.program_service import (
    BinPcnConflictError,
    apply_brd_to_program,
)

router = APIRouter(tags=["brd"])

_event_bus = InMemoryEventBus()


def _get_db():  # pragma: no cover
    from shared.db.session import get_db
    yield from get_db()


def _get_event_bus():
    return _event_bus


def _not_found(entity: str, eid: uuid.UUID, corr: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": {"code": f"{entity.upper()}_NOT_FOUND", "message": f"{entity} {eid} not found", "correlation_id": corr}},
    )


# ---------------------------------------------------------------------------
# BRD Templates
# ---------------------------------------------------------------------------


@router.post("/brd-templates", response_model=BrdTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_brd_template(
    body: BrdTemplateCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
) -> Any:
    correlation_id = str(uuid.uuid4())

    # Check slug uniqueness within tenant
    existing = db.query(BrdTemplate).filter_by(
        tenant_id=current_user.tenant_id, slug=body.slug
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "TEMPLATE_SLUG_EXISTS", "message": f"Template slug '{body.slug}' already exists", "correlation_id": correlation_id}},
        )

    template = BrdTemplate(
        tenant_id=current_user.tenant_id,
        name=body.name,
        slug=body.slug,
        program_type=body.program_type,
        form_builder_schema=body.form_builder_schema,
        created_by=current_user.id,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.get("/brd-templates", response_model=list[BrdTemplateResponse])
async def list_brd_templates(
    program_type: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
) -> Any:
    query = db.query(BrdTemplate).filter_by(tenant_id=current_user.tenant_id, is_active=True)
    if program_type:
        query = query.filter(BrdTemplate.program_type == program_type)
    return query.all()


@router.get("/brd-templates/{template_id}", response_model=BrdTemplateResponse)
async def get_brd_template(
    template_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
) -> Any:
    correlation_id = str(uuid.uuid4())
    template = db.query(BrdTemplate).filter_by(
        id=template_id, tenant_id=current_user.tenant_id
    ).first()
    if not template:
        raise _not_found("BrdTemplate", template_id, correlation_id)
    return template


@router.get("/brd-templates/defaults/{program_type}", response_model=dict[str, Any])
async def get_default_template_schema(
    program_type: str,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: ARG001
) -> Any:
    try:
        schema = build_default_template_schema(program_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_PROGRAM_TYPE", "message": str(exc), "correlation_id": str(uuid.uuid4())}},
        ) from exc
    return schema


# ---------------------------------------------------------------------------
# BRD Submissions
# ---------------------------------------------------------------------------


@router.post("/brd-submissions", response_model=BrdSubmissionResponse, status_code=status.HTTP_201_CREATED)
async def submit_brd(
    body: BrdSubmitRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
    event_bus=Depends(_get_event_bus),
) -> Any:
    correlation_id = str(uuid.uuid4())

    template = db.query(BrdTemplate).filter_by(
        id=body.template_id, tenant_id=current_user.tenant_id
    ).first()
    if not template:
        raise _not_found("BrdTemplate", body.template_id, correlation_id)

    # Validate before submit
    validation = validate_brd_submission(template.form_builder_schema, body.parsed_data)

    submission = BrdSubmission(
        tenant_id=current_user.tenant_id,
        template_id=body.template_id,
        template_version_at_upload=template.version,
        program_id=body.program_id,
        submitted_by=current_user.id,
        status="submitted",
        parsed_data=body.parsed_data,
        validation_results=validation,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    await event_bus.publish(
        brd_submitted_event(
            submission_id=submission.id,
            program_id=body.program_id,
            tenant_id=current_user.tenant_id,
            correlation_id=uuid.UUID(correlation_id),
        )
    )

    return submission


@router.get("/brd-submissions/{submission_id}", response_model=BrdSubmissionResponse)
async def get_brd_submission(
    submission_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
) -> Any:
    correlation_id = str(uuid.uuid4())
    submission = db.query(BrdSubmission).filter_by(
        id=submission_id, tenant_id=current_user.tenant_id
    ).first()
    if not submission:
        raise _not_found("BrdSubmission", submission_id, correlation_id)
    return submission


@router.post("/brd-submissions/{submission_id}/validate", response_model=BrdValidationResponse)
async def validate_brd(
    submission_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
) -> Any:
    correlation_id = str(uuid.uuid4())
    submission = db.query(BrdSubmission).filter_by(
        id=submission_id, tenant_id=current_user.tenant_id
    ).first()
    if not submission:
        raise _not_found("BrdSubmission", submission_id, correlation_id)

    template = db.query(BrdTemplate).filter_by(
        id=submission.template_id, tenant_id=current_user.tenant_id
    ).first()
    if not template:
        raise _not_found("BrdTemplate", submission.template_id, correlation_id)

    result = validate_brd_submission(template.form_builder_schema, submission.parsed_data)
    # Update stored validation results
    submission.validation_results = result
    db.commit()
    return result


@router.post("/brd-submissions/{submission_id}/review", response_model=BrdSubmissionResponse)
async def review_brd(
    submission_id: uuid.UUID,
    body: BrdReviewRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
    event_bus=Depends(_get_event_bus),
) -> Any:
    correlation_id = str(uuid.uuid4())
    submission = db.query(BrdSubmission).filter_by(
        id=submission_id, tenant_id=current_user.tenant_id
    ).first()
    if not submission:
        raise _not_found("BrdSubmission", submission_id, correlation_id)

    if submission.status not in ("submitted", "under_review"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_STATUS", "message": f"Cannot review BRD in status {submission.status!r}", "correlation_id": correlation_id}},
        )

    valid_actions = {"approve", "reject", "request_changes"}
    if body.action not in valid_actions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_ACTION", "message": f"action must be one of {valid_actions}", "correlation_id": correlation_id}},
        )

    status_map = {
        "approve": "approved",
        "reject": "submitted",  # Reject returns to submitted for resubmission
        "request_changes": "change_requested",
    }
    submission.status = status_map[body.action]
    submission.reviewer_id = current_user.id
    submission.review_notes = body.notes

    db.commit()
    db.refresh(submission)

    if body.action == "approve":
        await event_bus.publish(
            brd_approved_event(
                submission_id=submission.id,
                program_id=submission.program_id,
                tenant_id=current_user.tenant_id,
                correlation_id=uuid.UUID(correlation_id),
            )
        )

    return submission


@router.post("/brd-submissions/{submission_id}/sign", response_model=BrdSubmissionResponse)
async def sign_brd(
    submission_id: uuid.UUID,
    body: BrdSignRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
) -> Any:
    correlation_id = str(uuid.uuid4())
    submission = db.query(BrdSubmission).filter_by(
        id=submission_id, tenant_id=current_user.tenant_id
    ).first()
    if not submission:
        raise _not_found("BrdSubmission", submission_id, correlation_id)

    if submission.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "NOT_APPROVED", "message": "BRD must be in 'approved' status before signing", "correlation_id": correlation_id}},
        )

    now = datetime.now(UTC)
    sig_hash = compute_brd_signature_hash(
        submission_id=submission.id,
        parsed_data=submission.parsed_data,
        signer_id=current_user.id,
        timestamp=now,
    )
    submission.signature_hash = sig_hash
    submission.signed_at = now
    submission.status = "signed"

    db.commit()
    db.refresh(submission)
    return submission


@router.get("/brd-submissions/{submission_id}/diff", response_model=BrdDiffResponse)
async def preview_brd_diff(
    submission_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
) -> Any:
    """Show what will change when this BRD is applied to the program."""
    correlation_id = str(uuid.uuid4())
    submission = db.query(BrdSubmission).filter_by(
        id=submission_id, tenant_id=current_user.tenant_id
    ).first()
    if not submission:
        raise _not_found("BrdSubmission", submission_id, correlation_id)

    if submission.status not in ("signed", "approved"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "NOT_APPROVED_OR_SIGNED", "message": "BRD must be approved or signed to preview diff", "correlation_id": correlation_id}},
        )

    # Build proposed config from submission
    program_id = submission.program_id or uuid.UUID("00000000-0000-0000-0000-000000000000")
    proposed_config = parse_brd_into_config(
        submission.parsed_data, program_id, current_user.tenant_id
    )

    # Get existing config from program (if linked)
    existing_config: dict[str, Any] = {"drug_entries": [], "bin_pcn": {}}
    if submission.program_id:
        from src.models.tables import ProgramDrug
        existing_drugs = db.query(ProgramDrug).filter_by(
            program_id=submission.program_id, tenant_id=current_user.tenant_id
        ).all()
        existing_config["drug_entries"] = [
            {"ndc": d.ndc, "copay_amount": str(d.copay_amount) if d.copay_amount else None}
            for d in existing_drugs
        ]
        program = db.query(Program).filter_by(
            id=submission.program_id, tenant_id=current_user.tenant_id
        ).first()
        if program:
            existing_config["bin_pcn"] = {"bin_number": program.bin_number, "pcn": program.pcn}

    diff = compute_brd_diff(existing_config, proposed_config)
    return diff


@router.post("/brd-submissions/{submission_id}/apply", response_model=BrdSubmissionResponse)
async def apply_brd(
    submission_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
    event_bus=Depends(_get_event_bus),
) -> Any:
    """Atomically apply a signed BRD to its linked program."""
    correlation_id = str(uuid.uuid4())
    submission = db.query(BrdSubmission).filter_by(
        id=submission_id, tenant_id=current_user.tenant_id
    ).first()
    if not submission:
        raise _not_found("BrdSubmission", submission_id, correlation_id)

    if submission.status != "signed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "NOT_SIGNED", "message": "BRD must be signed before applying", "correlation_id": correlation_id}},
        )

    if not submission.program_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "NO_PROGRAM_LINKED", "message": "BRD must be linked to a program before applying", "correlation_id": correlation_id}},
        )

    program = db.query(Program).filter_by(
        id=submission.program_id, tenant_id=current_user.tenant_id
    ).first()
    if not program:
        raise _not_found("Program", submission.program_id, correlation_id)

    config = parse_brd_into_config(
        submission.parsed_data, program.id, current_user.tenant_id
    )

    try:
        apply_brd_to_program(program, config, current_user.id, db, correlation_id=uuid.UUID(correlation_id))
    except BinPcnConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "BIN_PCN_CONFLICT", "message": str(exc), "correlation_id": correlation_id}},
        ) from exc

    submission.status = "applied"
    submission.applied_at = datetime.now(UTC)

    db.commit()
    db.refresh(submission)

    await event_bus.publish(
        brd_applied_event(
            submission_id=submission.id,
            program_id=program.id,
            tenant_id=current_user.tenant_id,
            correlation_id=uuid.UUID(correlation_id),
        )
    )

    return submission


@router.post("/brd-submissions/{submission_id}/rollback", response_model=dict[str, str])
async def rollback_brd(
    submission_id: uuid.UUID,
    snapshot: dict[str, Any],
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
) -> Any:
    """Roll back a previously applied BRD to the snapshot state."""
    correlation_id = str(uuid.uuid4())
    submission = db.query(BrdSubmission).filter_by(
        id=submission_id, tenant_id=current_user.tenant_id
    ).first()
    if not submission:
        raise _not_found("BrdSubmission", submission_id, correlation_id)

    if not submission.program_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "NO_PROGRAM_LINKED", "message": "Submission has no linked program", "correlation_id": correlation_id}},
        )

    program = db.query(Program).filter_by(
        id=submission.program_id, tenant_id=current_user.tenant_id
    ).first()
    if not program:
        raise _not_found("Program", submission.program_id, correlation_id)

    from src.services.program_service import rollback_brd_apply
    rollback_brd_apply(program, snapshot, current_user.id, db)
    submission.status = "signed"  # Back to signed (not applied)
    submission.applied_at = None

    db.commit()
    return {"status": "rolled_back", "submission_id": str(submission_id)}
