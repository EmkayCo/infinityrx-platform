"""Wraps handler execution with timeout, exception capture, metrics."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .registry import JobRegistry, JobTypeNotRegistered

logger = logging.getLogger("core.jobs.runner")


@dataclass
class JobRunResult:
    status: str  # 'succeeded' | 'failed'
    result: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    items_processed: int = 0
    items_failed: int = 0


class JobRunner:
    def __init__(self, registry: JobRegistry, default_timeout_s: float = 300.0) -> None:
        self._registry = registry
        self._default_timeout = default_timeout_s

    async def run(
        self,
        *,
        job_type: str,
        payload: Dict[str, Any],
        timeout_s: Optional[float] = None,
    ) -> JobRunResult:
        try:
            handler = self._registry.get(job_type)
        except JobTypeNotRegistered as exc:
            logger.error("job_type_not_registered", extra={"job_type": job_type})
            return JobRunResult(status="failed", error_message=str(exc))

        t = timeout_s if timeout_s is not None else self._default_timeout
        try:
            result = await asyncio.wait_for(handler(payload), timeout=t)
        except asyncio.TimeoutError:
            logger.error("job_timeout", extra={"job_type": job_type, "timeout_s": t})
            return JobRunResult(status="failed", error_message=f"timeout after {t}s")
        except Exception as exc:  # noqa: BLE001 — intentional catch-all to record failure
            logger.exception("job_handler_error", extra={"job_type": job_type})
            return JobRunResult(status="failed", error_message=f"{type(exc).__name__}: {exc}")

        if not isinstance(result, dict):
            result = {"value": result}
        return JobRunResult(
            status="succeeded",
            result=result,
            items_processed=int(result.get("items_processed", 0) or 0),
            items_failed=int(result.get("items_failed", 0) or 0),
        )
