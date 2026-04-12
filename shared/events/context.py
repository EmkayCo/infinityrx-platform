"""Correlation id context variable.

The audit middleware and event bus cooperate so that one logical workflow
shares a single correlation id across modules, even when events fan out.
"""

from __future__ import annotations

import contextvars
import uuid

_correlation_id: contextvars.ContextVar[uuid.UUID | None] = contextvars.ContextVar(
    "correlation_id", default=None
)


def current_correlation_id() -> uuid.UUID | None:
    """Return the correlation id bound to the current context, or None."""
    return _correlation_id.get()


def set_correlation_id(value: uuid.UUID) -> contextvars.Token:
    """Bind a correlation id to the current context; returns a reset token."""
    return _correlation_id.set(value)


def reset_correlation_id(token: contextvars.Token) -> None:
    _correlation_id.reset(token)


def new_correlation_id() -> uuid.UUID:
    """Generate and bind a fresh correlation id for the current context."""
    value = uuid.uuid4()
    set_correlation_id(value)
    return value
