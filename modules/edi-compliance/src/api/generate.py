"""EDI generation API endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
try:
    from sqlalchemy.ext.asyncio import AsyncSession
    from shared.db.session import get_session  # type: ignore[import]
except ImportError:
    AsyncSession = None  # type: ignore[assignment,misc]

    async def get_session():  # type: ignore[misc]
        yield None

from ..x12.generators.gen_270 import generate_270
from ..x12.generators.gen_835 import generate_835
from ..x12.generators.gen_837p import generate_837p
from ..x12.generators.schemas import (
    Generate270Request,
    Generate835Request,
    Generate837PRequest,
)

router = APIRouter(prefix="/generate", tags=["generation"])


def _require_tenant(x_tenant_id: Annotated[Optional[str], Header()] = None) -> uuid.UUID:
    if not x_tenant_id:
        raise HTTPException(status_code=401, detail={"error": {"code": "MISSING_TENANT", "message": "x-tenant-id header required"}})
    try:
        return uuid.UUID(x_tenant_id)
    except ValueError:
        raise HTTPException(status_code=403, detail={"error": {"code": "INVALID_TENANT", "message": "x-tenant-id must be a valid UUID"}})


class GenerateResponse(BaseModel):
    content: str
    byte_count: int
    transaction_type: str


@router.post("/835", response_model=GenerateResponse)
async def api_generate_835(
    req: Generate835Request,
    tenant_id: uuid.UUID = Depends(_require_tenant),
    db: AsyncSession = Depends(get_session),
) -> GenerateResponse:
    """Generate a complete 835 remittance advice EDI file."""
    try:
        content = generate_835(req)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "GENERATION_FAILED", "message": str(exc), "correlation_id": str(uuid.uuid4())}},
        )
    return GenerateResponse(content=content, byte_count=len(content.encode()), transaction_type="835")


@router.post("/837p", response_model=GenerateResponse)
async def api_generate_837p(
    req: Generate837PRequest,
    tenant_id: uuid.UUID = Depends(_require_tenant),
    db: AsyncSession = Depends(get_session),
) -> GenerateResponse:
    """Generate a complete 837P professional claim EDI file."""
    try:
        content = generate_837p(req)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "GENERATION_FAILED", "message": str(exc), "correlation_id": str(uuid.uuid4())}},
        )
    return GenerateResponse(content=content, byte_count=len(content.encode()), transaction_type="837P")


@router.post("/270", response_model=GenerateResponse)
async def api_generate_270(
    req: Generate270Request,
    tenant_id: uuid.UUID = Depends(_require_tenant),
    db: AsyncSession = Depends(get_session),
) -> GenerateResponse:
    """Generate a 270 eligibility inquiry EDI file."""
    content = generate_270(req)
    return GenerateResponse(content=content, byte_count=len(content.encode()), transaction_type="270")
