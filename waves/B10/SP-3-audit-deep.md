# SP-3 Deep Audit — ReclaimRx Backend

**Date:** 2026-05-18  
**Auditor:** Sub-agent (deep-read session)  
**Scope:** All 10 sections mandated by orchestrator dispatch  
**Source spec:** `docs/superpowers/specs/2026-05-18-sp3-reclaimrx-portal-design.md`  
**Note:** `docs/superpowers/codex-sp3-plan-a-review-r1.md` does NOT exist. The codex reviews for the spec are at `docs/superpowers/codex-sp3-spec-review-r1.md` through `r5.md`. The failed Plan A draft (`docs/superpowers/plans/2026-05-18-sp3-plan-a-backend-contract-scaffold.md`) also does NOT exist — only the spec + spec-review files are present. All block citations in this audit refer to `codex-sp3-spec-review-r1.md` which lists the 9 BLOCKS on the original draft spec.

---

## Section 1: tables.py — Full Class Inventory

**File:** `modules/reclaimrx/src/models/tables.py`  
**Line count:** ~796 lines  
**Base class:** `src._shim.db.Base` (module-local shim, NOT `shared.db.models.base.Base`)  
**No mixins used.** No `TenantScopedMixin`, no `PHIMixin` from shared. All tenant scoping is manual `String(36)` columns with manual WHERE clauses.

### All Classes

#### DetectionRule (`reclaimrx_detection_rules`) — lines 48–76
| Column | SA Type | Nullable | Default |
|---|---|---|---|
| id | String(36) | No | `_uuid_str()` |
| tenant_id | String(36) | **Yes** | — |
| rule_code | String(50) | No | — |
| name | String(255) | No | — |
| description | Text | No | — |
| category | String(100) | No | — |
| client_types | JSON | No | `["all"]` |
| detection_mode | String(50) | No | — |
| rule_type | String(50) | No | — |
| rule_logic | JSON | No | — |
| default_parameters | JSON | No | — |
| default_action | String(50) | No | — |
| confidence_scoring | JSON | Yes | — |
| is_system | Boolean | No | False |
| is_active | Boolean | No | True |
| version | Integer | No | 1 |
| created_at | DateTime(tz) | No | `_now()` |
| updated_at | DateTime(tz) | No | `_now()` |

Relationships: `tenant_configs → list[TenantRuleConfig]` (cascade all, delete-orphan)  
FLAG: `tenant_id` is nullable here — system rules have no tenant, but this means tenant scoping queries must handle NULL. No `TenantScopedMixin`.

#### TenantRuleConfig (`reclaimrx_tenant_rule_configs`) — lines 79–96
Unique: `(tenant_id, detection_rule_id)`. FK to `reclaimrx_detection_rules.id`.

#### DetectionProfile (`reclaimrx_detection_profiles`) — lines 99–109
No tenant_id column. System-global profiles only.

#### FlaggedClaim (`reclaimrx_flagged_claims`) — lines 116–179
Indexes: `(tenant_id, investigation_status)`, `(tenant_id, pharmacy_npi)`, `(tenant_id, prescriber_npi)`, `(tenant_id, member_id)`, `(tenant_id, rule_code)`, `(tenant_id, severity)`.  
FK: `detection_rule_id → reclaimrx_detection_rules.id` (nullable), `investigation_id → reclaimrx_investigations.id` (nullable).  
Money columns: `billed_amount`, `paid_amount`, `expected_amount`, `variance_amount` all `Numeric(12,2)` — correct.  
SP-3 note: This is the existing "flagged claim" model. The spec uses separate `Investigation` model.

#### PharmacyProfile (`reclaimrx_pharmacy_profiles`) — lines 187–230
Unique: `(tenant_id, pharmacy_npi)`.

#### PrescriberProfile (`reclaimrx_prescriber_profiles`) — lines 233–260
Unique: `(tenant_id, prescriber_npi)`.

#### MemberProfile (`reclaimrx_member_profiles`) — lines 263–288
Unique: `(tenant_id, member_id)`.

#### ProfileSnapshot (`reclaimrx_profile_snapshots`) — lines 291–301
Unique: `(tenant_id, entity_type, entity_id, snapshot_date)`.

#### MlModel (`reclaimrx_ml_models`) — lines 309–342
Relationships: `predictions → list[MlPrediction]`

#### MlPrediction (`reclaimrx_ml_predictions`) — lines 345–365
FK: `model_id → reclaimrx_ml_models.id`.  
Has `feature_importance: JSON` column at line 358 — this IS the XGBoost feature importance storage. No separate table.

