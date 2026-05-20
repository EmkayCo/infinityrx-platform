"""Shared error-envelope helper for the reclaimrx router.

Per .claude/rules/error-handling.md the API error body MUST be:
{"error": {"code": "...", "message": "...", "field": "...", "correlation_id": "..."}}

A3 used a stub. A4 is the authoritative implementation.
"""
from __future__ import annotations
import uuid
from contextvars import ContextVar

_correlation_id_ctx: ContextVar[str | None] = ContextVar("reclaimrx_correlation_id", default=None)


def set_correlation_id(correlation_id: str | None) -> None:
    _correlation_id_ctx.set(correlation_id)


def get_correlation_id() -> str | None:
    return _correlation_id_ctx.get()


def build_error_envelope(code: str, message: str, *, field: str | None = None, correlation_id: str | None = None) -> dict:
    cid = correlation_id or get_correlation_id() or str(uuid.uuid4())
    return {"error": {"code": code, "message": message, "field": field, "correlation_id": cid}}
