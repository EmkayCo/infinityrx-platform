"""FastAPI dependencies for rules-engine module."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status


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
