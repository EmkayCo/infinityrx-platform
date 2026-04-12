"""Route markers: ``@auditable`` and ``@phi_access``.

The middleware inspects the marker metadata attached to a FastAPI route
function to decide:
    - what ``action`` string to use for the audit entry,
    - what ``entity_type`` / ``entity_id`` to capture,
    - whether to snapshot the entity state before the handler runs, and
    - whether to emit an additional ``phi_access`` entry recording which
      PHI fields were returned.

Both decorators are purely declarative — they attach attributes and never
wrap the handler. The heavy lifting happens in :mod:`src.audit.middleware`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

CaptureBefore = Callable[..., Awaitable[dict[str, Any] | None] | dict[str, Any] | None]


def auditable(
    *,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id_param: str | None = None,
    capture_before: CaptureBefore | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Attach audit metadata to a route handler.

    The middleware reads the ``__audit__`` attribute; the handler is
    returned unchanged so FastAPI introspection continues to work.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        func.__audit__ = {"action": action, "entity_type": entity_type, "entity_id_param": entity_id_param, "capture_before": capture_before}
        return func

    return decorator


def phi_access(fields: list[str]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Mark a route as returning PHI fields.

    The middleware will emit a second audit entry with
    ``action='phi_access'`` and ``after_value={'fields_accessed': fields}``.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        func.__phi_access__ = list(fields)
        return func

    return decorator
