"""API request schemas for the AI/NLP module."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, field_validator

_VALID_PORTAL_TYPES = frozenset({"pharmacy", "member", "client", "medical"})
_VALID_DOCUMENT_TYPES = frozenset({
    "eob", "prior_auth_form", "medical_record", "cms_1500",
    "cms_1450", "pharmacy_invoice", "audit_evidence", "appeal_letter", "unknown",
})


class ChatRequest(BaseModel):
    session_id: str
    portal_type: str
    message: str

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message must not be empty")
        if len(v) > 5000:
            raise ValueError("message must not exceed 5000 characters")
        return v

    @field_validator("portal_type")
    @classmethod
    def portal_type_valid(cls, v: str) -> str:
        if v not in _VALID_PORTAL_TYPES:
            raise ValueError(f"portal_type must be one of {_VALID_PORTAL_TYPES}")
        return v


class DocumentProcessRequest(BaseModel):
    document_type: str
    extracted_text: str
    fields_to_extract: list[str]

    @field_validator("document_type")
    @classmethod
    def document_type_valid(cls, v: str) -> str:
        if v not in _VALID_DOCUMENT_TYPES:
            raise ValueError(f"document_type must be one of {_VALID_DOCUMENT_TYPES}")
        return v

    @field_validator("fields_to_extract")
    @classmethod
    def fields_not_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("fields_to_extract must not be empty")
        return v


class GenerateContentRequest(BaseModel):
    template_name: str
    context_data: dict[str, Any]

    @field_validator("template_name")
    @classmethod
    def template_name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("template_name must not be empty")
        return v


class TextClassifyRequest(BaseModel):
    text: str
    classification_types: list[str] = ["document_type", "sentiment", "urgency"]

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be empty")
        return v
