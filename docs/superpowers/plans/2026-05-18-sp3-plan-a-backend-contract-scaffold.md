# SP-3 Plan A — Backend Extensions + SP-0 Contract Layer + Frontend Scaffold

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** DRAFT — awaiting codex consult
**Date:** 2026-05-18
**Vertical:** SP-3 ReclaimRx Operator Portal + Backend Closure
**Spec ref:** `docs/superpowers/specs/2026-05-18-sp3-reclaimrx-portal-design.md`
**Codex spec trail:** R1 NO-GO → R2 NO-GO → R3 NO-GO → R4 GO-WITH-CHANGES → R5 GO-WITH-CHANGES
**Builds on:** SP-0 (Plans A–D, shipped), SP-2 (federated search spine, shipped)

**Goal:** Land the SP-3 backend extensions (5 new models, 11 new/reshaped endpoints, outbox pattern, accumulator consumer, real graph job, production-grade app factory bindings) + SP-0 contract layer for ReclaimRx + frontend module scaffold with empty-state pages. After Plan A, the backend is feature-complete per spec; Plans B–E layer UI atop.

**Architecture:** Audit-first — Plan A starts with a verified delta between spec D1-D14 and the existing 4,000-line `modules/reclaimrx` module. Every task is pinned to a verified gap; no greenfield-scaffolding tasks that would duplicate existing implementation. New work touches `modules/reclaimrx/src/` (backend extensions), `packages/contract/src/` (SP-0 typed client + schemas + impls), and `packages/modules/reclaimrx/` (frontend module scaffold with empty-state pages — Plan B fills in functional UI).

**Tech Stack:** Python 3.13 + FastAPI + SQLAlchemy + Alembic; APScheduler (cron); shared/events EventEnvelope + transactional outbox; Postgres 17 (RLS + advisory locks); Redis (durable idempotency); TypeScript + zod (contract layer); Next.js 16 (frontend module).

---

## Locked-from-audit decisions

Audit ran 2026-05-18 against HEAD. Spec assumed greenfield in several places; this plan reconciles.

| Spec assertion | Audit finding | Plan A action |
|---|---|---|
| NEW `Investigation` model | Exists in `modules/reclaimrx/src/models/tables.py:373` (57 lines, with timeline + activity) | EXTEND — alembic 0008 adds: `outcome_label` enum, `recovered_amount` Numeric(14,2), `hold_amount` Numeric(14,2), `threshold_config_version` int FK, `threshold_snapshot` JSONB, `state_machine_version` int default 1 |
| NEW state machine | No state machine validator exists; status currently free-text | NEW service `investigation_state_machine.py`; transition table matches spec §5.5.1 |
| NEW `PaymentHold` model | Exists at `tables.py:587`, has `is_active`, `expires_at`, `release_reason`, `released_at` | EXTEND — add `released_by` (String, FK to user_id) |
| NEW `FraudRing` model | NOT present | NEW |
| NEW `GraphRun` model | NOT present | NEW (status enum `running`/`completed`/`completed_partial`/`failed`; failure fields per spec §5.2) |
| NEW `AccumulatorAnomaly` model | `AccumulatorDetection` exists at `tables.py:490` — same concept | EXTEND `AccumulatorDetection` with `pattern_type` enum, `evidence_window_start`/`end`, `triggering_event_ids` JSONB |
| NEW `ThresholdConfig` model | `TenantRuleConfig` exists at `tables.py:79` — overlaps | RENAME conceptually: keep `TenantRuleConfig` for per-rule numeric thresholds; ADD `threshold_config_version` rows in new `ThresholdConfigVersion` table with `effective_at`/`superseded_at`; ADD `ThresholdConfigAudit` with hash chain |
| NEW `OutboxEvent` model | NOT present | NEW (with `idempotency_key` UNIQUE) |
| NEW `InvestigationOutcome` model | Outcome can live as column on `Investigation` (above) | NOT a separate model — use `Investigation.outcome_label` per spec §5.2 |
| 18 new endpoints | 24 endpoints exist in `router.py`; ~6 overlap | DELTA (see §"Endpoint delta inventory" below) |
| Hold release `POST /holds/{id}/release` | Exists as `DELETE /holds/{hold_id}` at `router.py:475` | RESHAPE: add new `POST /holds/{hold_id}/release` with full body per spec §5.5#9; deprecate DELETE in same migration; `payment.hold_released` event emitted via outbox |
| `accumulator.updated` consumer | NOT in `CONSUMER_ROUTING` (8 consumers wired; accumulator absent) | NEW — register in `consumers.py:CONSUMER_ROUTING` + handler with envelope/payload tenant_id mismatch reject per spec §5.3 |
| Graph batch job (real impl) | `job_rebuild_fraud_network_graph` in `jobs/scheduled.py:25` is STUB (returns zeros); `services/graph_analysis.py` exists (218 lines, real graph code but not run from job) | NEW wiring: rewrite stub to call `graph_analysis_service.run(tenant_id, graph_run_id)`; add per-tenant fan-out + size guardrails + `pg_try_advisory_xact_lock` for run creation + durable `running` row + outbox emit of `fwa.graph_run_completed` |
| APScheduler wired | JOB_SCHEDULE dict exists at `scheduled.py:107` but NO scheduler runs them | NEW: integrate APScheduler in `create_app()` lifespan; honor JOB_SCHEDULE crons |
| Daily audit verification job | NOT present | NEW job `job_verify_audit_chain` at 03:00 UTC |
| Transactional outbox | NOT present | NEW: model + service + dispatcher background job (APScheduler 1s poll) |
| Production DLQ persistence | `main.py:46` uses `_EmptyDLQRepository` stub | REPLACE with real DB-backed `DLQRepository` (table likely exists in `shared/events/dlq`; verify at plan-exec) |
| DLQ depth monitoring | NOT present | NEW: metric + 15-min alert per `event-bus.md` |
| Durable idempotency store | `events/__init__.py:29` uses `InMemoryIdempotencyStore` — process-restart loses keys | REPLACE with Redis-backed `RedisIdempotencyStore` from shared (verify path at plan-exec) |
| `processed_events` cleanup | NOT present | NEW job `job_cleanup_processed_events` daily |
| Backend `require_role()` on every endpoint | Existing `router.py` endpoints currently use only `current_user` (auth) — no role gates | EXTEND: add `require_role()` dependency; per-endpoint role per spec §5.5; existing endpoints get gates added in same migration |
| MFA-elevated session check on PHI endpoints | NOT enforced on existing endpoints | NEW dependency `require_mfa_elevated()` via core-platform session lookup |
| SecurityHeadersMiddleware | `main.py:94` already mounts ✅ | KEEP |
| RateLimitMiddleware | `main.py:93` already mounts ✅ | EXTEND with per-endpoint limit table per spec D13 |
| DLQ router | `main.py:97` already mounts ✅ | KEEP (with real repo) |
| CORS | `main.py:84` already mounts ✅ | KEEP |
| PG RLS for new tables | Alembic 0002 exists (RLS); 0007 is latest — RLS coverage of new tables must be in 0008 | NEW in 0008: per spec D8, `tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid` |
| SP-0 contract layer for reclaimrx | NOT present in `packages/contract` | NEW: `clients/reclaimrx.ts`, `schemas/reclaimrx.ts`, `impls/reclaimrx-real.ts`, `impls/reclaimrx-mock.ts`, `cache/reclaimrx-policy.ts` |
| Frontend module `packages/modules/reclaimrx` | NOT present | NEW: scaffold (package.json, tsconfig, vitest.config, module.config.ts) + empty-state routed pages |
| Event contract docs | NOT present | NEW: `docs/api-contracts/events/payment.hold_released.md` + `fwa.graph_run_completed.md` (per spec §11.5) |

## Endpoint delta inventory

Spec lists 18 endpoints (§5.5). Audit found 24 in existing `router.py`. Mapping:

| Spec endpoint | Existing route | Action |
|---|---|---|
| #1 GET /investigations | GET /investigations (`router.py:287`) | EXTEND — add filter params (status, severity, source, assigned_to, date), add backend require_role |
| #2 GET /investigations/{id} | GET /investigations/{id} (`router.py:331`) | EXTEND — add PHI audit + Cache-Control: no-store + require_mfa_elevated + mask by phi_access_level |
| #3 POST /investigations/{id}/transitions | NONE (closest: PUT /investigations/{id} at `router.py:344` does free-text status update) | NEW endpoint with state machine validation |
| #4 POST /investigations/{id}/notes | NONE (closest: POST /investigations/{id}/activity at `router.py:380`) | NEW endpoint — `notes` is append-only audited; keep activity for other event types |
| #5 GET /rule-firings | GET /flags (`router.py:209`) | RENAME-or-ALIAS — flags ARE rule firings in current code; add `GET /rule-firings` as alias OR rename; recommend alias to avoid breaking existing consumers |
| #6 GET /ml-scores | NONE | NEW |
| #7 GET /ml-scores/{id}/features | NONE | NEW |
| #8 GET /holds | GET /holds (`router.py:460`) | EXTEND — add active/released/expired filter + require_role |
| #9 POST /holds/{id}/release | DELETE /holds/{hold_id} (`router.py:475`) | RESHAPE — add POST .../release with full body (reason, investigation_id, emergency fields); transactional outbox; deprecate DELETE in same release |
| #10 POST /graph-runs/trigger | NONE | NEW |
| #11 GET /graph-runs | NONE | NEW |
| #12 GET /graph-runs/{run_id} | NONE | NEW |
| #13 GET /fraud-rings/{id} | NONE | NEW |
| #14 GET /recovery | GET /recoveries (`router.py:402`) | EXTEND — add `?period=&group_by=` aggregation OR add NEW endpoint `GET /recovery` keeping `/recoveries` as the list view |
| #15 GET /dashboard-summary | NONE | NEW |
| #16 GET /thresholds | NONE | NEW |
| #17 PUT /thresholds | NONE | NEW — admin only |
| #18 GET /accumulator-anomalies | GET /accumulator/detections (`router.py:574`) | ALIAS — add `GET /accumulator-anomalies` as alias for spec naming |

**Net work:** 11 NEW endpoints + 4 EXTEND + 1 RESHAPE + 1 RENAME/ALIAS.

---

## File structure

### Backend (modules/reclaimrx/src)

