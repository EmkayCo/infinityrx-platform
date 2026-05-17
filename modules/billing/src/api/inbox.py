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
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select

from shared.auth.dependencies import CurrentUser, get_current_user
from src.api.dependencies import DBSession, TenantId
from src.models.tables import Carryover, Invoice, PaymentBatch, Upload, UploadStatus

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

    now_iso = datetime.now(UTC).isoformat()

    # P2-inbox-envelope: InboxItemSchema requires id, tenant_id, upload_id,
    # rbac_required, created_at, priority, kind, and a payload dict.
    # InboxQueue filters on item.rbac_required === role so this field is
    # mandatory for items to appear in the UI.

    # Upload pending review: status=parsing or validation_failed
    pending_stmt = select(Upload).where(
        Upload.tenant_id == tenant_id,
        Upload.status.in_([UploadStatus.parsing.value, UploadStatus.validation_failed.value]),
    )
    for u in db.execute(pending_stmt).scalars().all():
        priority = "high" if (u.error_count or 0) > 0 else "normal"
        items.append({
            "id": str(u.id),
            "kind": "upload_pending_review",
            "tenant_id": str(tenant_id),
            "upload_id": str(u.id),
            "rbac_required": "operator",
            "created_at": u.uploaded_at.isoformat() if u.uploaded_at else now_iso,
            "priority": priority,
            "payload": {
                "filename": u.filename,
                "status": u.status,
                "error_count": u.error_count or 0,
            },
        })

    # Upload validated: status=validated, awaiting batching
    validated_stmt = select(Upload).where(
        Upload.tenant_id == tenant_id,
        Upload.status == UploadStatus.validated.value,
    )
    for u in db.execute(validated_stmt).scalars().all():
        items.append({
            "id": str(u.id),
            "kind": "upload_validated_awaiting_batching",
            "tenant_id": str(tenant_id),
            "upload_id": str(u.id),
            "rbac_required": "operator",
            "created_at": u.uploaded_at.isoformat() if u.uploaded_at else now_iso,
            "priority": "normal",
            "payload": {
                "filename": u.filename,
                "status": u.status,
                "claim_count": u.row_count or 0,
            },
        })

    # Cycle items from PaymentBatch
    try:
        for b in db.execute(
            select(PaymentBatch).where(
                PaymentBatch.tenant_id == tenant_id,
                PaymentBatch.status == "pending_close",
            )
        ).scalars().all():
            items.append({
                "id": str(b.id),
                "kind": "cycle_pending_close",
                "tenant_id": str(tenant_id),
                "upload_id": None,
                "rbac_required": "operator",
                "created_at": now_iso,
                "priority": "normal",
                "payload": {"cycle_id": str(b.id), "status": b.status},
            })

        for b in db.execute(
            select(PaymentBatch).where(
                PaymentBatch.tenant_id == tenant_id,
                PaymentBatch.status == "closing",
            )
        ).scalars().all():
            items.append({
                "id": str(b.id),
                "kind": "cycle_close_review",
                "tenant_id": str(tenant_id),
                "upload_id": None,
                "rbac_required": "approver",
                "created_at": now_iso,
                "priority": "normal",
                "payload": {"cycle_id": str(b.id), "status": b.status},
            })
    except Exception:
        logger.exception(
            "billing.inbox.cycle_query_failed",
            extra={"svc_tenant_id": str(tenant_id)},
        )  # best-effort: return upload items even when cycle query fails


    # Plan C Task 7: batch_drafted -- PaymentBatch status=generated (no BatchIds released)
    try:
        for b in db.execute(
            select(PaymentBatch).where(
                PaymentBatch.tenant_id == tenant_id,
                PaymentBatch.status == "generated",
            )
        ).scalars().all():
            items.append({
                "id": str(b.id),
                "kind": "batch_drafted",
                "tenant_id": str(tenant_id),
                "upload_id": str(b.upload_id) if b.upload_id else None,
                "rbac_required": "approver",
                "created_at": b.created_at.isoformat() if b.created_at else now_iso,
                "priority": "normal",
                "payload": {
                    "batch_number": b.batch_number,
                    "total_amount": str(b.total_amount),
                    "batch_id": str(b.id),
                    "status": b.status,
                },
            })
    except Exception:
        logger.exception(
            "billing.inbox.batch_drafted_query_failed",
            extra={"svc_tenant_id": str(tenant_id)},
        )

    # Plan C Task 7: ar_invoice_draft -- Invoice status=draft
    try:
        for inv in db.execute(
            select(Invoice).where(
                Invoice.tenant_id == tenant_id,
                Invoice.status == "draft",
            )
        ).scalars().all():
            items.append({
                "id": str(inv.id),
                "kind": "ar_invoice_draft",
                "tenant_id": str(tenant_id),
                "upload_id": None,
                "rbac_required": "approver",
                "created_at": inv.created_at.isoformat() if inv.created_at else now_iso,
                "priority": "normal",
                "payload": {
                    "invoice_number": inv.invoice_number,
                    "client_name": inv.client_name,
                    "total": str(inv.total),
                    "invoice_id": str(inv.id),
                    "status": inv.status,
                },
            })
    except Exception:
        logger.exception(
            "billing.inbox.ar_invoice_draft_query_failed",
            extra={"svc_tenant_id": str(tenant_id)},
        )

    # Plan C Task 7: carryover_open -- Carryover resolved=False
    try:
        for co in db.execute(
            select(Carryover).where(
                Carryover.tenant_id == tenant_id,
                Carryover.resolved == False,  # noqa: E712
            )
        ).scalars().all():
            items.append({
                "id": str(co.id),
                "kind": "carryover_open",
                "tenant_id": str(tenant_id),
                "upload_id": str(co.upload_id) if co.upload_id else None,
                "rbac_required": "operator",
                "created_at": co.created_at.isoformat() if co.created_at else now_iso,
                "priority": "normal",
                "payload": {
                    "carryover_id": str(co.id),
                    "amount": str(co.amount),
                    "reason": co.reason,
                },
            })
    except Exception:
        logger.exception(
            "billing.inbox.carryover_open_query_failed",
            extra={"svc_tenant_id": str(tenant_id)},
        )
    return JSONResponse(
        content=items,
        headers={"Cache-Control": "no-store"},
    )





