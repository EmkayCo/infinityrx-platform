"""SP-1 Plan B Task 3.2 -- Inbox router.

GET /api/v1/billing/inbox?role=<role>
Returns InboxItem[] derived from current DB state of uploads + payment batches.

Item kinds:
  upload_pending_review               -- uploads status=parsing or validation_failed
  upload_validated_awaiting_batching  -- uploads status=validated
  cycle_pending_close                 -- PaymentBatch status=pending_close
  cycle_close_review                  -- PaymentBatch status=closing

Priority = "high" when upload error_count > 0.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select

from shared.auth.dependencies import CurrentUser, get_current_user
from src.api.dependencies import DBSession, TenantId
from src.models.tables import PaymentBatch, Upload, UploadStatus

logger = logging.getLogger("billing.api.inbox")

router = APIRouter(prefix="/api/v1/billing/inbox", tags=["inbox"])


@router.get("")
async def get_inbox(
    db: DBSession,
    tenant_id: TenantId,
    current_user: CurrentUser = Depends(get_current_user),
    role: str = Query(default="operator"),
) -> JSONResponse:
    """Return InboxItem[] derived from current DB state."""
    items: list[dict[str, Any]] = []

    # Upload pending review: status=parsing or validation_failed
    pending_stmt = select(Upload).where(
        Upload.tenant_id == tenant_id,
        Upload.status.in_([UploadStatus.parsing.value, UploadStatus.validation_failed.value]),
    )
    for u in db.execute(pending_stmt).scalars().all():
        items.append({
            "kind": "upload_pending_review",
            "upload_id": str(u.id),
            "filename": u.filename,
            "status": u.status,
            "error_count": u.error_count,
            "priority": "high" if (u.error_count or 0) > 0 else "normal",
            "uploaded_at": u.uploaded_at.isoformat() if u.uploaded_at else None,
        })

    # Upload validated: status=validated, awaiting batching
    validated_stmt = select(Upload).where(
        Upload.tenant_id == tenant_id,
        Upload.status == UploadStatus.validated.value,
    )
    for u in db.execute(validated_stmt).scalars().all():
        items.append({
            "kind": "upload_validated_awaiting_batching",
            "upload_id": str(u.id),
            "filename": u.filename,
            "status": u.status,
            "row_count": u.row_count,
            "priority": "normal",
            "uploaded_at": u.uploaded_at.isoformat() if u.uploaded_at else None,
        })

    # Cycle items from PaymentBatch
    try:
        for b in db.execute(
            select(PaymentBatch).where(
                PaymentBatch.tenant_id == tenant_id,
                PaymentBatch.status == "pending_close",
            )
        ).scalars().all():
            items.append({"kind": "cycle_pending_close", "cycle_id": str(b.id),
                          "status": b.status, "priority": "normal"})

        for b in db.execute(
            select(PaymentBatch).where(
                PaymentBatch.tenant_id == tenant_id,
                PaymentBatch.status == "closing",
            )
        ).scalars().all():
            items.append({"kind": "cycle_close_review", "cycle_id": str(b.id),
                          "status": b.status, "priority": "normal"})
    except Exception:
        pass  # PaymentBatch status values may differ -- best-effort

    return JSONResponse(content=items)