```
modules/reclaimrx/
  alembic/versions/
    0008_sp3_extensions.py                  ← NEW: model extensions + new tables + RLS + indexes
  src/
    api/
      router.py                             ← EXTEND: 11 new routes + 4 extended + 1 reshape + 1 alias; add require_role + require_mfa_elevated
      schemas/
        schemas.py                          ← EXTEND: new request/response shapes
        emergency_release.py                ← NEW: emergency_reason_code enum + body schema
    services/
      investigation_state_machine.py        ← NEW: transition validator
      outbox_service.py                     ← NEW: write outbox row in caller's TXN
      outbox_dispatcher.py                  ← NEW: background polling publisher
      payment_hold_service.py               ← EXTEND: release_with_outbox() method
      accumulator_anomaly_detector.py       ← NEW: 4 pattern detectors (sudden_spike, multi_payer_convergence, reset_evasion, threshold_oscillation)
      graph_analysis.py                     ← EXTEND: add run(tenant_id, graph_run_id, lookback_days) entrypoint + size guardrails
      threshold_versioning.py               ← NEW: version + per-field audit + hash chain
      role_gate.py                          ← NEW: require_role(role: str) dependency
      mfa_gate.py                           ← NEW: require_mfa_elevated() dependency via core-platform session lookup
      phi_masking.py                        ← NEW: mask response by user.phi_access_level
    events/
      consumers.py                          ← EXTEND: add handle_accumulator_updated + add 'accumulator.updated' to CONSUMER_ROUTING
      __init__.py                           ← EXTEND: wire_consumers uses RedisIdempotencyStore instead of InMemoryIdempotencyStore
    models/
      tables.py                             ← EXTEND: 6 new models (FraudRing, GraphRun, OutboxEvent, ThresholdConfigVersion, ThresholdConfigAudit) + extensions to Investigation, PaymentHold, AccumulatorDetection
    jobs/
      scheduled.py                          ← EXTEND: job_rebuild_fraud_network_graph rewritten as real; add job_verify_audit_chain, job_cleanup_processed_events, job_dispatch_outbox
      scheduler.py                          ← NEW: APScheduler bootstrap, JOB_SCHEDULE → scheduled jobs
    main.py                                 ← EXTEND: scheduler.start() in lifespan; real DLQ repo; DLQ depth monitoring binding
  tests/
    unit/
      test_investigation_state_machine.py
      test_outbox_service.py
      test_outbox_dispatcher.py
      test_payment_hold_release_with_outbox.py
      test_accumulator_anomaly_detector.py
      test_graph_analysis_run.py
      test_threshold_versioning.py
      test_role_gate.py
      test_mfa_gate.py
      test_phi_masking.py
    integration/
      test_endpoints_role_matrix.py
      test_hold_release_outbox_atomicity.py
      test_graph_run_concurrency.py
      test_accumulator_consumer_wiring.py
      test_audit_verification_job.py
      test_app_factory_bindings.py           ← LESSON-006: create_app() integration test
      test_rls_unset_tenant.py               ← spec R2 NEW BLOCK 2 acceptance
      test_cross_tenant_isolation_reclaimrx.py
      test_n_plus_one_detail_endpoints.py
```

### Contract layer (packages/contract/src)

```
packages/contract/src/
  clients/
    reclaimrx.ts                            ← NEW: typed ReclaimRxClient interface + methods for all 18 endpoints
  schemas/
    reclaimrx.ts                            ← NEW: zod request/response shapes
  impls/
    reclaimrx-real.ts                       ← NEW: RealImpl (calls backend via fetch)
    reclaimrx-mock.ts                       ← NEW: MockImpl (in-memory fixtures for tests)
  cache/
    reclaimrx-policy.ts                     ← NEW: cache tags + invalidation map per surface
packages/contract/tests/
  reclaimrx-contract.test.ts                ← NEW: Real impl matches Mock shape via zod
```

### Frontend module scaffold (packages/modules/reclaimrx)

```
packages/modules/reclaimrx/
  package.json
  tsconfig.json
  vitest.config.ts
  module.config.ts                          ← composition entry (routes, navEntry, commandPaletteScope)
  src/
    investigations/                         ← Plan B fills
      page-empty-state.tsx                  ← EmptyState with "Plan B will populate"
    rules/                                  ← Plan C fills
      page-empty-state.tsx
    ml/                                     ← Plan C fills
      page-empty-state.tsx
    holds/                                  ← Plan D fills
      page-empty-state.tsx
    recovery/                               ← Plan D fills
      page-empty-state.tsx
    graph/                                  ← Plan E fills
      page-empty-state.tsx
    rbac/
      RoleGate.tsx                          ← UX-layer gate (D5 layer 3)
    components/
      EmptyState.tsx                        ← reusable empty-state primitive
    index.ts
  tests/unit/
    EmptyState.test.tsx
    RoleGate.test.tsx
    module.config.test.ts
```

### Event contract docs

```
docs/api-contracts/events/
  payment.hold_released.md                  ← NEW per spec §11.5
  fwa.graph_run_completed.md                ← NEW per spec §11.5
```

---

## Tasks

### Phase 1: Model extensions + migration (T1-T4)

### Task 1: Extend `Investigation`, `PaymentHold`, `AccumulatorDetection` models + add 5 new models

**Files:**
- Modify: `modules/reclaimrx/src/models/tables.py` (extend lines around 373 Investigation, 587 PaymentHold, 490 AccumulatorDetection; append new models)
- Test: `modules/reclaimrx/tests/unit/test_models_extended.py`

- [ ] **Step 1: Write failing test for new model columns**

```python
# tests/unit/test_models_extended.py
from decimal import Decimal
import uuid
from src.models.tables import (
    Investigation, PaymentHold, AccumulatorDetection,
    FraudRing, GraphRun, OutboxEvent,
    ThresholdConfigVersion, ThresholdConfigAudit,
)

def test_investigation_has_outcome_columns():
    inv = Investigation()
    assert hasattr(inv, "outcome_label")
    assert hasattr(inv, "recovered_amount")
    assert hasattr(inv, "hold_amount")
    assert hasattr(inv, "threshold_config_version")
    assert hasattr(inv, "threshold_snapshot")

def test_payment_hold_has_released_by():
    h = PaymentHold()
    assert hasattr(h, "released_by")

def test_accumulator_detection_has_pattern_columns():
    d = AccumulatorDetection()
    assert hasattr(d, "pattern_type")
    assert hasattr(d, "evidence_window_start")
    assert hasattr(d, "evidence_window_end")
    assert hasattr(d, "triggering_event_ids")

def test_fraud_ring_model_exists():
    r = FraudRing(tenant_id=uuid.uuid4(), graph_run_id=uuid.uuid4(),
                  density_score=Decimal("0.5"), node_count=3, edge_count=4)
    assert r.spawned_investigation_id is None

def test_graph_run_status_enum_values():
    from src.models.tables import GraphRunStatus
    assert {s.value for s in GraphRunStatus} == {"running","completed","completed_partial","failed"}

def test_outbox_event_unique_idempotency_key():
    # Asserted via DB constraint in integration tests; here verify column exists
    assert "idempotency_key" in OutboxEvent.__table__.columns.keys()

def test_threshold_versioning_models():
    v = ThresholdConfigVersion(tenant_id=uuid.uuid4(), version=1)
    assert v.superseded_at is None
    a = ThresholdConfigAudit(tenant_id=uuid.uuid4(), threshold_config_id=uuid.uuid4(),
                             field="ml_score_thresholds.open", old_value="0.5", new_value="0.6")
    assert a.entry_hash is None  # filled in by service before commit
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd modules/reclaimrx && pytest tests/unit/test_models_extended.py -v`
Expected: ImportError on new model classes; AttributeError on new columns.

- [ ] **Step 3: Add columns + new models to `tables.py`**

Append to `tables.py` (in the order: GraphRunStatus enum, then models). Key additions:

```python
import enum
from sqlalchemy import Numeric, JSON, Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB

class InvestigationOutcome(str, enum.Enum):
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false_positive"
    NO_ACTION = "no_action"

# EXTEND Investigation (existing at line ~373) — add columns:
#   outcome_label = Column(SAEnum(InvestigationOutcome), nullable=True)
#   recovered_amount = Column(Numeric(14, 2), nullable=True)
#   hold_amount = Column(Numeric(14, 2), nullable=True)
#   threshold_config_version = Column(Integer, ForeignKey("threshold_config_version.id"), nullable=True)
#   threshold_snapshot = Column(JSONB, nullable=True)
#   state_machine_version = Column(Integer, nullable=False, default=1)

# EXTEND PaymentHold (existing at line ~587) — add:
#   released_by = Column(String(256), nullable=True)

class AccumulatorPatternType(str, enum.Enum):
    SUDDEN_SPIKE = "sudden_spike"
    MULTI_PAYER_CONVERGENCE = "multi_payer_convergence"
    RESET_EVASION = "reset_evasion"
    THRESHOLD_OSCILLATION = "threshold_oscillation"

# EXTEND AccumulatorDetection — add:
#   pattern_type = Column(SAEnum(AccumulatorPatternType), nullable=True)
#   evidence_window_start = Column(DateTime(timezone=True), nullable=True)
#   evidence_window_end = Column(DateTime(timezone=True), nullable=True)
#   triggering_event_ids = Column(JSONB, nullable=True)

class GraphRunStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_PARTIAL = "completed_partial"
    FAILED = "failed"

class FraudRing(TenantScopedBase):  # match existing TenantScopedMixin pattern
    __tablename__ = "fraud_ring"
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    graph_run_id = Column(PG_UUID(as_uuid=True), ForeignKey("graph_run.id"), nullable=False)
    detected_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    density_score = Column(Numeric(8, 6), nullable=False)
    node_count = Column(Integer, nullable=False)
    edge_count = Column(Integer, nullable=False)
    entity_refs = Column(JSONB, nullable=False)
    spawned_investigation_id = Column(PG_UUID(as_uuid=True), ForeignKey("investigation.id"), nullable=True)

class GraphRun(TenantScopedBase):
    __tablename__ = "graph_run"
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(SAEnum(GraphRunStatus), nullable=False, default=GraphRunStatus.RUNNING)
    trigger = Column(String(16), nullable=False)  # 'cron' | 'on_demand'
    started_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    completed_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)  # sanitized
    correlation_id = Column(String(64), nullable=False)
    stale_timeout_at = Column(DateTime(timezone=True), nullable=False)
    rings_detected = Column(Integer, nullable=False, default=0)
    investigations_opened = Column(Integer, nullable=False, default=0)
    records_scanned = Column(Integer, nullable=False, default=0)
    lookback_window_days = Column(Integer, nullable=False, default=90)

class OutboxEvent(TenantScopedBase):
    __tablename__ = "outbox_event"
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(128), nullable=False)
    envelope_json = Column(JSONB, nullable=False)
    status = Column(String(16), nullable=False, default="pending")  # pending | published | failed
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    published_at = Column(DateTime(timezone=True), nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    idempotency_key = Column(String(256), nullable=False, unique=True)

class ThresholdConfigVersion(TenantScopedBase):
    __tablename__ = "threshold_config_version"
    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(Integer, nullable=False)  # monotonic per tenant
    effective_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    superseded_at = Column(DateTime(timezone=True), nullable=True)
    payload = Column(JSONB, nullable=False)  # full ThresholdConfig snapshot
    updated_by = Column(String(256), nullable=False)
    __table_args__ = (UniqueConstraint("tenant_id", "version", name="uq_threshold_version"),)

class ThresholdConfigAudit(TenantScopedBase):
    __tablename__ = "threshold_config_audit"
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    threshold_config_id = Column(Integer, ForeignKey("threshold_config_version.id"), nullable=False)
    field = Column(String(256), nullable=False)
    old_value = Column(Text, nullable=False)
    new_value = Column(Text, nullable=False)
    changed_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    changed_by = Column(String(256), nullable=False)
    reason = Column(Text, nullable=True)
    entry_hash = Column(String(64), nullable=False)
    prev_entry_hash = Column(String(64), nullable=True)
```

