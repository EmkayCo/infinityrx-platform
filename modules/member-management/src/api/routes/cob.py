"""COB (Coordination of Benefits) routes.

GET    /members/{id}/cob
POST   /members/{id}/cob
PUT    /members/{id}/cob/{cob_id}
DELETE /members/{id}/cob/{cob_id}
"""
from __future__ import annotations

import uuid
from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from src.services.cob_service import CobSequence

router = APIRouter(tags=["cob"])

_VALID_SEQUENCES = {s.value for s in CobSequence}


class CobCreate(BaseModel):
    payer_sequence: str
    other_payer_name: str | None = None
    other_payer_bin: str | None = None
    other_payer_pcn: str | None = None
    other_payer_group: str | None = None
    other_payer_member_id: str | None = None
    other_payer_type: str | None = None
    effective_date: date
    termination_date: date | None = None

    @field_validator("payer_sequence")
    @classmethod
    def validate_payer_sequence(cls, v: str) -> str:
        if v not in _VALID_SEQUENCES:
            raise ValueError(f"payer_sequence must be one of: {sorted(_VALID_SEQUENCES)}")
        return v


class CobUpdate(BaseModel):
    termination_date: date | None = None
    other_payer_name: str | None = None


@router.get("/members/{member_id}/cob", summary="List COB records")
async def get_cob(member_id: UUID) -> dict[str, Any]:
    return {"member_id": str(member_id), "cob_records": []}


@router.post("/members/{member_id}/cob", status_code=201, summary="Add COB record")
async def add_cob(member_id: UUID, body: CobCreate) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "member_id": str(member_id),
        "payer_sequence": body.payer_sequence,
        "other_payer_name": body.other_payer_name,
        "effective_date": body.effective_date.isoformat(),
    }


@router.put("/members/{member_id}/cob/{cob_id}", summary="Update COB record")
async def update_cob(
    member_id: UUID,
    cob_id: UUID,
    body: CobUpdate,
) -> dict[str, Any]:
    raise HTTPException(
        status_code=404,
        detail={
            "error": {
                "code": "COB_NOT_FOUND",
                "message": "COB record not found",
                "correlation_id": str(uuid.uuid4()),
            }
        },
    )


@router.delete("/members/{member_id}/cob/{cob_id}", status_code=204, summary="Remove COB record")
async def delete_cob(member_id: UUID, cob_id: UUID) -> None:
    pass
