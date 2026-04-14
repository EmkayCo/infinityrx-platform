"""FastAPI dependencies for drug-database module."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from src.db.session import get_db_session


def get_db() -> Session:
    with get_db_session() as session:
        yield session


DBSession = Annotated[Session, Depends(get_db)]


def get_tenant_id(x_tenant_id: str = Header(...)) -> uuid.UUID:
    try:
        return uuid.UUID(x_tenant_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_TENANT_ID",
                    "message": "X-Tenant-Id header must be a valid UUID",
                    "correlation_id": str(uuid.uuid4()),
                }
            },
        ) from exc


TenantId = Annotated[uuid.UUID, Depends(get_tenant_id)]
