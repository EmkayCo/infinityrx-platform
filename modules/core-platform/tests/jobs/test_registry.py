from __future__ import annotations

import pytest

from src.jobs.registry import JobRegistry, JobTypeNotRegistered, job_handler


async def _h(_payload):
    return {"items_processed": 1}


def test_register_and_lookup():
    reg = JobRegistry()
    reg.register("x", _h)
    assert reg.get("x") is _h
    assert reg.known_types() == ["x"]


def test_missing_raises():
    reg = JobRegistry()
    with pytest.raises(JobTypeNotRegistered) as exc:
        reg.get("ghost")
    assert exc.value.job_type == "ghost"


def test_decorator_registers_on_custom_registry():
    reg = JobRegistry()

    @job_handler("late", registry=reg)
    async def handler(_payload):
        return {}

    assert reg.get("late") is handler


def test_clear_removes_all():
    reg = JobRegistry()
    reg.register("a", _h)
    reg.clear()
    assert reg.known_types() == []
