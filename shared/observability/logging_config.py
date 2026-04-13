"""Structured JSON logging with correlation/tenant/user context injection.

All log lines in production must be parseable JSON so Log Analytics /
Application Insights can filter on correlation_id, tenant_id, user_id
without regex-matching free text. In dev we still want human-readable
output, so ``configure_logging(mode="text")`` keeps the default
``logging.Formatter``.

ContextVars (not thread-locals) carry per-request context so async
handlers don't cross-contaminate. The ``ContextFilter`` reads them on
every record and injects them as attributes; the ``JsonFormatter`` then
serializes them. Use ``set_request_context(correlation_id=..., ...)``
in middleware to bind, and ``reset_request_context(token)`` to unbind.
"""

from __future__ import annotations

import contextvars
import logging
import sys
import uuid
from dataclasses import dataclass
from typing import Any

from pythonjsonlogger import json as jsonlogger

__all__ = [
    "ContextFilter",
    "RequestContext",
    "configure_logging",
    "set_request_context",
    "reset_request_context",
]


@dataclass(frozen=True)
class RequestContext:
    """Per-request context that every log line should carry."""

    correlation_id: uuid.UUID | None = None
    tenant_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None


_context: contextvars.ContextVar[RequestContext] = contextvars.ContextVar(
    "request_context", default=RequestContext()
)


def set_request_context(
    *,
    correlation_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> contextvars.Token:
    """Bind request context; returns a reset token for ``reset_request_context``."""
    return _context.set(
        RequestContext(
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )
    )


def reset_request_context(token: contextvars.Token) -> None:
    _context.reset(token)


def current_request_context() -> RequestContext:
    return _context.get()


class ContextFilter(logging.Filter):
    """Injects correlation_id / tenant_id / user_id onto every LogRecord.

    Installed at the root logger so every handler (console, file,
    Application Insights) sees the same fields. Missing context fields
    are emitted as ``None`` rather than omitted — consistent shape makes
    downstream aggregations (e.g., "group by tenant_id") simpler.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = current_request_context()
        record.correlation_id = str(ctx.correlation_id) if ctx.correlation_id else None
        record.tenant_id = str(ctx.tenant_id) if ctx.tenant_id else None
        record.user_id = str(ctx.user_id) if ctx.user_id else None
        return True


def _build_json_formatter() -> logging.Formatter:
    # The format string declares which standard LogRecord attributes
    # appear as top-level keys. Custom attributes set by ContextFilter
    # (correlation_id, tenant_id, user_id) are emitted automatically by
    # JsonFormatter via ``reserved_attrs`` defaults.
    fmt = (
        "%(asctime)s %(name)s %(levelname)s %(message)s "
        "%(correlation_id)s %(tenant_id)s %(user_id)s"
    )
    return jsonlogger.JsonFormatter(
        fmt,
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )


def _build_text_formatter() -> logging.Formatter:
    return logging.Formatter(
        fmt=(
            "%(asctime)s %(levelname)s [%(name)s] "
            "[corr=%(correlation_id)s tenant=%(tenant_id)s user=%(user_id)s] "
            "%(message)s"
        )
    )


def configure_logging(
    *, level: str | int = "INFO", mode: str = "json", stream: Any = None
) -> None:
    """Install JSON logging with context filter on the root logger.

    Args:
        level: "INFO", "DEBUG", etc. — also accepts int constants.
        mode: "json" (production) or "text" (dev/tests).
        stream: file-like; defaults to sys.stderr.

    Idempotent: re-calling replaces existing handlers so tests can swap
    configurations without accumulating duplicates.
    """
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    root = logging.getLogger()
    # Remove any handlers previous calls installed so re-configuration
    # doesn't multiply output.
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setLevel(level)
    if mode == "text":
        handler.setFormatter(_build_text_formatter())
    else:
        handler.setFormatter(_build_json_formatter())

    # ContextFilter on the handler (not the logger) so filters apply to
    # records from every logger in the process, not just the root.
    handler.addFilter(ContextFilter())

    root.addHandler(handler)
    root.setLevel(level)
