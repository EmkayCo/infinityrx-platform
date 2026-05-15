# H-07 Audit Chain Verification Job — Discovery Report

**Date:** 2026-05-15
**Requirement:** HIPAA 2026 §164.312(b) tamper-evident audit log — daily integrity verification

---

## 1. `verify_audit_chain` — Location and Signature

**File:** `modules/core-platform/src/jobs/verify_audit_chain_job.py`

**Entry point:** `handle_verify_audit_chain(payload: dict) -> dict`

Registered via `@job_handler("audit.verify_chain")` against `default_registry`.

### Payload fields (all optional)

| Field | Type | Default | Behavior |
|---|---|---|---|
| `tenant_id` | `str \| None` | None | If set, verifies only this tenant's chain. Otherwise iterates all tenants in `audit_log`. |
| `stop_on_first_failure` | `bool` | False | Abort scan after first broken link (saves time; loses full failure picture). |

### Return shape

```python
{
    "status": "ok" | "failed",
    "tenants_checked": int,
    "entries_checked": int,
    "failures": [
        {
            "tenant_id": str,
            "entry_id": int,
            "expected_hash": str,   # 64-char SHA-256 hex
            "stored_hash": str,     # 64-char SHA-256 hex
            "action": str,          # e.g. "login", "update" — no content
        }
    ],
    "duration_ms": int,
}
```

### Tenant discovery

Queries `SELECT DISTINCT tenant_id FROM core_platform.audit_log` — intentionally NOT from the `tenants` table. This means soft-deleted tenants with existing audit chains are still verified (correct for HIPAA: you must verify the integrity of all historical data, even for deprovisioned tenants).

### Internal helper

`_verify_tenant_chain(db, tenant_id, stop_on_first)` — reads entries for one tenant ordered by `(created_at ASC, id ASC)`, recomputes `compute_entry_hash()` for each, compares against stored value. Returns `{"entries_checked": int, "failures": list}`.

---

## 2. Existing Scheduler

**Mechanism:** Custom DB-backed cron scheduler (no APScheduler, no Celery Beat).

**Location:** `modules/core-platform/src/jobs/scheduler.py`

**How it works:**
- `Job` ORM rows in `core_jobs` table drive scheduling.
- Each `Job` has a `schedule` (cron expression, validated via `croniter`) and `next_run_at`.
- `JobScheduler.tick_once()` queries `WHERE status='active' AND next_run_at <= NOW()` with `skip_locked=True` (Postgres row-level lock; ignored on SQLite).
- On dispatch: creates a `JobRun` row, calls the registered handler via `JobRunner`, writes the result back, and recomputes `next_run_at`.
- Emits `job.completed` or `job.failed` events on the shim event bus after every run.

**Gap (pre-fix):** The `audit.verify_chain` handler was registered but no `Job` row with `job_type="audit.verify_chain"` existed in the database. The scheduler had nothing to dispatch.

**Fix applied:** `modules/core-platform/src/jobs/seed.py::ensure_audit_chain_job()` — idempotent upsert called from the FastAPI `lifespan` startup block. Creates the Job row with `schedule="0 2 * * *"` (02:00 UTC daily) and `tenant_id=NULL` (platform-wide).

---

## 3. Alerting Integration Point

**Mechanism:** Shim event bus (`modules/core-platform/src/_shim/events.py`) → notification routing (`modules/core-platform/src/notifications/routing.py`).

**New event types added to `shared/events/event_types.py`:**
- `audit.chain_broken` (`AUDIT_CHAIN_BROKEN`) — emitted once per failure entry with `{tenant_id, entry_id, expected_hash, stored_hash, action, severity="CRITICAL"}`
- `audit.chain_verified` (`AUDIT_CHAIN_VERIFIED`) — emitted once on clean run with `{tenants_checked, entries_checked, duration_ms}`

**Notification routing rule added:**
```
event_pattern: audit.chain_broken
notification_type: audit_chain_integrity_violation
severity: critical
title: "Audit chain integrity violation (HIPAA H-07)"
```

**Note:** The `select_recipients` lambda returns `[]` (no recipients) on all routing rules — this is the existing pattern in the codebase. A follow-up task is needed to wire recipient resolution (e.g., all `platform_admin` users) into the notification routing. The routing infrastructure is in place; the recipient selector is the outstanding gap.

---

## 4. Per-Tenant Iteration Pattern

The job queries `DISTINCT tenant_id` from `core_platform.audit_log` (not from `tenants` table) and iterates each tenant independently via `_verify_tenant_chain()`. Each tenant's chain is fully isolated — no cross-tenant hash state is shared between iterations.

---

## 5. What Was Built (H-07 Fix)

| Component | File | What changed |
|---|---|---|
| Event types | `shared/events/event_types.py` | Added `AUDIT_CHAIN_BROKEN`, `AUDIT_CHAIN_VERIFIED` |
| Job handler | `modules/core-platform/src/jobs/verify_audit_chain_job.py` | Now emits events on chain break (CRITICAL) and clean run (INFO) |
| Job seed | `modules/core-platform/src/jobs/seed.py` | New — idempotent upsert of audit.verify_chain Job row at 02:00 UTC |
| App startup | `modules/core-platform/src/main.py` | Calls `ensure_audit_chain_job()` in lifespan |
| Handler registration | `modules/core-platform/src/api.py` | Side-effect import of `verify_audit_chain_job` module |
| Notification routing | `modules/core-platform/src/notifications/routing.py` | Added `audit.chain_broken` CRITICAL rule |

---

## 6. Follow-Up Tasks

1. **Recipient resolution:** Implement `select_recipients` for `audit.chain_broken` rule to route to platform_admin users (or an ops webhook). Currently emits to empty recipient list.
2. **Webhook/PagerDuty notifier:** No outbound alert transport exists yet. The event bus + notification routing is the correct hook point once recipient resolution is wired.
3. **Job row observability:** Add a Grafana dashboard panel showing last `audit.verify_chain` run timestamp and status from `core_job_runs`.
