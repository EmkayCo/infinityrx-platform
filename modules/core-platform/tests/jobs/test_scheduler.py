from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from freezegun import freeze_time

from src._shim import db as db_shim
from src._shim import events as events_shim
from src.jobs.registry import JobRegistry
from src.jobs.scheduler import (
    EVENT_JOB_COMPLETED,
    EVENT_JOB_FAILED,
    JobScheduler,
    compute_next_run,
    validate_cron,
)
from src.models import Job, JobRun


async def _ok(_payload):
    return {"items_processed": 2, "items_failed": 0}


async def _fail(_payload):
    raise RuntimeError("nope")


@pytest.fixture
def registry() -> JobRegistry:
    r = JobRegistry()
    r.register("ok", _ok)
    r.register("bad", _fail)
    return r


def test_validate_cron():
    assert validate_cron("*/5 * * * *")
    assert not validate_cron("not a cron")


def test_compute_next_run():
    base = datetime(2026, 4, 12, 12, 0, tzinfo=timezone.utc)
    nxt = compute_next_run("0 * * * *", base)
    assert nxt == datetime(2026, 4, 12, 13, 0, tzinfo=timezone.utc)


async def test_tick_dispatches_due_job_and_emits_event(registry):
    SessionLocal = db_shim.get_sessionmaker()
    with SessionLocal() as s:
        due_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        job = Job(
            tenant_id="t1",
            name="hourly",
            job_type="ok",
            schedule="0 * * * *",
            status="active",
            next_run_at=due_at,
        )
        s.add(job)
        s.commit()
        job_id = job.id

    scheduler = JobScheduler(SessionLocal, registry, tick_seconds=0.01)
    dispatched = await scheduler.tick_once()
    assert dispatched == 1

    with SessionLocal() as s:
        job = s.get(Job, job_id)
        assert job.last_run_at is not None
        assert job.next_run_at is not None
        runs = s.query(JobRun).filter_by(job_id=job_id).all()
        assert len(runs) == 1
        assert runs[0].status == "succeeded"
        assert runs[0].items_processed == 2

    topics = [e.topic for e in events_shim.published_events()]
    assert EVENT_JOB_COMPLETED in topics


async def test_tick_captures_handler_failure(registry):
    SessionLocal = db_shim.get_sessionmaker()
    with SessionLocal() as s:
        job = Job(
            tenant_id="t1",
            name="bad",
            job_type="bad",
            schedule="* * * * *",
            status="active",
            next_run_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        s.add(job)
        s.commit()
        job_id = job.id

    await JobScheduler(SessionLocal, registry).tick_once()
    with SessionLocal() as s:
        run = s.query(JobRun).filter_by(job_id=job_id).one()
        assert run.status == "failed"
        assert "RuntimeError" in (run.error_message or "")

    assert any(e.topic == EVENT_JOB_FAILED for e in events_shim.published_events())


async def test_tick_ignores_paused_jobs(registry):
    SessionLocal = db_shim.get_sessionmaker()
    with SessionLocal() as s:
        s.add(
            Job(
                name="p",
                job_type="ok",
                schedule="* * * * *",
                status="paused",
                next_run_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            )
        )
        s.commit()
    assert await JobScheduler(SessionLocal, registry).tick_once() == 0


async def test_tick_ignores_future_jobs(registry):
    SessionLocal = db_shim.get_sessionmaker()
    with SessionLocal() as s:
        s.add(
            Job(
                name="f",
                job_type="ok",
                schedule="* * * * *",
                status="active",
                next_run_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )
        s.commit()
    assert await JobScheduler(SessionLocal, registry).tick_once() == 0


async def test_tick_no_schedule_clears_next_run(registry):
    """One-off job (no cron) runs then stops being due."""
    SessionLocal = db_shim.get_sessionmaker()
    with SessionLocal() as s:
        j = Job(
            name="once",
            job_type="ok",
            schedule=None,
            status="active",
            next_run_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        s.add(j)
        s.commit()
        jid = j.id
    await JobScheduler(SessionLocal, registry).tick_once()
    with SessionLocal() as s:
        assert s.get(Job, jid).next_run_at is None


@freeze_time("2026-04-12 12:00:00")
async def test_scheduler_recomputes_next_run_with_frozen_time(registry):
    SessionLocal = db_shim.get_sessionmaker()
    with SessionLocal() as s:
        j = Job(
            name="hourly",
            job_type="ok",
            schedule="0 * * * *",
            status="active",
            next_run_at=datetime(2026, 4, 12, 11, 59, tzinfo=timezone.utc),
        )
        s.add(j)
        s.commit()
        jid = j.id
    await JobScheduler(SessionLocal, registry).tick_once()
    with SessionLocal() as s:
        job = s.get(Job, jid)
        # SQLite drops tz info — compare naive
        nxt = job.next_run_at
        if nxt.tzinfo is not None:
            nxt = nxt.replace(tzinfo=None)
        assert nxt == datetime(2026, 4, 12, 13, 0)


async def test_run_forever_stops_on_signal(registry):
    SessionLocal = db_shim.get_sessionmaker()
    sch = JobScheduler(SessionLocal, registry, tick_seconds=0.01)
    sch.stop()  # pre-signal
    await sch.run_forever()  # should exit immediately


async def test_run_forever_swallows_tick_errors(registry, monkeypatch):
    SessionLocal = db_shim.get_sessionmaker()
    sch = JobScheduler(SessionLocal, registry, tick_seconds=0.01)

    calls = {"n": 0}

    async def boom():
        calls["n"] += 1
        if calls["n"] >= 2:
            sch.stop()
        raise RuntimeError("tick oops")

    monkeypatch.setattr(sch, "tick_once", boom)
    await sch.run_forever()
    assert calls["n"] >= 2
