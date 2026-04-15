"""Enrollment file upload, preview, and processing routes.

POST /members/enrollment
  - Content-Type: text/csv            → csv_parser
  - Content-Type: application/edi-x12 → edi_834_parser
  - other                             → 400

GET /enrollment/files              → list enrollment files
GET /enrollment/files/{file_id}    → get file status
"""
from __future__ import annotations

import io
import logging
import uuid
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.tables import EnrollmentFile
from src.services.csv_parser import CsvEnrollmentParser, FieldMapping
from src.services.edi_834_parser import Edi834Parser
from shared.db.tenant_context import current_tenant_id

logger = logging.getLogger("member-management.routes.enrollment")

router = APIRouter(prefix="/enrollment", tags=["enrollment"])

_edi_parser = Edi834Parser()

_DEFAULT_FIELD_MAPPING = FieldMapping(
    member_id="member_id",
    first_name="first_name",
    last_name="last_name",
    date_of_birth="date_of_birth",
    gender="gender",
    effective_date="effective_date",
    rx_bin="rx_bin",
    rx_pcn="rx_pcn",
    rx_group="rx_group",
    action="action",
    termination_date="termination_date",
    middle_name="middle_name",
    suffix="suffix",
    address_line_1="address_line_1",
    address_line_2="address_line_2",
    city="city",
    state="state",
    zip_code="zip_code",
    phone="phone",
    email="email",
)

_csv_parser = CsvEnrollmentParser(_DEFAULT_FIELD_MAPPING)


def _get_db() -> Session:  # pragma: no cover — overridden in tests
    raise NotImplementedError("DB session dependency must be overridden")


@router.post("/upload", status_code=201, summary="Upload enrollment file (CSV or EDI-834)")
async def upload_enrollment_file(
    request: Request,
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    tid = current_tenant_id.get()
    if tid is None:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "MISSING_TENANT", "message": "No tenant context", "correlation_id": str(uuid.uuid4())}},
        )

    content_type = request.headers.get("content-type", "").split(";")[0].strip()

    body_bytes = await request.body()
    if not body_bytes:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "EMPTY_BODY", "message": "Request body is empty", "correlation_id": str(uuid.uuid4())}},
        )

    if content_type == "text/csv":
        file_type = "csv"
        try:
            text = body_bytes.decode("utf-8", errors="replace")
            result = _csv_parser.parse_with_errors(io.StringIO(text))
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail={"error": {"code": "CSV_PARSE_ERROR", "message": str(exc), "correlation_id": str(uuid.uuid4())}},
            )
        total_records = len(result.valid_records) + len(result.errors)
        error_records = len(result.errors)

    elif content_type == "application/edi-x12":
        file_type = "edi_834"
        try:
            text = body_bytes.decode("utf-8", errors="replace")
            records = _edi_parser.parse(text)
            error_records = 0
            total_records = len(records)
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail={"error": {"code": "EDI_PARSE_ERROR", "message": str(exc), "correlation_id": str(uuid.uuid4())}},
            )

    else:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "UNSUPPORTED_CONTENT_TYPE",
                    "message": f"Content-Type {content_type!r} not supported. Use text/csv or application/edi-x12",
                    "correlation_id": str(uuid.uuid4()),
                }
            },
        )

    file_id = uuid.uuid4()
    enrollment_file = EnrollmentFile(
        id=uuid.uuid4(),
        tenant_id=tid,
        file_id=file_id,
        file_type=file_type,
        status="uploaded",
        total_records=total_records,
        error_records=error_records,
    )
    db.add(enrollment_file)
    db.commit()
    db.refresh(enrollment_file)

    logger.info(
        "Enrollment file uploaded",
        extra={
            "svc_enrollment_file_id": str(enrollment_file.id),
            "auth_tenant_id": str(tid),
            "svc_file_type": file_type,
        },
    )

    return {
        "id": str(enrollment_file.id),
        "file_id": str(file_id),
        "file_type": file_type,
        "status": enrollment_file.status,
        "total_records": total_records,
        "error_records": error_records,
    }


@router.get("/upload/{file_id}/preview", summary="Preview parsed records")
async def preview_enrollment_file(
    file_id: UUID,
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    tid = current_tenant_id.get()
    if tid is None:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "MISSING_TENANT", "message": "No tenant context", "correlation_id": str(uuid.uuid4())}},
        )

    stmt = select(EnrollmentFile).where(
        EnrollmentFile.file_id == file_id,
        EnrollmentFile.tenant_id == tid,
    )
    ef = db.execute(stmt).scalar_one_or_none()
    if ef is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "FILE_NOT_FOUND", "message": "Enrollment file not found", "correlation_id": str(uuid.uuid4())}},
        )

    return {
        "id": str(ef.id),
        "file_id": str(ef.file_id),
        "file_type": ef.file_type,
        "status": ef.status,
        "total_records": ef.total_records,
        "processed_records": ef.processed_records,
        "error_records": ef.error_records,
    }


@router.post("/upload/{file_id}/process", summary="Process enrollment file")
async def process_enrollment_file(
    file_id: UUID,
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    tid = current_tenant_id.get()
    if tid is None:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "MISSING_TENANT", "message": "No tenant context", "correlation_id": str(uuid.uuid4())}},
        )

    stmt = select(EnrollmentFile).where(
        EnrollmentFile.file_id == file_id,
        EnrollmentFile.tenant_id == tid,
    )
    ef = db.execute(stmt).scalar_one_or_none()
    if ef is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "FILE_NOT_FOUND", "message": "Enrollment file not found", "correlation_id": str(uuid.uuid4())}},
        )

    ef.status = "processing"
    db.commit()

    return {"id": str(ef.id), "file_id": str(ef.file_id), "status": "processing"}


@router.get("/files", summary="List enrollment files")
async def list_enrollment_files(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    tid = current_tenant_id.get()
    if tid is None:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "MISSING_TENANT", "message": "No tenant context", "correlation_id": str(uuid.uuid4())}},
        )

    stmt = (
        select(EnrollmentFile)
        .where(EnrollmentFile.tenant_id == tid)
        .offset(offset)
        .limit(limit)
    )
    rows = db.execute(stmt).scalars().all()

    return {
        "files": [
            {
                "id": str(ef.id),
                "file_id": str(ef.file_id),
                "file_type": ef.file_type,
                "status": ef.status,
                "total_records": ef.total_records,
                "created_at": ef.created_at.isoformat(),
            }
            for ef in rows
        ],
        "total": len(rows),
    }


@router.get("/files/{file_id}", summary="Enrollment file status")
async def get_enrollment_file(
    file_id: UUID,
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    tid = current_tenant_id.get()
    if tid is None:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "MISSING_TENANT", "message": "No tenant context", "correlation_id": str(uuid.uuid4())}},
        )

    stmt = select(EnrollmentFile).where(
        EnrollmentFile.file_id == file_id,
        EnrollmentFile.tenant_id == tid,
    )
    ef = db.execute(stmt).scalar_one_or_none()
    if ef is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "FILE_NOT_FOUND", "message": "Enrollment file not found", "correlation_id": str(uuid.uuid4())}},
        )

    return {
        "id": str(ef.id),
        "file_id": str(ef.file_id),
        "file_type": ef.file_type,
        "status": ef.status,
        "total_records": ef.total_records,
        "processed_records": ef.processed_records,
        "added_records": ef.added_records,
        "updated_records": ef.updated_records,
        "terminated_records": ef.terminated_records,
        "error_records": ef.error_records,
        "created_at": ef.created_at.isoformat(),
    }
