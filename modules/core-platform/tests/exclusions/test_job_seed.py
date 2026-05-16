"""Tests for src/jobs/seed.py — CONCERN-3 fix (P0a v2).

Verifies that seed_system_jobs:
- inserts the exclusion_refresh job in core_jobs
- is idempotent (second call adds 0 rows)
- marks it with cron schedule "0 3 * * *"
- exclusion_refresh handler is registered in default_registry
"""
from __future__ import annotations

import pytest

from src.jobs.registry import default_registry
from src.jobs.seed import seed_system_jobs
from src.models import Job


def test_seed_inserts_exclusion_refresh(db_session):
    """seed_system_jobs inserts exclusion_refresh into core_jobs."""
    count = seed_system_jobs(db_session)
    db_session.commit()
    assert count >= 1, "at least one system job must be seeded"

    job = db_session.query(Job).filter(Job.job_type == "exclusion_refresh").first()
    assert job is not None, "exclusion_refresh job must be in core_jobs"
    assert job.status == "active"
    assert job.schedule == "0 3 * * *"


def test_seed_is_idempotent(db_session):
    """Calling seed_system_jobs twice must not create duplicates."""
    first = seed_system_jobs(db_session)
    db_session.commit()

    second = seed_system_jobs(db_session)
    db_session.commit()
    assert second == 0, "second seed call must insert 0 rows"

    jobs = db_session.query(Job).filter(Job.job_type == "exclusion_refresh").all()
    assert len(jobs) == 1, "only one exclusion_refresh row must exist after two seed calls"


def test_exclusion_refresh_handler_registered():
    """exclusion_refresh handler is registered in the default job registry.

    This is the actual CONCERN-3 gate: if the handler is not registered the
    scheduler silently fails every run of the seeded job.
    """
    # Import side-effect registers the handler
    from src.exclusions import job_handler as _jh  # noqa: F401

    known = default_registry.known_types()
    assert "exclusion_refresh" in known, (
        "exclusion_refresh must be registered in default_registry; "
        "check that job_handler.py is imported during app startup"
    )