#### Investigation (`reclaimrx_investigations`) — lines 373–426
| Selected columns | SA Type | Notes |
|---|---|---|
| id | String(36) | PK |
| tenant_id | String(36) | Not null, indexed |
| investigation_number | String(50) | Not null |
| title | String(500) | Not null |
| subject_type | String(50) | Not null |
| subject_entity_id | String(100) | Not null |
| subject_name | String(255) | Nullable |
| status | String(50) | Default "open" |
| priority | String(20) | Default "medium" |
| total_flagged_amount | Numeric(15,2) | Default 0 |
| actual_recovered | Numeric(15,2) | Default 0 |
| opened_at | DateTime(tz) | Default `_now()` |

**SP-3 GAPS in Investigation:** Missing the following spec-required columns:
- `severity` (spec: `low/medium/high/critical`) — ABSENT
- `source` (spec: `rule_firing/ml_score/graph_ring/accumulator_anomaly/manual`) — ABSENT
- `source_ref_id` (UUID FK) — ABSENT
- `member_id` (UUID FK, NOT PHI per D6) — ABSENT
- `opened_by` (`system` | UserSub) — ABSENT
- `closed_at` / `closed_by` — ABSENT (only `resolved_at`)
- `outcome_label` (confirmed/false_positive/no_action) — ABSENT (only `resolution_type`)
- `recovered_amount` / `hold_amount` as separate Decimal columns — ABSENT (exists as `actual_recovered` but different semantics)
- `threshold_config_version` (FK to ThresholdConfig) — ABSENT (ThresholdConfig table does not exist)
- `threshold_snapshot` (JSONB) — ABSENT
- `notes` (AuditedNote[]) — ABSENT (activities exist but aren't append-only notes)
- `status_transitions` (AuditedTransition[]) — ABSENT

The existing `Investigation` model uses a different status vocabulary and different field names. Plan A must either extend this model or replace it. The spec's 7-state machine (`open/in_progress/pending_review/closed_confirmed/closed_false_positive/closed_no_action/escalated`) is NOT in the existing model.

Relationships: `activities → list[InvestigationActivity]` (cascade), `recoveries → list[Recovery]` (cascade)

#### InvestigationActivity (`reclaimrx_investigation_activities`) — lines 429–443
FK: `investigation_id → reclaimrx_investigations.id`.

#### Recovery (`reclaimrx_recoveries`) — lines 446–468
FK: `investigation_id → reclaimrx_investigations.id`.  
Money: `amount: Numeric(15,2)` — correct.

#### LetterTemplate (`reclaimrx_letter_templates`) — lines 471–482
tenant_id nullable.

#### AccumulatorDetection (`reclaimrx_accumulator_detections`) — lines 490–515
SP-3 note: This is a DIFFERENT model from the spec's `AccumulatorAnomaly`. The existing model tracks copay assistance accumulator detection (plan type detection). The spec's `AccumulatorAnomaly` requires:
- `pattern_type` enum (sudden_spike/multi_payer_convergence/reset_evasion/threshold_oscillation) — ABSENT
- `evidence_window_start/end` — ABSENT
- `triggering_event_ids` (UUID[]) — ABSENT
- `spawned_investigation_id` — ABSENT

The spec's `AccumulatorAnomaly` is a NEW table even though `AccumulatorDetection` exists.

#### VerificationConfig / VerificationResult — lines 522–559
Standard; not SP-3 targets.

#### ReportConfig (`reclaimrx_report_configs`) — lines 567–580

#### PaymentHold (`reclaimrx_payment_holds`) — lines 587–613
| Column | SA Type | Nullable | Notes |
|---|---|---|---|
| id | String(36) | No | PK |
| tenant_id | String(36) | No | indexed |
| entity_type | String(50) | No | |
| entity_id | String(100) | No | indexed |
| entity_name | String(255) | Yes | |
| investigation_id | String(36) → FK investigations.id | Yes | |
| hold_scope | String(50) | No | Default "all" |
| rule_filter | JSON | Yes | |
| amount_threshold | Numeric(12,2) | Yes | |
| placed_by | String(36) | No | |
| placed_at | DateTime(tz) | No | Default `_now()` |
| expires_at | DateTime(tz) | Yes | |
| **released_by** | String(36) | **Yes** | **ALREADY EXISTS** — codex BLOCK 1 cited this at line 607 |
| **released_at** | DateTime(tz) | **Yes** | **ALREADY EXISTS** — line 608 |
| **release_reason** | Text | **Yes** | **ALREADY EXISTS** — line 609 |
| **is_active** | Boolean | No | Default True |
| created_at | DateTime(tz) | No | |

**CRITICAL: Codex cited BLOCK 1 as "PaymentHold.released_by at tables.py:607 already exists." This is CONFIRMED. `released_by`, `released_at`, and `release_reason` are already present.** No `__table_args__` on PaymentHold — NO UniqueConstraint, no composite index on `(tenant_id, id)`.

**SP-3 GAPS in PaymentHold:**
- NO `status` column. Model uses boolean `is_active` instead. Spec requires `status` with values `active/released/expired/cancelled`. The idempotency logic in spec §7.2 checks `status == 'released'` — this logic doesn't exist (model uses `is_active=False`).
- NO `idempotency_key` unique constraint on the hold itself.
- No composite index on `(tenant_id, is_active)` — only `entity_id` indexed.

#### TipRecord, RegulatoryReport, StateAuditRule, StatuteOfLimitations, NetworkRiskRegistry, WatchlistEntry, CorrectiveActionPlan, CorrectiveActionItem — lines 621–795
Standard; not SP-3 primary targets.

### Tables the spec calls NEW (Plan A) that DO NOT EXIST yet

| Spec Table | Status |
|---|---|
| FraudRing | ABSENT — no `reclaimrx_fraud_rings` table |
| GraphRun | ABSENT — no `reclaimrx_graph_runs` table |
| AccumulatorAnomaly | ABSENT (≠ AccumulatorDetection) |
| ThresholdConfig | ABSENT |
| ThresholdConfigAudit | ABSENT |
| OutboxEvent | ABSENT |

### Tables that exist but need extension

| Existing Table | Required additions |
|---|---|
| Investigation | severity, source, source_ref_id, member_id, opened_by, closed_at, closed_by, outcome_label, threshold_config_version, threshold_snapshot, notes, status_transitions |
| PaymentHold | status (replace is_active bool), idempotency_key |

---

## Section 2: shared/events/types.py — EventEnvelope

**File:** `shared/events/types.py` (103 lines, read in full)

### EventEnvelope (Pydantic BaseModel, frozen=True)

| Field | Type | Default | Notes |
|---|---|---|---|
| event_type | str | required | |
| tenant_id | uuid.UUID | required | |
| correlation_id | uuid.UUID | required | |
| source_module | str | required | |
| payload | dict[str, Any] | `{}` | |
| timestamp | datetime | `_utc_now()` | |
| event_id | uuid.UUID | `_new_uuid()` | |
| schema_version | str | `"1.0"` | |
| idempotency_key | str | `""` then `str(event_id)` in `model_post_init` | |
| ordering_key | str | None | |

**Key findings:**
1. The field name is `event_type` (NOT `type`). Plan A must use `event_type=`.
2. The field `timestamp` is used (NOT `emitted_at`). Plan A must use `timestamp=`.
3. Both `to_wire()` and `from_wire()` exist for transport serialization.
4. `from_wire()` is forward-compatible (ignores unknown keys).
5. `model_config = ConfigDict(frozen=True)` — instances are immutable.

### Correct construction example

```python
from shared.events.types import EventEnvelope
import uuid

envelope = EventEnvelope(
    event_type="payment.hold_released",
    tenant_id=uuid.UUID("..."),            # NOT str
    correlation_id=uuid.uuid4(),
    source_module="reclaimrx",
    schema_version="1.0",
    ordering_key=str(hold_id),
    idempotency_key=f"hold:release:{hold_id}",
    payload={
        "hold_id": str(hold_id),
        "amount": str(decimal_amount),     # Decimal as str
        "released_by": jwt_sub,
        "reason": reason,
        "investigation_id": str(investigation_id),
        "released_at": datetime.now(UTC).isoformat(),
    },
)
```

**What Plan A must NOT do (from codex block):** `EventEnvelope(type=..., emitted_at=...)` — these field names do not exist. The correct fields are `event_type` and `timestamp` (auto-set).

---

## Section 3: modules/reclaimrx/src/_shim/auth.py — CurrentUser

**File:** `modules/reclaimrx/src/_shim/auth.py` (46 lines, read in full)

### CurrentUser dataclass

```python
@dataclass
class CurrentUser:
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str = "dev@example.com"
    roles: list[str] = field(default_factory=lambda: ["tenant_admin"])

    def has_role(self, role: str) -> bool:
        return role in self.roles
```

**It IS a dataclass** — codex's concern is confirmed correct. `user.get("roles")` would be a dict call and would raise `AttributeError`. Correct access is `user.roles` (list) or `user.has_role("reclaimrx.investigator")`.

### Injection mechanism

`current_user()` function returns the global `_override: CurrentUser | None`. It's a global override pattern (test shim), NOT a real FastAPI Depends on JWT. Production would replace with `shared.auth.*`.

### require_role usage

```python
def require_role(*roles: str):
    def _dep() -> CurrentUser:
        user = current_user()
        if not any(user.has_role(r) for r in roles):
            raise HTTPException(status_code=403, ...)
        return user
    return _dep
```

### Route signature example

```python
@router.delete("/holds/{hold_id}", response_model=PaymentHoldRead)
def release_hold(
    hold_id: str,
    reason: str = Query(default="Released"),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_investigator),   # router.py:480
) -> PaymentHold:
```

**dependencies.py** uses `require_investigator()` which wraps `require_role("investigator", "tenant_admin", "super_admin")()`. Note: the current role names (`investigator`, `tenant_admin`) differ from the spec's 3-role model (`reclaimrx.viewer`, `reclaimrx.investigator`, `reclaimrx.admin`). Plan A must align the role names.

---

## Section 4: modules/reclaimrx/src/api/router.py — Route Inventory

**File:** `modules/reclaimrx/src/api/router.py` (635 lines, read in full)  
**Router prefix:** `/api/v1/reclaimrx` (line 54)

### Existing routes

| Method | Path | Auth Dep | Notes |
|---|---|---|---|
| POST | /evaluate | `get_current_user` | Real-time claim evaluation |
| GET | /rules | `get_current_user` | List active detection rules |
| GET | /rules/{rule_id} | `get_current_user` | Get single rule |
| GET | /flags | `get_current_user` | List flagged claims, paginated |
| GET | /flags/{flag_id} | `get_current_user` | Get single flag |
| PUT | /flags/{flag_id} | `require_investigator` | Update flag status |
| GET | /investigations | `get_current_user` | List investigations |
| POST | /investigations | `require_investigator` | Create investigation |
| GET | /investigations/{investigation_id} | `get_current_user` | Get investigation |
| PUT | /investigations/{investigation_id} | `require_investigator` | Update investigation |
| GET | /investigations/{investigation_id}/timeline | `get_current_user` | Get timeline |
| POST | /investigations/{investigation_id}/activity | `require_investigator` | Add activity |
| GET | /recoveries | `get_current_user` | List recoveries |
| POST | /recoveries | `require_investigator` | Create recovery |
| POST | /holds | `require_investigator` | Create hold |
| GET | /holds | `get_current_user` | List active holds |
| DELETE | /holds/{hold_id} | `require_investigator` | Release hold (uses reason as Query param) |
| GET | /pharmacy-profiles | `get_current_user` | |
| GET | /pharmacy-profiles/{npi} | `get_current_user` | |
| GET | /prescriber-profiles | `get_current_user` | |
| GET | /member-profiles | `get_current_user` | |
| GET | /accumulator/detections | `get_current_user` | |
| POST | /tips | `get_current_user` | |
| GET | /tips | `require_investigator` | |

**Total existing routes: 24**

### SP-3 spec endpoints (#1-18) that DO NOT EXIST

| # | Spec path | Missing? |
|---|---|---|
| 1 | GET /investigations (paginated with filters: status, severity) | Partial — exists but missing severity filter |
| 2 | GET /investigations/{id} (with PHI audit, MFA gate, masking) | Partial — exists but no PHI/MFA logic |
| 3 | POST /investigations/{id}/transitions | **MISSING** |
| 4 | POST /investigations/{id}/notes | **MISSING** (POST /activity exists but different shape) |
| 5 | GET /rule-firings | **MISSING** |
| 6 | GET /ml-scores | **MISSING** |
| 7 | GET /ml-scores/{id}/features | **MISSING** |
| 8 | GET /holds | Exists at /holds but not filtered by status |
| 9 | POST /holds/{hold_id}/release | Exists as DELETE /holds/{hold_id} — wrong method + shape |
| 10 | POST /graph-runs/trigger | **MISSING** |
| 11 | GET /graph-runs | **MISSING** |
| 12 | GET /graph-runs/{run_id} | **MISSING** |
| 13 | GET /fraud-rings/{id} | **MISSING** |
| 14 | GET /recovery | **MISSING** (GET /recoveries exists but different shape) |
| 15 | GET /dashboard-summary | **MISSING** |
| 16 | GET /thresholds | **MISSING** |
| 17 | PUT /thresholds | **MISSING** |
| 18 | GET /accumulator-anomalies | Partial — GET /accumulator/detections exists but different model |

**Count of genuinely missing new routes: 13 clean gaps + 5 partial-mismatches needing replacement**

### Issues with existing hold release route

Current: `DELETE /holds/{hold_id}` with `reason` as Query param (line 476). Spec requires `POST /holds/{hold_id}/release` with body `{reason, investigation_id, emergency_reason_code?, emergency_note?}`. The current route does NOT validate `investigation_id` match (spec requirement: 403 HOLD_INVESTIGATION_MISMATCH). The current route does NOT implement the 3-case idempotency logic.

### Role name mismatch

Current `require_investigator` uses roles: `["investigator", "tenant_admin", "super_admin"]`.  
Spec requires: `reclaimrx.viewer`, `reclaimrx.investigator`, `reclaimrx.admin`.  
These are different string values. Plan A must update role names throughout.

---

## Section 5: packages/contract/src/ — Real Layout

**Full recursive file tree** (from `find` on packages/contract/src):

```
packages/contract/src/
  cache-policy.ts
  client-base.ts
  error-envelope.ts
  index.ts
  __tests__/
    cache-policy.test.ts
    error-envelope.test.ts
    framework-agnostic.test.ts
    prescriber-directory.test.ts
  impls/
    prescriber-directory/
      client.ts      ← typed PrescriberDirectoryClient interface + cache policies
      mock.ts        ← MockImpl
      real.ts        ← RealImpl (createRealPrescriberDirectoryClient factory)
      types.ts       ← Zod schemas + TypeScript types
```

**CRITICAL: The actual layout is `src/impls/<domain>/` with 4 files per domain (client.ts, mock.ts, real.ts, types.ts), NOT the spec's assumed `src/clients/ + src/schemas/ + src/impls/ + src/cache/` split.**

The spec (Plan A scope, R3 NEW BLOCK 2) says to add:
- `packages/contract/src/clients/reclaimrx.ts`
- `packages/contract/src/schemas/reclaimrx.ts`
- `packages/contract/src/impls/reclaimrx-real.ts` + `reclaimrx-mock.ts`
- `packages/contract/src/cache/reclaimrx-policy.ts`

**The real pattern has NO `clients/` or `schemas/` or `cache/` subdirectories.** The prescriber-directory impl puts ALL of these in `impls/prescriber-directory/`:
- Interface + cache policies → `client.ts`
- Types/Zod schemas → `types.ts`
- RealImpl factory → `real.ts`
- MockImpl → `mock.ts`

**Plan A1 must create: `packages/contract/src/impls/reclaimrx/client.ts`, `types.ts`, `real.ts`, `mock.ts`**  
NOT the 4 separate subdirectory split the failed plan assumed.

### client-base.ts interface

`BaseClient` requires:
- `name: string` — stable identifier
- `cachePolicies: Record<string, CachePolicy>`
- `probeHealth(): Promise<{ok: boolean; latency_ms: number; error?: string}>`

Reclaimrx impl will satisfy all three.

---

## Section 6: shared/events/dlq.py + shared/events/idempotency.py

### DLQService (shared/events/dlq.py, 215 lines)

**Public classes and methods:**

`DLQRepository` (Protocol):
- `list(tenant_id, event_type, status, limit)` → `list[EventDLQEntry]`
- `get(entry_id)` → `EventDLQEntry | None`
- `save(entry)` → None

`DLQService`:
- `__init__(repository: DLQRepository)`
- `list(tenant_id, event_type, status, limit)` → `list[EventDLQEntry]`
- `replay(entry_id, bus)` → None (re-publishes envelope, marks `replayed`)
- `drop(entry_id, reason)` → None (marks `dropped`)

`build_dlq_router(get_service, get_permissions, bus)` → `APIRouter`
- Mounts at `/api/v1/events/dlq`
- GET `` (list), POST `/{entry_id}/replay`, POST `/{entry_id}/drop`
- Checks `events:dlq:read` + `events:dlq:replay` permissions

**DLQ is already wired in `modules/reclaimrx/src/main.py`** at lines 97–102 via `build_dlq_router`. DLQ router is mounted. However it uses `_EmptyDLQRepository` — an in-memory stub that returns empty lists. There is NO real DB-backed DLQ repository for reclaimrx.

**Usage example:**
```python
# In create_app():
app.include_router(
    build_dlq_router(
        get_service=_get_dlq_service,    # async dep returning DLQService
        get_permissions=_get_dlq_permissions,  # async dep returning set[str]
    )
)
```

### IdempotencyStore (shared/events/idempotency.py, 195 lines)

`IdempotencyStore` (Protocol):
- `seen(key, consumer_name)` → bool
- `mark(key, consumer_name, ttl_seconds)` → None

`InMemoryIdempotencyStore` — test double with TTL, thread-safe dict

`PostgresIdempotencyStore(engine: AsyncEngine)`:
- `ensure_table()` — creates `core.processed_events` table
- `seen(key, consumer_name)` → bool (SELECT 1 ... LIMIT 1)
- `mark(key, consumer_name, ttl_seconds)` — INSERT ON CONFLICT DO NOTHING
- `purge_expired(older_than_seconds=604800)` → int (rows deleted)

`idempotent_handler(store, consumer_name, ttl_seconds)` — decorator factory:
- First arg to wrapped function = idempotency key
- Checks `store.seen(key)` → skips on True
- Calls inner handler → on success calls `store.mark(key)`
- On exception: key NOT marked (allows retry)

**Usage example:**
```python
store = PostgresIdempotencyStore(engine)
handler = idempotent_handler(store, consumer_name="reclaimrx.accumulator", ttl_seconds=86400)(
    handle_accumulator_updated
)
# handler signature: async def handler(idempotency_key: str, *args, **kwargs)
```

**`processed_events` cleanup job:** EXISTS at `shared/events/jobs/cleanup_processed_events.py`. Provides `purge_processed_events(engine, retention_days=7)` and `run_cleanup(engine, retention_days=7)`. This IS the function to schedule. It is NOT yet scheduled in reclaimrx's `create_app()`.

---

## Section 7: shared/scheduling/ — Scheduling Primitive Availability

**`shared/scheduling/` directory does NOT exist.** Confirmed via `find` command returning DIRECTORY_NOT_FOUND.

**What DOES exist:**

1. `shared/data_ingestion/scheduler.py` — `IngestionScheduler` class. Uses `asyncio.create_task` + `croniter` for scheduling. Custom asyncio loop-based scheduler, NOT APScheduler. Features: `register(source, factory, cron)`, `start()` (blocking coroutine), `stop()`. Durable state via `IngestionSchedule` ORM rows. In-flight detection via `IngestionRun` rows.

2. `shared/events/jobs/cleanup_processed_events.py` — standalone async function, not a scheduler.

3. `modules/billing/src/jobs/scheduled.py` — comment says "APScheduler, Celery Beat, or Azure Functions" but this is just a comment; no actual APScheduler import.

4. `docs/audit/h-07-audit-chain-job-discovery.md` line 55 explicitly states: **"Custom DB-backed cron scheduler (no APScheduler, no Celery Beat)."**

**Conclusion:** APScheduler is NOT installed and NOT used anywhere. The scheduling primitive is `shared/data_ingestion/scheduler.py`'s `IngestionScheduler` pattern using `asyncio.create_task + croniter`. Plan A MUST:
- Adapt `IngestionScheduler` pattern (or create a parallel `IngestionScheduler`-style class for reclaimrx) rather than importing APScheduler
- Use `croniter` (already in `pyproject.toml` at line 20 as `"croniter>=5.0"`)
- OR use simpler `asyncio.create_task` oneshots for on-demand graph runs

The spec says "APScheduler in-process (verify `shared/scheduling/` path at plan-write per R1 ADVISORY 5)." Both the path and APScheduler are absent. This is a CONFIRMED gap the plan-writer must resolve before writing Plan A.

---

## Section 8: D14 Binding Check — modules/reclaimrx/src/main.py

**File:** `modules/reclaimrx/src/main.py` (149 lines, read in full)

### The 6 required bindings per D14

| Binding | Status | Evidence |
|---|---|---|
| SecurityHeadersMiddleware | **MOUNTED** | Line 94: `app.add_middleware(SecurityHeadersMiddleware)` |
| RateLimitMiddleware | **MOUNTED** | Line 93: `app.add_middleware(RateLimitMiddleware, config=RateLimitConfig())` |
| DLQ router | **MOUNTED** | Lines 97–102: `build_dlq_router(...)` included |
| processed_events cleanup scheduler | **MISSING** | Not in lifespan or create_app. `_EmptyDLQRepository` only |
| DLQ depth monitoring + alerting | **MISSING** | `_EmptyDLQRepository` returns empty lists; no depth check, no alerting |
| Daily audit hash-chain verification job (03:00 UTC) | **MISSING** | Not scheduled anywhere in reclaimrx |

**Score: 3/6 mounted, 3/6 missing.**

### Additional gaps in main.py

- `lifespan` uses `wire_consumers(bus)` — good, the 8 consumers fire.
- `_EmptyDLQRepository` is a stub returning `[]` — DLQ replay/drop are no-ops. This is LESSON-006 violation: the DLQ router is mounted but the backing repo is non-functional.
- `RateLimitConfig()` is instantiated with no per-endpoint configuration — it's a default config. Plan A spec requires per-endpoint overrides (1/hr/tenant for graph-run trigger, 10/hr/tenant for thresholds, etc.).

---

## Section 9: Advisory-Lock Determinism

The spec requires `pg_try_advisory_xact_lock(hash('graph_run', tenant_id))` where `hash()` is noted as PYTHONHASHSEED-randomized in the codex review. What deterministic alternatives exist in shared?

**Search results for deterministic int hash primitives:**
- `hashlib.sha256` — used in `shared/auth/mfa/backup_codes.py:72` and `shared/events/rabbitmq_bus.py:63`
- `hashlib.sha256` in `rabbitmq_bus.py` line 63: `digest = hashlib.sha256(ordering_key.encode()).hexdigest()` — used for queue routing
- `zlib.crc32` — NOT found in codebase
- `fnv` / `xxhash` — NOT found
- `struct.pack` — NOT found for hash purposes
- `int.from_bytes` — NOT found for hash purposes

**Available deterministic int-hash approaches for `pg_try_advisory_xact_lock`:**

1. **`zlib.crc32`** (Python stdlib, always deterministic, returns int): `import zlib; lock_key = zlib.crc32(f"graph_run:{tenant_id}".encode())` → produces `int` usable directly. This is the simplest approach.

2. **`hashlib.md5` + `int.from_bytes`**: `import hashlib; int.from_bytes(hashlib.md5(f"graph_run:{tenant_id}".encode()).digest()[:8], "big")` — truncate to 64-bit signed int for PostgreSQL bigint compatibility.

3. **`hashlib.sha256` + `int.from_bytes`**: Same as md5 but SHA-256. Already in codebase.

**Recommendation for Plan A:** Use `zlib.crc32(f"graph_run:{tenant_id}".encode()) & 0x7FFFFFFF` — gives a stable 31-bit positive integer, always within PostgreSQL's bigint range, no external deps, always the same output regardless of PYTHONHASHSEED.

**Do NOT use `hash(...)` — Python's built-in `hash()` is PYTHONHASHSEED-randomized per process start. Two different FastAPI workers will compute different lock keys for the same tenant, defeating the advisory lock.**

---

## Section 10: Idempotency Case Coverage — PaymentHold

### Current PaymentHold model state (tables.py:587–613)

The model uses a **boolean `is_active`** flag, NOT a `status` string column. Fields:
- `is_active: Boolean, default=True`
- `released_by: String(36), nullable`
- `released_at: DateTime(tz), nullable`
- `release_reason: Text, nullable`

There is NO `status` column with `active/released/expired/cancelled` string values. The spec's idempotency logic in §7.2 checks `status == 'released'` — this concept doesn't map to the current model.

### Current uniqueness constraints on PaymentHold

Looking at `tables.py` PaymentHold class definition (lines 587–613): there are NO `__table_args__` defined. There is NO `UniqueConstraint` on this table. There is NO `idempotency_key` column. The only index is the implicit `index=True` on `entity_id` (line 594).

### Current PaymentHoldService.release_hold (payment_hold_service.py:73–100)

The current implementation:
1. Fetches any hold by `(tenant_id, hold_id)` — NOT filtered by `is_active=True`
2. Sets `is_active = False`, `released_by`, `released_at`, `release_reason`
3. Publishes `fwa.payment_hold_released` via `_shim.events.publish` (fire-and-forget, no outbox)

### Spec §7.2 three idempotency cases vs. current implementation

| Case | Spec behavior | Current behavior |
|---|---|---|
| Same actor + same reason + same investigation_id, already released | 200 OK with prior release info | NOT IMPLEMENTED — `_get_active_or_raise` doesn't filter by is_active, so it would find the hold and try to double-release |
| Already released by different actor OR different reason OR different investigation_id | 409 ALREADY_RELEASED | NOT IMPLEMENTED |
| Hold in expired/cancelled state | 422 HOLD_NOT_ACTIVE | NOT IMPLEMENTED (no such states exist) |

**All 3 idempotency cases are UNIMPLEMENTED.** The current service doesn't even check `is_active` in `_get_active_or_raise` — it fetches the hold regardless of status and would silently double-release (setting `released_by` to the new caller, overwriting the original release data).

### Transactional outbox gap

The current `payment_hold_service.py` publishes via `_shim.events.publish` (line 87–99) which is a synchronous fire-and-forget call. There is NO transactional outbox. If the DB commit succeeds but the publish fails, the event is lost. Spec D11 requires transactional outbox (R1 BLOCK 4).

---

## Cross-Cutting Findings

### Consumers (events/consumers.py)
8 consumer handlers exist in `CONSUMER_ROUTING`:
1. `claim.adjudicated` → `handle_claim_adjudicated`
2. `claim.reversed` → `handle_claim_reversed`
3. `ap.created` → `handle_ap_created`
4. `ap.settled` → `handle_ap_settled`
5. `exclusion.match_found` → `handle_exclusion_match_found`
6. `payment.return_suspicious` → `handle_payment_return_suspicious`
7. `pharmacy.application_submitted` → `handle_pharmacy_application_submitted`
8. `pharmacy.ownership_changed` → `handle_pharmacy_ownership_changed`

Missing SP-3 consumer: `accumulator.updated` → NEW accumulator_consumer (Plan A)

### Graph Analysis Service (services/graph_analysis.py)
`FraudNetworkAnalyzer` class EXISTS with `build_graph`, `detect_communities`, `get_entity_neighbors`. Uses NetworkX + Louvain (with greedy fallback). NO `GraphRun` table yet; the service does NOT persist run state. This is the basis for Plan A's `graph_analysis_service.py` — it exists but needs wiring to `GraphRun` ORM + per-tenant query.

### Scheduled Jobs (jobs/scheduled.py)
`JOB_SCHEDULE` dict exists with cron expressions for 8 jobs including `rebuild_fraud_network_graph (cron: "0 3 * * *")`. However ALL job implementations are stubs returning `{"count": 0}`. The graph rebuild job at `job_rebuild_fraud_network_graph` is a 3-line stub (lines 25–31). No `GraphRun` table, no advisory lock, no persistence.

### No TenantScopedMixin / PHIMixin
Zero usage of `shared.db.models.TenantScopedMixin` or `shared.db.models.phi_mixin.PHIMixin` anywhere in reclaimrx. Plan A adding the 6 new tables must apply `TenantScopedMixin` per the architecture rules. Also NO PostgreSQL RLS policies are defined in the existing migration files (migrations 0001-0007 present but 0002 is `0002_reclaimrx_rls.py` — need to verify content).

### No PHI encryption
`subject_name` in Investigation (line 384), `entity_name` in PaymentHold (line 595), `prescriber_name` in PrescriberProfile (line 240), and `pharmacy_name` in PharmacyProfile (line 194) are all plain `String(255)` columns. If any of these fields could be PHI they must use `EncryptedString`. Per spec D6, `member_name/dob/ssn/address/phone/email` are PHI; these name fields may be PHI depending on context.

### No async SQLAlchemy
All route handlers use sync `def` with synchronous `Session` — blocking the event loop. Architecture rules say MUST use `async def`. This is a pre-existing issue Plan A inherits.

---

## Summary Table: What Plan A Must Create vs. Extend

| Item | Action | Already Exists? |
|---|---|---|
| GraphRun table | CREATE | No |
| FraudRing table | CREATE | No |
| AccumulatorAnomaly table | CREATE | No |
| ThresholdConfig table | CREATE | No |
| ThresholdConfigAudit table | CREATE | No |
| OutboxEvent table | CREATE | No |
| Investigation extensions (6+ columns) | ALTER | Partial |
| PaymentHold.status column | ALTER (replace is_active) | No |
| 13 new API endpoints | CREATE | No |
| Hold release endpoint (POST /holds/{id}/release) | REPLACE current DELETE | Partial |
| Outbox + dispatcher | CREATE | No |
| Accumulator consumer | CREATE | No |
| graph_analysis_job.py (wired to GraphRun) | CREATE (extend stub) | Stub only |
| ThresholdConfig service | CREATE | No |
| packages/contract/src/impls/reclaimrx/ | CREATE (4 files in impls/reclaimrx/) | No |
| processed_events cleanup scheduler in create_app | WIRE | cleanup function exists |
| DLQ depth monitor + alerting in create_app | CREATE | No |
| Audit hash-chain daily job in create_app | WIRE | No |
| Scheduling: APScheduler | NOT AVAILABLE — use asyncio.create_task + croniter pattern | Pattern in data_ingestion |
| Advisory lock: deterministic hash | zlib.crc32 | Not yet used in reclaimrx |