Verify imports at top of `tables.py` cover: `Numeric`, `Text`, `UniqueConstraint`, `enum`. Add `from sqlalchemy.dialects.postgresql import JSONB` if not present.

- [ ] **Step 4: Run test, verify it passes**

Run: `pytest tests/unit/test_models_extended.py -v`
Expected: PASS (10 tests).

- [ ] **Step 5: Commit**

```bash
git add modules/reclaimrx/src/models/tables.py modules/reclaimrx/tests/unit/test_models_extended.py
git commit -m "feat(sp3-a): extend Investigation/PaymentHold/AccumulatorDetection + add 5 new models"
```

---

### Task 2: Alembic 0008 — schema + RLS + indexes

**Files:**
- Create: `modules/reclaimrx/alembic/versions/0008_sp3_extensions.py`
- Test: `modules/reclaimrx/tests/integration/test_migration_0008.py`

- [ ] **Step 1: Write failing migration round-trip test**

```python
# tests/integration/test_migration_0008.py
import subprocess

def test_0008_upgrade_then_downgrade():
    # Assumes a test Postgres URL via env; uses alembic upgrade head + downgrade -1
    r1 = subprocess.run(["alembic", "upgrade", "head"], check=False, capture_output=True, text=True,
                        cwd="modules/reclaimrx")
    assert r1.returncode == 0, r1.stderr
    r2 = subprocess.run(["alembic", "downgrade", "-1"], check=False, capture_output=True, text=True,
                        cwd="modules/reclaimrx")
    assert r2.returncode == 0, r2.stderr
    r3 = subprocess.run(["alembic", "upgrade", "head"], check=False, capture_output=True, text=True,
                        cwd="modules/reclaimrx")
    assert r3.returncode == 0, r3.stderr
```

- [ ] **Step 2: Run test, verify it fails**

Run: `pytest tests/integration/test_migration_0008.py -v`
Expected: FAIL — 0008 doesn't exist yet.

- [ ] **Step 3: Author 0008 migration**

```python
# alembic/versions/0008_sp3_extensions.py
"""SP-3 extensions: investigation outcome + payment hold released_by +
accumulator pattern + 5 new tables + RLS + indexes.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

revision = "0008_sp3_extensions"
down_revision = "0007_flagged_npis"
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. EXTEND existing tables
    op.add_column("investigation", sa.Column("outcome_label",
        sa.Enum("confirmed","false_positive","no_action", name="investigation_outcome"), nullable=True))
    op.add_column("investigation", sa.Column("recovered_amount", sa.Numeric(14, 2), nullable=True))
    op.add_column("investigation", sa.Column("hold_amount", sa.Numeric(14, 2), nullable=True))
    op.add_column("investigation", sa.Column("threshold_config_version", sa.Integer(), nullable=True))
    op.add_column("investigation", sa.Column("threshold_snapshot", JSONB(), nullable=True))
    op.add_column("investigation", sa.Column("state_machine_version", sa.Integer(), nullable=False, server_default="1"))
    op.create_index("ix_investigation_tenant_status", "investigation", ["tenant_id","status"])
    op.create_index("ix_investigation_tenant_severity", "investigation", ["tenant_id","severity"])
    op.create_index("ix_investigation_tenant_opened_at", "investigation", ["tenant_id", sa.text("opened_at DESC")])

    op.add_column("payment_hold", sa.Column("released_by", sa.String(256), nullable=True))

    op.add_column("accumulator_detection", sa.Column("pattern_type",
        sa.Enum("sudden_spike","multi_payer_convergence","reset_evasion","threshold_oscillation",
                name="accumulator_pattern_type"), nullable=True))
    op.add_column("accumulator_detection", sa.Column("evidence_window_start", sa.DateTime(timezone=True), nullable=True))
    op.add_column("accumulator_detection", sa.Column("evidence_window_end", sa.DateTime(timezone=True), nullable=True))
    op.add_column("accumulator_detection", sa.Column("triggering_event_ids", JSONB(), nullable=True))

    # 2. NEW tables (all tenant-scoped with RLS)
    op.create_table("fraud_ring",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("graph_run_id", PG_UUID(as_uuid=True), sa.ForeignKey("graph_run.id"), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("density_score", sa.Numeric(8, 6), nullable=False),
        sa.Column("node_count", sa.Integer(), nullable=False),
        sa.Column("edge_count", sa.Integer(), nullable=False),
        sa.Column("entity_refs", JSONB(), nullable=False),
        sa.Column("spawned_investigation_id", PG_UUID(as_uuid=True), sa.ForeignKey("investigation.id"), nullable=True),
    )
    op.create_index("ix_fraud_ring_tenant_detected", "fraud_ring", ["tenant_id", sa.text("detected_at DESC")])

    op.create_table("graph_run",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Enum("running","completed","completed_partial","failed", name="graph_run_status"), nullable=False),
        sa.Column("trigger", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("stale_timeout_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rings_detected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("investigations_opened", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_scanned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lookback_window_days", sa.Integer(), nullable=False, server_default="90"),
    )
    op.create_index("ix_graph_run_tenant_status_started", "graph_run", ["tenant_id","status", sa.text("started_at DESC")])

    op.create_table("outbox_event",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("envelope_json", JSONB(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(256), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_outbox_idempotency"),
    )
    op.create_index("ix_outbox_pending", "outbox_event", ["status","created_at"],
                    postgresql_where=sa.text("status = 'pending'"))

    op.create_table("threshold_config_version",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("updated_by", sa.String(256), nullable=False),
        sa.UniqueConstraint("tenant_id","version", name="uq_threshold_version"),
    )

    op.create_table("threshold_config_audit",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("threshold_config_id", sa.Integer(), sa.ForeignKey("threshold_config_version.id"), nullable=False),
        sa.Column("field", sa.String(256), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=False),
        sa.Column("new_value", sa.Text(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_by", sa.String(256), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("entry_hash", sa.String(64), nullable=False),
        sa.Column("prev_entry_hash", sa.String(64), nullable=True),
    )
    op.create_index("ix_threshold_audit_tenant_changed", "threshold_config_audit", ["tenant_id", sa.text("changed_at DESC")])

    # 3. FK from investigation.threshold_config_version → threshold_config_version.id
    op.create_foreign_key("fk_inv_threshold_version", "investigation",
                          "threshold_config_version", ["threshold_config_version"], ["id"])

    # 4. PG RLS — null-deny via current_setting('app.tenant_id', true) per spec D8
    for table in ("fraud_ring","graph_run","outbox_event","threshold_config_version","threshold_config_audit"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
            WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
        """)

def downgrade() -> None:
    for table in ("threshold_config_audit","threshold_config_version","outbox_event","graph_run","fraud_ring"):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_constraint("fk_inv_threshold_version", "investigation", type_="foreignkey")
    op.drop_index("ix_threshold_audit_tenant_changed")
    op.drop_table("threshold_config_audit")
    op.drop_table("threshold_config_version")
    op.drop_index("ix_outbox_pending")
    op.drop_table("outbox_event")
    op.drop_index("ix_graph_run_tenant_status_started")
    op.drop_table("graph_run")
    op.drop_index("ix_fraud_ring_tenant_detected")
    op.drop_table("fraud_ring")
    op.drop_column("accumulator_detection","triggering_event_ids")
    op.drop_column("accumulator_detection","evidence_window_end")
    op.drop_column("accumulator_detection","evidence_window_start")
    op.drop_column("accumulator_detection","pattern_type")
    op.execute("DROP TYPE IF EXISTS accumulator_pattern_type")
    op.drop_column("payment_hold","released_by")
    op.drop_index("ix_investigation_tenant_opened_at")
    op.drop_index("ix_investigation_tenant_severity")
    op.drop_index("ix_investigation_tenant_status")
    op.drop_column("investigation","state_machine_version")
    op.drop_column("investigation","threshold_snapshot")
    op.drop_column("investigation","threshold_config_version")
    op.drop_column("investigation","hold_amount")
    op.drop_column("investigation","recovered_amount")
    op.drop_column("investigation","outcome_label")
    op.execute("DROP TYPE IF EXISTS investigation_outcome")
    op.execute("DROP TYPE IF EXISTS graph_run_status")
```

- [ ] **Step 4: Run round-trip, verify PASS**

Run: `pytest tests/integration/test_migration_0008.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add modules/reclaimrx/alembic/versions/0008_sp3_extensions.py modules/reclaimrx/tests/integration/test_migration_0008.py
git commit -m "feat(sp3-a): alembic 0008 — sp3 model extensions + 5 new tables + RLS + indexes"
```

---

### Task 3: RLS null-deny acceptance test (spec R2 NEW BLOCK 2)

**Files:**
- Create: `modules/reclaimrx/tests/integration/test_rls_unset_tenant.py`

- [ ] **Step 1: Write failing test for unset-tenant null-deny**

```python
# tests/integration/test_rls_unset_tenant.py
import pytest
from sqlalchemy import text

@pytest.mark.integration
def test_unset_app_tenant_id_yields_zero_rows(db_engine):
    """Per spec D8 + R2 NEW BLOCK 2: open session WITHOUT setting app.tenant_id,
    query each new tenant-owned table, assert zero rows AND no exception."""
    new_tables = ["fraud_ring","graph_run","outbox_event","threshold_config_version","threshold_config_audit"]
    with db_engine.connect() as conn:
        # do NOT set app.tenant_id
        for t in new_tables:
            result = conn.execute(text(f"SELECT count(*) FROM {t}")).scalar()
            assert result == 0, f"{t}: expected 0 rows under unset tenant; got {result}"
```

- [ ] **Step 2: Run, verify FAIL (unless rows happen to be 0; ensure test seeds data with different tenant first)**

Update test to: seed data with `set_config('app.tenant_id', '<tid>')` then query without setting. Run.

- [ ] **Step 3: No code change needed if 0008 RLS clauses are correct.**

- [ ] **Step 4: Run, verify PASS**

- [ ] **Step 5: Commit**

```bash
git add modules/reclaimrx/tests/integration/test_rls_unset_tenant.py
git commit -m "test(sp3-a): RLS null-deny acceptance test (R2 NEW BLOCK 2)"
```

---

### Task 4: Investigation state machine validator

**Files:**
- Create: `modules/reclaimrx/src/services/investigation_state_machine.py`
- Test: `modules/reclaimrx/tests/unit/test_investigation_state_machine.py`

- [ ] **Step 1: Write failing test matching spec §5.5.1**

