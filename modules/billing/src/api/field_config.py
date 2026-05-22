"""Stage 2 -- Field config API.

Endpoints:
  GET  /api/v1/billing/uploads/{upload_id}/field-config/sample-values
  GET  /api/v1/billing/uploads/{upload_id}/field-config
  PUT  /api/v1/billing/uploads/{upload_id}/field-config

Auth: same as uploads -- get_current_user + TenantId dependency.
RBAC: reads = all roles; write = operator + approver.
PHI: sample-values endpoint emits phi_access audit. Cache-Control: no-store on all responses.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from shared.auth.dependencies import CurrentUser, get_current_user
from src.api.dependencies import DBSession, TenantId
from src.models.tables import ClaimUploadRawRow, Upload, UploadFieldConfig
from src.services.upload import decrypt_raw_row_fields

logger = logging.getLogger("billing.api.field_config")

router = APIRouter(
    prefix="/api/v1/billing/uploads/{upload_id}/field-config",
    tags=["field-config"],
)

_WRITE_ROLES = frozenset({"operator", "approver"})
_VALID_DATA_TYPES = frozenset({"string", "date", "decimal", "npi", "ndc", "integer"})
_SAMPLE_MAX_LEN = 256


def _no_store(data: Any, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        content=data,
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


def _emit_phi_audit(
    *, tenant_id: uuid.UUID, user_id: uuid.UUID, entity_id: uuid.UUID
) -> None:
    try:
        from shared.audit.client import emit_phi_access  # noqa: PLC0415
        emit_phi_access(
            tenant_id=tenant_id,
            user_id=user_id,
            entity_type="upload_field_config",
            entity_id=entity_id,
        )
    except Exception:
        logger.error(
            "billing.phi_audit_failed",
            extra={"svc_entity_id": str(entity_id), "svc_tenant_id": str(tenant_id)},
        )


class FieldConfigEntry(BaseModel):
    position: int = Field(..., ge=1, le=512)
    field_name: str = Field(..., min_length=1, max_length=128)
    data_type: str = Field(default="string")
    is_mandatory: bool = False
    is_phi: bool = False

    @field_validator("data_type")
    @classmethod
    def validate_data_type(cls, v: str) -> str:
        if v not in _VALID_DATA_TYPES:
            raise ValueError(f"data_type must be one of: {sorted(_VALID_DATA_TYPES)}")
        return v

    @field_validator("field_name")
    @classmethod
    def validate_field_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("field_name must not be blank")
        return v


class FieldConfigPutBody(BaseModel):
    fields: list[FieldConfigEntry]


def _config_to_dict(cfg: UploadFieldConfig) -> dict:
    return {
        "position": cfg.position,
        "field_name": cfg.field_name,
        "data_type": cfg.data_type,
        "is_mandatory": cfg.is_mandatory,
        "is_phi": cfg.is_phi,
        "sample_value": cfg.sample_value,
        "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
    }


@router.get("/sample-values")
async def get_sample_values(
    upload_id: uuid.UUID,
    db: DBSession,
    tenant_id: TenantId,
    current_user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    """Decrypt one raw row and return position->sample_value mapping.

    PHI-safe: positions with is_phi=True in saved config are returned as null.
    Emits phi_access audit entry since decryption may surface PHI.
    """
    stmt = select(Upload).where(Upload.id == upload_id, Upload.tenant_id == tenant_id)
    upload = db.execute(stmt).scalar_one_or_none()
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    _emit_phi_audit(tenant_id=tenant_id, user_id=current_user.id, entity_id=upload_id)

    row_stmt = (
        select(ClaimUploadRawRow)
        .where(
            ClaimUploadRawRow.upload_id == upload_id,
            ClaimUploadRawRow.tenant_id == tenant_id,
        )
        .order_by(ClaimUploadRawRow.row_number)
        .limit(1)
    )
    raw_row = db.execute(row_stmt).scalar_one_or_none()

    if raw_row is None:
        return _no_store({"upload_id": str(upload_id), "samples": {}, "field_count": 0})

    try:
        fields = decrypt_raw_row_fields(raw_row.fields_blob, tenant_id=str(tenant_id))
    except Exception:
        logger.error(
            "billing.field_config.decrypt_failed",
            extra={"svc_upload_id": str(upload_id), "svc_tenant_id": str(tenant_id)},
        )
        return _no_store({"upload_id": str(upload_id), "samples": {}, "field_count": 0})

    cfg_stmt = (
        select(UploadFieldConfig)
        .where(UploadFieldConfig.tenant_id == tenant_id)
        .order_by(UploadFieldConfig.position)
    )
    saved_configs = {str(c.position): c for c in db.execute(cfg_stmt).scalars().all()}

    samples: dict[str, str | None] = {}
    for pos_str, value in fields.items():
        cfg = saved_configs.get(pos_str)
        if cfg and cfg.is_phi:
            samples[pos_str] = None
        else:
            samples[pos_str] = value[:_SAMPLE_MAX_LEN] if value else ""

    return _no_store({
        "upload_id": str(upload_id),
        "samples": samples,
        "field_count": raw_row.field_count,
    })


@router.get("")
async def get_field_config(
    upload_id: uuid.UUID,
    db: DBSession,
    tenant_id: TenantId,
    current_user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    """Return saved field config for this tenant (all positions, ordered)."""
    stmt = select(Upload).where(Upload.id == upload_id, Upload.tenant_id == tenant_id)
    upload = db.execute(stmt).scalar_one_or_none()
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    cfg_stmt = (
        select(UploadFieldConfig)
        .where(UploadFieldConfig.tenant_id == tenant_id)
        .order_by(UploadFieldConfig.position)
    )
    configs = db.execute(cfg_stmt).scalars().all()

    return _no_store({
        "upload_id": str(upload_id),
        "tenant_id": str(tenant_id),
        "fields": [_config_to_dict(c) for c in configs],
        "field_count": len(configs),
    })


@router.put("", status_code=status.HTTP_200_OK)
async def put_field_config(
    upload_id: uuid.UUID,
    body: FieldConfigPutBody,
    db: DBSession,
    tenant_id: TenantId,
    current_user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    """Upsert field config for this tenant (positions in request, others unchanged).

    PHI safety: when is_phi=True, sample_value is forced to null in the DB.
    """
    if not any(current_user.has_role(r) for r in _WRITE_ROLES):
        raise HTTPException(
            status_code=403,
            detail="Only operators and approvers can update field config",
        )

    stmt = select(Upload).where(Upload.id == upload_id, Upload.tenant_id == tenant_id)
    upload = db.execute(stmt).scalar_one_or_none()
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    if not body.fields:
        raise HTTPException(status_code=422, detail="fields list must not be empty")

    positions = [e.position for e in body.fields]
    if len(positions) != len(set(positions)):
        raise HTTPException(status_code=422, detail="Duplicate positions in request body")

    now = datetime.now(UTC)

    for entry in body.fields:
        stmt_upsert = pg_insert(UploadFieldConfig).values(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            position=entry.position,
            field_name=entry.field_name,
            data_type=entry.data_type,
            is_mandatory=entry.is_mandatory,
            is_phi=entry.is_phi,
            sample_value=None,
            updated_at=now,
            updated_by=current_user.id,
        ).on_conflict_do_update(
            constraint="uq_field_config_tenant_pos",
            set_={
                "field_name": entry.field_name,
                "data_type": entry.data_type,
                "is_mandatory": entry.is_mandatory,
                "is_phi": entry.is_phi,
                "sample_value": None,
                "updated_at": now,
                "updated_by": current_user.id,
            },
        )
        db.execute(stmt_upsert)

    db.commit()

    cfg_stmt = (
        select(UploadFieldConfig)
        .where(UploadFieldConfig.tenant_id == tenant_id)
        .order_by(UploadFieldConfig.position)
    )
    configs = db.execute(cfg_stmt).scalars().all()

    return _no_store({
        "upload_id": str(upload_id),
        "tenant_id": str(tenant_id),
        "fields": [_config_to_dict(c) for c in configs],
        "field_count": len(configs),
    })
