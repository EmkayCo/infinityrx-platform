"""FastAPI dependencies for billing module."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from src.db.session import get_db_session


def get_db() -> Session:
    """Yield a database session."""
    with get_db_session() as session:
        yield session


DBSession = Annotated[Session, Depends(get_db)]


def get_tenant_id(x_tenant_id: str = Header(...)) -> uuid.UUID:
    """Extract and validate tenant ID from request header."""
    try:
        return uuid.UUID(x_tenant_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid X-Tenant-Id header — must be a valid UUID",
        ) from exc


TenantId = Annotated[uuid.UUID, Depends(get_tenant_id)]
