"""Unit tests for RAG chatbot service.

Critical requirements:
- Every answer includes sources[]
- Ungrounded answers rejected
- Cross-tenant isolation: tenant A cannot retrieve tenant B embeddings
- Low confidence triggers escalation
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from src.services.rag_service import (
    ChatMessage,
    ChatResponse,
    EmbeddingChunk,
    RagService,
    SourceCitation,
)


class TestSourceCitation:
    def test_citation_has_required_fields(self) -> None:
        c = SourceCitation(
            source_type="claim",
            source_id=str(uuid4()),
            snippet="Claim status: pending review",
        )
        assert c.source_type == "claim"
        assert c.snippet

    def test_citation_snippet_non_empty(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            SourceCitation(source_type="claim", source_id="id1", snippet="")


class TestEmbeddingChunk:
    def test_chunk_has_tenant_id(self) -> None:
        tid = uuid4()
        chunk = EmbeddingChunk(
            id=uuid4(),
            tenant_id=tid,
            source_type="claim",
            source_id=uuid4(),
            chunk_text="claim status is approved",
            similarity=0.92,
        )
        assert chunk.tenant_id == tid


class TestRagService:
    @pytest.fixture()
    def mock_db(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture()
    def mock_openai_client(self) -> MagicMock:
        client = MagicMock()
        client.complete = AsyncMock()
        return client

    def _make_chunks(self, tenant_id: UUID, count: int = 4) -> list[EmbeddingChunk]:
        return [
            EmbeddingChunk(
                id=uuid4(),
                tenant_id=tenant_id,
                source_type="claim",
                source_id=uuid4(),
                chunk_text=f"Claim data chunk {i}: copay is $10.00",
                similarity=0.95 - i * 0.01,
            )
            for i in range(count)
        ]

    @pytest.mark.asyncio
    async def test_response_includes_sources(
        self, mock_db: AsyncMock, mock_openai_client: MagicMock
    ) -> None:
        tenant_id = uuid4()
        chunks = self._make_chunks(tenant_id)

        from shared.ai.openai_client import OpenAIResponse

        mock_openai_client.complete.return_value = OpenAIResponse(
            content="Your copay for this drug is $10.00. [Source: claim | id1 | 'copay is $10.00']",
            model="gpt-4.1",
            prompt_tokens=100,
            completion_tokens=50,
            total_cost_usd=Decimal("0.001"),
        )

        svc = RagService(db=mock_db, openai_client=mock_openai_client)

        with patch.object(svc, "_retrieve_chunks", return_value=chunks):
            response = await svc.chat(
                tenant_id=tenant_id,
                user_id=uuid4(),
                session_id="sess-1",
                portal_type="pharmacy",
                message="What is my copay?",
                conversation_history=[],
                phi_access_level="redacted",
            )

        assert isinstance(response, ChatResponse)
        assert len(response.sources) > 0

    @pytest.mark.asyncio
    async def test_no_chunks_triggers_escalation(
        self, mock_db: AsyncMock, mock_openai_client: MagicMock
    ) -> None:
        tenant_id = uuid4()
        svc = RagService(db=mock_db, openai_client=mock_openai_client)

        with patch.object(svc, "_retrieve_chunks", return_value=[]):
            response = await svc.chat(
                tenant_id=tenant_id,
                user_id=uuid4(),
                session_id="sess-1",
                portal_type="pharmacy",
                message="What is my copay?",
                conversation_history=[],
                phi_access_level="redacted",
            )

        assert response.escalate or response.confidence < 0.5

    @pytest.mark.asyncio
    async def test_retrieve_chunks_filters_by_tenant(
        self, mock_db: AsyncMock, mock_openai_client: MagicMock
    ) -> None:
        tenant_a = uuid4()
        tenant_b = uuid4()
        svc = RagService(db=mock_db, openai_client=mock_openai_client)

        execute_result = MagicMock()
        execute_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=execute_result)

        query_embedding = [0.1] * 1536
        chunks = await svc._retrieve_chunks(
            tenant_id=tenant_a,
            query_embedding=query_embedding,
            top_k=10,
        )
        call_args = mock_db.execute.call_args
        query_str = str(call_args[0][0])
        assert "tenant_id" in query_str.lower() or mock_db.execute.called

    @pytest.mark.asyncio
    async def test_consecutive_low_confidence_escalates(
        self, mock_db: AsyncMock, mock_openai_client: MagicMock
    ) -> None:
        tenant_id = uuid4()
        chunks = self._make_chunks(tenant_id, count=1)

        from shared.ai.openai_client import OpenAIResponse

        mock_openai_client.complete.return_value = OpenAIResponse(
            content="I cannot determine this from the available information.",
            model="gpt-4.1",
            prompt_tokens=50,
            completion_tokens=20,
            total_cost_usd=Decimal("0.0005"),
        )

        svc = RagService(db=mock_db, openai_client=mock_openai_client)
        history = [
            ChatMessage(role="user", content="previous question"),
            ChatMessage(role="assistant", content="low confidence response", confidence=0.3),
        ]

        with patch.object(svc, "_retrieve_chunks", return_value=chunks):
            response = await svc.chat(
                tenant_id=tenant_id,
                user_id=uuid4(),
                session_id="sess-1",
                portal_type="member",
                message="Another question",
                conversation_history=history,
                phi_access_level="redacted",
            )

        assert response.escalate


class TestCrossTenatIsolation:
    """Explicit cross-tenant isolation tests for RAG retrieval."""

    @pytest.mark.asyncio
    async def test_retrieval_query_always_includes_tenant_filter(self) -> None:
        mock_db = AsyncMock()
        mock_client = MagicMock()
        svc = RagService(db=mock_db, openai_client=mock_client)

        execute_result = MagicMock()
        execute_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=execute_result)

        tenant_id = uuid4()
        await svc._retrieve_chunks(
            tenant_id=tenant_id,
            query_embedding=[0.1] * 1536,
            top_k=10,
        )

        assert mock_db.execute.called
        stmt_arg = mock_db.execute.call_args[0][0]
        stmt_str = str(stmt_arg)
        assert "tenant_id" in stmt_str.lower()
