"""SP-1 Plan D Task 2 -- Files router.

Endpoints:
  POST   /api/v1/billing/files/generate   generate NACHA or 835 (Approver only)
  GET    /api/v1/billing/files            list file artifacts (all roles)
  GET    /api/v1/billing/files/{id}       metadata only (all roles; Cache-Control: no-store)
  GET    /api/v1/billing/files/{id}/download  stream file bytes (all roles; PHI audit; no-store)

Security:
  - All endpoints require a valid JWT (get_current_user -> 401 without token).
  - generate is Approver-only; Operator and Auditor receive 403.
  - download emits a phi_access audit entry (files contain payment PHI surrogates).
  - file_path is NEVER returned in any JSON response.
  - Cache-Control: no-store on every response (files contain payment data).
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select

from shared.auth.dependencies import CurrentUser, get_current_user
from src.api.dependencies import DBSession, TenantId
from src.models.file_artifact import FileArtifact

logger = logging.getLogger("billing.api.files")

router = APIRouter(prefix="/api/v1/billing/files", tags=["files"])

_APPROVER_ROLE = "approver"


# ---------------------------------------------------------------------------
# PHI audit helper
# ---------------------------------------------------------------------------


def _emit_phi_audit(
    *, tenant_id: uuid.UUID, user_id: uuid.UUID, entity_id: uuid.UUID
) -> None:
    """Best-effort phi_access audit entry. Never fails the request."""
    try:
        from shared.audit.client import emit_phi_access  # noqa: PLC0415

        emit_phi_access(
            tenant_id=tenant_id,
            user_id=user_id,
            entity_type="file_artifact",
            entity_id=entity_id,
        )
    except Exception:
        logger.error(
            "billing.phi_audit_failed",
            extra={
                "svc_entity_id": str(entity_id),
                "svc_tenant_id": str(tenant_id),
            },
        )


# ---------------------------------------------------------------------------
# Response serialization (file_path excluded)
# ---------------------------------------------------------------------------


def _artifact_to_dict(artifact: FileArtifact) -> dict[str, Any]:
    """Serialize FileArtifact to a safe dict.  file_path is NEVER included."""
    return {
        "id": str(artifact.id),
        "tenant_id": str(artifact.tenant_id),
        "kind": artifact.kind,
        "source_batch_id": str(artifact.source_batch_id) if artifact.source_batch_id else None,
        "source_payment_run_id": (
            str(artifact.source_payment_run_id) if artifact.source_payment_run_id else None
        ),
        "upload_id": str(artifact.upload_id) if artifact.upload_id else None,
        "generated_by": str(artifact.generated_by),
        "generated_at": artifact.generated_at.isoformat() if artifact.generated_at else None,
        "filename": artifact.filename,
        "file_size": artifact.file_size,
        "sha256": artifact.sha256,
        "status": artifact.status,
    }


def _no_store(data: Any, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        content=data,
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------


class GenerateFileRequest(BaseModel):
    kind: str  # "nacha" | "835"
    source_id: uuid.UUID


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/generate", status_code=status.HTTP_201_CREATED)
async def generate_file(
    body: GenerateFileRequest,
    db: DBSession,
    tenant_id: TenantId,
    current_user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    """Generate a NACHA or 835 file from a source batch / payment run.

    RBAC: Approver only.  Operator and Auditor receive 403.
    """
    if not current_user.has_role(_APPROVER_ROLE):
        raise HTTPException(
            status_code=403,
            detail="Only approvers can generate payment files",
        )

    if body.kind not in ("nacha", "835"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported kind '{body.kind}'. Must be 'nacha' or '835'.",
        )

    from src.models.tables import PaymentBatch  # noqa: PLC0415

    batch = db.execute(
        select(PaymentBatch).where(
            PaymentBatch.id == body.source_id,
            PaymentBatch.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if batch is None:
        raise HTTPException(status_code=404, detail="Source batch not found")

    from src.services.file_artifact import generate_nacha, generate_835  # noqa: PLC0415

    try:
        if body.kind == "nacha":
            artifact = _generate_nacha_artifact(
                db=db,
                tenant_id=tenant_id,
                batch=batch,
                generated_by=current_user.id,
            )
        else:
            artifact = _generate_835_artifact(
                db=db,
                tenant_id=tenant_id,
                batch=batch,
                generated_by=current_user.id,
            )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return _no_store(_artifact_to_dict(artifact), status_code=201)


def _generate_nacha_artifact(*, db, tenant_id, batch, generated_by):
    """Build minimal NachaFileConfig/BatchConfig from batch and generate."""
    from src.services.file_artifact import generate_nacha  # noqa: PLC0415

    (
        generate_nacha_file,
        NachaFileConfig,
        NachaBatchConfig,
        NachaEntryDetail,
    ) = _import_nacha_types()

    from datetime import date  # noqa: PLC0415

    file_cfg = NachaFileConfig(
        immediate_destination="021000021",
        immediate_origin="123456789",
        immediate_destination_name="RECEIVING BANK",
        immediate_origin_name="INFINITYRX",
        reference_code="        ",
    )
    batch_cfg = NachaBatchConfig(
        service_class_code="220",
        company_name="INFINITYRX",
        company_identification=str(tenant_id).replace("-", "")[:10],
        standard_entry_class_code="PPD",
        company_entry_description="PAYMENT",
        originating_dfi_id="02100002",
        batch_number=1,
        effective_date=None,
        same_day=False,
    )
    # Build one entry per Payment in the batch
    from src.models.tables import Payment  # noqa: PLC0415
    from sqlalchemy import select as sa_select  # noqa: PLC0415

    payments = db.execute(
        sa_select(Payment).where(Payment.payment_batch_id == batch.id)
    ).scalars().all()

    entries = []
    for p in payments:
        if p.bank_routing_number and p.bank_account_number:
            from decimal import ROUND_HALF_UP  # noqa: PLC0415
            entries.append(
                NachaEntryDetail(
                    transaction_code="22",  # checking credit
                    routing_number=p.bank_routing_number,
                    account_number=p.bank_account_number,
                    amount=p.amount,
                    individual_id=str(p.pay_to_entity_id)[:15],
                    individual_name=p.pay_to_entity_name[:22],
                    trace_number=str(p.id.int)[:15],
                )
            )

    if not entries:
        raise ValueError(
            "No payments with bank routing data found in batch; cannot generate NACHA file."
        )

    return generate_nacha(
        db=db,
        tenant_id=tenant_id,
        batch_id=batch.id,
        generated_by=generated_by,
        file_cfg=file_cfg,
        batch_cfg=batch_cfg,
        entries=entries,
    )


def _generate_835_artifact(*, db, tenant_id, batch, generated_by):
    from src.services.file_artifact import generate_835 as svc_generate_835  # noqa: PLC0415
    from src.services.file_artifact import _import_835_generator  # noqa: PLC0415

    _, Generate835Request = _import_835_generator()

    from decimal import Decimal, ROUND_HALF_UP  # noqa: PLC0415
    from x12.generators.schemas import N1Party, ClpClaim  # type: ignore[import]  # noqa: PLC0415

    payer = N1Party(
        entity_id_code="PR",
        name="INFINITYRX",
        id_qualifier="XX",
        id="1234567890",
    )
    payee = N1Party(
        entity_id_code="PE",
        name="RECEIVING PHARMACY",
        id_qualifier="XX",
        id="0987654321",
    )

    req = Generate835Request(
        sender_id=str(tenant_id).replace("-", "")[:15],
        sender_qualifier="ZZ",
        receiver_id="RECEIVER       ",
        receiver_qualifier="ZZ",
        isa_control_number=1,
        gs_control_number=1,
        transaction_set_number=1,
        payer=payer,
        payee=payee,
        claims=[
            ClpClaim(
                claim_id=str(batch.batch_number),
                status_code="1",
                total_charge_amount=batch.total_amount,
                payment_amount=batch.total_amount,
                patient_control_number=str(batch.id)[:20],
                claim_filing_indicator="MC",
            )
        ],
        production_date=None,
        test_mode=False,
    )

    return svc_generate_835(
        db=db,
        tenant_id=tenant_id,
        source_payment_run_id=batch.id,
        generated_by=generated_by,
        request_835=req,
    )


def _import_nacha_types():
    """Import NACHA types from payment-processing for use in router helpers."""
    import sys  # noqa: PLC0415
    from pathlib import Path as _Path  # noqa: PLC0415

    pp_src = _Path(__file__).resolve().parents[4] / "payment-processing" / "src"
    if str(pp_src) not in sys.path:
        sys.path.insert(0, str(pp_src))
    from services.nacha_generator import (  # type: ignore[import]
        generate_nacha_file,
        NachaFileConfig,
        NachaBatchConfig,
        NachaEntryDetail,
    )
    return generate_nacha_file, NachaFileConfig, NachaBatchConfig, NachaEntryDetail


@router.get("")
async def list_file_artifacts(
    db: DBSession,
    tenant_id: TenantId,
    current_user: CurrentUser = Depends(get_current_user),
    kind: str | None = None,
    limit: int = 50,
) -> JSONResponse:
    """List file artifacts for the current tenant."""
    stmt = select(FileArtifact).where(FileArtifact.tenant_id == tenant_id)
    if kind:
        stmt = stmt.where(FileArtifact.kind == kind)
    stmt = stmt.order_by(FileArtifact.generated_at.desc()).limit(limit)
    artifacts = db.execute(stmt).scalars().all()
    return JSONResponse(content=[_artifact_to_dict(a) for a in artifacts])


@router.get("/{artifact_id}/download")
async def download_file_artifact(
    artifact_id: uuid.UUID,
    db: DBSession,
    tenant_id: TenantId,
    current_user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    """Stream the file bytes for a file artifact.

    PHI audit is emitted on every download.
    Cache-Control: no-store is set (files contain payment data).
    file_path is never returned in the response.
    """
    artifact = db.execute(
        select(FileArtifact).where(
            FileArtifact.id == artifact_id,
            FileArtifact.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if artifact is None:
        raise HTTPException(status_code=404, detail="File artifact not found")

    _emit_phi_audit(
        tenant_id=tenant_id,
        user_id=current_user.id,
        entity_id=artifact_id,
    )

    file_path = Path(artifact.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    def _iter_file():
        with file_path.open("rb") as fh:
            while chunk := fh.read(65536):
                yield chunk

    media_type = "application/octet-stream"
    if artifact.kind == "nacha":
        media_type = "text/plain"

    return StreamingResponse(
        _iter_file(),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.filename}"',
            "Cache-Control": "no-store",
            "Content-Length": str(artifact.file_size),
        },
    )


@router.get("/{artifact_id}")
async def get_file_artifact(
    artifact_id: uuid.UUID,
    db: DBSession,
    tenant_id: TenantId,
    current_user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    """Return file artifact metadata (file_path excluded)."""
    artifact = db.execute(
        select(FileArtifact).where(
            FileArtifact.id == artifact_id,
            FileArtifact.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if artifact is None:
        raise HTTPException(status_code=404, detail="File artifact not found")

    return _no_store(_artifact_to_dict(artifact))
