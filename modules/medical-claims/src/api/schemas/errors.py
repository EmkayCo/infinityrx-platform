"""Standard error envelope for all API errors."""
from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str
    field: str | None = None
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class ErrorEnvelope(BaseModel):
    error: ErrorDetail

    @classmethod
    def make(cls, code: str, message: str, field: str | None = None, correlation_id: str | None = None) -> "ErrorEnvelope":
        detail = ErrorDetail(
            code=code,
            message=message,
            field=field,
            correlation_id=correlation_id or str(uuid.uuid4()),
        )
        return cls(error=detail)
