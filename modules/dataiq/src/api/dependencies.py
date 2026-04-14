"""FastAPI dependencies for DataIQ module."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status


def get_tenant_id(x_tenant_id: str = Header(...)) -> uuid.UUID:
    """Extract and validate tenant ID from X-Tenant-Id request header."""
    try:
        return uuid.UUID(x_tenant_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_TENANT_ID",
                    "message": "X-Tenant-Id header must be a valid UUID",
                    "field": "x_tenant_id",
                    "correlation_id": str(uuid.uuid4()),
                }
            },
        ) from exc


TenantId = Annotated[uuid.UUID, Depends(get_tenant_id)]
