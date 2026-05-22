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

import json
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
_WRITE_ROLES = frozenset({"operator", "approver"})
_DEFAULT_UPLOAD_DIR = "./data/uploads"

# Hardening limits for x-column-mapping header (FIX 2).
_MAPPING_MAX_BYTES = 8 * 1024  # 8 KB
_MAPPING_MAX_KEYS = 64


def _parse_column_mapping_header(request: Request) -> dict[str, str] | None:
    """Parse and validate the optional x-column-mapping JSON header.

    Returns {canonical_field: user_column_name} or None when header absent.
    Raises HTTPException 400 on:
      - header > 8 KB
      - malformed JSON
      - value is not a JSON object
      - more than 64 mapping keys
      - same user column mapped to multiple canonical fields (ambiguous)
      - user column name is itself a canonical field name (canonical-overwrite collision)
    """
    from src.services.upload import _REQUIRED_COLUMNS  # noqa: PLC0415

    raw = request.headers.get("x-column-mapping")
    if raw is None:
        return None

    # Size cap before JSON parsing to prevent memory DoS.
    if len(raw.encode("utf-8")) > _MAPPING_MAX_BYTES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_COLUMN_MAPPING",
                    "message": (
                        f"x-column-mapping header exceeds "
                        f"{_MAPPING_MAX_BYTES // 1024} KB limit"
                    ),
                }
            },
        )

    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_COLUMN_MAPPING",
                    "message": "x-column-mapping header is not valid JSON",
                }
            },
        )

    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_COLUMN_MAPPING",
                    "message": "x-column-mapping must be a JSON object",
                }
            },
        )

    if len(parsed) > _MAPPING_MAX_KEYS:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_COLUMN_MAPPING",
                    "message": (
                        f"x-column-mapping exceeds {_MAPPING_MAX_KEYS} key limit"
                    ),
                }
            },
        )

    mapping: dict[str, str] = {str(k): str(v) for k, v in parsed.items()}

    # Ambiguity: same user column mapped to multiple canonical fields.
    seen_user_cols: dict[str, str] = {}
    for canonical, user_col in mapping.items():
        if user_col in seen_user_cols:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "INVALID_COLUMN_MAPPING",
                        "message": (
                            f"Ambiguous mapping: user column '{user_col}' "
                            f"is mapped to both "
                            f"'{seen_user_cols[user_col]}' and '{canonical}'"
                        ),
                    }
                },
            )
        seen_user_cols[user_col] = canonical

    # Collision: a user column whose name is itself a canonical field name would
    # silently overwrite a real money/identity column.  Reject explicitly.
    canonical_set = set(_REQUIRED_COLUMNS)
    for canonical, user_col in mapping.items():
        if user_col != canonical and user_col in canonical_set:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "INVALID_COLUMN_MAPPING",
                        "message": (
                            f"Mapping collision: user column '{user_col}' is a "
                            f"canonical field name. This would silently overwrite "
                            f"the real '{user_col}' column. Rename your column or "
                            f"remove the mapping entry."
                        ),
                    }
                },
            )

    return mapping


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
    upload: Upload, *, include_row_errors: bool = False, db: Any = None
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
    # Compute total_billed_amount from ClaimRecord rows when a db session is available.
    total_billed: str | None = None
    if db is not None:
        from decimal import ROUND_HALF_UP, Decimal  # noqa: PLC0415
        from sqlalchemy import func as sa_func  # noqa: PLC0415
        raw = db.execute(
            select(sa_func.sum(ClaimRecord.amount_billed)).where(
                ClaimRecord.upload_id == upload.id,
                ClaimRecord.tenant_id == upload.tenant_id,
            )
        ).scalar()
        if raw is not None:
            # .claude/rules/financial-precision.md: ROUND_HALF_UP required on every quantize.
            total_billed = str(
                Decimal(str(raw)).quantize(Decimal("0.0000"), rounding=ROUND_HALF_UP)
            )
    data: dict[str, Any] = {
        "id": str(upload.id),
        "tenant_id": str(upload.tenant_id),
        "filename": upload.filename,
        "content_sha256": upload.sha256,
        "status": contract_status,
        "claim_count": upload.row_count or 0,
        "row_error_count": upload.error_count or 0,
        "total_billed_amount": total_billed,
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
    # P1-rbac: require operator or approver explicitly; deny everyone else.
    if not any(current_user.has_role(r) for r in _WRITE_ROLES):
        raise HTTPException(status_code=403, detail="Only operators and approvers can upload files")

    # FIX 2: centralised header parser enforces 8 KB size cap, 64-key limit,
    # ambiguity check (same user col -> two canonicals), and canonical-overwrite
    # collision check.  Raises 400 on violation; returns None when header absent.
    # Replaces old inline parse that silently swallowed malformed JSON.
    column_mapping = _parse_column_mapping_header(request)

    content = await file.read()
    sha256 = compute_sha256(content)
    existing = find_existing_upload(db, tenant_id=tenant_id, sha256=sha256)
    if existing is not None:
        return _no_store(
            {
                "error": {
                    "code": "DUPLICATE_UPLOAD",
                    "message": "File already uploaded",
                    "correlation_id": str(uuid.uuid4()),
                    "details": {"existing_upload_id": str(existing.id)},
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
    # P2-create-parse: wrap parse_upload so malformed files return 422 (not 500).
    # Mirrors the supersede path pattern.
    try:
        parse_upload(db, upload=upload, file_bytes=content, column_mapping=column_mapping)
    except ValueError as exc:
        db.rollback()
        return _no_store(
            {
                "error": {
                    "code": "PARSE_ERROR",
                    "message": f"File is invalid: {exc}",
                    "correlation_id": str(uuid.uuid4()),
                }
            },
            status_code=422,
        )
    if upload.status == UploadStatus.validation_failed.value:
        db.rollback()
        return _no_store(
            {
                "error": {
                    "code": "VALIDATION_FAILED",
                    "message": "File failed validation -- all rows rejected.",
                    "correlation_id": str(uuid.uuid4()),
                    "details": {
                        "row_error_count": upload.error_count or 0,
                        "row_errors": upload.row_errors or [],
                    },
                }
            },
            status_code=422,
        )
    db.commit()

    await _publish_parsed(request, upload=upload, correlation_id=uuid.uuid4())

    return _no_store(_upload_to_dict(upload, include_row_errors=True, db=db), status_code=201)


@router.get("")
async def list_uploads(
    db: DBSession,
    tenant_id: TenantId,
    current_user: CurrentUser = Depends(get_current_user),
    status: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> JSONResponse:
    # Map contract status values back to DB values for filtering.
    _CONTRACT_TO_DB = {"rejected": "validation_failed", "applied": "superseded"}
    db_status = _CONTRACT_TO_DB.get(status, status) if status else None
    stmt = select(Upload).where(Upload.tenant_id == tenant_id)
    if db_status:
        stmt = stmt.where(Upload.status == db_status)
    # P1-cursor: apply cursor as a keyset filter (uploaded_at < cursor ISO string).
    if cursor:
        from datetime import datetime  # noqa: PLC0415
        try:
            cursor_dt = datetime.fromisoformat(cursor)
            stmt = stmt.where(Upload.uploaded_at < cursor_dt)
        except ValueError:
            pass  # malformed cursor -- ignore and return from the start
    stmt = stmt.order_by(Upload.uploaded_at.desc()).limit(limit + 1)
    uploads = list(db.execute(stmt).scalars().all())
    body: dict[str, object] = {"results": [_upload_to_dict(u) for u in uploads[:limit]], "total": len(uploads[:limit])}
    if len(uploads) > limit:
        body["next_cursor"] = str(uploads[limit - 1].uploaded_at.isoformat())
    return JSONResponse(content=body)


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
    return _no_store(_upload_to_dict(upload, include_row_errors=True, db=db))


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
    # P1-rbac: require operator or approver explicitly.
    if not any(current_user.has_role(r) for r in _WRITE_ROLES):
        raise HTTPException(
            status_code=403, detail="Only operators and approvers can supersede uploads"
        )
    stmt = select(Upload).where(
        Upload.id == upload_id, Upload.tenant_id == tenant_id
    )
    old_upload = db.execute(stmt).scalar_one_or_none()
    if old_upload is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    # FIX 1: read x-column-mapping so a supersede with non-standard headers
    # goes through the same mapping pipeline as create_upload.  Without this,
    # the replacement file's parse_upload call misses the mapping and 422s.
    column_mapping = _parse_column_mapping_header(request)

    content = await file.read()
    sha256 = compute_sha256(content)
    existing = find_existing_upload(db, tenant_id=tenant_id, sha256=sha256)
    if existing is not None:
        return _no_store(
            {
                "error": {
                    "code": "DUPLICATE_UPLOAD",
                    "message": "File already uploaded",
                    "correlation_id": str(uuid.uuid4()),
                    "details": {"existing_upload_id": str(existing.id)},
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
    try:
        supersede_upload(db, old_upload=old_upload, new_upload=new_upload)
    except ValueError as exc:
        msg = str(exc)
        if "CLAIMS_IN_AP_PROCESSING" in msg:
            return _no_store(
                {
                    "error": {
                        "code": "CLAIMS_IN_AP_PROCESSING",
                        "message": (
                            "Cannot supersede: one or more claims from this upload "
                            "are already in AP payment processing. Void or settle "
                            "those AP records before superseding."
                        ),
                        "correlation_id": str(uuid.uuid4()),
                    }
                },
                status_code=409,
            )
        raise
    # FIX 1: forward column_mapping so non-standard-header replacement files succeed.
    try:
        parse_upload(db, upload=new_upload, file_bytes=content, column_mapping=column_mapping)
    except ValueError as exc:
        db.rollback()
        return _no_store(
            {
                "error": {
                    "code": "PARSE_ERROR",
                    "message": f"Replacement file is invalid: {exc}",
                    "correlation_id": str(uuid.uuid4()),
                }
            },
            status_code=422,
        )
    if new_upload.status == UploadStatus.validation_failed.value:
        db.rollback()
        return _no_store(
            {
                "error": {
                    "code": "VALIDATION_FAILED",
                    "message": (
                        "Replacement file failed validation -- all rows rejected. "
                        "Original upload and claims are preserved."
                    ),
                    "correlation_id": str(uuid.uuid4()),
                    "details": {
                        "row_error_count": new_upload.error_count or 0,
                        "row_errors": new_upload.row_errors or [],
                    },
                }
            },
            status_code=422,
        )
    db.commit()

    await _publish_parsed(request, upload=new_upload, correlation_id=uuid.uuid4())

    return _no_store(_upload_to_dict(new_upload, include_row_errors=True, db=db))
