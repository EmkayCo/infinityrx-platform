"""FastAPI dependency injection for the reporting module."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_session


async def get_db(session: AsyncSession = Depends(get_session)) -> AsyncSession:
    return session


async def get_current_tenant_id(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
) -> str:
    """Extract and validate tenant ID from request header."""
    if not x_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "MISSING_TENANT", "message": "X-Tenant-ID header required"}},
        )
    return x_tenant_id


async def get_current_user_id(
    x_user_id: str = Header(..., alias="X-User-ID"),
) -> str:
    """Extract user ID from request header (set by auth middleware)."""
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Authentication required"}},
        )
    return x_user_id


async def get_user_role(
    x_user_role: str = Header("operator", alias="X-User-Role"),
) -> str:
    return x_user_role


async def get_user_permissions(
    x_permissions: str = Header("", alias="X-Permissions"),
) -> list[str]:
    if not x_permissions:
        return []
    return [p.strip() for p in x_permissions.split(",") if p.strip()]