```python
# tests/unit/test_investigation_state_machine.py
import pytest
from src.services.investigation_state_machine import (
    InvestigationStateMachine, InvalidTransition, RequiredFieldMissing,
)

def test_open_to_in_progress_with_reason():
    sm = InvestigationStateMachine()
    sm.validate(from_status="open", to_status="in_progress", role="investigator",
                fields={"reason": "starting triage"})  # OK, no raise

def test_open_to_invalid_status_raises():
    sm = InvestigationStateMachine()
    with pytest.raises(InvalidTransition) as exc:
        sm.validate(from_status="open", to_status="closed_confirmed", role="investigator",
                    fields={"reason":"x","outcome_label":"confirmed","recovered_amount":"100.00"})
    assert "in_progress" in str(exc.value)  # error.field shows allowed-next

def test_in_progress_to_closed_confirmed_requires_recovered_amount():
    sm = InvestigationStateMachine()
    with pytest.raises(RequiredFieldMissing) as exc:
        sm.validate(from_status="in_progress", to_status="closed_confirmed",
                    role="investigator", fields={"reason":"x","outcome_label":"confirmed"})
    assert "recovered_amount" in str(exc.value)

def test_escalated_to_in_progress_requires_admin():
    sm = InvestigationStateMachine()
    with pytest.raises(InvalidTransition):
        sm.validate(from_status="escalated", to_status="in_progress",
                    role="investigator", fields={"reason":"x"})
    sm.validate(from_status="escalated", to_status="in_progress",
                role="admin", fields={"reason":"x"})  # OK

def test_closed_to_open_admin_only_override():
    sm = InvestigationStateMachine()
    with pytest.raises(InvalidTransition):
        sm.validate(from_status="closed_confirmed", to_status="open",
                    role="investigator", fields={"reason":"x"})
    sm.validate(from_status="closed_confirmed", to_status="open",
                role="admin", fields={"reason":"x"})  # OK

def test_invalid_transition_lists_allowed_next_states():
    sm = InvestigationStateMachine()
    try:
        sm.validate(from_status="open", to_status="closed_no_action", role="investigator", fields={"reason":"x"})
        assert False, "should have raised"
    except InvalidTransition as e:
        assert set(e.allowed_next) >= {"in_progress","pending_review","escalated"}
```

- [ ] **Step 2: Run, verify FAIL**

Run: `pytest tests/unit/test_investigation_state_machine.py -v`

- [ ] **Step 3: Implement state machine matching spec §5.5.1 table**

```python
# src/services/investigation_state_machine.py
from typing import Mapping

class InvalidTransition(Exception):
    def __init__(self, message: str, allowed_next: list[str] | None = None):
        super().__init__(message)
        self.allowed_next = allowed_next or []

class RequiredFieldMissing(Exception):
    pass

# (from, to) -> (required_role: set, required_fields: set)
_TRANSITIONS: dict[tuple[str, str], tuple[set[str], set[str]]] = {
    ("open","in_progress"): ({"investigator","admin"}, {"reason"}),
    ("open","pending_review"): ({"investigator","admin"}, {"reason"}),
    ("open","escalated"): ({"investigator","admin"}, {"reason"}),
    ("in_progress","pending_review"): ({"investigator","admin"}, {"reason"}),
    ("in_progress","closed_confirmed"): ({"investigator","admin"}, {"reason","outcome_label","recovered_amount"}),
    ("in_progress","closed_false_positive"): ({"investigator","admin"}, {"reason","outcome_label"}),
    ("in_progress","closed_no_action"): ({"investigator","admin"}, {"reason","outcome_label"}),
    ("in_progress","escalated"): ({"investigator","admin"}, {"reason"}),
    ("pending_review","in_progress"): ({"investigator","admin"}, {"reason"}),
    ("pending_review","closed_confirmed"): ({"investigator","admin"}, {"reason","outcome_label","recovered_amount"}),
    ("pending_review","closed_false_positive"): ({"investigator","admin"}, {"reason","outcome_label"}),
    ("pending_review","closed_no_action"): ({"investigator","admin"}, {"reason","outcome_label"}),
    ("pending_review","escalated"): ({"investigator","admin"}, {"reason"}),
    ("escalated","in_progress"): ({"admin"}, {"reason"}),  # override
    ("escalated","closed_confirmed"): ({"admin"}, {"reason","outcome_label","recovered_amount"}),
    ("escalated","closed_false_positive"): ({"admin"}, {"reason","outcome_label"}),
    ("escalated","closed_no_action"): ({"admin"}, {"reason","outcome_label"}),
    ("closed_confirmed","open"): ({"admin"}, {"reason"}),  # override-locked re-open
    ("closed_false_positive","open"): ({"admin"}, {"reason"}),
    ("closed_no_action","open"): ({"admin"}, {"reason"}),
}

class InvestigationStateMachine:
    def validate(self, *, from_status: str, to_status: str, role: str, fields: Mapping[str, object]) -> None:
        if (from_status, to_status) not in _TRANSITIONS:
            allowed = [to for (f, to) in _TRANSITIONS if f == from_status]
            raise InvalidTransition(
                f"{from_status} → {to_status} not allowed; valid: {sorted(allowed)}",
                allowed_next=allowed,
            )
        required_roles, required_fields = _TRANSITIONS[(from_status, to_status)]
        if role not in required_roles:
            raise InvalidTransition(f"{role} cannot perform {from_status} → {to_status}; required: {sorted(required_roles)}")
        missing = [f for f in required_fields if f not in fields or fields[f] in (None, "")]
        if missing:
            raise RequiredFieldMissing(f"missing required fields: {missing}")
```

- [ ] **Step 4: Run, verify PASS**

- [ ] **Step 5: Commit**

```bash
git add modules/reclaimrx/src/services/investigation_state_machine.py modules/reclaimrx/tests/unit/test_investigation_state_machine.py
git commit -m "feat(sp3-a): investigation state machine validator per spec §5.5.1"
```

---

### Phase 2: Outbox + hold release reshape (T5-T8)

### Task 5: Outbox service (write outbox row in caller's TXN)

**Files:**
- Create: `modules/reclaimrx/src/services/outbox_service.py`
- Test: `modules/reclaimrx/tests/unit/test_outbox_service.py`

- [ ] **Step 1: Failing test**

```python
# tests/unit/test_outbox_service.py
from decimal import Decimal
from src.services.outbox_service import write_outbox_event
from src.models.tables import OutboxEvent

def test_write_outbox_event_creates_pending_row(db_session, tenant_id):
    write_outbox_event(
        db=db_session,
        tenant_id=tenant_id,
        event_type="payment.hold_released",
        ordering_key="hold-123",
        idempotency_key="hold:release:hold-123",
        schema_version="1.0",
        payload={"hold_id":"hold-123","amount":"42.00"},
    )
    row = db_session.query(OutboxEvent).filter_by(idempotency_key="hold:release:hold-123").one()
    assert row.status == "pending"
    assert row.envelope_json["tenant_id"] == str(tenant_id)
    assert row.envelope_json["payload"]["amount"] == "42.00"

def test_duplicate_idempotency_key_raises(db_session, tenant_id):
    import pytest
    from sqlalchemy.exc import IntegrityError
    write_outbox_event(db=db_session, tenant_id=tenant_id, event_type="payment.hold_released",
                      ordering_key="h1", idempotency_key="dup", schema_version="1.0", payload={})
    db_session.flush()
    write_outbox_event(db=db_session, tenant_id=tenant_id, event_type="payment.hold_released",
                      ordering_key="h2", idempotency_key="dup", schema_version="1.0", payload={})
    with pytest.raises(IntegrityError):
        db_session.flush()
```

- [ ] **Step 2: Run, fail**

- [ ] **Step 3: Implement**

```python
# src/services/outbox_service.py
"""Transactional outbox writer. Caller MUST be inside an open TXN; commit is
the caller's responsibility — outbox row + business writes must atomicize."""
from __future__ import annotations
from datetime import UTC, datetime
import uuid
from typing import Any
from sqlalchemy.orm import Session
from src.models.tables import OutboxEvent

def write_outbox_event(
    *, db: Session, tenant_id: uuid.UUID, event_type: str,
    ordering_key: str, idempotency_key: str, schema_version: str, payload: dict[str, Any],
) -> OutboxEvent:
    envelope = {
        "type": event_type,
        "tenant_id": str(tenant_id),                # R1 BLOCK 3 envelope-level
        "ordering_key": ordering_key,
        "idempotency_key": idempotency_key,
        "schema_version": schema_version,
        "payload": payload,
        "emitted_at": datetime.now(UTC).isoformat(),
    }
    row = OutboxEvent(
        id=uuid.uuid4(), tenant_id=tenant_id, event_type=event_type,
        envelope_json=envelope, status="pending",
        created_at=datetime.now(UTC), attempt_count=0, idempotency_key=idempotency_key,
    )
    db.add(row)
    return row
```

- [ ] **Step 4: Run, pass**

- [ ] **Step 5: Commit**

```bash
git add modules/reclaimrx/src/services/outbox_service.py modules/reclaimrx/tests/unit/test_outbox_service.py
git commit -m "feat(sp3-a): transactional outbox writer service"
```

---

### Task 6: Outbox dispatcher (background polling publisher with retry)

**Files:**
- Create: `modules/reclaimrx/src/services/outbox_dispatcher.py`
- Test: `modules/reclaimrx/tests/unit/test_outbox_dispatcher.py`

- [ ] **Step 1: Failing test for retry + idempotent publish**

```python
# tests/unit/test_outbox_dispatcher.py
from unittest.mock import AsyncMock, MagicMock
import pytest
from src.services.outbox_dispatcher import OutboxDispatcher
from src.models.tables import OutboxEvent

@pytest.mark.asyncio
async def test_dispatch_publishes_pending_and_marks_published(db_session, tenant_id):
    bus = MagicMock(); bus.publish = AsyncMock()
    row = OutboxEvent(id=...id, tenant_id=tenant_id, event_type="payment.hold_released",
                     envelope_json={"type":"payment.hold_released","payload":{}},
                     status="pending", idempotency_key="k1", attempt_count=0)
    db_session.add(row); db_session.commit()
    d = OutboxDispatcher(bus=bus, session_factory=lambda: db_session)
    await d.dispatch_batch(limit=10)
    db_session.refresh(row)
    assert row.status == "published"
    assert row.published_at is not None
    bus.publish.assert_awaited_once()

@pytest.mark.asyncio
async def test_dispatch_failure_increments_attempt_count(db_session, tenant_id):
    bus = MagicMock(); bus.publish = AsyncMock(side_effect=ConnectionError("broker down"))
    row = OutboxEvent(...status="pending", attempt_count=0)
    db_session.add(row); db_session.commit()
    d = OutboxDispatcher(bus=bus, session_factory=lambda: db_session)
    await d.dispatch_batch(limit=10)
    db_session.refresh(row)
    assert row.status == "pending"
    assert row.attempt_count == 1
    assert "broker down" in (row.last_error or "")

@pytest.mark.asyncio
async def test_dispatch_marks_failed_after_max_attempts(db_session, tenant_id):
    bus = MagicMock(); bus.publish = AsyncMock(side_effect=ConnectionError("x"))
    row = OutboxEvent(...status="pending", attempt_count=9)  # 10 = max
    db_session.add(row); db_session.commit()
    d = OutboxDispatcher(bus=bus, session_factory=lambda: db_session, max_attempts=10)
    await d.dispatch_batch(limit=10)
    db_session.refresh(row)
    assert row.status == "failed"
```

- [ ] **Step 2-4: Implement, run, verify pass**

