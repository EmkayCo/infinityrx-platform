from __future__ import annotations

import asyncio

import pytest

from src.jobs.registry import JobRegistry
from src.jobs.runner import JobRunner


async def _ok(_payload):
    return {"items_processed": 3, "items_failed": 1, "detail": "ok"}


async def _boom(_payload):
    raise ValueError("kaboom")


async def _slow(_payload):
    await asyncio.sleep(0.2)
    return {}


async def _nondict(_payload):
    return 42


@pytest.fixture
def registry() -> JobRegistry:
    r = JobRegistry()
    r.register("ok", _ok)
    r.register("boom", _boom)
    r.register("slow", _slow)
    r.register("nondict", _nondict)
    return r


async def test_runner_success(registry):
    r = JobRunner(registry)
    result = await r.run(job_type="ok", payload={})
    assert result.status == "succeeded"
    assert result.items_processed == 3
    assert result.items_failed == 1


async def test_runner_exception(registry):
    result = await JobRunner(registry).run(job_type="boom", payload={})
    assert result.status == "failed"
    assert "ValueError" in (result.error_message or "")


async def test_runner_timeout(registry):
    result = await JobRunner(registry).run(job_type="slow", payload={}, timeout_s=0.01)
    assert result.status == "failed"
    assert "timeout" in (result.error_message or "")


async def test_runner_unregistered():
    result = await JobRunner(JobRegistry()).run(job_type="missing", payload={})
    assert result.status == "failed"
    assert "missing" in (result.error_message or "")


async def test_runner_non_dict_return_wrapped(registry):
    result = await JobRunner(registry).run(job_type="nondict", payload={})
    assert result.status == "succeeded"
    assert result.result == {"value": 42}
