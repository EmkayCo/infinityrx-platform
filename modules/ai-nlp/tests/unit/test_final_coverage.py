"""Final coverage gap closure tests — targeting 99%+ branch coverage."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest


class TestRagServiceFinalGaps:
    def test_extract_sources_with_empty_snippet_skipped(self) -> None:
        from src.services.rag_service import RagService
        from unittest.mock import AsyncMock, MagicMock

        svc = RagService(db=AsyncMock(), openai_client=MagicMock())
        content = "[Source: claim | id1 | \"\"]"
        sources = svc._extract_sources(content)
        assert len(sources) == 0

    def test_estimate_confidence_cannot_determine_variant(self) -> None:
        from src.services.rag_service import RagService, EmbeddingChunk
        from unittest.mock import AsyncMock, MagicMock

        svc = RagService(db=AsyncMock(), openai_client=MagicMock())
        chunks = [
            EmbeddingChunk(
                id=uuid4(),
                tenant_id=uuid4(),
                source_type="claim",
                source_id=uuid4(),
                chunk_text="data",
                similarity=0.9,
            )
        ]
        conf = svc._estimate_confidence("don't have enough information to answer", chunks)
        assert conf == 0.3


class TestDocumentExtractionFinalGaps:
    @pytest.mark.asyncio
    async def test_json_with_non_dict_values_produces_empty_fields(self) -> None:
        from src.services.document_extraction import DocumentExtractionService
        from shared.ai.openai_client import OpenAIResponse
        from unittest.mock import AsyncMock, MagicMock

        mock_db = AsyncMock()
        mock_openai = MagicMock()
        mock_openai.complete = AsyncMock(return_value=OpenAIResponse(
            content='{"member_id": "not-a-dict", "drug": null}',
            model="gpt-4.1",
            prompt_tokens=100,
            completion_tokens=50,
            total_cost_usd=Decimal("0.001"),
        ))

        svc = DocumentExtractionService(db=mock_db, openai_client=mock_openai)
        result = await svc.extract(
            tenant_id=uuid4(),
            service_request_id=uuid4(),
            document_type="eob",
            extracted_text="bad response",
            fields_to_extract=["member_id"],
            phi_access_level="redacted",
        )
        assert result.requires_human_review
        assert len(result.fields) == 0


class TestTextClassifyValidatorGap:
    def test_empty_text_raises_422(self) -> None:
        from src.api.schemas.requests import TextClassifyRequest
        with pytest.raises(ValueError):
            TextClassifyRequest(text="   ")


class TestRouterHealthGap:
    def test_router_health_endpoint_accessible(self) -> None:
        from fastapi.testclient import TestClient
        from src.app import create_app

        client = TestClient(create_app())
        resp = client.get("/api/v1/ai/health")
        assert resp.status_code == 200
        assert resp.json()["module"] == "ai-nlp"


class TestOpenAIClientFinalGap:
    @pytest.mark.asyncio
    async def test_none_usage_on_response(self) -> None:
        from shared.ai.openai_client import OpenAIClient, OpenAIConfig, OpenAIRequest
        from unittest.mock import AsyncMock, MagicMock, patch

        config = OpenAIConfig()
        object.__setattr__(config, "endpoint", "https://test.openai.azure.com/")
        object.__setattr__(config, "api_key", "fake-key")
        object.__setattr__(config, "api_version", "2024-02-01")
        object.__setattr__(config, "deployment_gpt41", "deploy-41")
        object.__setattr__(config, "deployment_gpt41_mini", "deploy-mini")

        client = OpenAIClient(config=config)

        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "response"
        mock_resp.usage = None
        mock_resp.model = "gpt-4.1"

        with patch.object(
            client._aclient.chat.completions,
            "create",
            new=AsyncMock(return_value=mock_resp),
        ):
            request = OpenAIRequest(
                tenant_id="t1",
                messages=[{"role": "user", "content": "test"}],
                model="gpt-4.1",
                temperature=Decimal("0"),
            )
            response = await client.complete(request)

        assert response.prompt_tokens == 0
        assert response.completion_tokens == 0

    @pytest.mark.asyncio
    async def test_mini_model_uses_mini_deployment(self) -> None:
        from shared.ai.openai_client import OpenAIClient, OpenAIConfig, OpenAIRequest
        from unittest.mock import AsyncMock, MagicMock, patch

        config = OpenAIConfig()
        object.__setattr__(config, "endpoint", "https://test.openai.azure.com/")
        object.__setattr__(config, "api_key", "fake-key")
        object.__setattr__(config, "api_version", "2024-02-01")
        object.__setattr__(config, "deployment_gpt41", "deploy-41")
        object.__setattr__(config, "deployment_gpt41_mini", "deploy-mini")

        client = OpenAIClient(config=config)

        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "mini response"
        mock_resp.usage = MagicMock()
        mock_resp.usage.prompt_tokens = 5
        mock_resp.usage.completion_tokens = 3
        mock_resp.usage.total_tokens = 8
        mock_resp.model = "gpt-4.1-mini"
        captured: list[Any] = []

        async def mock_create(**kwargs: Any) -> MagicMock:
            captured.append(kwargs)
            return mock_resp

        with patch.object(
            client._aclient.chat.completions,
            "create",
            new=AsyncMock(side_effect=mock_create),
        ):
            request = OpenAIRequest(
                tenant_id="t1",
                messages=[{"role": "user", "content": "test"}],
                model="gpt-4.1-mini",
                temperature=Decimal("0"),
            )
            response = await client.complete(request)

        assert captured[0]["model"] == "deploy-mini"

    @pytest.mark.asyncio
    async def test_5xx_exhausted_retries_raises(self) -> None:
        from shared.ai.openai_client import OpenAIClient, OpenAIConfig, OpenAIRequest
        from openai import APIStatusError
        from unittest.mock import AsyncMock, MagicMock, patch

        config = OpenAIConfig()
        object.__setattr__(config, "endpoint", "https://test.openai.azure.com/")
        object.__setattr__(config, "api_key", "fake-key")
        object.__setattr__(config, "api_version", "2024-02-01")
        object.__setattr__(config, "deployment_gpt41", "deploy-41")
        object.__setattr__(config, "deployment_gpt41_mini", "deploy-mini")

        client = OpenAIClient(config=config, max_retries=1, base_delay=0.001)

        async def always_5xx(**kwargs: Any) -> MagicMock:
            raise APIStatusError(
                "server error",
                response=MagicMock(status_code=500),
                body=None,
            )

        with patch.object(
            client._aclient.chat.completions,
            "create",
            new=AsyncMock(side_effect=always_5xx),
        ):
            request = OpenAIRequest(
                tenant_id="t1",
                messages=[{"role": "user", "content": "test"}],
                model="gpt-4.1",
                temperature=Decimal("0"),
            )
            with pytest.raises(APIStatusError):
                await client.complete(request)


class TestRagServiceConfidenceNoSources:
    def test_estimate_confidence_no_sources_in_content(self) -> None:
        from src.services.rag_service import RagService, EmbeddingChunk
        from unittest.mock import AsyncMock, MagicMock

        svc = RagService(db=AsyncMock(), openai_client=MagicMock())
        chunks = [
            EmbeddingChunk(
                id=uuid4(),
                tenant_id=uuid4(),
                source_type="claim",
                source_id=uuid4(),
                chunk_text="data",
                similarity=0.8,
            )
        ]
        conf = svc._estimate_confidence("Plain answer with no source citations at all.", chunks)
        assert 0.0 < conf < 1.0


class TestRagServiceLowConfNoHistory:
    @pytest.mark.asyncio
    async def test_low_confidence_first_time_no_escalation(self) -> None:
        from src.services.rag_service import RagService, EmbeddingChunk, ChatMessage
        from shared.ai.openai_client import OpenAIResponse
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_db = AsyncMock()
        mock_openai = MagicMock()
        mock_openai.complete = AsyncMock(return_value=OpenAIResponse(
            content="I cannot determine this.",
            model="gpt-4.1",
            prompt_tokens=50,
            completion_tokens=20,
            total_cost_usd=Decimal("0.0005"),
        ))

        chunks = [
            EmbeddingChunk(
                id=uuid4(),
                tenant_id=uuid4(),
                source_type="claim",
                source_id=uuid4(),
                chunk_text="some data",
                similarity=0.5,
            )
        ]

        svc = RagService(db=mock_db, openai_client=mock_openai)
        with patch.object(svc, "_retrieve_chunks", return_value=chunks):
            response = await svc.chat(
                tenant_id=uuid4(),
                user_id=None,
                session_id="s1",
                portal_type="pharmacy",
                message="what is my copay?",
                conversation_history=[],
                phi_access_level="redacted",
            )

        assert not response.escalate