```python
# src/services/outbox_dispatcher.py
"""Background outbox dispatcher. Polls pending OutboxEvent rows, publishes to
EventBus, marks published or increments retry. Max attempts default 10."""
from __future__ import annotations
import logging
from datetime import UTC, datetime
from typing import Callable
from sqlalchemy import select
from shared.events.bus import EventBus
from shared.events.types import EventEnvelope
from src.models.tables import OutboxEvent

logger = logging.getLogger("reclaimrx.outbox.dispatcher")

class OutboxDispatcher:
    def __init__(self, *, bus: EventBus, session_factory: Callable, max_attempts: int = 10):
        self.bus = bus
        self.session_factory = session_factory
        self.max_attempts = max_attempts

    async def dispatch_batch(self, *, limit: int = 100) -> int:
        session = self.session_factory()
        try:
            pending = session.execute(
                select(OutboxEvent).where(OutboxEvent.status == "pending")
                .order_by(OutboxEvent.created_at).limit(limit).with_for_update(skip_locked=True)
            ).scalars().all()
            published = 0
            for row in pending:
                envelope = EventEnvelope(**row.envelope_json)
                try:
                    await self.bus.publish(envelope)
                    row.status = "published"
                    row.published_at = datetime.now(UTC)
                    published += 1
                except Exception as exc:
                    row.attempt_count += 1
                    row.last_error = f"{type(exc).__name__}: {exc}"[:500]
                    if row.attempt_count >= self.max_attempts:
                        row.status = "failed"
                        logger.error("outbox.dispatch_failed_permanently",
                                     extra={"outbox_id": str(row.id), "attempts": row.attempt_count})
            session.commit()
            return published
        finally:
            session.close()
```

- [ ] **Step 5: Commit**

```bash
git add modules/reclaimrx/src/services/outbox_dispatcher.py modules/reclaimrx/tests/unit/test_outbox_dispatcher.py
git commit -m "feat(sp3-a): outbox background dispatcher with retry"
```

---

### Task 7: Reshape `payment_hold_service` — `release_with_outbox()` method

**Files:**
- Modify: `modules/reclaimrx/src/services/payment_hold_service.py`
- Test: `modules/reclaimrx/tests/unit/test_payment_hold_release_with_outbox.py`

- [ ] **Step 1: Failing test for the three idempotency cases (spec R2 NEW CONCERN 1)**

```python
# tests/unit/test_payment_hold_release_with_outbox.py
import pytest
from decimal import Decimal
from src.services.payment_hold_service import (
    release_with_outbox, ReleaseConflict, HoldNotActive, HoldInvestigationMismatch,
)
from src.models.tables import PaymentHold, Investigation, OutboxEvent

def test_release_active_hold_publishes_outbox_event(db_session, tenant_id, hold_id, inv_id):
    hold = PaymentHold(id=hold_id, tenant_id=tenant_id, investigation_id=inv_id,
                       hold_amount=Decimal("100.00"), is_active=True)
    db_session.add(hold); db_session.commit()
    release_with_outbox(db=db_session, tenant_id=tenant_id, hold_id=hold_id,
                        body={"reason":"resolved","investigation_id":str(inv_id)},
                        actor_sub="user-A", role="investigator")
    db_session.refresh(hold)
    assert hold.is_active is False
    assert hold.released_by == "user-A"
    out = db_session.query(OutboxEvent).filter_by(idempotency_key=f"hold:release:{hold_id}").one()
    assert out.envelope_json["type"] == "payment.hold_released"
    assert out.envelope_json["tenant_id"] == str(tenant_id)

def test_release_same_actor_reason_idempotent_replay_200(db_session, tenant_id, hold_id, inv_id):
    # Already released by user-A with reason "resolved"
    hold = PaymentHold(id=hold_id, tenant_id=tenant_id, investigation_id=inv_id,
                       is_active=False, released_by="user-A", release_reason="resolved")
    db_session.add(hold); db_session.commit()
    # Same actor + reason + investigation → 200 idempotent
    result = release_with_outbox(db=db_session, tenant_id=tenant_id, hold_id=hold_id,
                                  body={"reason":"resolved","investigation_id":str(inv_id)},
                                  actor_sub="user-A", role="investigator")
    assert result["status"] == "ok_idempotent"

def test_release_different_actor_raises_conflict(db_session, tenant_id, hold_id, inv_id):
    hold = PaymentHold(id=hold_id, tenant_id=tenant_id, investigation_id=inv_id,
                       is_active=False, released_by="user-A", release_reason="resolved")
    db_session.add(hold); db_session.commit()
    with pytest.raises(ReleaseConflict):
        release_with_outbox(db=db_session, tenant_id=tenant_id, hold_id=hold_id,
                             body={"reason":"resolved","investigation_id":str(inv_id)},
                             actor_sub="user-B", role="investigator")

def test_release_non_active_non_released_raises_HoldNotActive(db_session, ...):
    hold = PaymentHold(...status="expired", is_active=False, released_by=None)
    # Test expects HoldNotActive raised
    with pytest.raises(HoldNotActive):
        release_with_outbox(...)

def test_release_mismatched_investigation_raises(db_session, ...):
    hold = PaymentHold(...investigation_id=inv_A)
    with pytest.raises(HoldInvestigationMismatch):
        release_with_outbox(db=..., body={"reason":"x","investigation_id":str(inv_B)}, ...)
```

- [ ] **Step 2-4: Implement, run, pass**

```python
# src/services/payment_hold_service.py (EXTEND existing — add release_with_outbox)
from datetime import UTC, datetime
from src.services.outbox_service import write_outbox_event
from src.models.tables import PaymentHold

class HoldNotActive(Exception): pass
class HoldInvestigationMismatch(Exception): pass
class ReleaseConflict(Exception):
    def __init__(self, prior_release: dict):
        self.prior_release = prior_release

def release_with_outbox(*, db, tenant_id, hold_id, body, actor_sub, role,
                        emergency_reason_code=None, emergency_note=None):
    hold = db.get(PaymentHold, hold_id)
    if not hold or hold.tenant_id != tenant_id:
        raise HoldInvestigationMismatch("hold not found in tenant")
    if str(hold.investigation_id) != body["investigation_id"]:
        raise HoldInvestigationMismatch("investigation_id mismatch")
    # Lock FOR UPDATE
    db.refresh(hold, with_for_update=True)
    # Idempotency tri-case (R2 NEW CONCERN 1)
    if hold.released_by is not None:  # already released
        if (hold.released_by == actor_sub and hold.release_reason == body["reason"]):
            return {"status":"ok_idempotent", "released_at": hold.released_at, "released_by": hold.released_by}
        raise ReleaseConflict({
            "released_at": str(hold.released_at), "released_by": hold.released_by,
            "release_reason": hold.release_reason,
        })
    if not hold.is_active:
        raise HoldNotActive(f"hold status not releasable")
    # Admin emergency override skips active check (R5 wiring) — already past for non-active
    hold.is_active = False
    hold.released_at = datetime.now(UTC)
    hold.released_by = actor_sub
    hold.release_reason = body["reason"]
    # Outbox emit
    payload = {
        "hold_id": str(hold_id),
        "amount": str(hold.hold_amount) if hold.hold_amount else "0.00",
        "released_by": actor_sub,
        "reason": body["reason"],
        "investigation_id": body["investigation_id"],
        "released_at": hold.released_at.isoformat(),
        "emergency_reason_code": emergency_reason_code,
        "emergency_note": emergency_note,
    }
    write_outbox_event(
        db=db, tenant_id=tenant_id, event_type="payment.hold_released",
        ordering_key=str(hold_id),
        idempotency_key=f"hold:release:{hold_id}",
        schema_version="1.0", payload=payload,
    )
    return {"status":"released", "released_at": hold.released_at}
```

- [ ] **Step 5: Commit**

```bash
git add modules/reclaimrx/src/services/payment_hold_service.py modules/reclaimrx/tests/unit/test_payment_hold_release_with_outbox.py
git commit -m "feat(sp3-a): hold release with transactional outbox + 3 idempotency cases"
```

---

### Task 8: Hold release endpoint — POST /holds/{hold_id}/release + deprecate DELETE

**Files:**
- Modify: `modules/reclaimrx/src/api/router.py` (around line 475)
- Modify: `modules/reclaimrx/src/api/schemas/schemas.py` (add release body schema)
- Test: `modules/reclaimrx/tests/integration/test_hold_release_endpoint.py`

- [ ] **Step 1: Test for endpoint contract + role gate**

```python
# tests/integration/test_hold_release_endpoint.py
from decimal import Decimal
def test_release_active_hold_200(client, db_session, tenant_id, hold_id, inv_id, investigator_token):
    resp = client.post(f"/holds/{hold_id}/release",
                        json={"reason":"resolved","investigation_id":str(inv_id)},
                        headers={"Authorization": f"Bearer {investigator_token}",
                                 "x-tenant-id": str(tenant_id)})
    assert resp.status_code == 200
    assert resp.json()["status"] == "released"

def test_release_by_viewer_returns_403_INSUFFICIENT_ROLE(client, ..., viewer_token):
    resp = client.post(f"/holds/{hold_id}/release", json={...}, headers={...viewer_token})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "INSUFFICIENT_ROLE"

def test_release_replay_same_actor_returns_200_idempotent(client, ...):
    # Release twice in sequence — both 200
    r1 = client.post(f"/holds/{hold_id}/release", json={...}, headers={...investigator_token})
    r2 = client.post(f"/holds/{hold_id}/release", json={...}, headers={...investigator_token})
    assert r1.status_code == 200 and r2.status_code == 200

def test_release_different_actor_returns_409_ALREADY_RELEASED(client, ...):
    client.post(f"/holds/{hold_id}/release", json={...}, headers={...investigator_A_token})
    resp = client.post(f"/holds/{hold_id}/release", json={...}, headers={...investigator_B_token})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ALREADY_RELEASED"

def test_emergency_release_admin_only(client, ...):
    body = {"reason":"x","investigation_id":..., "emergency_reason_code":"LEGAL_HOLD"}
    resp_investigator = client.post(..., json=body, headers={...investigator_token})
    assert resp_investigator.status_code == 403  # only admin can use emergency fields
    resp_admin = client.post(..., json=body, headers={...admin_token})
    assert resp_admin.status_code == 200
```

- [ ] **Step 2: Run, fail (no endpoint)**

- [ ] **Step 3: Add schema + endpoint**

