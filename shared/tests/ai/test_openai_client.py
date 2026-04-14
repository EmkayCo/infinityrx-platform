"""Tests for shared.ai.openai_client — written FIRST (TDD).

Every Azure OpenAI call in the platform must go through this client.
Tests cover: configuration, PHI scrubbing, cost logging (Decimal), retry
on 429/5xx, fail-fast on 4xx, circuit breaker, and usage logging.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.ai.openai_client import (
    OpenAIClient,
    OpenAIConfig,
    OpenAIRequest,
    OpenAIResponse,
    PHIScrubber,
    UsageRecord,
    scrub_phi,
)


# ---------------------------------------------------------------------------
# PHI Scrubber tests (100% coverage required)
# ---------------------------------------------------------------------------


class TestPHIScrubber:
    def test_scrub_ssn_nine_digits(self) -> None:
        result = scrub_phi("Patient SSN: 123-45-6789 needs review")
        assert "123-45-6789" not in result
        assert "[REDACTED-SSN]" in result

    def test_scrub_ssn_no_dashes(self) -> None:
        result = scrub_phi("SSN 123456789 on file")
        assert "123456789" not in result
        assert "[REDACTED-SSN]" in result

    def test_scrub_dob_mm_dd_yyyy(self) -> None:
        result = scrub_phi("DOB: 01/15/1980")
        assert "01/15/1980" not in result
        assert "[REDACTED-DOB]" in result

    def test_scrub_dob_yyyy_mm_dd(self) -> None:
        result = scrub_phi("born 1980-01-15 per records")
        assert "1980-01-15" not in result
        assert "[REDACTED-DOB]" in result

    def test_scrub_phone_e164(self) -> None:
        result = scrub_phi("Call +1-555-123-4567 for info")
        assert "+1-555-123-4567" not in result
        assert "[REDACTED-PHONE]" in result

    def test_scrub_phone_plain(self) -> None:
        result = scrub_phi("phone 5551234567 listed")
        assert "5551234567" not in result
        assert "[REDACTED-PHONE]" in result

    def test_scrub_email(self) -> None:
        result = scrub_phi("email john.doe@example.com for member")
        assert "john.doe@example.com" not in result
        assert "[REDACTED-EMAIL]" in result

    def test_scrub_does_not_alter_clinical_terms(self) -> None:
        text = "diagnosis: hypertension ICD-10 I10"
        result = scrub_phi(text)
        assert "hypertension" in result
        assert "I10" in result

    def test_scrub_empty_string(self) -> None:
        assert scrub_phi("") == ""

    def test_phi_scrubber_class_same_as_function(self) -> None:
        scrubber = PHIScrubber()
        text = "SSN 123-45-6789 DOB 01/15/1980"
        assert scrubber.scrub(text) == scrub_phi(text)


# ---------------------------------------------------------------------------
# UsageRecord tests — Decimal cost, never float
# ---------------------------------------------------------------------------


class TestUsageRecord:
    def test_cost_is_decimal(self) -> None:
        record = UsageRecord(
            tenant_id="t1",
            model="gpt-4.1",
            prompt_tokens=100,
            completion_tokens=50,
            total_cost_usd=Decimal("0.001500"),
        )
        assert isinstance(record.total_cost_usd, Decimal)

    def test_cost_rejects_float(self) -> None:
        with pytest.raises((TypeError, ValueError)):
            UsageRecord(
                tenant_id="t1",
                model="gpt-4.1",
                prompt_tokens=100,
                completion_tokens=50,
                total_cost_usd=0.0015,  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------------------
# OpenAIConfig — reads from environment, never hardcoded
# ---------------------------------------------------------------------------


class TestOpenAIConfig:
    def test_config_reads_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key-abc")
        monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT_GPT41", "gpt-41-deploy")
        cfg = OpenAIConfig()
        assert cfg.endpoint == "https://test.openai.azure.com/"
        assert cfg.api_key == "test-key-abc"
        assert cfg.api_version == "2024-02-01"
        assert cfg.deployment_gpt41 == "gpt-41-deploy"

    def test_config_has_no_hardcoded_secrets(self) -> None:
        import inspect

        import shared.ai.openai_client as mod

        source = inspect.getsource(mod)
        # Must not contain literal API key patterns
        assert "sk-" not in source
        assert "Bearer " not in source


# ---------------------------------------------------------------------------
# OpenAIClient — core call path
# ---------------------------------------------------------------------------


class TestOpenAIClient:
    def _make_mock_response(
        self,
        content: str = "test response",
        prompt_tokens: int = 10,
        completion_tokens: int = 5,
    ) -> MagicMock:
        choice = MagicMock()
        choice.message.content = content
        usage = MagicMock()
        usage.prompt_tokens = prompt_tokens
        usage.completion_tokens = completion_tokens
        usage.total_tokens = prompt_tokens + completion_tokens
        resp = MagicMock()
        resp.choices = [choice]
        resp.usage = usage
        resp.model = "gpt-4.1"
        return resp

    @pytest.fixture()
    def config(self, monkeypatch: pytest.MonkeyPatch) -> OpenAIConfig:
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "fake-key")
        monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT_GPT41", "gpt-41-deploy")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT_GPT41_MINI", "gpt-41-mini-deploy")
        return OpenAIConfig()

    @pytest.mark.asyncio
    async def test_complete_returns_response(
        self, config: OpenAIConfig
    ) -> None:
        client = OpenAIClient(config=config)
        mock_resp = self._make_mock_response("hello world", 10, 5)

        with patch.object(
            client._aclient.chat.completions,  # type: ignore[attr-defined]
            "create",
            new=AsyncMock(return_value=mock_resp),
        ):
            request = OpenAIRequest(
                tenant_id="tenant-1",
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-4.1",
                temperature=Decimal("0"),
            )
            response = await client.complete(request)

        assert isinstance(response, OpenAIResponse)
        assert response.content == "hello world"
        assert response.prompt_tokens == 10
        assert response.completion_tokens == 5

    @pytest.mark.asyncio
    async def test_cost_logged_as_decimal(
        self, config: OpenAIConfig
    ) -> None:
        client = OpenAIClient(config=config)
        mock_resp = self._make_mock_response("result", 1000, 500)
        usage_records: list[UsageRecord] = []

        async def capture_usage(record: UsageRecord) -> None:
            usage_records.append(record)

        client.on_usage = capture_usage

        with patch.object(
            client._aclient.chat.completions,  # type: ignore[attr-defined]
            "create",
            new=AsyncMock(return_value=mock_resp),
        ):
            request = OpenAIRequest(
                tenant_id="tenant-1",
                messages=[{"role": "user", "content": "summarize"}],
                model="gpt-4.1",
                temperature=Decimal("0"),
            )
            await client.complete(request)

        assert len(usage_records) == 1
        assert isinstance(usage_records[0].total_cost_usd, Decimal)
        assert usage_records[0].prompt_tokens == 1000
        assert usage_records[0].completion_tokens == 500

    @pytest.mark.asyncio
    async def test_phi_scrubbed_before_sending(
        self, config: OpenAIConfig
    ) -> None:
        client = OpenAIClient(config=config)
        mock_resp = self._make_mock_response("ok", 5, 3)
        captured_calls: list[Any] = []

        async def mock_create(**kwargs: Any) -> MagicMock:
            captured_calls.append(kwargs)
            return mock_resp

        with patch.object(
            client._aclient.chat.completions,  # type: ignore[attr-defined]
            "create",
            new=AsyncMock(side_effect=mock_create),
        ):
            request = OpenAIRequest(
                tenant_id="tenant-1",
                messages=[{"role": "user", "content": "SSN is 123-45-6789"}],
                model="gpt-4.1",
                temperature=Decimal("0"),
                phi_access_level="redacted",
            )
            await client.complete(request)

        assert captured_calls
        sent_messages = captured_calls[0]["messages"]
        for msg in sent_messages:
            assert "123-45-6789" not in msg["content"]

    @pytest.mark.asyncio
    async def test_phi_not_scrubbed_when_full_access(
        self, config: OpenAIConfig
    ) -> None:
        client = OpenAIClient(config=config)
        mock_resp = self._make_mock_response("ok", 5, 3)
        captured_calls: list[Any] = []

        async def mock_create(**kwargs: Any) -> MagicMock:
            captured_calls.append(kwargs)
            return mock_resp

        with patch.object(
            client._aclient.chat.completions,  # type: ignore[attr-defined]
            "create",
            new=AsyncMock(side_effect=mock_create),
        ):
            request = OpenAIRequest(
                tenant_id="tenant-1",
                messages=[{"role": "user", "content": "SSN is 123-45-6789"}],
                model="gpt-4.1",
                temperature=Decimal("0"),
                phi_access_level="full",
            )
            await client.complete(request)

        sent_messages = captured_calls[0]["messages"]
        user_msg = next(m for m in sent_messages if m["role"] == "user")
        assert "123-45-6789" in user_msg["content"]

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit_error(
        self, config: OpenAIConfig
    ) -> None:
        from openai import RateLimitError

        client = OpenAIClient(config=config, max_retries=2, base_delay=0.01)
        mock_resp = self._make_mock_response("ok", 5, 3)
        call_count = 0

        async def flaky_create(**kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RateLimitError(
                    "rate limited",
                    response=MagicMock(status_code=429),
                    body=None,
                )
            return mock_resp

        with patch.object(
            client._aclient.chat.completions,  # type: ignore[attr-defined]
            "create",
            new=AsyncMock(side_effect=flaky_create),
        ):
            request = OpenAIRequest(
                tenant_id="tenant-1",
                messages=[{"role": "user", "content": "test"}],
                model="gpt-4.1",
                temperature=Decimal("0"),
            )
            response = await client.complete(request)

        assert response.content == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_fail_fast_on_400_error(
        self, config: OpenAIConfig
    ) -> None:
        from openai import BadRequestError

        client = OpenAIClient(config=config, max_retries=3, base_delay=0.01)
        call_count = 0

        async def bad_request_create(**kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            raise BadRequestError(
                "invalid request",
                response=MagicMock(status_code=400),
                body=None,
            )

        with patch.object(
            client._aclient.chat.completions,  # type: ignore[attr-defined]
            "create",
            new=AsyncMock(side_effect=bad_request_create),
        ):
            request = OpenAIRequest(
                tenant_id="tenant-1",
                messages=[{"role": "user", "content": "bad"}],
                model="gpt-4.1",
                temperature=Decimal("0"),
            )
            with pytest.raises(BadRequestError):
                await client.complete(request)

        assert call_count == 1  # No retries on 4xx

    @pytest.mark.asyncio
    async def test_temperature_zero_for_extraction(
        self, config: OpenAIConfig
    ) -> None:
        client = OpenAIClient(config=config)
        mock_resp = self._make_mock_response("extracted", 10, 5)
        captured_calls: list[Any] = []

        async def mock_create(**kwargs: Any) -> MagicMock:
            captured_calls.append(kwargs)
            return mock_resp

        with patch.object(
            client._aclient.chat.completions,  # type: ignore[attr-defined]
            "create",
            new=AsyncMock(side_effect=mock_create),
        ):
            request = OpenAIRequest(
                tenant_id="tenant-1",
                messages=[{"role": "user", "content": "extract"}],
                model="gpt-4.1",
                temperature=Decimal("0"),
            )
            await client.complete(request)

        assert captured_calls[0]["temperature"] == 0.0
