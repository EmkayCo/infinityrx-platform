"""Tests for ReclaimRxScheduler, audit hash-chain job, and DLQ monitor.

Scheduler pattern from shared/data_ingestion/scheduler.py (audit §7).
APScheduler is NOT installed -- do NOT import it.

TDD: MUST FAIL before Task 8 implements the scheduler and jobs.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.jobs.reclaimrx_scheduler import ReclaimRxScheduler  # FAILS until Task 8


class TestReclaimRxScheduler:
    """ReclaimRxScheduler uses asyncio + croniter, not APScheduler."""

    def test_register_job_stores_it(self):
        """register() stores the job name + cron + callable."""
        sched = ReclaimRxScheduler()
        mock_fn = AsyncMock()
        sched.register("cleanup_processed_events", mock_fn, cron="0 2 * * *")
        assert "cleanup_processed_events" in sched._jobs

    @pytest.mark.asyncio
    async def test_stop_prevents_further_ticks(self):
        """stop() sets _running=False; start() exits after current tick.

        R2 CONCERN 10 fix: concrete assertions on scheduler state and task completion.
        """
        sched = ReclaimRxScheduler(tick_interval_seconds=0)
        mock_fn = AsyncMock()
        sched.register("test_job", mock_fn, cron="0 0 1 1 *")  # Jan 1 only -- won't fire
        task = asyncio.create_task(sched.start())
        await asyncio.sleep(0)  # yield
        await sched.stop()
        await asyncio.wait_for(task, timeout=1.0)

        assert sched._running is False
        assert task.done()
        assert task.exception() is None

    def test_no_apscheduler_import(self):
        """Verify the scheduler module does not import APScheduler.

        R1 CONCERN 4 fix: source-level assertion, not an import check.
        """
        import src.jobs.reclaimrx_scheduler as sched_mod
        module_source = open(sched_mod.__file__).read()
        assert "apscheduler" not in module_source.lower(), (
            "ReclaimRxScheduler must use asyncio + croniter, not APScheduler"
        )
        assert "import apscheduler" not in module_source
        assert "from apscheduler" not in module_source


class TestAuditHashChainJob:
    """Audit hash-chain verification job walks audit table, detects breaks.

    R7 BLOCK-22 fix: verify_audit_hash_chain is plain def (not async def).
    Tests call it synchronously -- no @pytest.mark.asyncio, no await.
    The scheduler wrapper in main.py runs it via asyncio.to_thread().
    """

    def test_clean_chain_returns_ok(self, db_session):
        """An intact hash chain returns result with status='ok', breaks=0."""
        from src.jobs.audit_chain_job import verify_audit_hash_chain  # FAILS until Task 8
        result = verify_audit_hash_chain(db_session, tenant_id=None)
        assert result["status"] in ("ok", "no_entries")
        assert result["breaks"] == 0

    def test_broken_chain_returns_alert(self, db_session):
        """A tampered prev_entry_hash triggers status='alert' with breaks > 0."""
        from src.jobs.audit_chain_job import verify_audit_hash_chain
        from src.models.tables import ThresholdConfigAudit, ThresholdConfig
        import uuid
        import hashlib
        from datetime import UTC, datetime

        tenant_id = uuid.uuid4()
        # Need a ThresholdConfig parent for the FK
        config = ThresholdConfig(
            id=str(uuid.uuid4()),
            tenant_id=str(tenant_id),
            version=1,
            ml_score_thresholds={"open": 0.70},
            rule_thresholds={"high": 3},
            graph_density_threshold=0.5,
            accumulator_anomaly_sensitivity=0.5,
            updated_by="test",
            created_at=datetime.now(UTC),
        )
        db_session.add(config)
        db_session.flush()

        # Entry 1 with valid entry_hash
        e1 = ThresholdConfigAudit(
            id=str(uuid.uuid4()),
            tenant_id=str(tenant_id),
            threshold_config_id=config.id,
            field="ml_score_thresholds.open",
            old_value="0.70",
            new_value="0.75",
            changed_at=datetime.now(UTC),
            changed_by="user-abc",
            reason="tuning",
            entry_hash=hashlib.sha256(b"entry1").hexdigest(),
            prev_entry_hash=None,
        )
        db_session.add(e1)
        # Entry 2 with WRONG prev_entry_hash (tampered)
        e2 = ThresholdConfigAudit(
            id=str(uuid.uuid4()),
            tenant_id=str(tenant_id),
            threshold_config_id=config.id,
            field="ml_score_thresholds.open",
            old_value="0.75",
            new_value="0.80",
            changed_at=datetime.now(UTC),
            changed_by="user-abc",
            reason="tuning",
            entry_hash=hashlib.sha256(b"entry2").hexdigest(),
            prev_entry_hash="TAMPERED_HASH",  # does not match e1.entry_hash
        )
        db_session.add(e2)
        db_session.commit()

        result = verify_audit_hash_chain(db_session, tenant_id=tenant_id)
        assert result["status"] == "alert"
        assert result["breaks"] >= 1


class TestDLQMonitorJob:
    """DLQ depth monitor alerts when depth > 0 for extended period."""

    @pytest.mark.asyncio
    async def test_zero_depth_returns_ok(self, async_db_engine):
        """Empty DLQ returns status='ok'."""
        from src.jobs.dlq_monitor import check_dlq_depth  # FAILS until Task 8
        result = await check_dlq_depth(async_db_engine)
        assert result["status"] == "ok"
        assert result["queued_count"] == 0
