"""Member CRUD and search API routes."""
from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from src.api.schemas.member import (
    MemberCreate,
    MemberResponse,
    MemberTerminate,
    MemberUpdate,
    PhiAccessLevel,
)

router = APIRouter(tags=["members"])


@router.get("", summary="Search/list members")
async def list_members(
    member_id: str | None = Query(None),
    status: str | None = Query(None),
    group_id: UUID | None = Query(None),
) -> dict[str, Any]:
    return {"members": [], "total": 0}


@router.post("", status_code=201, summary="Create member (manual enrollment)")
async def create_member(body: MemberCreate) -> dict[str, Any]:
    return {"id": str(uuid.uuid4()), "member_id": body.member_id, "status": "active"}


@router.get("/{member_id}", summary="Member detail")
async def get_member(
    member_id: UUID,
    phi_access: PhiAccessLevel = Query(default=PhiAccessLevel.PARTIAL),
) -> dict[str, Any]:
    raise HTTPException(status_code=404, detail={"error": {"code": "MEMBER_NOT_FOUND", "message": "Member not found", "correlation_id": str(uuid.uuid4())}})


@router.put("/{member_id}", summary="Update member demographics")
async def update_member(member_id: UUID, body: MemberUpdate) -> dict[str, Any]:
    raise HTTPException(status_code=404, detail={"error": {"code": "MEMBER_NOT_FOUND", "message": "Member not found", "correlation_id": str(uuid.uuid4())}})


@router.post("/{member_id}/terminate", summary="Terminate member")
async def terminate_member(member_id: UUID, body: MemberTerminate) -> dict[str, Any]:
    raise HTTPException(status_code=404, detail={"error": {"code": "MEMBER_NOT_FOUND", "message": "Member not found", "correlation_id": str(uuid.uuid4())}})


@router.get("/{member_id}/id-card", summary="ID card data")
async def get_id_card(member_id: UUID) -> dict[str, Any]:
    raise HTTPException(status_code=404, detail={"error": {"code": "MEMBER_NOT_FOUND", "message": "Member not found", "correlation_id": str(uuid.uuid4())}})
