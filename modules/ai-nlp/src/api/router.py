"""AI/NLP API router — all endpoints under /api/v1/ai/."""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse

from src.api.schemas.requests import (
    ChatRequest,
    DocumentProcessRequest,
    GenerateContentRequest,
    TextClassifyRequest,
)
from src.api.schemas.responses import (
    ChatMessageResponse,
    DocumentResultResponse,
    GeneratedContentResponse,
)

logger = logging.getLogger("ai_nlp.api")

router = APIRouter(prefix="/api/v1/ai", tags=["ai-nlp"])

_CACHE_NO_STORE = "no-store"


def _require_tenant(
    x_tenant_id: Annotated[str | None, Header(alias="x-tenant-id")] = None,
) -> UUID:
    if not x_tenant_id:
        raise HTTPException(status_code=422, detail="x-tenant-id header is required")
    try:
        return UUID(x_tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="x-tenant-id must be a valid UUID") from exc


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "module": "ai-nlp"}


@router.post("/chat")
async def chat(
    request: ChatRequest,
    tenant_id: UUID = Depends(_require_tenant),
) -> JSONResponse:

    correlation_id = str(uuid4())
    response_data = ChatMessageResponse(
        content=(
            "I can help with pharmacy benefit questions. "
            "Please note this is a demo response — configure Azure OpenAI credentials for full functionality."
        ),
        sources=[],
        confidence=1.0,
        escalate=False,
        escalation_reason="",
    )
    return JSONResponse(
        content=response_data.model_dump(),
        headers={"Cache-Control": _CACHE_NO_STORE, "X-Correlation-ID": correlation_id},
    )


@router.post("/documents/process")
async def process_document(
    request: DocumentProcessRequest,
    tenant_id: UUID = Depends(_require_tenant),
) -> JSONResponse:
    correlation_id = str(uuid4())
    response_data = DocumentResultResponse(
        service_request_id=str(uuid4()),
        document_type=request.document_type,
        overall_confidence=0.0,
        requires_human_review=True,
        fields=[],
        low_confidence_field_count=0,
    )
    return JSONResponse(
        content=response_data.model_dump(),
        headers={"Cache-Control": _CACHE_NO_STORE, "X-Correlation-ID": correlation_id},
    )


@router.get("/documents/{service_request_id}/results")
async def get_document_results(
    service_request_id: str,
    tenant_id: UUID = Depends(_require_tenant),
) -> JSONResponse:
    correlation_id = str(uuid4())
    return JSONResponse(
        content={"service_request_id": service_request_id, "status": "not_found"},
        status_code=404,
        headers={"Cache-Control": _CACHE_NO_STORE, "X-Correlation-ID": correlation_id},
    )


@router.post("/text/classify")
async def classify_text(
    request: TextClassifyRequest,
    tenant_id: UUID = Depends(_require_tenant),
) -> JSONResponse:
    correlation_id = str(uuid4())
    return JSONResponse(
        content={"classifications": {}, "service_request_id": str(uuid4())},
        headers={"Cache-Control": _CACHE_NO_STORE, "X-Correlation-ID": correlation_id},
    )


@router.post("/text/extract-entities")
async def extract_entities(
    request: TextClassifyRequest,
    tenant_id: UUID = Depends(_require_tenant),
) -> JSONResponse:
    correlation_id = str(uuid4())
    return JSONResponse(
        content={"entities": [], "service_request_id": str(uuid4())},
        headers={"Cache-Control": _CACHE_NO_STORE, "X-Correlation-ID": correlation_id},
    )


@router.post("/generate")
async def generate_content(
    request: GenerateContentRequest,
    tenant_id: UUID = Depends(_require_tenant),
) -> JSONResponse:
    correlation_id = str(uuid4())
    response_data = GeneratedContentResponse(
        content="Draft content pending configuration of Azure OpenAI credentials.",
        template_name=request.template_name,
        requires_human_review=True,
        service_request_id=str(uuid4()),
    )
    return JSONResponse(
        content=response_data.model_dump(),
        headers={"Cache-Control": _CACHE_NO_STORE, "X-Correlation-ID": correlation_id},
    )


@router.get("/generate/templates")
async def list_templates(
    tenant_id: UUID = Depends(_require_tenant),
) -> JSONResponse:
    templates = [
        "PA Request Letter",
        "PA Appeal Letter",
        "Audit Demand Letter",
        "Investigation Summary",
        "Member Communication",
        "Client Report Narrative",
        "Corrective Action Plan",
    ]
    return JSONResponse(content={"templates": templates})


@router.get("/usage")
async def get_usage(
    tenant_id: UUID = Depends(_require_tenant),
) -> JSONResponse:
    return JSONResponse(
        content={"usage": [], "tenant_id": str(tenant_id)},
        headers={"Cache-Control": _CACHE_NO_STORE},
    )


@router.get("/usage/by-module")
async def get_usage_by_module(
    tenant_id: UUID = Depends(_require_tenant),
) -> JSONResponse:
    return JSONResponse(
        content={"usage_by_module": [], "tenant_id": str(tenant_id)},
        headers={"Cache-Control": _CACHE_NO_STORE},
    )
