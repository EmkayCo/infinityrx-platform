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
from ..x12.generators.gen_271 import generate_271
from ..x12.generators.gen_276 import generate_276
from ..x12.generators.gen_277 import generate_277
from ..x12.generators.gen_278 import generate_278
from ..x12.generators.gen_835 import generate_835
from ..x12.generators.gen_837d import generate_837d
from ..x12.generators.gen_837i import generate_837i
from ..x12.generators.gen_837p import generate_837p
from ..x12.generators.gen_999 import generate_999, generate_ta1
from ..x12.generators.schemas import (
    Generate270Request,
    Generate271Request,
    Generate276Request,
    Generate277Request,
    Generate278Request,
    Generate835Request,
    Generate837DRequest,
    Generate837IRequest,
    Generate837PRequest,
    Generate999Request,
    GenerateTA1Request,
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


@router.post("/271", response_model=GenerateResponse)
async def api_generate_271(
    req: Generate271Request,
    tenant_id: uuid.UUID = Depends(_require_tenant),
    db: AsyncSession = Depends(get_session),
) -> GenerateResponse:
    """Generate a 271 eligibility response EDI file."""
    content = generate_271(req)
    return GenerateResponse(content=content, byte_count=len(content.encode()), transaction_type="271")


@router.post("/276", response_model=GenerateResponse)
async def api_generate_276(
    req: Generate276Request,
    tenant_id: uuid.UUID = Depends(_require_tenant),
    db: AsyncSession = Depends(get_session),
) -> GenerateResponse:
    """Generate a 276 claim status request EDI file."""
    content = generate_276(req)
    return GenerateResponse(content=content, byte_count=len(content.encode()), transaction_type="276")


@router.post("/277", response_model=GenerateResponse)
async def api_generate_277(
    req: Generate277Request,
    tenant_id: uuid.UUID = Depends(_require_tenant),
    db: AsyncSession = Depends(get_session),
) -> GenerateResponse:
    """Generate a 277 claim status response EDI file."""
    content = generate_277(req)
    return GenerateResponse(content=content, byte_count=len(content.encode()), transaction_type="277")


@router.post("/837i", response_model=GenerateResponse)
async def api_generate_837i(
    req: Generate837IRequest,
    tenant_id: uuid.UUID = Depends(_require_tenant),
    db: AsyncSession = Depends(get_session),
) -> GenerateResponse:
    """Generate a 837I institutional claim EDI file."""
    try:
        content = generate_837i(req)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "GENERATION_FAILED", "message": str(exc), "correlation_id": str(uuid.uuid4())}},
        )
    return GenerateResponse(content=content, byte_count=len(content.encode()), transaction_type="837I")


@router.post("/837d", response_model=GenerateResponse)
async def api_generate_837d(
    req: Generate837DRequest,
    tenant_id: uuid.UUID = Depends(_require_tenant),
    db: AsyncSession = Depends(get_session),
) -> GenerateResponse:
    """Generate a 837D dental claim EDI file."""
    try:
        content = generate_837d(req)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "GENERATION_FAILED", "message": str(exc), "correlation_id": str(uuid.uuid4())}},
        )
    return GenerateResponse(content=content, byte_count=len(content.encode()), transaction_type="837D")


@router.post("/278", response_model=GenerateResponse)
async def api_generate_278(
    req: Generate278Request,
    tenant_id: uuid.UUID = Depends(_require_tenant),
    db: AsyncSession = Depends(get_session),
) -> GenerateResponse:
    """Generate a 278 prior authorization request or response EDI file."""
    content = generate_278(req)
    return GenerateResponse(content=content, byte_count=len(content.encode()), transaction_type="278")


@router.post("/999", response_model=GenerateResponse)
async def api_generate_999(
    req: Generate999Request,
    tenant_id: uuid.UUID = Depends(_require_tenant),
    db: AsyncSession = Depends(get_session),
) -> GenerateResponse:
    """Generate a 999 functional acknowledgment EDI file."""
    content = generate_999(req)
    return GenerateResponse(content=content, byte_count=len(content.encode()), transaction_type="999")


@router.post("/ta1", response_model=GenerateResponse)
async def api_generate_ta1(
    req: GenerateTA1Request,
    tenant_id: uuid.UUID = Depends(_require_tenant),
    db: AsyncSession = Depends(get_session),
) -> GenerateResponse:
    """Generate a TA1 interchange acknowledgment EDI file."""
    content = generate_ta1(req)
    return GenerateResponse(content=content, byte_count=len(content.encode()), transaction_type="TA1")
