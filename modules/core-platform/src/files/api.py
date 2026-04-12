"""Files REST API."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, File as FastFile, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from .._shim.auth import CurrentUser, current_user, require_role
from .._shim.config import settings
from .._shim.db import get_session
from .service import ContentTypeNotAllowedError, FileService, FileTooLargeError
from .storage import LocalStorageBackend

router = APIRouter(prefix="/files", tags=["files"])

_backend_singleton: LocalStorageBackend | None = None


def _get_backend() -> LocalStorageBackend:
    global _backend_singleton
    if _backend_singleton is None:
        _backend_singleton = LocalStorageBackend(settings.STORAGE_LOCAL_PATH)
    return _backend_singleton


def set_backend(backend: LocalStorageBackend) -> None:
    """Test hook to override the module-level backend."""
    global _backend_singleton
    _backend_singleton = backend


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tenant_id: str
    filename: str
    original_filename: str
    content_type: Optional[str]
    size_bytes: Optional[int]
    module: Optional[str]
    entity_type: Optional[str]
    entity_id: Optional[str]
    sha256: Optional[str]


@router.post("/upload", response_model=FileOut, status_code=201, dependencies=[Depends(require_role("platform_admin", "tenant_admin", "tenant_operator"))])
async def upload_file(
    upload: UploadFile = FastFile(...),
    module: Optional[str] = Form(default=None),
    entity_type: Optional[str] = Form(default=None),
    entity_id: Optional[str] = Form(default=None),
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> FileOut:
    content = await upload.read()
    svc = FileService(session, _get_backend())
    try:
        result = await svc.upload(
            tenant_id=str(user.tenant_id),
            original_filename=upload.filename or "unnamed",
            content=content,
            content_type=upload.content_type,
            uploaded_by=str(user.id),
            module=module,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    except FileTooLargeError as exc:
        raise HTTPException(status_code=413, detail={"error": "file_too_large", "message": str(exc)}) from exc
    except ContentTypeNotAllowedError as exc:
        raise HTTPException(status_code=415, detail={"error": "content_type_not_allowed", "message": str(exc)}) from exc

    return FileOut(
        id=result.id,
        tenant_id=result.tenant_id,
        filename=result.filename,
        original_filename=result.original_filename,
        content_type=result.content_type,
        size_bytes=result.size_bytes,
        module=result.module,
        entity_type=result.entity_type,
        entity_id=result.entity_id,
        sha256=result.sha256,
    )


@router.get("", response_model=List[FileOut], dependencies=[Depends(require_role("platform_admin", "tenant_admin", "tenant_operator"))])
def list_files(
    module: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> List[FileOut]:
    svc = FileService(session, _get_backend())
    rows = svc.list(tenant_id=str(user.tenant_id), module=module, entity_type=entity_type, entity_id=entity_id)
    return [FileOut.model_validate(r) for r in rows]


@router.get("/{file_id}", dependencies=[Depends(require_role("platform_admin", "tenant_admin", "tenant_operator"))])
async def download_file(
    file_id: str,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> Response:
    svc = FileService(session, _get_backend())
    try:
        row, data = await svc.download(tenant_id=str(user.tenant_id), file_id=file_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error": "file_not_found"}) from exc
    headers = {"Content-Disposition": f'attachment; filename="{row.original_filename}"'}
    return Response(content=data, media_type=row.content_type or "application/octet-stream", headers=headers)


@router.delete("/{file_id}", status_code=204, dependencies=[Depends(require_role("platform_admin", "tenant_admin"))])
async def delete_file(
    file_id: str,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> Response:
    svc = FileService(session, _get_backend())
    try:
        await svc.delete(tenant_id=str(user.tenant_id), file_id=file_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error": "file_not_found"}) from exc
    return Response(status_code=204)
