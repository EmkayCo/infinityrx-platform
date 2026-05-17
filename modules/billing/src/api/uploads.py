"""SP-1 Plan B Task 3 -- Upload resource router.

5 endpoints:
  POST   /api/v1/billing/uploads                  create
  GET    /api/v1/billing/uploads                  list (tenant-scoped)
  GET    /api/v1/billing/uploads/{id}             detail (PHI audit)
  GET    /api/v1/billing/uploads/{id}/claims      claims (PHI audit)
  POST   /api/v1/billing/uploads/{id}/supersede   immutable supersede

RBAC: POST + supersede = Operator + Approver; reads = all roles. Auditor blocked on writes.
Auth gate: Depends(get_current_user) -> 401 without valid JWT.
PHI controls: Cache-Control: no-store on every body containing row_errors or PHI surrogates.
Eventing: paysync.upload.parsed published after db.commit() via app.state.event_bus.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import select

from shared.auth.dependencies import CurrentUser, get_current_user
from src.api.dependencies import DBSession, TenantId
from src.events.upload_events import publish_upload_parsed
from src.models.tables import ClaimRecord, Upload, UploadStatus
from src.services.upload import (
    compute_sha256,
    find_existing_upload,
    parse_upload,
    supersede_upload,
    write_upload_file,
)

logger = logging.getLogger("billing.api.uploads")

router = APIRouter(prefix="/api/v1/billing/uploads", tags=["uploads"])

_AUDITOR_ROLE = "auditor"
_DEFAULT_UPLOAD_DIR = "./data/uploads"


def _emit_phi_audit(
    *, tenant_id: uuid.UUID, user_id: uuid.UUID, entity_id: uuid.UUID
) -> None:
    """Best-effort phi_access audit entry. Never fails the request."""
    try:
        from shared.audit.client import emit_phi_access  # noqa: PLC0415

        emit_phi_access(
            tenant_id=tenant_id,
            user_id=user_id,
            entity_type="upload",
            entity_id=entity_id,
        )
    except Exception:
        logger.error(
            "billing.phi_audit_failed",
            extra={
                "svc_entity_id": str(entity_id),
                "svc_tenant_id": str(tenant_id),
            },
        )


def _upload_to_dict(
    upload: Upload, *, include_row_errors: bool = False
) -> dict[str, Any]:
    # P1-contract: field names must match UploadSchema in packages/contract/src/impls/paysync/types.ts.
    # content_sha256 (not sha256), uploaded_by_user_id (not uploaded_by),
    # claim_count (not row_count), row_error_count (not error_count),
    # total_billed_amount (Decimal string or null).
    # UploadStatus enum values: received/parsing/validated/rejected/applied.
    # validation_failed maps to "rejected" for the TS contract.
    _STATUS_MAP = {
        "validation_failed": "rejected",
        "superseded": "applied",
    }
    contract_status = _STATUS_MAP.get(upload.status, upload.status)
    data: dict[str, Any] = {
        "id": str(upload.id),
        "tenant_id": str(upload.tenant_id),
        "filename": upload.filename,
        "content_sha256": upload.sha256,
        "status": contract_status,
        "claim_count": upload.row_count or 0,
        "row_error_count": upload.error_count or 0,
        "total_billed_amount": None,  # populated by billing cycle aggregation
        "uploaded_by_user_id": str(upload.uploaded_by),
        "uploaded_at": (
            upload.uploaded_at.isoformat() if upload.uploaded_at else None
        ),
    }
    if include_row_errors:
        data["row_errors"] = upload.row_errors or []
    return data


def _no_store(data: Any, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        content=data,
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


def _build_upload(
    *,
    upload_id: uuid.UUID,
    tenant_id: uuid.UUID,
    filename: str,
    sha256: str,
    file_size: int,
    mime_type: str,
    uploaded_by: uuid.UUID,
) -> Upload:
    return Upload(
        id=upload_id,
        tenant_id=tenant_id,
        filename=filename,
        sha256=sha256,
        file_size=file_size,
        mime_type=mime_type,
        uploaded_at=datetime.now(UTC),
        uploaded_by=uploaded_by,
        source_platform=None,
        status=UploadStatus.parsing.value,
    )


async def _publish_parsed(
    request: Request, *, upload: Upload, correlation_id: uuid.UUID
) -> None:
    """Best-effort post-commit publish. Never propagates failure to the client."""
    bus = getattr(request.app.state, "event_bus", None)
    if bus is None:
        return
    try:
        await publish_upload_parsed(
            bus, upload=upload, correlation_id=correlation_id
        )
    except Exception:
        logger.exception("billing.upload.publish_failed")


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_upload(
    request: Request,
    file: UploadFile,
    db: DBSession,
    tenant_id: TenantId,
    current_user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    if current_user.has_role(_AUDITOR_ROLE):
        raise HTTPException(status_code=403, detail="Auditors cannot upload files")

    content = await file.read()
    sha256 = compute_sha256(content)
    existing = find_existing_upload(db, tenant_id=tenant_id, sha256=sha256)
    if existing is not None:
        return _no_store(
            {
                "error": {
                    "code": "DUPLICATE_UPLOAD",
                    "message": "File already uploaded",
                    "existing_upload_id": str(existing.id),
                }
            },
            status_code=409,
        )

    upload_id = uuid.uuid4()
    base_dir = Path(os.getenv("PAYSYNC_UPLOAD_DIR", _DEFAULT_UPLOAD_DIR))
    filename = file.filename or "upload.csv"
    write_upload_file(
        base_dir=base_dir,
        tenant_id=tenant_id,
        upload_id=upload_id,
        filename=filename,
        content=content,
    )

    upload = _build_upload(
        upload_id=upload_id,
        tenant_id=tenant_id,
        filename=filename,
        sha256=sha256,
        file_size=len(content),
        mime_type=file.content_type or "application/octet-stream",
        uploaded_by=current_user.id,
    )
    db.add(upload)
    db.flush()
    parse_upload(db, upload=upload, file_bytes=content)
    db.commit()

    await _publish_parsed(request, upload=upload, correlation_id=uuid.uuid4())

    return _no_store(_upload_to_dict(upload, include_row_errors=True), status_code=201)


@router.get("")
async def list_uploads(
    db: DBSession,
    tenant_id: TenantId,
    current_user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    stmt = (
        select(Upload)
        .where(Upload.tenant_id == tenant_id)
        .order_by(Upload.uploaded_at.desc())
    )
    uploads = db.execute(stmt).scalars().all()
    results = [_upload_to_dict(u) for u in uploads]
    # P2-pagination: UploadListResponseSchema expects { results, next_cursor, total }.
    return JSONResponse(content={"results": results, "total": len(results)})


@router.get("/{upload_id}")
async def get_upload(
    upload_id: uuid.UUID,
    db: DBSession,
    tenant_id: TenantId,
    current_user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    stmt = select(Upload).where(
        Upload.id == upload_id, Upload.tenant_id == tenant_id
    )
    upload = db.execute(stmt).scalar_one_or_none()
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload not found")
    _emit_phi_audit(
        tenant_id=tenant_id, user_id=current_user.id, entity_id=upload_id
    )
    return _no_store(_upload_to_dict(upload, include_row_errors=True))


@router.get("/{upload_id}/claims")
async def get_upload_claims(
    upload_id: uuid.UUID,
    db: DBSession,
    tenant_id: TenantId,
    current_user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    stmt = select(Upload).where(
        Upload.id == upload_id, Upload.tenant_id == tenant_id
    )
    upload = db.execute(stmt).scalar_one_or_none()
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload not found")
    _emit_phi_audit(
        tenant_id=tenant_id, user_id=current_user.id, entity_id=upload_id
    )
    claims_stmt = select(ClaimRecord).where(
        ClaimRecord.upload_id == upload_id,
        ClaimRecord.tenant_id == tenant_id,
    )
    claims = db.execute(claims_stmt).scalars().all()
    # P2-claims-shape: getClaims contract expects { results, next_cursor, total }
    # and field name "claim_id" (contract alias for auth_number — the business
    # identifier stored in ClaimRecord.auth_number per Plan B data model).
    results = [
        {
            "id": str(c.id),
            "claim_id": c.auth_number,
            "claim_type": c.claim_type,
            "date_of_service": (
                c.date_of_service.isoformat() if c.date_of_service else None
            ),
            "ndc": c.ndc,
            "npi": c.pharmacy_npi,
            "amount_billed": (
                str(c.amount_billed) if c.amount_billed is not None else None
            ),
            "status": c.status,
        }
        for c in claims
    ]
    return _no_store({"results": results, "total": len(results)})


@router.post("/{upload_id}/supersede")
async def supersede_upload_endpoint(
    request: Request,
    upload_id: uuid.UUID,
    file: UploadFile,
    db: DBSession,
    tenant_id: TenantId,
    current_user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    if current_user.has_role(_AUDITOR_ROLE):
        raise HTTPException(
            status_code=403, detail="Auditors cannot supersede uploads"
        )
    stmt = select(Upload).where(
        Upload.id == upload_id, Upload.tenant_id == tenant_id
    )
    old_upload = db.execute(stmt).scalar_one_or_none()
    if old_upload is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    content = await file.read()
    sha256 = compute_sha256(content)
    # uq_uploads_tenant_sha256 forbids reusing identical content for ANY upload
    # on this tenant, including the one being superseded.  Return 409 rather
    # than attempting an insert that the DB will reject anyway.
    existing = find_existing_upload(db, tenant_id=tenant_id, sha256=sha256)
    if existing is not None:
        return _no_store(
            {
                "error": {
                    "code": "DUPLICATE_UPLOAD",
                    "message": "File already uploaded",
                    "existing_upload_id": str(existing.id),
                }
            },
            status_code=409,
        )

    new_upload_id = uuid.uuid4()
    base_dir = Path(os.getenv("PAYSYNC_UPLOAD_DIR", _DEFAULT_UPLOAD_DIR))
    filename = file.filename or "upload.csv"
    write_upload_file(
        base_dir=base_dir,
        tenant_id=tenant_id,
        upload_id=new_upload_id,
        filename=filename,
        content=content,
    )

    new_upload = _build_upload(
        upload_id=new_upload_id,
        tenant_id=tenant_id,
        filename=filename,
        sha256=sha256,
        file_size=len(content),
        mime_type=file.content_type or "application/octet-stream",
        uploaded_by=current_user.id,
    )
    db.add(new_upload)
    db.flush()
    # P2-supersede: void old claim rows before parsing so the unique constraint
    # (tenant_id, auth_number) doesn't fire when the replacement file reuses
    # the same claim_id values.  supersede_upload deletes old ClaimRecord rows
    # and marks the old upload superseded; parse_upload then inserts fresh rows.
    supersede_upload(db, old_upload=old_upload, new_upload=new_upload)
    parse_upload(db, upload=new_upload, file_bytes=content)
    db.commit()

    await _publish_parsed(request, upload=new_upload, correlation_id=uuid.uuid4())

    return _no_store(_upload_to_dict(new_upload, include_row_errors=True))