```python
# src/api/schemas/schemas.py — ADD
from pydantic import BaseModel
from typing import Literal
class HoldReleaseBody(BaseModel):
    reason: str
    investigation_id: str
    emergency_reason_code: Literal["LEGAL_HOLD","REGULATORY_DIRECTIVE","IRRECOVERABLE_HARM","OTHER_WITH_NOTE"] | None = None
    emergency_note: str | None = None

# src/api/router.py — ADD after existing /holds endpoints (around line 498)
from src.services.payment_hold_service import (
    release_with_outbox, HoldNotActive, HoldInvestigationMismatch, ReleaseConflict,
)
from src.services.role_gate import require_role

@router.post("/holds/{hold_id}/release", response_model=dict)
async def release_hold(
    hold_id: UUID,
    body: HoldReleaseBody,
    user=Depends(get_current_user),
    _=Depends(require_role("reclaimrx.investigator")),
    db=Depends(get_db),
    request: Request = None,
):
    # Emergency fields → admin role required
    if body.emergency_reason_code is not None:
        if "reclaimrx.admin" not in (user.get("roles") or []):
            raise HTTPException(403, {"error":{"code":"INSUFFICIENT_ROLE",
                                              "message":"emergency override requires reclaimrx.admin",
                                              "correlation_id": request.headers.get("x-correlation-id")}})
        if body.emergency_reason_code == "OTHER_WITH_NOTE" and not body.emergency_note:
            raise HTTPException(422, {"error":{"code":"EMERGENCY_NOTE_REQUIRED"}})
    try:
        return release_with_outbox(
            db=db, tenant_id=user["tenant_id"], hold_id=hold_id,
            body=body.model_dump(), actor_sub=user["sub"],
            role="admin" if "reclaimrx.admin" in (user.get("roles") or []) else "investigator",
            emergency_reason_code=body.emergency_reason_code,
            emergency_note=body.emergency_note,
        )
    except HoldInvestigationMismatch as e:
        raise HTTPException(403, {"error":{"code":"HOLD_INVESTIGATION_MISMATCH","message":str(e)}})
    except HoldNotActive as e:
        raise HTTPException(422, {"error":{"code":"HOLD_NOT_ACTIVE","field":str(e)}})
    except ReleaseConflict as e:
        raise HTTPException(409, {"error":{"code":"ALREADY_RELEASED", "field": e.prior_release}})

# DEPRECATE existing DELETE /holds/{hold_id} — mark as deprecated in docstring, add Sunset header
# (do NOT delete in same PR — leave for grace period; remove in Plan A.5 or SP-4)
```

- [ ] **Step 4: Run, verify all 4 tests pass**

- [ ] **Step 5: Commit**

```bash
git add modules/reclaimrx/src/api/router.py modules/reclaimrx/src/api/schemas/schemas.py modules/reclaimrx/tests/integration/test_hold_release_endpoint.py
git commit -m "feat(sp3-a): POST /holds/{id}/release endpoint w/ role gate + idempotency + emergency override"
```

---

### Phase 3: Production app factory bindings (T9-T14)

### Task 9: Real DLQ repository — replace `_EmptyDLQRepository` stub

**Files:**
- Create: `modules/reclaimrx/src/services/dlq_repository.py`
- Modify: `modules/reclaimrx/src/main.py:46-58` (replace stub)
- Test: `modules/reclaimrx/tests/unit/test_dlq_repository.py`

Steps mirror prior tasks: test → fail → implement (DB-backed `DLQRepository` using existing `shared.events.dlq` table model; verify path at impl time) → wire into `main.py` → pass → commit.

```bash
git commit -m "feat(sp3-a): real DB-backed DLQ repository replacing _EmptyDLQRepository stub"
```

---

### Task 10: DLQ depth monitoring + 15-min alert

**Files:**
- Create: `modules/reclaimrx/src/services/dlq_depth_monitor.py`
- Test: `modules/reclaimrx/tests/unit/test_dlq_depth_monitor.py`

Per `.claude/rules/event-bus.md` "MUST monitor DLQ depth — alert when > 0 for > 15 minutes".

Implementation: APScheduler job runs every 60s; counts `dlq_entries` with `created_at > now-15min` per tenant; if non-zero, emits structured alert log (`svc=dlq_depth_alert`). Integrated into `create_app()` lifespan.

Commit: `feat(sp3-a): DLQ depth monitor with 15-min alert per event-bus.md`

---

### Task 11: Redis-backed durable idempotency store (replace InMemoryIdempotencyStore)

**Files:**
- Create: `modules/reclaimrx/src/services/redis_idempotency_store.py` (or use existing in shared/events/idempotency if present)
- Modify: `modules/reclaimrx/src/events/__init__.py:29` (replace `InMemoryIdempotencyStore()` with `RedisIdempotencyStore()`)
- Test: `modules/reclaimrx/tests/integration/test_redis_idempotency_store.py`

```python
# Test pattern
def test_idempotency_survives_process_restart(redis_url):
    store1 = RedisIdempotencyStore(redis_url=redis_url, key_prefix=f"tenant:test:reclaimrx:idemp:")
    asyncio.run(store1.mark("key-1", consumer_name="c1"))
    del store1  # simulate restart
    store2 = RedisIdempotencyStore(redis_url=redis_url, key_prefix=f"tenant:test:reclaimrx:idemp:")
    seen = asyncio.run(store2.seen("key-1", consumer_name="c1"))
    assert seen is True
```

Per spec D8: Redis keys MUST be prefixed `tenant:{tenant_id}:reclaimrx:idemp:`.

Commit: `feat(sp3-a): Redis-backed idempotency store (durable across process restart)`

---

### Task 12: processed_events cleanup scheduled job

**Files:**
- Modify: `modules/reclaimrx/src/jobs/scheduled.py` (add `job_cleanup_processed_events`)
- Test: `modules/reclaimrx/tests/integration/test_processed_events_cleanup.py`

Per `.claude/rules/event-bus.md`: `DELETE WHERE processed_at < NOW() - INTERVAL '7 days'`. Daily cron.

```python
def job_cleanup_processed_events(session) -> dict:
    cutoff = datetime.now(UTC) - timedelta(days=7)
    n = session.execute(text("DELETE FROM processed_events WHERE processed_at < :cutoff"),
                        {"cutoff": cutoff}).rowcount
    return {"deleted": n}
```

Add to JOB_SCHEDULE: `"cleanup_processed_events": {"cron":"0 4 * * *"}`.

Commit: `feat(sp3-a): daily processed_events cleanup job`

---

### Task 13: Daily audit hash-chain verification job

**Files:**
- Create: `modules/reclaimrx/src/services/audit_chain_verifier.py`
- Modify: `modules/reclaimrx/src/jobs/scheduled.py` (add `job_verify_audit_chain`)
- Test: `modules/reclaimrx/tests/unit/test_audit_chain_verifier.py`

Per `.claude/rules/hipaa-2026.md`: "MUST compute `entry_hash` on EVERY audit log write — never write with empty hash" + daily verification.

Implementation walks audit table ordered by `created_at`, verifies each entry's `prev_entry_hash` matches the prior entry's `entry_hash`. Returns first-broken entry (if any). Reject-on-write enforced by adding a SQLAlchemy event listener `before_insert` on audit models that raises if `entry_hash` is empty.

JOB_SCHEDULE: `"verify_audit_chain": {"cron":"0 3 * * *"}`.

Commit: `feat(sp3-a): daily audit hash-chain verification + no-empty-hash gate`

---

### Task 14: APScheduler wired into `create_app()` lifespan + outbox dispatcher job

**Files:**
- Create: `modules/reclaimrx/src/jobs/scheduler.py`
- Modify: `modules/reclaimrx/src/main.py` (extend lifespan to start scheduler)
- Test: `modules/reclaimrx/tests/integration/test_app_factory_bindings.py`

```python
# src/jobs/scheduler.py
"""APScheduler bootstrap — wires JOB_SCHEDULE → APScheduler jobs.
Runs in process; tasks call into src.jobs.scheduled.*."""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.jobs.scheduled import (
    JOB_SCHEDULE, job_recalculate_entity_profiles, job_rebuild_fraud_network_graph,
    job_retrain_ml_models, job_check_statute_deadlines, job_check_regulatory_deadlines,
    job_expire_payment_holds, job_calculate_false_positive_rates,
    job_take_entity_profile_snapshots, job_cleanup_processed_events,
    job_verify_audit_chain, job_dispatch_outbox,
)
_FN_MAP = {
    "recalculate_entity_profiles": job_recalculate_entity_profiles,
    "rebuild_fraud_network_graph": job_rebuild_fraud_network_graph,
    # ...add all
}

def start_scheduler() -> AsyncIOScheduler:
    sched = AsyncIOScheduler()
    for job_name, cfg in JOB_SCHEDULE.items():
        fn = _FN_MAP.get(job_name)
        if not fn: continue
        sched.add_job(fn, "cron", **_cron_kwargs(cfg["cron"]), id=job_name)
    # Outbox dispatcher — every 1s
    sched.add_job(job_dispatch_outbox, "interval", seconds=1, id="dispatch_outbox")
    sched.start()
    return sched
```

`main.py` lifespan additions:
```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # ... existing consumer wiring ...
    from .jobs.scheduler import start_scheduler  # noqa: PLC0415
    sched = start_scheduler()
    app.state.scheduler = sched
    try:
        yield
    finally:
        sched.shutdown(wait=False)
```

Integration test asserts `create_app().state.scheduler` exists after startup AND that all 6 D14 bindings are present (SecurityHeaders, RateLimit, DLQ router, processed_events cleanup, DLQ depth monitor, audit verification).

Commit: `feat(sp3-a): APScheduler in create_app() lifespan + outbox dispatcher cron`

---

### Phase 4: Accumulator consumer (T15-T17)

### Task 15: AccumulatorAnomalyDetector — 4 pattern detectors

**Files:**
- Create: `modules/reclaimrx/src/services/accumulator_anomaly_detector.py`
- Test: `modules/reclaimrx/tests/unit/test_accumulator_anomaly_detector.py`

Implements `detect(payload, window=last_7d, db) -> list[dict]` returning detected patterns. Each detector is a pure function checking the payload against historical accumulator events within the window:

- `_detect_sudden_spike`: current period oop > 3× rolling 7-day average for this member+payer
- `_detect_multi_payer_convergence`: ≥3 distinct payers updating the same member's accumulator in a 24h window
- `_detect_reset_evasion`: accumulator resets to zero in a period that should not have reset (e.g., mid-month)
- `_detect_threshold_oscillation`: deductible amount oscillates >2 times in a 30-day period (could indicate retroactive adjustment fraud)

Each returns `{pattern_type, severity, evidence_window_start, evidence_window_end, triggering_event_ids}` or None.

Commit: `feat(sp3-a): accumulator anomaly detector with 4 pattern types`

---

### Task 16: `handle_accumulator_updated` consumer + register in CONSUMER_ROUTING

**Files:**
- Modify: `modules/reclaimrx/src/events/consumers.py` (add handler + add `"accumulator.updated": handle_accumulator_updated` to `CONSUMER_ROUTING` dict)
- Test: `modules/reclaimrx/tests/integration/test_accumulator_consumer_wiring.py`

```python
# src/events/consumers.py — ADD
from src.services.accumulator_anomaly_detector import AccumulatorAnomalyDetector
from src.services.investigation_service import auto_open_investigation
from src.models.tables import AccumulatorDetection, AccumulatorPatternType

async def handle_accumulator_updated(envelope, *, db, bus):
    # Envelope/payload tenant_id mismatch reject (spec §5.3 + R2 NEW CONCERN 3)
    envelope_tid = envelope.tenant_id
    payload_tid = envelope.payload.get("tenant_id")
    if str(envelope_tid) != str(payload_tid):
        logger.warning("reclaimrx.accumulator.tenant_mismatch",
                       extra={"svc_envelope_tid": str(envelope_tid), "svc_payload_tid": str(payload_tid),
                              "correlation_id": envelope.correlation_id})
        # 200 OK behavior — no state change, no retry; investigated via audit + DLQ
        return
    detector = AccumulatorAnomalyDetector(db=db)
    detected = detector.detect(payload=envelope.payload, window_days=7)
    for pattern in detected:
        anomaly = AccumulatorDetection(
            tenant_id=envelope_tid,
            member_id=envelope.payload["member_id"],
            pattern_type=AccumulatorPatternType(pattern["pattern_type"]),
            evidence_window_start=pattern["evidence_window_start"],
            evidence_window_end=pattern["evidence_window_end"],
            triggering_event_ids=pattern["triggering_event_ids"],
            detected_at=datetime.now(UTC),
        )
        db.add(anomaly); db.flush()
        if pattern["severity"] in ("medium","high","critical"):
            inv = auto_open_investigation(db=db, source="accumulator_anomaly",
                                          source_ref_id=anomaly.id, severity=pattern["severity"])
            anomaly.spawned_investigation_id = inv.id

# At bottom of file, EXTEND CONSUMER_ROUTING
CONSUMER_ROUTING["accumulator.updated"] = handle_accumulator_updated
```

