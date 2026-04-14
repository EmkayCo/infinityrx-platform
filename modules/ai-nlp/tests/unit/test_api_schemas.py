"""Unit tests for API request/response schemas."""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.api.schemas.requests import (
    ChatRequest,
    DocumentProcessRequest,
    GenerateContentRequest,
)
from src.api.schemas.responses import (
    ChatMessageResponse,
    ServiceRequestResponse,
)


class TestChatRequest:
    def test_valid_portal_types(self) -> None:
        for portal in ("pharmacy", "member", "client", "medical"):
            req = ChatRequest(
                session_id="sess-1",
                portal_type=portal,
                message="What is my copay?",
            )
            assert req.portal_type == portal

    def test_message_must_not_be_empty(self) -> None:
        with pytest.raises(ValueError):
            ChatRequest(session_id="sess-1", portal_type="pharmacy", message="")

    def test_message_max_length(self) -> None:
        long_msg = "x" * 5001
        with pytest.raises(ValueError):
            ChatRequest(session_id="sess-1", portal_type="pharmacy", message=long_msg)


class TestDocumentProcessRequest:
    def test_valid_document_types(self) -> None:
        for doc_type in (
            "eob", "prior_auth_form", "medical_record", "cms_1500",
            "cms_1450", "pharmacy_invoice", "audit_evidence", "appeal_letter"
        ):
            req = DocumentProcessRequest(
                document_type=doc_type,
                extracted_text="sample text",
                fields_to_extract=["member_id"],
            )
            assert req.document_type == doc_type

    def test_fields_to_extract_must_not_be_empty(self) -> None:
        with pytest.raises(ValueError):
            DocumentProcessRequest(
                document_type="eob",
                extracted_text="sample",
                fields_to_extract=[],
            )


class TestGenerateContentRequest:
    def test_template_name_required(self) -> None:
        with pytest.raises(ValueError):
            GenerateContentRequest(
                template_name="",
                context_data={"member": "MBR-001"},
            )

    def test_valid_request(self) -> None:
        req = GenerateContentRequest(
            template_name="PA Request Letter",
            context_data={"drug_name": "Humira"},
        )
        assert req.template_name == "PA Request Letter"


class TestServiceRequestResponse:
    def test_confidence_is_optional(self) -> None:
        resp = ServiceRequestResponse(
            id=str(uuid4()),
            service_type="document_extraction",
            status="completed",
            confidence_score=None,
            requires_human_review=False,
        )
        assert resp.confidence_score is None

    def test_requires_human_review_included(self) -> None:
        resp = ServiceRequestResponse(
            id=str(uuid4()),
            service_type="document_extraction",
            status="human_review_required",
            confidence_score=0.70,
            requires_human_review=True,
        )
        assert resp.requires_human_review


class TestChatMessageResponse:
    def test_sources_list_present(self) -> None:
        resp = ChatMessageResponse(
            content="Your copay is $10.",
            sources=[{"source_type": "claim", "source_id": "id1", "snippet": "copay $10"}],
            confidence=0.92,
            escalate=False,
        )
        assert len(resp.sources) == 1

    def test_escalate_flag_present(self) -> None:
        resp = ChatMessageResponse(
            content="Please contact a human agent.",
            sources=[],
            confidence=0.2,
            escalate=True,
        )
        assert resp.escalate
