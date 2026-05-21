"""FastAPI dependencies for billing module."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from shared.auth.dependencies import CurrentUser, get_current_user
from src.db.session import get_db_session


def validate_tenant_id(
    x_tenant_id: str = Header(...),
    current_user: CurrentUser = Depends(get_current_user),
) -> uuid.UUID:
    """Validate X-Tenant-Id and enforce it matches the authenticated user tenant.

    Security (B2): A Tenant-A token presenting X-Tenant-Id: <Tenant-B>
    receives HTTP 403. This enforces the tenant isolation hard rule at the
    API layer in addition to RLS -- the hard API rule requires 403.
    """
    try:
        header_tenant = uuid.UUID(x_tenant_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid X-Tenant-Id header - must be a valid UUID",
        ) from exc

    if header_tenant != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="X-Tenant-Id does not match authenticated user tenant",
        )
    return header_tenant


TenantId = Annotated[uuid.UUID, Depends(validate_tenant_id)]


def get_db(tenant_id: TenantId) -> Session:
    """Yield a database session with the Postgres RLS variable pre-set.

    ``tenant_id`` dependency is declared first so FastAPI resolves
    ``validate_tenant_id`` (which calls ``get_current_user`` and sets the
    shared ``current_tenant_id`` contextvar) before opening the DB session.
    We then explicitly set ``app.current_tenant_id`` on the connection so
    that Postgres-level RLS policies (which check that session variable) are
    satisfied for INSERT/UPDATE/DELETE on tenant-scoped tables.
    """
    with get_db_session() as session:
        # SET SESSION persists for the connection lifetime (including across
        # transaction boundaries), so that lazy-loads after session.commit()
        # can still satisfy the RLS policy. SET LOCAL would reset on commit.
        session.execute(
            text("SET SESSION app.current_tenant_id = :tid"),
            {"tid": str(tenant_id)},
        )
        yield session


DBSession = Annotated[Session, Depends(get_db)]
