"""Audit query + export API.

Endpoints (tenant-scoped automatically):
    GET  /api/v1/audit              filterable list
    GET  /api/v1/audit/export       CSV or Excel streaming export
    GET  /api/v1/audit/{id}         single entry

Authorization is permission-based: ``audit:read`` for list/get,
``audit:export`` for export. The current user is resolved via a
caller-provided dependency so this module stays decoupled from T2's auth
implementation.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse

from src.audit.schemas import AuditEntryRead, AuditPage, AuditQuery
from src.audit.service import AuditService


def build_audit_router(
    *,
    get_session: Callable[..., object],
    require_permission: Callable[[str], Callable[..., object]],
) -> APIRouter:
    """Assemble the audit router with the caller-supplied dependencies."""

    router = APIRouter(prefix="/api/v1/audit", tags=["audit"])

    read_dep = require_permission("audit:read")
    export_dep = require_permission("audit:export")

    @router.get("", response_model=AuditPage)
    def list_audit(
        action: str | None = Query(default=None),
        module: str | None = Query(default=None),
        entity_type: str | None = Query(default=None),
        entity_id: str | None = Query(default=None),
        user_id: uuid.UUID | None = Query(default=None),
        correlation_id: uuid.UUID | None = Query(default=None),
        date_from: datetime | None = Query(default=None),
        date_to: datetime | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        session=Depends(get_session),
        current=Depends(read_dep),
    ) -> AuditPage:
        q = AuditQuery(
            action=action,
            module=module,
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
            correlation_id=correlation_id,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
        return AuditService(session).query(current.tenant_id, q)

    @router.get("/export")
    def export_audit(
        format: str = Query(default="csv", pattern="^(csv|xlsx)$"),
        action: str | None = Query(default=None),
        module: str | None = Query(default=None),
        entity_type: str | None = Query(default=None),
        entity_id: str | None = Query(default=None),
        user_id: uuid.UUID | None = Query(default=None),
        correlation_id: uuid.UUID | None = Query(default=None),
        date_from: datetime | None = Query(default=None),
        date_to: datetime | None = Query(default=None),
        session=Depends(get_session),
        current=Depends(export_dep),
    ):
        q = AuditQuery(
            action=action,
            module=module,
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
            correlation_id=correlation_id,
            date_from=date_from,
            date_to=date_to,
            limit=500,
            offset=0,
        )
        svc = AuditService(session)
        if format == "csv":
            generator = svc.export_csv(current.tenant_id, q)
            return StreamingResponse(
                generator,
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=audit.csv"},
            )
        body = svc.export_xlsx(current.tenant_id, q)
        return Response(
            content=body,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=audit.xlsx"},
        )

    @router.get("/{audit_id}", response_model=AuditEntryRead)
    def get_audit(
        audit_id: int,
        session=Depends(get_session),
        current=Depends(read_dep),
    ) -> AuditEntryRead:
        entry = AuditService(session).get(current.tenant_id, audit_id)
        if entry is None:
            raise HTTPException(status_code=404, detail={"error": "not_found"})
        return entry

    return router
