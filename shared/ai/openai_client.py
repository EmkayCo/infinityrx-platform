"""Shared Azure OpenAI client — single chokepoint for all LLM calls.

Every module that needs to call Azure OpenAI MUST import and use this client.
It provides:
- Configuration from environment (never hardcoded)
- PHI scrubbing before sending to OpenAI (unless phi_access_level=full)
- Exponential backoff retry on RateLimitError and 5xx
- Fail-fast on 4xx (except 429)
- Cost logging in Decimal (never float)
- Token counting and usage callbacks
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from openai import APIStatusError, AsyncAzureOpenAI, RateLimitError
from pydantic_settings import BaseSettings

logger = logging.getLogger("shared.ai.openai_client")

# ---------------------------------------------------------------------------
# Cost per 1K tokens (USD) — these are estimates; real cost tracked in DB
# ---------------------------------------------------------------------------

_COST_PER_1K: dict[str, dict[str, Decimal]] = {
    "gpt-4.1": {"input": Decimal("0.000010"), "output": Decimal("0.000030")},
    "gpt-4.1-mini": {"input": Decimal("0.000001"), "output": Decimal("0.000004")},
}

_DEFAULT_COST = {"input": Decimal("0.000010"), "output": Decimal("0.000030")}


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> Decimal:
    rates = _COST_PER_1K.get(model, _DEFAULT_COST)
    input_cost = rates["input"] * Decimal(str(prompt_tokens)) / Decimal("1000")
    output_cost = rates["output"] * Decimal(str(completion_tokens)) / Decimal("1000")
    return (input_cost + output_cost).quantize(Decimal("0.000001"))


# ---------------------------------------------------------------------------
# PHI Scrubber
# ---------------------------------------------------------------------------

_PHI_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED-SSN]"),
    (re.compile(r"\b\d{9}\b"), "[REDACTED-SSN]"),
    (re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b"), "[REDACTED-DOB]"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), "[REDACTED-DOB]"),
    (re.compile(r"\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[REDACTED-PHONE]"),
    (re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), "[REDACTED-EMAIL]"),
]


def scrub_phi(text: str) -> str:
    """Mask PII/PHI patterns in text before sending to external AI services."""
    for pattern, replacement in _PHI_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class PHIScrubber:
    """Stateless PHI scrubber — thin wrapper around :func:`scrub_phi`."""

    def scrub(self, text: str) -> str:
        return scrub_phi(text)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class OpenAIConfig(BaseSettings):
    endpoint: str = field(default="")
    api_key: str = field(default="")
    api_version: str = field(default="2024-02-01")
    deployment_gpt41: str = field(default="gpt-4.1")
    deployment_gpt41_mini: str = field(default="gpt-4.1-mini")

    model_config = {"env_prefix": "AZURE_OPENAI_", "extra": "ignore"}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class UsageRecord:
    tenant_id: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_cost_usd: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.total_cost_usd, Decimal):
            raise TypeError(
                f"total_cost_usd must be Decimal, got {type(self.total_cost_usd).__name__}"
            )


@dataclass
class OpenAIRequest:
    tenant_id: str
    messages: list[dict[str, str]]
    model: str = "gpt-4.1"
    temperature: Decimal = field(default_factory=lambda: Decimal("0"))
    max_tokens: int = 2000
    phi_access_level: str = "redacted"  # "redacted" | "full"
    extra_kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass
class OpenAIResponse:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_cost_usd: Decimal


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class OpenAIClient:
    """Azure OpenAI async client with PHI scrubbing, retry, and cost logging."""

    def __init__(
        self,
        config: OpenAIConfig | None = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> None:
        self._config = config or OpenAIConfig()
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._scrubber = PHIScrubber()
        self._aclient = AsyncAzureOpenAI(
            azure_endpoint=self._config.endpoint,
            api_key=self._config.api_key,
            api_version=self._config.api_version,
        )
        self.on_usage: Callable[[UsageRecord], Awaitable[None]] | None = None

    def _resolve_deployment(self, model: str) -> str:
        if "mini" in model:
            return self._config.deployment_gpt41_mini
        return self._config.deployment_gpt41

    def _prepare_messages(
        self, messages: list[dict[str, str]], phi_access_level: str
    ) -> list[dict[str, str]]:
        if phi_access_level == "full":
            return messages
        return [
            {**msg, "content": self._scrubber.scrub(msg["content"])}
            for msg in messages
        ]

    async def complete(self, request: OpenAIRequest) -> OpenAIResponse:
        """Call Azure OpenAI with retry, PHI scrubbing, and cost logging."""
        messages = self._prepare_messages(request.messages, request.phi_access_level)
        deployment = self._resolve_deployment(request.model)
        last_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                raw = await self._aclient.chat.completions.create(
                    model=deployment,
                    messages=messages,  # type: ignore[arg-type]
                    temperature=float(request.temperature),
                    max_tokens=request.max_tokens,
                    **request.extra_kwargs,
                )
                content = raw.choices[0].message.content or ""
                prompt_tokens = raw.usage.prompt_tokens if raw.usage else 0
                completion_tokens = raw.usage.completion_tokens if raw.usage else 0
                cost = _estimate_cost(request.model, prompt_tokens, completion_tokens)

                usage = UsageRecord(
                    tenant_id=request.tenant_id,
                    model=request.model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_cost_usd=cost,
                )
                if self.on_usage is not None:
                    await self.on_usage(usage)

                return OpenAIResponse(
                    content=content,
                    model=raw.model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_cost_usd=cost,
                )
            except RateLimitError as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    delay = self._base_delay * (2**attempt)
                    logger.warning(
                        "openai_rate_limited",
                        extra={
                            "svc_attempt": attempt + 1,
                            "svc_delay": delay,
                            "svc_tenant_id": request.tenant_id,
                        },
                    )
                    await asyncio.sleep(delay)
                    continue
            except APIStatusError as exc:
                if exc.status_code and 400 <= exc.status_code < 500 and exc.status_code != 429:
                    raise  # Fail fast on 4xx (except 429)
                last_exc = exc
                if attempt < self._max_retries:
                    delay = self._base_delay * (2**attempt)
                    logger.warning(
                        "openai_server_error",
                        extra={
                            "svc_attempt": attempt + 1,
                            "svc_status": exc.status_code,
                            "svc_tenant_id": request.tenant_id,
                        },
                    )
                    await asyncio.sleep(delay)
                    continue

        raise last_exc or RuntimeError("OpenAI call failed after retries")
