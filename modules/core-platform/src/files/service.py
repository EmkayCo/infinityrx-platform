"""FileService — orchestrates metadata + blob storage."""
from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .._shim.config import settings
from ..models import File
from .storage import StorageBackend, UnsafePathError


class FileServiceError(Exception):
    """Base error for file service."""


class FileTooLargeError(FileServiceError):
    pass


class ContentTypeNotAllowedError(FileServiceError):
    pass


_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9._\-]+")


def _sanitize_filename(raw: str) -> str:
    # Drop any path components — keep only the basename
    basename = raw.strip().replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = _FILENAME_SAFE.sub("_", basename)
    cleaned = cleaned.strip("._")
    return cleaned or "unnamed"


@dataclass
class FileUploadResult:
    id: str
    tenant_id: str
    filename: str
    original_filename: str
    content_type: Optional[str]
    size_bytes: int
    storage_path: str
    sha256: str
    module: Optional[str]
    entity_type: Optional[str]
    entity_id: Optional[str]


class FileService:
    def __init__(
        self,
        session: Session,
        backend: StorageBackend,
        *,
        max_bytes: Optional[int] = None,
        allowed_content_types: Optional[list[str]] = None,
    ) -> None:
        self._session = session
        self._backend = backend
        self._max_bytes = max_bytes if max_bytes is not None else settings.MAX_UPLOAD_BYTES
        if allowed_content_types is None:
            allowed_content_types = [s.strip() for s in settings.ALLOWED_CONTENT_TYPES.split(",") if s.strip()]
        self._allowed = set(allowed_content_types)

    def _check(self, content_type: Optional[str], size: int) -> None:
        if size > self._max_bytes:
            raise FileTooLargeError(f"{size} bytes exceeds max {self._max_bytes}")
        if content_type is None or content_type not in self._allowed:
            raise ContentTypeNotAllowedError(f"content_type={content_type!r} not allowed")

    async def upload(
        self,
        *,
        tenant_id: str,
        original_filename: str,
        content: bytes,
        content_type: Optional[str],
        uploaded_by: Optional[str] = None,
        module: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
    ) -> FileUploadResult:
        self._check(content_type, len(content))
        safe_name = _sanitize_filename(original_filename)
        now = datetime.now(timezone.utc)
        file_id = str(uuid.uuid4())
        rel_path = f"{tenant_id}/{now.year:04d}/{now.month:02d}/{file_id}-{safe_name}"
        try:
            storage_path = await self._backend.put(rel_path, content)
        except UnsafePathError as exc:
            raise FileServiceError(f"storage rejected path: {exc}") from exc

        sha = hashlib.sha256(content).hexdigest()
        row = File(
            id=file_id,
            tenant_id=tenant_id,
            filename=rel_path,
            original_filename=original_filename,
            content_type=content_type,
            size_bytes=len(content),
            storage_path=storage_path,
            module=module,
            entity_type=entity_type,
            entity_id=entity_id,
            uploaded_by=uploaded_by,
            sha256=sha,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return FileUploadResult(
            id=row.id,
            tenant_id=row.tenant_id,
            filename=row.filename,
            original_filename=row.original_filename,
            content_type=row.content_type,
            size_bytes=row.size_bytes or 0,
            storage_path=row.storage_path,
            sha256=row.sha256 or "",
            module=row.module,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
        )

    def list(
        self,
        *,
        tenant_id: str,
        module: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
    ) -> list[File]:
        stmt = select(File).where(File.tenant_id == tenant_id)
        if module is not None:
            stmt = stmt.where(File.module == module)
        if entity_type is not None:
            stmt = stmt.where(File.entity_type == entity_type)
        if entity_id is not None:
            stmt = stmt.where(File.entity_id == entity_id)
        stmt = stmt.order_by(File.created_at.desc())
        return list(self._session.execute(stmt).scalars())

    def get(self, *, tenant_id: str, file_id: str) -> File:
        row = self._session.get(File, file_id)
        if row is None or row.tenant_id != tenant_id:
            raise FileNotFoundError(file_id)
        return row

    async def download(self, *, tenant_id: str, file_id: str) -> tuple[File, bytes]:
        row = self.get(tenant_id=tenant_id, file_id=file_id)
        data = await self._backend.get(row.filename)
        return row, data

    async def delete(self, *, tenant_id: str, file_id: str) -> None:
        row = self.get(tenant_id=tenant_id, file_id=file_id)
        await self._backend.delete(row.filename)
        self._session.delete(row)
        self._session.commit()