Integration test: publish synthetic accumulator.updated envelope → assert AccumulatorDetection row created + Investigation auto-opened for high-severity patterns + tenant mismatch envelope produces audit log + no state change.

Commit: `feat(sp3-a): accumulator.updated consumer wired with tenant mismatch reject`

---

### Task 17: Tenant mismatch behavior + DLQ entry

**Files:**
- Modify: `modules/reclaimrx/src/events/consumers.py:handle_accumulator_updated` (write DLQ entry on mismatch)
- Test: `modules/reclaimrx/tests/integration/test_accumulator_tenant_mismatch.py`

Verify mismatch produces: WARNING log with correlation_id; DLQ entry with reason="ACCUMULATOR_TENANT_MISMATCH"; no AccumulatorDetection row; no Investigation row.

Commit: `feat(sp3-a): accumulator tenant mismatch produces DLQ entry per event-bus.md`

---

### Phase 5: Graph job real implementation (T18-T20)

### Task 18: `graph_analysis_service.run()` — entrypoint with size guardrails

**Files:**
- Modify: `modules/reclaimrx/src/services/graph_analysis.py` (add `run()` function alongside existing graph code)
- Test: `modules/reclaimrx/tests/unit/test_graph_analysis_run.py`

Per spec §7.3 + §9.5: load last 90d claims + entities scoped by tenant_id; check size bounds (max 50K nodes / 200K edges); build NetworkX graph; connected-component + density scoring; insert fraud_rings; auto-open investigations for high-severity; update graph_runs status. Failure path: cleanup partial fraud_rings.

```python
# src/services/graph_analysis.py — ADD
import networkx as nx
import logging
from datetime import UTC, datetime
from decimal import Decimal
from src.models.tables import FraudRing, GraphRun, GraphRunStatus
from src.services.outbox_service import write_outbox_event

logger = logging.getLogger("reclaimrx.graph.run")

MAX_NODES = 50_000
MAX_EDGES = 200_000
DENSITY_THRESHOLD = Decimal("0.40")  # per-tenant override via ThresholdConfig at runtime

def run(*, db, tenant_id, graph_run_id, lookback_days: int = 90) -> dict:
    run_row = db.get(GraphRun, graph_run_id)
    try:
        # 1. Load entities (scoped via RLS or explicit tenant filter)
        nodes, edges = _load_entity_graph(db=db, tenant_id=tenant_id, lookback_days=lookback_days)
        run_row.records_scanned = len(nodes)
        # 2. Size guardrail
        if len(nodes) > MAX_NODES or len(edges) > MAX_EDGES:
            return _run_partial_by_program(db=db, tenant_id=tenant_id, run_row=run_row)
        # 3. Build graph + density scoring
        G = nx.Graph(); G.add_nodes_from(nodes); G.add_edges_from(edges)
        components = list(nx.connected_components(G))
        rings_detected = 0; investigations_opened = 0
        for comp in components:
            density = _component_density(G, comp)
            if density > DENSITY_THRESHOLD:
                ring = FraudRing(tenant_id=tenant_id, graph_run_id=graph_run_id,
                                 density_score=density, node_count=len(comp),
                                 edge_count=G.subgraph(comp).number_of_edges(),
                                 entity_refs=list(comp), detected_at=datetime.now(UTC))
                db.add(ring); db.flush()
                rings_detected += 1
                # Open investigation for high-density
                if density > Decimal("0.70"):
                    inv = _auto_open_graph_investigation(db=db, tenant_id=tenant_id, ring_id=ring.id)
                    ring.spawned_investigation_id = inv.id
                    investigations_opened += 1
        # 4. Mark completed
        run_row.status = GraphRunStatus.COMPLETED
        run_row.completed_at = datetime.now(UTC)
        run_row.rings_detected = rings_detected
        run_row.investigations_opened = investigations_opened
        # 5. Outbox emit
        write_outbox_event(db=db, tenant_id=tenant_id, event_type="fwa.graph_run_completed",
            ordering_key=str(graph_run_id),
            idempotency_key=f"graph_run:{graph_run_id}:completed",
            schema_version="1.0",
            payload={"graph_run_id":str(graph_run_id),"status":"completed",
                     "rings_detected":rings_detected,"investigations_opened":investigations_opened,
                     "records_scanned":run_row.records_scanned,
                     "lookback_window_days":lookback_days,
                     "started_at":run_row.started_at.isoformat(),
                     "completed_at":run_row.completed_at.isoformat(),
                     "failed_at": None, "error_code": None, "error_message": None})
        return {"status":"completed","rings_detected":rings_detected}
    except Exception as exc:
        # Cleanup partial fraud_rings + mark failed
        db.query(FraudRing).filter_by(graph_run_id=graph_run_id).delete()
        run_row.status = GraphRunStatus.FAILED
        run_row.failed_at = datetime.now(UTC)
        run_row.error_code = type(exc).__name__
        run_row.error_message = str(exc)[:500]  # sanitized
        write_outbox_event(db=db, tenant_id=tenant_id, event_type="fwa.graph_run_completed",
            ordering_key=str(graph_run_id),
            idempotency_key=f"graph_run:{graph_run_id}:completed",
            schema_version="1.0",
            payload={"graph_run_id":str(graph_run_id),"status":"failed",
                     "rings_detected":0,"investigations_opened":0,
                     "records_scanned":run_row.records_scanned or 0,
                     "lookback_window_days":lookback_days,
                     "started_at":run_row.started_at.isoformat(),
                     "completed_at": None,
                     "failed_at": run_row.failed_at.isoformat(),
                     "error_code": run_row.error_code,
                     "error_message": run_row.error_message})
        raise
```

Tests: happy path with synthetic graph → fraud_rings + investigation; size-bound exceed → completed_partial; failure → partial cleanup + failed status; outbox event written with correct envelope (incl. tenant_id at envelope level).

Commit: `feat(sp3-a): graph_analysis.run() with size guardrails + outbox emit + failure cleanup`

---

### Task 19: Rewrite `job_rebuild_fraud_network_graph` to call real implementation

**Files:**
- Modify: `modules/reclaimrx/src/jobs/scheduled.py:25` (replace stub)
- Test: `modules/reclaimrx/tests/integration/test_graph_job_per_tenant_fanout.py`

```python
def job_rebuild_fraud_network_graph(session, tenant_id) -> dict:
    """REAL implementation: fan out per tenant; create GraphRun row;
    spawn graph_analysis_service.run() in same DB session."""
    from src.services.graph_analysis import run as graph_run
    from src.models.tables import GraphRun, GraphRunStatus
    from sqlalchemy import text
    import uuid
    from datetime import datetime, timedelta, UTC

    # Concurrency: pg_try_advisory_xact_lock; durable 'running' row as authority
    tid_hash = hash(("graph_run", str(tenant_id))) & 0x7FFFFFFF
    locked = session.execute(text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": tid_hash}).scalar()
    if not locked:
        _logger.info("reclaimrx.graph.lock_busy", extra={"tenant_id": tenant_id})
        return {"status":"skipped","reason":"lock_busy"}
    in_flight = session.execute(text(
        "SELECT 1 FROM graph_run WHERE tenant_id=:tid AND status='running' LIMIT 1"
    ), {"tid": tenant_id}).first()
    if in_flight:
        return {"status":"skipped","reason":"already_running"}
    run = GraphRun(id=uuid.uuid4(), tenant_id=tenant_id, status=GraphRunStatus.RUNNING,
                   trigger="cron", correlation_id=str(uuid.uuid4()),
                   stale_timeout_at=datetime.now(UTC) + timedelta(hours=6))
    session.add(run); session.flush()
    session.commit()  # release advisory lock + persist running row
    # Run analysis in same session (caller owns commit on success)
    return graph_run(db=session, tenant_id=tenant_id, graph_run_id=run.id, lookback_days=90)
```

Commit: `feat(sp3-a): real graph rebuild job with advisory lock + durable running row`

---

### Task 20: Graph run concurrency test (worker crash + stale timeout + re-trigger)

**Files:**
- Create: `modules/reclaimrx/tests/integration/test_graph_run_concurrency.py`

Test scenarios per spec §7.3 + R3 NEW BLOCK 1:
- Two concurrent triggers → second receives 409
- Worker crashes after creating running row → stale sweeper auto-fails after 6h
- After failure, next trigger succeeds (new row, new run)

Commit: `test(sp3-a): graph run concurrency + crash recovery`

---

### Phase 6: New endpoints (T21-T28)

### Task 21: NEW POST /investigations/{id}/transitions

**Files:**
- Modify: `modules/reclaimrx/src/api/router.py` (add new endpoint near existing investigations routes)
- Test: `modules/reclaimrx/tests/integration/test_transition_endpoint.py`

Uses `InvestigationStateMachine` from Task 4 to validate. 422 INVALID_TRANSITION with allowed-next in error.field; 422 REASON_REQUIRED; 403 INSUFFICIENT_ROLE.

Commit: `feat(sp3-a): POST /investigations/{id}/transitions w/ state machine validation`

---

### Task 22: NEW endpoints — GET /ml-scores, GET /ml-scores/{id}/features

**Files:**
- Modify: `router.py` (add 2 endpoints)
- Test: `tests/integration/test_ml_scores_endpoints.py`

Backed by existing `services/ml_scoring.py` + `MlPrediction` model. Features endpoint returns XGBoost feature importance (model name + per-feature gain/weight) — uses `model.feature_importance_` if SKL/XGB model object cached, else returns empty list with warning per spec §8.

Commit: `feat(sp3-a): GET /ml-scores list + GET /ml-scores/{id}/features endpoints`

---

### Task 23: NEW endpoints — POST /graph-runs/trigger, GET /graph-runs, GET /graph-runs/{run_id}

**Files:**
- Modify: `router.py` (add 3 endpoints)
- Test: `tests/integration/test_graph_runs_endpoints.py`

Trigger endpoint: enforces D13 rate-limit 1/hr/tenant; check existing running row → 409; spawn APScheduler oneshot calling `job_rebuild_fraud_network_graph`. Status endpoints are simple reads scoped by tenant_id.

Commit: `feat(sp3-a): graph runs trigger + list + detail endpoints`

---

### Task 24: NEW endpoint — GET /fraud-rings/{id}

**Files:**
- Modify: `router.py` (add 1 endpoint)
- Test: `tests/integration/test_fraud_ring_detail.py`

Returns node/edge graph payload capped at 500 nodes / 2000 edges (binding per R2 ADVISORY 2). If component exceeds, returns neighborhood subgraph with `truncated: true`.

