"""Job handler registry.

Handlers are registered by decorator or direct call. Lookup raises a
specific exception so the runner can distinguish "no handler" from
"handler raised". Registry is module-global but can be cleared for tests.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

JobHandler = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]


class JobTypeNotRegistered(LookupError):
    """Raised when a job dispatches to an unregistered job_type."""

    def __init__(self, job_type: str) -> None:
        super().__init__(f"No handler registered for job_type={job_type!r}")
        self.job_type = job_type


class JobRegistry:
    def __init__(self) -> None:
        self._handlers: Dict[str, JobHandler] = {}

    def register(self, job_type: str, handler: JobHandler) -> None:
        self._handlers[job_type] = handler

    def get(self, job_type: str) -> JobHandler:
        if job_type not in self._handlers:
            raise JobTypeNotRegistered(job_type)
        return self._handlers[job_type]

    def known_types(self) -> list[str]:
        return sorted(self._handlers.keys())

    def clear(self) -> None:
        self._handlers.clear()


#: Module-level default registry used by the @job_handler decorator.
default_registry = JobRegistry()


def job_handler(job_type: str, registry: JobRegistry | None = None) -> Callable[[JobHandler], JobHandler]:
    """Decorator — registers the function against the registry."""

    target = registry or default_registry

    def _wrap(fn: JobHandler) -> JobHandler:
        target.register(job_type, fn)
        return fn

    return _wrap


async def _noop_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Built-in no-op handler for tests and for the scheduler smoke tick."""
    return {"noop": True, "items_processed": 0, "items_failed": 0}


default_registry.register("noop", _noop_handler)
