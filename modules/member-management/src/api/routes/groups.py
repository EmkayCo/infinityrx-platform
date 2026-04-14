"""Group/employer management routes."""
from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from src.api.schemas.member import GroupCreate

router = APIRouter(prefix="/groups", tags=["groups"])


@router.get("", summary="List groups (tenant-scoped)")
async def list_groups(is_active: bool | None = Query(None)) -> dict[str, Any]:
    return {"groups": [], "total": 0}


@router.post("", status_code=201, summary="Create group")
async def create_group(body: GroupCreate) -> dict[str, Any]:
    return {"id": str(uuid.uuid4()), "group_number": body.group_number, "group_name": body.group_name}


@router.put("/{group_id}", summary="Update group")
async def update_group(group_id: UUID, body: GroupCreate) -> dict[str, Any]:
    raise HTTPException(status_code=404, detail={"error": {"code": "GROUP_NOT_FOUND", "message": "Group not found", "correlation_id": str(uuid.uuid4())}})


@router.get("/{group_id}/members", summary="Members in group")
async def get_group_members(group_id: UUID) -> dict[str, Any]:
    return {"members": [], "total": 0}
