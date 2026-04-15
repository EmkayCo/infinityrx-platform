"""AI/NLP API router — all endpoints under /api/v1/ai/."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from shared.ai.openai_client import OpenAIClient, OpenAIConfig, OpenAIRequest
from shared.db.session import get_session
from src.api.schemas.requests import (
    ChatRequest,
    DocumentProcessRequest,
    GenerateContentRequest,
    TextClassifyRequest,
)
from src.api.schemas.responses import (
    ChatMessageResponse,
    DocumentResultResponse,
    ExtractionFieldResponse,
    GeneratedContentResponse,
)
from src.models.tables import AiNlpDocumentResult, AiNlpPromptTemplate
from src.services.document_extraction import DocumentExtractionService
from src.services.guardrails import GuardrailAction, GuardrailService
from src.services.rag_service import RagService
from src.services.usage_logger import UsageLogger

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


def _openai_client() -> OpenAIClient:
    return OpenAIClient(config=OpenAIConfig())


def _structured_error(
    code: str,
    message: str,
    correlation_id: str,
    status_code: int = 500,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "correlation_id": correlation_id}},
        headers={"Cache-Control": _CACHE_NO_STORE, "X-Correlation-ID": correlation_id},
    )


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "module": "ai-nlp"}


@router.post("/chat")
async def chat(
    request: ChatRequest,
    tenant_id: UUID = Depends(_require_tenant),
    db: AsyncSession = Depends(get_session),
) -> JSONResponse:
    correlation_id = str(uuid4())
    service_request_id = uuid4()

    guardrail_svc = GuardrailService(db=db)

    # Topic guardrail before any processing
    topic_result = await guardrail_svc.check_topic(
        tenant_id=tenant_id,
        user_id=None,
        text=request.message,
        service_request_id=service_request_id,
    )
    if topic_result.triggered and topic_result.action == GuardrailAction.CANNED_RESPONSE:
        return JSONResponse(
            content=ChatMessageResponse(
                content=topic_result.canned_response,
                sources=[],
                confidence=1.0,
                escalate=False,
                escalation_reason="out_of_scope",
            ).model_dump(),
            headers={"Cache-Control": _CACHE_NO_STORE, "X-Correlation-ID": correlation_id},
        )

    # Input guardrail — block prompt injection
    input_result = await guardrail_svc.check_input(
        tenant_id=tenant_id,
        user_id=None,
        text=request.message,
        service_request_id=service_request_id,
    )
    if input_result.triggered and input_result.action == GuardrailAction.BLOCK:
        logger.warning(
            "chat_input_blocked",
            extra={"svc_rule": input_result.rule_name, "svc_tenant_id": str(tenant_id)},
        )
        return _structured_error(
            code="INPUT_BLOCKED",
            message="Request blocked by content policy.",
            correlation_id=correlation_id,
            status_code=400,
        )

    try:
        client = _openai_client()
        rag_svc = RagService(db=db, openai_client=client)
        chat_response = await rag_svc.chat(
            tenant_id=tenant_id,
            user_id=None,
            session_id=request.session_id,
            portal_type=request.portal_type,
            message=request.message,
            conversation_history=[],
            phi_access_level="redacted",
        )
    except OperationalError as exc:
        err_str = str(exc).lower()
        if "vector" in err_str or "pgvector" in err_str:
            return _structured_error(
                code="PGVECTOR_UNAVAILABLE",
                message="pgvector extension required — run CREATE EXTENSION vector",
                correlation_id=correlation_id,
            )
        logger.error(
            "chat_db_error",
            extra={"svc_correlation_id": correlation_id, "svc_tenant_id": str(tenant_id)},
            exc_info=True,
        )
        return _structured_error(
            code="SERVICE_UNAVAILABLE",
            message="Database error. Please try again later.",
            correlation_id=correlation_id,
        )
    except Exception as exc:
        err_str = str(exc).lower()
        if "api_key" in err_str or "authentication" in err_str or "unauthorized" in err_str:
            return _structured_error(
                code="LLM_UNAVAILABLE",
                message="AI service not configured. Please contact support.",
                correlation_id=correlation_id,
            )
        logger.error(
            "chat_service_error",
            extra={"svc_correlation_id": correlation_id, "svc_tenant_id": str(tenant_id)},
            exc_info=True,
        )
        return _structured_error(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred.",
            correlation_id=correlation_id,
        )

    # Output guardrail — check LLM response
    output_result = await guardrail_svc.check_output(
        tenant_id=tenant_id,
        user_id=None,
        text=chat_response.content,
        service_request_id=service_request_id,
    )
    if output_result.triggered and output_result.action == GuardrailAction.ESCALATE:
        logger.warning(
            "chat_output_phi_leak",
            extra={"svc_rule": output_result.rule_name, "svc_tenant_id": str(tenant_id)},
        )
        return _structured_error(
            code="PHI_LEAK_DETECTED",
            message="Response blocked by PHI guardrail. Request escalated for review.",
            correlation_id=correlation_id,
            status_code=422,
        )

    response_data = ChatMessageResponse(
        content=chat_response.content,
        sources=[
            {"source_type": s.source_type, "source_id": s.source_id, "snippet": s.snippet}
            for s in chat_response.sources
        ],
        confidence=chat_response.confidence,
        escalate=chat_response.escalate or (
            output_result.triggered and output_result.action == GuardrailAction.REPROMPT
        ),
        escalation_reason=chat_response.escalation_reason or (
            output_result.rule_name if output_result.triggered else ""
        ),
    )
    return JSONResponse(
        content=response_data.model_dump(),
        headers={"Cache-Control": _CACHE_NO_STORE, "X-Correlation-ID": correlation_id},
    )


@router.post("/documents/process")
async def process_document(
    request: DocumentProcessRequest,
    tenant_id: UUID = Depends(_require_tenant),
    db: AsyncSession = Depends(get_session),
) -> JSONResponse:
    correlation_id = str(uuid4())
    service_request_id = uuid4()

    try:
        client = _openai_client()
        extraction_svc = DocumentExtractionService(db=db, openai_client=client)
        result = await extraction_svc.extract(
            tenant_id=tenant_id,
            service_request_id=service_request_id,
            document_type=request.document_type,
            extracted_text=request.extracted_text,
            fields_to_extract=request.fields_to_extract,
            phi_access_level="redacted",
        )
    except Exception as exc:
        err_str = str(exc).lower()
        if "api_key" in err_str or "authentication" in err_str or "unauthorized" in err_str:
            return _structured_error(
                code="LLM_UNAVAILABLE",
                message="AI service not configured. Please contact support.",
                correlation_id=correlation_id,
            )
        logger.error(
            "document_process_error",
            extra={"svc_correlation_id": correlation_id, "svc_tenant_id": str(tenant_id)},
            exc_info=True,
        )
        return _structured_error(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred during document processing.",
            correlation_id=correlation_id,
        )

    response_data = DocumentResultResponse(
        service_request_id=str(service_request_id),
        document_type=result.document_type,
        overall_confidence=result.overall_confidence,
        requires_human_review=result.requires_human_review,
        fields=[
            ExtractionFieldResponse(
                name=f.name,
                value=f.value,
                confidence=f.confidence,
                requires_review=f.requires_review,
            )
            for f in result.fields
        ],
        low_confidence_field_count=len(result.low_confidence_fields),
    )
    return JSONResponse(
        content=response_data.model_dump(),
        headers={"Cache-Control": _CACHE_NO_STORE, "X-Correlation-ID": correlation_id},
    )


@router.get("/documents/{service_request_id}/results")
async def get_document_results(
    service_request_id: str,
    tenant_id: UUID = Depends(_require_tenant),
    db: AsyncSession = Depends(get_session),
) -> JSONResponse:
    correlation_id = str(uuid4())

    try:
        doc_uuid = UUID(service_request_id)
    except ValueError:
        return _structured_error(
            code="INVALID_ID",
            message="service_request_id must be a valid UUID.",
            correlation_id=correlation_id,
            status_code=400,
        )

    stmt = (
        select(AiNlpDocumentResult)
        .where(
            AiNlpDocumentResult.service_request_id == doc_uuid,
            AiNlpDocumentResult.tenant_id == tenant_id,
        )
        .limit(1)
    )

    try:
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
    except OperationalError as exc:
        err_str = str(exc).lower()
        if "vector" in err_str or "pgvector" in err_str:
            return _structured_error(
                code="PGVECTOR_UNAVAILABLE",
                message="pgvector extension required — run CREATE EXTENSION vector",
                correlation_id=correlation_id,
            )
        logger.error(
            "document_results_db_error",
            extra={"svc_correlation_id": correlation_id, "svc_tenant_id": str(tenant_id)},
            exc_info=True,
        )
        return _structured_error(
            code="SERVICE_UNAVAILABLE",
            message="Database error. Please try again later.",
            correlation_id=correlation_id,
        )

    if row is None:
        return JSONResponse(
            content={"error": {
                "code": "NOT_FOUND",
                "message": f"No document results found for service_request_id {service_request_id}",
                "correlation_id": correlation_id,
            }},
            status_code=404,
            headers={"Cache-Control": _CACHE_NO_STORE, "X-Correlation-ID": correlation_id},
        )

    return JSONResponse(
        content={
            "service_request_id": service_request_id,
            "tenant_id": str(tenant_id),
            "document_type": row.document_type,
            "extracted_fields": row.extracted_fields,
            "extracted_text": row.extracted_text,
            "page_count": row.page_count,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        },
        headers={"Cache-Control": _CACHE_NO_STORE, "X-Correlation-ID": correlation_id},
    )


@router.post("/text/classify")
async def classify_text(
    request: TextClassifyRequest,
    tenant_id: UUID = Depends(_require_tenant),
    db: AsyncSession = Depends(get_session),
) -> JSONResponse:
    """Classify text using the document extraction service with the 'unknown' document type."""
    correlation_id = str(uuid4())
    service_request_id = uuid4()

    try:
        client = _openai_client()
        extraction_svc = DocumentExtractionService(db=db, openai_client=client)
        result = await extraction_svc.extract(
            tenant_id=tenant_id,
            service_request_id=service_request_id,
            document_type="unknown",
            extracted_text=request.text,
            fields_to_extract=request.classification_types,
            phi_access_level="redacted",
        )
        classifications = {f.name: f.value for f in result.fields}
    except Exception as exc:
        err_str = str(exc).lower()
        if "api_key" in err_str or "authentication" in err_str or "unauthorized" in err_str:
            return _structured_error(
                code="LLM_UNAVAILABLE",
                message="AI service not configured. Please contact support.",
                correlation_id=correlation_id,
            )
        logger.error(
            "classify_text_error",
            extra={"svc_correlation_id": correlation_id, "svc_tenant_id": str(tenant_id)},
            exc_info=True,
        )
        return _structured_error(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred during classification.",
            correlation_id=correlation_id,
        )

    return JSONResponse(
        content={
            "classifications": classifications,
            "service_request_id": str(service_request_id),
            "confidence": result.overall_confidence,
            "requires_human_review": result.requires_human_review,
        },
        headers={"Cache-Control": _CACHE_NO_STORE, "X-Correlation-ID": correlation_id},
    )


@router.post("/text/extract-entities")
async def extract_entities(
    request: TextClassifyRequest,
    tenant_id: UUID = Depends(_require_tenant),
    db: AsyncSession = Depends(get_session),
) -> JSONResponse:
    """Extract named entities from text using the document extraction service."""
    correlation_id = str(uuid4())
    service_request_id = uuid4()

    _ENTITY_FIELDS = [
        "member_id", "ndc", "npi", "drug_name", "pharmacy_name",
        "prescriber_name", "date_of_service", "claim_number",
    ]

    try:
        client = _openai_client()
        extraction_svc = DocumentExtractionService(db=db, openai_client=client)
        result = await extraction_svc.extract(
            tenant_id=tenant_id,
            service_request_id=service_request_id,
            document_type="unknown",
            extracted_text=request.text,
            fields_to_extract=_ENTITY_FIELDS,
            phi_access_level="redacted",
        )
        entities = [
            {
                "name": f.name,
                "value": f.value,
                "confidence": f.confidence,
                "requires_review": f.requires_review,
            }
            for f in result.fields
            if f.value
        ]
    except Exception as exc:
        err_str = str(exc).lower()
        if "api_key" in err_str or "authentication" in err_str or "unauthorized" in err_str:
            return _structured_error(
                code="LLM_UNAVAILABLE",
                message="AI service not configured. Please contact support.",
                correlation_id=correlation_id,
            )
        logger.error(
            "extract_entities_error",
            extra={"svc_correlation_id": correlation_id, "svc_tenant_id": str(tenant_id)},
            exc_info=True,
        )
        return _structured_error(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred during entity extraction.",
            correlation_id=correlation_id,
        )

    return JSONResponse(
        content={
            "entities": entities,
            "service_request_id": str(service_request_id),
        },
        headers={"Cache-Control": _CACHE_NO_STORE, "X-Correlation-ID": correlation_id},
    )


@router.post("/generate")
async def generate_content(
    request: GenerateContentRequest,
    tenant_id: UUID = Depends(_require_tenant),
    db: AsyncSession = Depends(get_session),
) -> JSONResponse:
    """Generate content using a named prompt template via RagService."""
    correlation_id = str(uuid4())
    service_request_id = uuid4()

    # Build a generation message using the template name and context
    context_str = "\n".join(f"{k}: {v}" for k, v in request.context_data.items())
    prompt_content = (
        f"Generate a {request.template_name} document.\n"
        f"Context data:\n{context_str}\n\n"
        "Provide a professional, pharmacy-benefit-focused document. "
        "Include citations where applicable."
    )

    try:
        client = _openai_client()
        openai_request = OpenAIRequest(
            tenant_id=str(tenant_id),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a pharmacy benefit document generation assistant. "
                        "Do not include PHI in your response unless the caller has passed "
                        "phi_access_level=full. Generate professional, accurate documents."
                    ),
                },
                {"role": "user", "content": prompt_content},
            ],
            model="gpt-4.1",
            temperature=Decimal("0.2"),
            phi_access_level="redacted",
        )
        response = await client.complete(openai_request)
        generated_content = response.content
        requires_human_review = True
    except Exception as exc:
        err_str = str(exc).lower()
        if "api_key" in err_str or "authentication" in err_str or "unauthorized" in err_str:
            return _structured_error(
                code="LLM_UNAVAILABLE",
                message="AI service not configured. Please contact support.",
                correlation_id=correlation_id,
            )
        logger.error(
            "generate_content_error",
            extra={"svc_correlation_id": correlation_id, "svc_tenant_id": str(tenant_id)},
            exc_info=True,
        )
        return _structured_error(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred during content generation.",
            correlation_id=correlation_id,
        )

    response_data = GeneratedContentResponse(
        content=generated_content,
        template_name=request.template_name,
        requires_human_review=requires_human_review,
        service_request_id=str(service_request_id),
    )
    return JSONResponse(
        content=response_data.model_dump(),
        headers={"Cache-Control": _CACHE_NO_STORE, "X-Correlation-ID": correlation_id},
    )


@router.get("/generate/templates")
async def list_templates(
    tenant_id: UUID = Depends(_require_tenant),
    db: AsyncSession = Depends(get_session),
) -> JSONResponse:
    """Return tenant-specific prompt templates from DB, falling back to built-in list."""
    correlation_id = str(uuid4())

    _BUILTIN_TEMPLATES = [
        "PA Request Letter",
        "PA Appeal Letter",
        "Audit Demand Letter",
        "Investigation Summary",
        "Member Communication",
        "Client Report Narrative",
        "Corrective Action Plan",
    ]

    try:
        stmt = (
            select(AiNlpPromptTemplate.name)
            .where(
                AiNlpPromptTemplate.is_active.is_(True),
                (AiNlpPromptTemplate.tenant_id == tenant_id)
                | (AiNlpPromptTemplate.tenant_id.is_(None)),
            )
            .order_by(AiNlpPromptTemplate.name)
        )
        result = await db.execute(stmt)
        db_templates = [row[0] for row in result.fetchall()]
        templates = db_templates if db_templates else _BUILTIN_TEMPLATES
    except Exception:
        logger.warning(
            "list_templates_db_fallback",
            extra={"svc_tenant_id": str(tenant_id)},
        )
        templates = _BUILTIN_TEMPLATES

    return JSONResponse(
        content={"templates": templates},
        headers={"Cache-Control": _CACHE_NO_STORE, "X-Correlation-ID": correlation_id},
    )


@router.get("/usage")
async def get_usage(
    tenant_id: UUID = Depends(_require_tenant),
    db: AsyncSession = Depends(get_session),
) -> JSONResponse:
    correlation_id = str(uuid4())

    try:
        usage_logger = UsageLogger(db=db)
        usage = await usage_logger.get_usage_stats(tenant_id=tenant_id)
    except Exception:
        logger.error(
            "get_usage_error",
            extra={"svc_correlation_id": correlation_id, "svc_tenant_id": str(tenant_id)},
            exc_info=True,
        )
        usage = []

    return JSONResponse(
        content={"usage": usage, "tenant_id": str(tenant_id)},
        headers={"Cache-Control": _CACHE_NO_STORE, "X-Correlation-ID": correlation_id},
    )


@router.get("/usage/by-module")
async def get_usage_by_module(
    tenant_id: UUID = Depends(_require_tenant),
    db: AsyncSession = Depends(get_session),
) -> JSONResponse:
    correlation_id = str(uuid4())

    try:
        usage_logger = UsageLogger(db=db)
        usage_by_module = await usage_logger.get_usage_by_module(tenant_id=tenant_id)
    except Exception:
        logger.error(
            "get_usage_by_module_error",
            extra={"svc_correlation_id": correlation_id, "svc_tenant_id": str(tenant_id)},
            exc_info=True,
        )
        usage_by_module = []

    return JSONResponse(
        content={"usage_by_module": usage_by_module, "tenant_id": str(tenant_id)},
        headers={"Cache-Control": _CACHE_NO_STORE, "X-Correlation-ID": correlation_id},
    )
