"""API response schemas for the AI/NLP module."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ServiceRequestResponse(BaseModel):
    id: str
    service_type: str
    status: str
    confidence_score: float | None
    requires_human_review: bool


class ExtractionFieldResponse(BaseModel):
    name: str
    value: str
    confidence: float
    requires_review: bool


class DocumentResultResponse(BaseModel):
    service_request_id: str
    document_type: str
    overall_confidence: float
    requires_human_review: bool
    fields: list[ExtractionFieldResponse]
    low_confidence_field_count: int


class SourceCitationResponse(BaseModel):
    source_type: str
    source_id: str
    snippet: str


class ChatMessageResponse(BaseModel):
    content: str
    sources: list[dict[str, Any]]
    confidence: float
    escalate: bool
    escalation_reason: str = ""


class GeneratedContentResponse(BaseModel):
    content: str
    template_name: str
    requires_human_review: bool = True
    service_request_id: str


class ErrorResponse(BaseModel):
    error: dict[str, str]
