"""FastAPI dependencies for DataIQ module."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from shared.db.tenant_context import set_tenant_context


async def get_tenant_id(x_tenant_id: str = Header(...)) -> uuid.UUID:
    """Extract and validate tenant ID from X-Tenant-Id request header.

    Also sets the shared tenant context so ORM tenant-isolation middleware
    applies the correct WHERE tenant_id = :tid filter on all queries.
    Must be async so the ContextVar is set in the same async task context
    as the route handler and DB session execution.
    """
    try:
        tenant_uuid = uuid.UUID(x_tenant_id)
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

    set_tenant_context(tenant_uuid)
    return tenant_uuid


TenantId = Annotated[uuid.UUID, Depends(get_tenant_id)]
