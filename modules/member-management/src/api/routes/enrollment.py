"""Enrollment file upload, preview, and processing routes."""
from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, UploadFile

router = APIRouter(prefix="/enrollment", tags=["enrollment"])


@router.post("/upload", status_code=201, summary="Upload enrollment file")
async def upload_enrollment_file(file: UploadFile) -> dict[str, Any]:
    return {"id": str(uuid.uuid4()), "file_name": file.filename, "status": "uploaded"}


@router.get("/upload/{file_id}/preview", summary="Preview parsed records")
async def preview_enrollment_file(file_id: UUID) -> dict[str, Any]:
    raise HTTPException(status_code=404, detail={"error": {"code": "FILE_NOT_FOUND", "message": "Enrollment file not found", "correlation_id": str(uuid.uuid4())}})


@router.post("/upload/{file_id}/process", summary="Process enrollment file")
async def process_enrollment_file(file_id: UUID) -> dict[str, Any]:
    raise HTTPException(status_code=404, detail={"error": {"code": "FILE_NOT_FOUND", "message": "Enrollment file not found", "correlation_id": str(uuid.uuid4())}})


@router.get("/files", summary="List enrollment files")
async def list_enrollment_files() -> dict[str, Any]:
    return {"files": [], "total": 0}


@router.get("/files/{file_id}", summary="Enrollment file status")
async def get_enrollment_file(file_id: UUID) -> dict[str, Any]:
    raise HTTPException(status_code=404, detail={"error": {"code": "FILE_NOT_FOUND", "message": "Enrollment file not found", "correlation_id": str(uuid.uuid4())}})