Commit: `feat(sp3-a): GET /fraud-rings/{id} with payload cap`

---

### Task 25: NEW endpoint — GET /recovery (aggregations) + GET /dashboard-summary

**Files:**
- Modify: `router.py` (add 2 endpoints)
- Test: `tests/integration/test_recovery_dashboard_endpoints.py`

Recovery: `?period=mtd|qtd|ytd|all&group_by=program|none`. Decimal sums via `Decimal(str(func.sum()))` per CLAUDE.md invariant. 100% coverage gate.

Dashboard: 6 tile metrics (open investigations count, critical-severity count, hold $ volume, recovered $ MTD, false-positive rate, graph rings detected last 7d). 60s cached.

Commit: `feat(sp3-a): GET /recovery aggregations + GET /dashboard-summary tiles`

---

### Task 26: NEW endpoints — GET /thresholds, PUT /thresholds (admin only)

**Files:**
- Create: `modules/reclaimrx/src/services/threshold_versioning.py`
- Modify: `router.py` (add 2 endpoints)
- Test: `tests/unit/test_threshold_versioning.py` + `tests/integration/test_thresholds_endpoints.py`

PUT inserts new `ThresholdConfigVersion` row (monotonic version per tenant) + per-field hash-chained `ThresholdConfigAudit` rows. Supersedes prior version (sets `superseded_at`). Admin role gate via `require_role("reclaimrx.admin")`. Out-of-range values → 422 THRESHOLD_OUT_OF_RANGE.

Hash chain: `entry_hash = sha256(prev_entry_hash + field + old_value + new_value + changed_at + changed_by)`. Verified by daily audit job (Task 13).

Commit: `feat(sp3-a): GET + PUT /thresholds w/ versioning + per-field audit + hash chain`

---

### Task 27: NEW endpoint alias — GET /accumulator-anomalies (alias of existing /accumulator/detections)

**Files:**
- Modify: `router.py` (add alias route)
- Test: `tests/integration/test_accumulator_anomalies_alias.py`

Commit: `feat(sp3-a): GET /accumulator-anomalies alias for spec naming`

---

### Task 28: Backend require_role() + require_mfa_elevated() — applied across all 18 endpoints

**Files:**
- Create: `modules/reclaimrx/src/services/role_gate.py`
- Create: `modules/reclaimrx/src/services/mfa_gate.py`
- Modify: `modules/reclaimrx/src/api/router.py` (add Depends on every endpoint per spec §5.5 RBAC column)
- Test: `modules/reclaimrx/tests/integration/test_endpoints_role_matrix.py`

```python
# src/services/role_gate.py
from fastapi import Depends, HTTPException
from src.api.dependencies import get_current_user

def require_role(role: str):
    def _check(user=Depends(get_current_user)):
        roles = user.get("roles") or []
        if role not in roles and "reclaimrx.admin" not in roles:
            raise HTTPException(403, {"error":{"code":"INSUFFICIENT_ROLE","field":role}})
        return user
    return _check

# src/services/mfa_gate.py
from fastapi import Depends, HTTPException
import httpx
async def require_mfa_elevated(user=Depends(get_current_user)) -> dict:
    """Check core-platform session.mfa_elevated_until > now() (D6a).
    Path verified at impl time per spec §12.5."""
    from src.config import get_settings
    settings = get_settings()
    async with httpx.AsyncClient() as cli:
        r = await cli.get(f"{settings.CORE_PLATFORM_URL}/internal/session/{user['sub']}/mfa-status",
                          headers={"X-Internal-Token": settings.INTERNAL_SERVICE_TOKEN})
    if r.status_code != 200 or not r.json().get("mfa_elevated_until_active"):
        raise HTTPException(403, {"error":{"code":"MFA_REQUIRED",
                                          "message":"ePHI access requires MFA-elevated session"}})
    return user
```

Integration test matrix: 3 roles × 18 endpoints = 54 cases. Each case asserts correct 200/403 per spec §5.5 RBAC column.

Commit: `feat(sp3-a): backend require_role() + require_mfa_elevated() across all endpoints (R1 BLOCK 1)`

---

### Phase 7: Event contract docs (T29)

### Task 29: Author event contract docs

**Files:**
- Create: `docs/api-contracts/events/payment.hold_released.md`
- Create: `docs/api-contracts/events/fwa.graph_run_completed.md`

Each doc follows the format of existing `docs/api-contracts/events/*.md` (verify pattern at impl time). Must contain envelope spec from spec §11.5 verbatim, payload schema, consumer guidance, forward-compatibility rule, example envelope.

Commit: `docs(sp3-a): event contract docs for payment.hold_released + fwa.graph_run_completed`

---

### Phase 8: SP-0 contract layer (T30-T33)

### Task 30: ReclaimRxClient interface + zod schemas

**Files:**
- Create: `packages/contract/src/clients/reclaimrx.ts`
- Create: `packages/contract/src/schemas/reclaimrx.ts`
- Test: `packages/contract/tests/reclaimrx-schemas.test.ts`

Pattern verified against `packages/contract/src/clients/paysync.ts` (SP-1) and `packages/contract/src/clients/directories.ts` (SP-2). 18 typed methods on `ReclaimRxClient` interface; per-method input/output zod schemas matching backend endpoints.

Commit: `feat(sp3-a): ReclaimRxClient interface + zod schemas for 18 endpoints`

---

### Task 31: RealImpl + MockImpl

**Files:**
- Create: `packages/contract/src/impls/reclaimrx-real.ts`
- Create: `packages/contract/src/impls/reclaimrx-mock.ts`
- Test: `packages/contract/tests/reclaimrx-real-mock-parity.test.ts`

RealImpl: fetch-based client respecting `baseUrl`, `Authorization` header, `x-tenant-id` header. MockImpl: in-memory store seeded from fixtures. Parity test: every method called against both impls returns shapes that pass the SAME zod schema.

Commit: `feat(sp3-a): RealImpl + MockImpl for ReclaimRxClient + parity test`

---

### Task 32: Cache policy

**Files:**
- Create: `packages/contract/src/cache/reclaimrx-policy.ts`
- Test: `packages/contract/tests/reclaimrx-cache-policy.test.ts`

Cache tags per surface; invalidation map (e.g., `transitionInvestigation` invalidates `reclaimrx:investigations:{tid}` + `reclaimrx:dashboard:{tid}`). Pattern verified against SP-2 `packages/contract/src/cache/directories-policy.ts`.

Commit: `feat(sp3-a): cache policy for reclaimrx surfaces`

---

### Phase 9: Frontend module scaffold (T33)

### Task 33: packages/modules/reclaimrx scaffold + empty-state pages

**Files:**
- Create: `packages/modules/reclaimrx/package.json` (mirror `packages/modules/directories/package.json`)
- Create: `packages/modules/reclaimrx/tsconfig.json`
- Create: `packages/modules/reclaimrx/vitest.config.ts`
- Create: `packages/modules/reclaimrx/module.config.ts`
- Create: `packages/modules/reclaimrx/src/components/EmptyState.tsx`
- Create: `packages/modules/reclaimrx/src/rbac/RoleGate.tsx`
- Create: 6 empty-state route pages: `src/investigations/page-empty-state.tsx`, `src/rules/...`, `src/ml/...`, `src/holds/...`, `src/recovery/...`, `src/graph/...`
- Test: `tests/unit/EmptyState.test.tsx`, `RoleGate.test.tsx`, `module.config.test.ts`
- Modify: `infrastructure/manifests/operator-dev.yml` (add `reclaimrx` to module list)
- Modify: `packages/shell/src/_generated/manifest.json` (regenerated by composition script)

```typescript
// src/components/EmptyState.tsx
export function EmptyState({ title, cta }: { title: string; cta: string }) {
  return <div data-testid="empty-state"><h2>{title}</h2><p>{cta}</p></div>;
}

// src/rbac/RoleGate.tsx — UX-layer enforcement (D5 layer 3)
import type { ReactNode } from "react";
export function RoleGate({ require, userRoles, children }: {
  require: string; userRoles: string[]; children: ReactNode;
}) {
  if (!userRoles.includes(require) && !userRoles.includes("reclaimrx.admin")) return null;
  return <>{children}</>;
}

// module.config.ts (mirror directories pattern)
export default {
  id: "reclaimrx",
  routes: [
    "/reclaimrx",
    "/reclaimrx/investigations",
    "/reclaimrx/investigations/[id]",
    "/reclaimrx/rules",
    "/reclaimrx/ml",
    "/reclaimrx/holds",
    "/reclaimrx/recovery",
    "/reclaimrx/graph",
  ],
  navEntry: { label: "ReclaimRx", icon: "ShieldAlert", order: 4 },
  shellSurfaces: {
    commandPaletteScopes: ["reclaimrx-investigations"],
    cacheTagPrefixes: ["reclaimrx"],
    routePrefixes: ["/reclaimrx"],
    cacheKeyNamespaces: ["rclm"],
    redisKeyPrefixes: ["rclm:"],
  },
  requires: {
    backends: ["reclaimrx","core-platform"],
    sharedServices: ["redis","postgres","rabbitmq"],
    schemas: ["reclaimrx","shared","audit"],
    env: ["RECLAIMRX_URL","CORE_PLATFORM_URL"],
    health: ["reclaimrx"],
    seedData: ["reclaimrx/fixtures"],
    queues: [],
    jobs: ["graph_run_trigger"],
    buckets: [],
    integrations: ["sp2-federated-search"],
    secrets: [],
  },
  surfaceKinds: ["server","client"],
} as const;
```

Commit: `feat(sp3-a): frontend module scaffold + 6 empty-state pages + module.config`

---

## Self-review checklist (run after Plan A draft is committed)

- [ ] Spec coverage: each spec D1-D14 has at least one task implementing it (D1-D4 are decisions, D5/D6/D6a/D7/D8/D9/D10/D11/D12/D13/D14 have tasks)
- [ ] No "TBD / TODO" in steps
- [ ] All file paths verified against audit (Task 0 inventory)
- [ ] State machine transitions in Task 4 match spec §5.5.1 exactly
- [ ] Event envelope shape in Tasks 5/7/18 matches spec §11.5 exactly (incl. envelope-level tenant_id)
- [ ] RLS expression in Task 2 matches spec D8 (null-deny via `current_setting('app.tenant_id', true)`)
- [ ] Coverage gates: 100% on financial + PHI + security + auth/role; 95% baseline elsewhere
- [ ] Production app factory (Task 14) integration test asserts all 6 D14 bindings
- [ ] No invented paths (per R1 CONCERN 10) — all `from X import Y` references verified at audit
- [ ] Page-render tests for empty-state pages (avoid dead-code scanner per R1 BLOCK 9)

---

## Cross-references

- Spec: `docs/superpowers/specs/2026-05-18-sp3-reclaimrx-portal-design.md`
- Audit: `waves/B10/SP-3-design-draft.md` §"Locked-from-audit decisions"
- Codex spec reviews: r1-r5
- Wave control ledger: `waves/B10/SP-3-charter.md` (will be written when codex consults this plan)

---

**Next:** Codex Plan A consult → user gate → Plans B, C, D, E.
