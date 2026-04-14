"""FastAPI dependencies for prescriber-directory module."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from src.db.session import get_db_session


def get_db():  # pragma: no cover — overridden in tests via dependency_overrides
    with get_db_session() as session:
        yield session


def get_tenant_id(x_tenant_id: str = Header(...)) -> uuid.UUID:
    try:
        return uuid.UUID(x_tenant_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_TENANT_ID", "message": "x-tenant-id must be a valid UUID"}},
        ) from exc


DBSession = Annotated[Session, Depends(get_db)]
TenantId = Annotated[uuid.UUID, Depends(get_tenant_id)]
