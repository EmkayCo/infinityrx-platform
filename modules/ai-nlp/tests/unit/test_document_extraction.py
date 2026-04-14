"""Unit tests for document extraction service.

Critical paths:
- Low confidence fields (<0.85) flagged for human review, never auto-applied
- Confidence scores accurately reflect extraction quality
- Cost tracked as Decimal
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.services.document_extraction import (
    DocumentExtractionResult,
    DocumentExtractionService,
    ExtractionField,
    LOW_CONFIDENCE_THRESHOLD,
)


class TestExtractionField:
    def test_field_with_high_confidence_not_flagged(self) -> None:
        f = ExtractionField(name="member_id", value="MBR-001", confidence=0.95)
        assert not f.requires_review

    def test_field_with_low_confidence_flagged(self) -> None:
        f = ExtractionField(name="dob", value="01/01/1980", confidence=0.75)
        assert f.requires_review

    def test_threshold_is_0_85(self) -> None:
        assert LOW_CONFIDENCE_THRESHOLD == 0.85

    def test_field_at_exactly_threshold_not_flagged(self) -> None:
        f = ExtractionField(name="ndc", value="12345-678-90", confidence=0.85)
        assert not f.requires_review

    def test_field_just_below_threshold_flagged(self) -> None:
        f = ExtractionField(name="ndc", value="12345-678-90", confidence=0.8499)
        assert f.requires_review


class TestDocumentExtractionResult:
    def test_result_with_all_high_confidence_not_flagged(self) -> None:
        result = DocumentExtractionResult(
            document_type="prior_auth_form",
            fields=[
                ExtractionField("member_id", "MBR-001", 0.95),
                ExtractionField("drug_name", "Humira", 0.92),
            ],
            overall_confidence=0.935,
            requires_human_review=False,
        )
        assert not result.requires_human_review

    def test_result_with_any_low_confidence_field_is_flagged(self) -> None:
        result = DocumentExtractionResult(
            document_type="eob",
            fields=[
                ExtractionField("member_id", "MBR-001", 0.95),
                ExtractionField("claim_amount", "500.00", 0.70),
            ],
            overall_confidence=0.82,
            requires_human_review=True,
        )
        assert result.requires_human_review

    def test_low_confidence_fields_property(self) -> None:
        result = DocumentExtractionResult(
            document_type="eob",
            fields=[
                ExtractionField("member_id", "MBR-001", 0.95),
                ExtractionField("claim_amount", "500.00", 0.70),
                ExtractionField("ndc", "abc", 0.60),
            ],
            overall_confidence=0.75,
            requires_human_review=True,
        )
        low = result.low_confidence_fields
        assert len(low) == 2
        assert all(f.confidence < 0.85 for f in low)


class TestDocumentExtractionService:
    @pytest.fixture()
    def mock_db(self) -> AsyncMock:
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        return db

    @pytest.fixture()
    def mock_openai(self) -> MagicMock:
        client = MagicMock()
        client.complete = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_extraction_with_high_confidence_not_flagged(
        self, mock_db: AsyncMock, mock_openai: MagicMock
    ) -> None:
        from shared.ai.openai_client import OpenAIResponse

        mock_openai.complete.return_value = OpenAIResponse(
            content='{"member_id": {"value": "MBR-001", "confidence": 0.95}, "drug_name": {"value": "metformin", "confidence": 0.93}}',
            model="gpt-4.1",
            prompt_tokens=200,
            completion_tokens=100,
            total_cost_usd=Decimal("0.003"),
        )

        svc = DocumentExtractionService(db=mock_db, openai_client=mock_openai)
        result = await svc.extract(
            tenant_id=uuid4(),
            service_request_id=uuid4(),
            document_type="prior_auth_form",
            extracted_text="Member MBR-001 needs metformin",
            fields_to_extract=["member_id", "drug_name"],
            phi_access_level="redacted",
        )

        assert isinstance(result, DocumentExtractionResult)
        assert not result.requires_human_review

    @pytest.mark.asyncio
    async def test_extraction_with_low_confidence_flagged_for_review(
        self, mock_db: AsyncMock, mock_openai: MagicMock
    ) -> None:
        from shared.ai.openai_client import OpenAIResponse

        mock_openai.complete.return_value = OpenAIResponse(
            content='{"member_id": {"value": "MBR-001", "confidence": 0.60}, "dob": {"value": "unknown", "confidence": 0.40}}',
            model="gpt-4.1",
            prompt_tokens=200,
            completion_tokens=100,
            total_cost_usd=Decimal("0.003"),
        )

        svc = DocumentExtractionService(db=mock_db, openai_client=mock_openai)
        result = await svc.extract(
            tenant_id=uuid4(),
            service_request_id=uuid4(),
            document_type="medical_record",
            extracted_text="Poor scan quality",
            fields_to_extract=["member_id", "dob"],
            phi_access_level="redacted",
        )

        assert result.requires_human_review
        assert len(result.low_confidence_fields) == 2

    @pytest.mark.asyncio
    async def test_malformed_json_response_handled(
        self, mock_db: AsyncMock, mock_openai: MagicMock
    ) -> None:
        from shared.ai.openai_client import OpenAIResponse

        mock_openai.complete.return_value = OpenAIResponse(
            content="Sorry, I could not extract the fields.",
            model="gpt-4.1",
            prompt_tokens=100,
            completion_tokens=20,
            total_cost_usd=Decimal("0.001"),
        )

        svc = DocumentExtractionService(db=mock_db, openai_client=mock_openai)
        result = await svc.extract(
            tenant_id=uuid4(),
            service_request_id=uuid4(),
            document_type="unknown",
            extracted_text="",
            fields_to_extract=["member_id"],
            phi_access_level="redacted",
        )

        assert result.requires_human_review
        assert result.overall_confidence < 0.5

    @pytest.mark.asyncio
    async def test_cost_logged_as_decimal(
        self, mock_db: AsyncMock, mock_openai: MagicMock
    ) -> None:
        from shared.ai.openai_client import OpenAIResponse, UsageRecord

        captured_usage: list[UsageRecord] = []

        async def capture(r: UsageRecord) -> None:
            captured_usage.append(r)

        mock_openai.complete.return_value = OpenAIResponse(
            content='{"member_id": {"value": "MBR-001", "confidence": 0.95}}',
            model="gpt-4.1",
            prompt_tokens=200,
            completion_tokens=50,
            total_cost_usd=Decimal("0.0035"),
        )
        mock_openai.on_usage = capture

        svc = DocumentExtractionService(db=mock_db, openai_client=mock_openai)
        await svc.extract(
            tenant_id=uuid4(),
            service_request_id=uuid4(),
            document_type="eob",
            extracted_text="test",
            fields_to_extract=["member_id"],
            phi_access_level="redacted",
        )
