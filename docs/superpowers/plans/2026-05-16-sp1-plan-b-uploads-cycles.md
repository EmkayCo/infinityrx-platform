# SP-1 Plan B — Upload Resource + Cycles Surface Wiring

**Date:** 2026-05-16
**Sub-project:** SP-1 PaySync Operator Portal
**Status:** Ready for execution (R3 — addresses 2nd pre-execute codex NO-GO of 2026-05-16; 3 design-decision items resolved on top of R2's 10)
**Depends on:** SP-1 Plan A complete on `wave/B10-w5-sp1-paysync` (HEAD `e97a1bb0`)

---

## R3 Revision Summary (2nd pre-execute codex NO-GO fixes)

After R2, codex re-review returned NO-GO with 3 remaining items requiring design decisions. R3 resolves each in the cleanest-against-HEAD direction:

| # | Issue | R3 decision |
|---|---|---|
| R3.1 | MFA gate as specified was non-sensical against HEAD. `modules/core-platform/src/auth/api/auth_router.py` issues the JWT ONLY at `/mfa/verify` success (line 152-216). HEAD's `CurrentUser` has no `mfa_verified` attribute, JWT claims have no MFA claim, sessions table has no `mfa_verified` column. The proposed `require_mfa_for_phi` would have nothing to read. | **DROP the per-route MFA gate.** MFA is enforced at the AUTH GATE: a user who hasn't completed MFA cannot obtain a JWT and therefore cannot reach any authenticated PaySync route. Adding `require_mfa_for_phi` would duplicate this enforcement against an attribute that doesn't exist. Plan B's MFA "gate tests" are replaced with a SINGLE assertion per new route that the route is protected by `get_current_user` (which itself rejects unauthenticated requests). Session-level MFA-reverification-on-PHI-access is a core-platform-level concern — not paysync-specific — and is documented as out-of-scope for SP-1 here. Drops Task 3.1 entirely; drops MFA gate test from every other route test. |
| R3.2 | Event publisher sketch was sync — `bus.publish(envelope)` without `await`. HEAD's `EventBus.publish()` is async; all existing billing publishers use `async def` + `await bus.publish(...)`. R2 sketch would produce unawaited coroutines (silent no-op). | **Make `publish_upload_parsed` async** + `await bus.publish(envelope)`. The calling site in upload service is also async (`async def parse_upload(...)`) — propagates naturally. Mechanical fix; see Task 3b sample updated below. |
| R3.3 | Financial schema claim false: said `claim_records.amount_billed Numeric(18, 4)` and `quantity Numeric(18, 4)`. HEAD: NO `amount_billed` column at all; `quantity` is `Numeric(10, 3)`; money columns are `Numeric(12, 2)` (`net_amount`, `ingredient_cost`, etc.). Plan B's parser would have failed at INSERT. | **Two concrete fixes:** (a) Migration `0011` ALSO adds `amount_billed Numeric(14, 4)` to `billing.claim_records` — this is a semantically distinct first-class field (pharmacy-claimed amount, pre-adjudication; different from `net_amount` which is post-adjudication paid amount). 14-digit precision with 4dp preserves source-of-truth precision from the CSV upload for audit/dispute resolution. (b) CSV spec §10.3 `quantity` constraint tightened from "max 4dp" to "max 3dp" — matches HEAD's `Numeric(10, 3)` exactly; no quantity migration needed. |

## R2 Revision Summary (1st pre-execute codex NO-GO fixes)

Pre-execute codex returned NO-GO with 10 items. R2 addresses each against HEAD:

| # | Issue | Fix |
|---|---|---|
| 1 | EventEnvelope path: cited `shared/events/envelope.py`; actually at `shared/events/types.py:20` (re-exported from `shared/events/__init__.py`). Sample constructor omitted required HEAD fields `correlation_id` and `source_module`. | Update all imports to `from shared.events.types import EventEnvelope` (or `from shared.events import EventEnvelope` via re-export). Sample constructor now includes `correlation_id`, `source_module="billing"`, alongside `event_type`/`tenant_id`/`payload`/`idempotency_key`/`ordering_key`/`schema_version`. |
| 2 | TenantScopedMixin path: cited `shared/db/models/tenant_scoped_mixin.py`; actually at `shared/db/tenant_context.py:90`. | Update all references to `from shared.db.tenant_context import TenantScopedMixin, install_tenant_loader`. |
| 3 | Table name: plan said FK/index on `claims`; actual table is `claim_records` (`ClaimRecord.__tablename__ = "claim_records"`, `modules/billing/src/models/tables.py:39-44`). Existing indices use `idx_claims_*` naming convention. | Migration `0011` alters `claim_records` (not `claims`); FK column is `claim_records.upload_id`; new index named `idx_claims_upload` for consistency. |
| 4 | Task 1.2 test contradicted the safe migration: said "claim_record.upload_id not null FK" while the migration correctly makes it nullable. | Test wording updated: "nullable FK present; upload service is responsible for setting `upload_id` on every NEW upload-created ClaimRecord; existing rows have NULL by design." |
| 5 | False PHI claims: said `ClaimRecord.member_id` uses `EncryptedString`; HEAD has it as plaintext `String(100), nullable=True`. Also said `PHIMixin` carries a `row_errors` audit marker; PHIMixin only adds demographic encrypted columns (`first_name_encrypted`, `last_name_encrypted`, `dob_encrypted`). | (a) Remove the false "existing encryption" claim. (b) Define explicit PHI-audit emission via existing `audit.middleware` patterns (modules/core-platform/src/audit/middleware.py:200 `action="phi_access"`): the upload router emits `phi_access` audit entries directly when reading row_errors. (c) Drop PHIMixin from Upload model — it doesn't fit; instead mark Upload as PHI-handling via existing audit + Cache-Control discipline. Member_id PHI hardening on ClaimRecord is OUT OF SCOPE for Plan B (separate hardening task tracked). |
| 6 | MFA gate tests asserted "valid JWT with `mfa_verified=False` → 403" but no concrete dependency named. HEAD's `get_current_user` doesn't check `mfa_verified`; tenant carries `mfa_required` boolean. | Plan B introduces an explicit `require_mfa_for_phi` FastAPI dependency in modules/billing (or imports one from core-platform if it exists post-grep). The dependency reads the user session's `mfa_verified` flag, looks up `tenant.mfa_required`, and raises 403 when `mfa_required=True and not mfa_verified`. Every new upload/inbox route adds this dep alongside `get_current_user`. Tests assert the 403 response. |
| 7 | Contract path drift: Plan B named `uploads-client.ts`, `cycles-client.ts`, `inbox-client.ts` siblings; Plan A consolidated to `client.ts` + `real.ts` + `mock.ts` (singular per codex R3). | Modify the existing 4 files IN PLACE: extend `client.ts` with `CyclesClient` interface; extend `real.ts` with `createRealCyclesClient` + wire `createRealUploadsClient`/`createRealInboxClient` to real HTTP; extend `mock.ts` with `createMockCyclesClient` + fixture-fed responses. types.ts gets `CycleStatus` + `Cycle` schemas. index.ts gains the new CyclesClient + Cycle named exports. |
| 8 | Event-bus consumer wording was ambiguous: Task 3 derives inbox items from DB queries; Task 3b had an event consumer "in api/inbox.py" with no clear persistence target. | Explicit separation: Task 3's `GET /api/v1/billing/inbox` derives items from current DB state (uploads + cycles queries) — this is the source of truth. Task 3b's event publication is fire-and-forget for downstream consumers (cache invalidation, future modules, audit chain). The "consumer" in this plan is a single in-module `@idempotent_handler`-decorated handler that invalidates the inbox query cache (Redis key `paysync:inbox:list:{tenant_id}:*`). Duplicate-event test: handler is no-op on second receipt. |
| 9 | Task 6 atomicity: combined cycles rewire + BFF + 4 inbox cards + inbox real-call swap + fixtures into one commit. | Split into 3 atomic commits: Task 6a (cycles surface rewire + BFF), Task 6b (4 inbox card implementations + swap `bff/inbox.ts` stub for real call), Task 6c (populate 3 CSV fixtures + 2 seeds JSON). |
| 10 | Drafter-discipline: plan said "no separate `claims.py` service" — `modules/billing/src/services/claims.py` exists. | Removed the false statement from cross-references; plan now explicitly cites `modules/billing/src/services/{ar,ap,nacha,journal,claims,routing,budget,remittance_835}.py` as existing services. Upload service adds a new `upload.py` sibling. |

---

## §10 Plan-Time Decisions Owned by This Plan

| # | Decision | Resolution |
|---|---|---|
| §10.2 | Upload file storage strategy | Local disk under `{PAYSYNC_UPLOAD_DIR}/{tenant_id}/{upload_id}/{original_filename}`; `PAYSYNC_UPLOAD_DIR` defaults to `./data/uploads` relative to the billing module working dir; 90-day retention enforced by a nightly job `paysync.cleanup_old_uploads` registered in `operator-dev.yml` `required_jobs`; files are never deleted before 90 days even if upload is superseded (provenance immutability, spec §5.2) |
| §10.3 | CSV/Excel minimum schema | 8 mandatory columns: `ndc` (11 digits), `npi` (10 digits, Luhn-checked via 80840-prefix), `claim_id` (string, unique within upload), `date_of_service` (YYYY-MM-DD), `quantity` (positive Decimal, **max 3dp** to match HEAD's `claim_records.quantity Numeric(10, 3)` — R3 fix), `days_supply` (positive integer), `amount_billed` (Decimal ≥ 0, max 4dp; stored as new `claim_records.amount_billed Numeric(14, 4)` column added by migration 0011 — R3 fix), `member_id` (string, non-empty); `source_platform` optional header comment (free-text, stored on Upload row); row errors are collected per-row and never abort the parse of other rows |

---

## Goal

Wire the Upload resource end-to-end and the Cycles surface. Specifically:

1. **Backend — Upload resource** (`modules/billing/`): new SQLAlchemy model `Upload`, Alembic migration `0011`, file-storage writer, CSV/Excel parser dispatcher, row-error capture, sha256 dedup, `upload_id` nullable FK on existing `ClaimRecord` model in `claim_records` table, FastAPI router (5 endpoints).
2. **Backend — Inbox feed endpoint**: `GET /api/v1/billing/inbox?role=<role>` returns `InboxItem[]` derived from current DB state of uploads + cycles.
3. **Backend — `paysync.upload.parsed` event**: `EventEnvelope`-published on parse completion; idempotent-handler consumer invalidates the inbox cache.
4. **Frontend — `surfaces/uploads/`**: `UploadsListPage`, `UploadDropzone`, `UploadDetailPage`, `UploadClaimViewer`; BFF handlers.
5. **Frontend — `surfaces/cycles/`**: relocate + rewire existing `portal/operator/app/admin/paysync/cycles/` pages into the module; replace direct `paysync-api.ts` imports with the contract-layer `CyclesClient`; add `ProvenanceBreadcrumb`, `RbacGate` on close action.
6. **Inbox wired**: `useInboxItems` calls real BFF; 4 Inbox card components (2 upload + 2 cycle) fully implemented.

This plan proves the upload-driven data flow end-to-end: CSV in → Upload row → Inbox item → UploadDetailPage → Cycle view with provenance breadcrumb.

---

## Scope

**In:**
- `modules/billing/src/models/upload.py` — `Upload` ORM model + `UploadStatus` enum
- `modules/billing/src/services/upload.py` — parser dispatcher, sha256 dedup, row-error capture, file writer, supersede semantics
- `modules/billing/alembic/versions/0011_add_upload_resource.py` — migration adding `billing.uploads` table + nullable `upload_id` FK on `billing.claim_records` + `idx_claims_upload` index
- `modules/billing/src/api/uploads.py` — FastAPI router (5 endpoints, RBAC-gated via standard get_current_user, PHI-audited; MFA enforced upstream at auth gate per R3.1)
- `modules/billing/src/api/inbox.py` — FastAPI router returning `InboxItem[]` from current DB state
- `modules/billing/src/events/upload_events.py` — `paysync.upload.parsed` `EventEnvelope` publication + `@idempotent_handler` consumer that invalidates inbox cache
<!-- R3 fix: removed modules/billing/src/auth/mfa_dependency.py from scope. MFA is enforced at JWT issuance (auth gate) per modules/core-platform/src/auth/api/auth_router.py:152-216; no per-route MFA dependency is needed or implementable against HEAD. -->
- `modules/billing/tests/unit/test_upload_model.py`
- `modules/billing/tests/unit/test_upload_service.py` — parser, dedup, row-error, supersede semantics, upload_id propagation, financial Decimal precision
- `modules/billing/tests/unit/test_upload_events.py` — EventEnvelope shape (correlation_id, source_module, idempotency_key, schema_version), consumer idempotency, forward-compat
- `modules/billing/tests/integration/test_uploads_router.py` — 5 routes × 3 roles + per-endpoint cross-tenant + per-endpoint MFA gate + per-read-endpoint PHI audit
- `modules/billing/tests/integration/test_inbox_router.py` — real items per kind + cross-tenant + MFA gate
- `packages/contract/src/impls/paysync/types.ts` — add `CycleSchema`, `CycleStatusSchema`, `Cycle` type
- `packages/contract/src/impls/paysync/client.ts` — extend with `CyclesClient` interface + cache policies (with `{tenant_id}` per GC.2)
- `packages/contract/src/impls/paysync/real.ts` — wire `createRealUploadsClient`, `createRealInboxClient` to real HTTP; add `createRealCyclesClient`
- `packages/contract/src/impls/paysync/mock.ts` — add `createMockCyclesClient`; uploads/inbox mocks gain fixture-fed responses
- `packages/contract/src/index.ts` — export the new CyclesClient + Cycle types
- `packages/modules/paysync/src/surfaces/uploads/` — `UploadsListPage`, `UploadDropzone`, `UploadDetailPage`, `UploadClaimViewer`, BFF handlers
- `packages/modules/paysync/src/surfaces/cycles/` — rewired cycle pages + BFF handlers
- `packages/modules/paysync/src/bff/inbox.ts` — replaced stub with real call to `InboxClient`
- `packages/modules/paysync/src/inbox/cards/` — 4 card components implemented: `UploadPendingReviewCard`, `UploadValidatedCard`, `CyclePendingCloseCard`, `CycleCloseReviewCard`
- `packages/modules/paysync/fixtures/uploads/{upload-001-healthy,upload-002-validation-fail,upload-003-half-bad}.csv` — populated with real synthetic data
- `packages/modules/paysync/fixtures/seeds/users.json` — 3 synthetic users (Operator/Approver/Auditor; non-PHI names)
- `packages/modules/paysync/fixtures/seeds/cycles.json` — 5 synthetic cycles (mixed statuses)
- `infrastructure/manifests/operator-dev.yml` — add `paysync.cleanup_old_uploads` to `required_jobs`
- `docs/api-contracts/events/paysync.upload.parsed.md` — event contract doc

**Out:**
- Batches, AR/AP, payment runs (Plan C)
- Files (NACHA/835), journal (Plan D)
- Reports, setup, E2E round trip (Plan E)
- Carryovers, bank-settlements, reconciliations surfaces (Plans C/D/E)
- ClaimRecord.member_id PHI encryption hardening (out-of-scope follow-up; tracked separately)

---

## Tasks

### Task 1 — Backend: Upload ORM model + nullable FK on ClaimRecord + alembic migration

| # | Subject | Files touched | Test added | Deliverable |
|---|---|---|---|---|
| 1.1 | `Upload` ORM model | `modules/billing/src/models/upload.py` (new file) | unit: model fields + enum transitions | `Upload` importable from billing models |
| 1.2 | Add nullable `upload_id` FK to `ClaimRecord` model | `modules/billing/src/models/tables.py` (existing `ClaimRecord`, line 39) | unit: `nullable=True` FK column present; service requires `upload_id` for new upload-created claims (DB layer permits NULL for backwards compat) | FK present on existing model |
| 1.3 | Alembic migration | `modules/billing/alembic/versions/0011_add_upload_resource.py` | migration runs upgrade + downgrade cleanly | schema updated |

**`Upload` model fields** (from spec §5.2):
- `id` — `PG_UUID(as_uuid=True)`, PK
- `tenant_id` — `PG_UUID(as_uuid=True)`, NOT NULL, FK `core.tenants.id`, indexed `(tenant_id, uploaded_at)`
- `filename` — `VARCHAR(512)`, NOT NULL
- `sha256` — `CHAR(64)`, NOT NULL; unique index `(tenant_id, sha256)` for dedup
- `file_size` — `BIGINT`, NOT NULL
- `mime_type` — `VARCHAR(128)`, NOT NULL
- `uploaded_at` — `TIMESTAMP WITH TIME ZONE`, NOT NULL, `server_default=now()`
- `uploaded_by` — `PG_UUID(as_uuid=True)`, NOT NULL (FK to `core.users.id` if such table exists; otherwise a plain UUID — verify via grep before migration)
- `source_platform` — `VARCHAR(256)`, nullable
- `supersedes_upload_id` — `PG_UUID(as_uuid=True)`, nullable, FK `billing.uploads.id` (self-referential)
- `status` — `VARCHAR(32)`, NOT NULL, default `'parsing'`; allowed: `parsing`, `validation_failed`, `validated`, `superseded`
- `row_count` — `INTEGER`, nullable (set after parse completes)
- `error_count` — `INTEGER`, nullable (set after parse completes)
- `row_errors` — `JSONB`, nullable (list of per-row error dicts; populated after parse; **MUST NEVER echo member_id values** — only describes the failure)
- Inherits `TenantScopedMixin` from `shared.db.tenant_context` (R2: correct path) — adds `__table_args__` `(tenant_id)` query filter via `install_tenant_loader`
- Inherits `AuditMixin` from `shared.db.models.audit_mixin` (verify path via grep before writing) — every mutation gets audit chain entry
- Does NOT inherit `PHIMixin` (R2 GC.5: PHIMixin adds demographic encrypted columns; Upload has no demographic columns. PHI handling is enforced at the router level via `phi_access` audit emission + `Cache-Control: no-store`, not via column encryption)

**PHI controls on row_errors** (R2 fix to GC.5):
- `row_errors` JSONB MUST NEVER echo full `member_id` values — error messages describe the failure category without revealing input bytes. Acceptable: `{"row": 12, "field": "member_id", "message": "member_id too long"}`. Forbidden: `{"row": 12, "message": "member_id 'M12345ABC' exceeds 64 chars"}`.
- All API responses containing `row_errors` MUST include `Cache-Control: no-store` header (per `.claude/rules/phi-compliance.md`).
- Every read of upload row_errors by an authenticated user MUST emit a `phi_access` audit entry via the existing `modules/core-platform/src/audit/middleware.py` pattern (action="phi_access", entity_type="upload", entity_id=<upload_id>, user_id, tenant_id).
- Out of scope: `ClaimRecord.member_id` is currently plaintext `String(100)`. Encrypting it (with `EncryptedString` from `shared/crypto/sqlalchemy_types.py`) is a separate follow-up — documented but not blocking Plan B.

**Migration rules:**
- `upload_id` FK on `claim_records` is NULLABLE initially (existing claims have no upload; new claims require it at service layer, not DB layer)
- **R3 fix: same migration ALSO adds `amount_billed Numeric(14, 4) NULL` to `claim_records`** — pharmacy-claimed amount, pre-adjudication. Semantically distinct from existing `net_amount` (post-adjudication paid amount). 14-digit precision with 4dp preserves source-of-truth Decimal precision from CSV uploads for audit/dispute resolution. Nullable for backwards compat with existing rows; service layer requires it for new upload-created claims.
- Index: `idx_claims_upload` on `claim_records(upload_id)` for `GET /uploads/{id}/claims` query performance
- Migration uses `op.create_table('uploads', schema='billing', ...)` matching the existing `billing` schema namespace
- `op.add_column('claim_records', sa.Column('upload_id', UUID, nullable=True), schema='billing')`
- `op.add_column('claim_records', sa.Column('amount_billed', sa.Numeric(14, 4), nullable=True), schema='billing')` (R3 fix)
- `op.create_foreign_key('fk_claims_upload', 'claim_records', 'uploads', ['upload_id'], ['id'], source_schema='billing', referent_schema='billing')`
- `op.downgrade()` drops in reverse order: FK, both columns, then uploads table

- [ ] Step 1.1: Write `modules/billing/src/models/upload.py` with `Upload` model + `UploadStatus` enum; inherit `TenantScopedMixin` from `shared.db.tenant_context` + `AuditMixin`
- [ ] Step 1.2: Add `upload_id` nullable FK column to `ClaimRecord` in `modules/billing/src/models/tables.py` (line 39, after `__table_args__`)
- [ ] Step 1.3: Write Alembic migration `0011_add_upload_resource.py`; targets `billing` schema; verify `alembic upgrade head` and `alembic downgrade -1` run cleanly on a fresh schema
- [ ] Step 1.4: Write unit tests in `modules/billing/tests/unit/test_upload_model.py` for model fields, enum transitions, tenant scoping inheritance, and the nullable FK shape on ClaimRecord
- [ ] Step 1.5: Run `pytest modules/billing/tests/unit/test_upload_model.py` — all pass
- [ ] Step 1.6: Commit — `feat(sp-1-b): Upload ORM model + alembic 0011 (nullable upload_id FK on billing.claim_records)`

---

### Task 2 — Backend: Upload service (parser + storage + supersede + financial precision)

| # | Subject | Files touched | Test added | Deliverable |
|---|---|---|---|---|
| 2.1 | File writer + sha256 dedup | `modules/billing/src/services/upload.py` (new file, sibling to existing `claims.py`/`nacha.py`/etc.) | unit: sha256 match returns existing upload | Dedup works |
| 2.2 | CSV parser dispatcher | same | unit: valid CSV → Upload validated, claims written with upload_id | Claims tagged |
| 2.3 | Row-error capture | same | unit: bad rows captured, status=validation_failed when all rows bad; partial bad → validated with error_count | Per-row errors |
| 2.4 | Excel parser dispatcher | same | unit: `.xlsx` dispatches to openpyxl reader, same output shape | Excel supported |
| 2.5 | Supersede semantics | same | unit: supersedes_upload_id set, old upload status → superseded, old claims NOT deleted | Immutable provenance |

**CSV minimum schema validation** (§10.3):

```python
REQUIRED_COLUMNS = {
    "ndc", "npi", "claim_id", "date_of_service",
    "quantity", "days_supply", "amount_billed", "member_id",
}
```

Per-row validation (using `\A...\Z` regex anchors per LESSON-004):
- `ndc`: `re.fullmatch(r"\A\d{11}\Z", value)`
- `npi`: exactly 10 digits + Luhn check with 80840 prefix (use existing `shared.validation.npi.is_valid_npi` if present; otherwise inline)
- `date_of_service`: `datetime.date.fromisoformat(value)` — no try/except swallowing (use a guarded helper that returns row error on `ValueError`)
- `quantity`: `Decimal(str(value))` — must be `>= 0`, **`<= 3 decimal places`** via `value.as_tuple().exponent >= -3` (R3 fix: matches HEAD `claim_records.quantity Numeric(10, 3)`); ROUND_HALF_UP for any computed sums
- `amount_billed`: `Decimal(str(value))` — must be `>= 0`, `<= 4 decimal places` via `value.as_tuple().exponent >= -4`; stored as new `claim_records.amount_billed Numeric(14, 4)` column added by migration 0011; ROUND_HALF_UP for any computed sums
- `days_supply`: `int(value)`, `>= 1`
- `member_id`: non-empty string, length `<= 64`

Row errors stored as `list[dict[str, str]]` on `Upload.row_errors` JSONB. **Never logged** (may contain PHI-adjacent context per `.claude/rules/phi-compliance.md`). Error messages MUST describe the failure category without echoing the `member_id` VALUE itself.

**Storage layout** (§10.2):
```
{PAYSYNC_UPLOAD_DIR}/{tenant_id}/{upload_id}/{original_filename}
```
`PAYSYNC_UPLOAD_DIR` defaults to `./data/uploads`. Directory created on first write. Atomic write: write to `.tmp` suffix, `os.replace()` on success. Mid-write crash → orphaned `.tmp` cleaned by the nightly `paysync.cleanup_old_uploads` job.

**Financial precision (R3 fix to GC.3):** `amount_billed` stored as new `claim_records.amount_billed Numeric(14, 4)` column added by migration 0011; `quantity` stored as existing `claim_records.quantity Numeric(10, 3)`. All Decimal math uses `Decimal(str(raw_value))` — never `Decimal(float)`. ROUND_HALF_UP on every `.quantize()`. Per `.claude/rules/financial-precision.md`. The earlier R2 claim of `Numeric(18, 4)` for both was wrong against HEAD — `amount_billed` didn't exist, `quantity` was `(10, 3)`.

- [ ] Step 2.1: Write `modules/billing/src/services/upload.py` with all 5 service functions
- [ ] Step 2.2: Write `modules/billing/tests/unit/test_upload_service.py` covering all unit cases in table above; use SAVEPOINT-based fixture per LESSON-001
- [ ] Step 2.3: Run unit tests — 100% branch coverage on service (financial + security paths)
- [ ] Step 2.4: Commit — `feat(sp-1-b): Upload service — parser, sha256 dedup, row-error capture, supersede, Decimal precision`

---

### Task 3 — Backend: Upload + Inbox API routers (RBAC + tenant + PHI audit)

| # | Subject | Files touched | Test added | Deliverable |
|---|---|---|---|---|
| 3.1 | Upload router (5 endpoints) | `modules/billing/src/api/uploads.py` (new file) | integration: 5 routes × 3 roles + cross-tenant per endpoint + PHI audit per read endpoint | Routes live |
| 3.2 | Inbox router | `modules/billing/src/api/inbox.py` (new file) | integration: each Inbox kind for correct state + cross-tenant | Inbox derives from DB |
| 3.3 | Mount routers on billing app | `modules/billing/src/main.py` | integration: health check + auth-gated route responds | Routers in production app |

**MFA enforcement** (R3 fix to GC.6 + R3.1):
**Per-route MFA reverification is OUT OF SCOPE for SP-1.** HEAD's `modules/core-platform/src/auth/api/auth_router.py:152-216` issues the JWT ONLY at `/auth/mfa/verify` success — a user who hasn't completed MFA cannot obtain a JWT and therefore cannot reach any authenticated PaySync route. Adding a per-route `require_mfa_for_phi` dependency would duplicate enforcement against an attribute (`mfa_verified` on CurrentUser / JWT claims / sessions) that does not exist in HEAD.

Plan B's new routes use the standard `Depends(get_current_user)` dependency. Test assertion per route: "returns 401 without bearer token" — this proves auth-gate protection (which implicitly proves MFA protection because JWT issuance requires MFA). No `mfa_verified=False` JWT can exist in HEAD, so a "403 on mfa_verified=False" test cannot be written.

If future requirements call for session-level MFA-reverification-on-PHI-access (e.g., "force fresh MFA within 15 min of PHI route access"), it lands as a core-platform `auth/mfa_session.py` feature with a corresponding `CurrentUser.mfa_verified_at` attribute. That is a separate sprint and not a paysync-module-specific concern.

**RBAC enforcement on upload router** (spec §5.4):
- `POST /api/v1/billing/uploads` — Operator + Approver; Auditor → 403
- `GET /api/v1/billing/uploads`, `GET /api/v1/billing/uploads/{id}` — all roles
- `GET /api/v1/billing/uploads/{id}/claims` — all roles
- `POST /api/v1/billing/uploads/{id}/supersede` — Operator + Approver; Auditor → 403

**Inbox endpoint logic** (DB-query-derived per R2 GC.8):
`GET /api/v1/billing/inbox?role=<role>` returns `InboxItem[]` derived from CURRENT DB state:
- Uploads with `status=parsing` or `status=validation_failed` → `upload_pending_review` (Operator)
- Uploads with `status=validated` and no downstream batch → `upload_validated_awaiting_batching` (Operator)
- Cycles with `window_closed=true` and `status=open` → `cycle_pending_close` (Operator)
- Cycles with `status=closing` → `cycle_close_review` (Approver)

Items carry `upload_id` where derivable. `priority='high'` when upload `error_count > 0` or cycle window closed > 24h ago.

The event publication in Task 3b is for downstream consumers (cache invalidation, future modules) — the inbox endpoint itself remains a SQL query.

**Tenant isolation** (`.claude/rules/tenant-isolation.md`): all queries inherit `WHERE tenant_id = :current_tenant_id` via `TenantScopedMixin` + `install_tenant_loader`. Routes also validate `x-tenant-id` header matches JWT tenant claim — 403 mismatch.

**Cross-tenant test (mandatory per .claude/rules/tenant-isolation.md:23):** EVERY new endpoint (5 upload + 1 inbox = 6) gets a dedicated cross-tenant isolation test: create 2 tenants, seed data for both, authenticate as Tenant A, assert ZERO Tenant B records appear. Separate named test function per endpoint, not a shared helper.

**PHI access audit on row_errors read** (R2 fix to GC.5):
`GET /api/v1/billing/uploads/{id}` and `GET /api/v1/billing/uploads/{id}/claims` MUST emit a `phi_access` audit entry. Use existing pattern from `modules/core-platform/src/audit/middleware.py:200`:

```python
from modules.core_platform.src.audit.client import emit_audit  # confirm exact path
emit_audit(
    tenant_id=current_user.tenant_id,
    user_id=current_user.id,
    action="phi_access",
    entity_type="upload",
    entity_id=upload_id,
)
```

Test asserts the audit row is written for each call.

**Auth-gate test** per new route (replaces R2's MFA gate test): `GET/POST <new route>` without Authorization header → 401. This proves auth-gate protection; MFA is enforced upstream at JWT issuance, so any valid JWT is implicitly MFA-verified.

- [ ] Step 3.1: Write `modules/billing/src/api/uploads.py` with 5 endpoints + RBAC + PHI audit + Cache-Control on row_errors responses
- [ ] Step 3.2: Write `modules/billing/src/api/inbox.py` with DB-query-derived items
- [ ] Step 3.3: Mount routers in `modules/billing/src/main.py`
- [ ] Step 3.4: Write `modules/billing/tests/integration/test_uploads_router.py` — RBAC (3 roles × 5 endpoints) + cross-tenant per endpoint + PHI audit per read endpoint + auth-gate (no-token = 401) per endpoint + Cache-Control header assertion on row_errors responses
- [ ] Step 3.5: Write `modules/billing/tests/integration/test_inbox_router.py` — items per kind + cross-tenant + auth-gate per endpoint
- [ ] Step 3.6: Run `pytest modules/billing/tests/` — 100% on auth/RBAC/PHI paths, ≥99% branch elsewhere
- [ ] Step 3.7: Commit — `feat(sp-1-b): billing Upload + Inbox routers, RBAC-gated, tenant-isolated, PHI-audited`

---

### Task 3b — Backend: `paysync.upload.parsed` event (EventEnvelope + idempotent consumer)

**Event publication** (in `modules/billing/src/events/upload_events.py`, called from `upload.py` service end-of-parse). **R3 fix: async** — HEAD's `EventBus.publish()` is async; existing billing publishers use `async def` + `await`. Calling site is already `async def parse_upload(...)`.

```python
import uuid
from shared.events import EventEnvelope, EventBus

async def publish_upload_parsed(bus: EventBus, *, upload, correlation_id: uuid.UUID) -> None:
    envelope = EventEnvelope(
        event_type="paysync.upload.parsed",
        tenant_id=upload.tenant_id,
        correlation_id=correlation_id,
        source_module="billing",
        payload={
            "upload_id": str(upload.id),
            "tenant_id": str(upload.tenant_id),
            "status": upload.status,
            "row_count": upload.row_count,
            "error_count": upload.error_count,
        },
        ordering_key=str(upload.id),
        idempotency_key=f"paysync:upload:{upload.id}:parsed",
        schema_version="1.0",
    )
    await bus.publish(envelope)
```

**Required EventEnvelope fields confirmed against HEAD** (`shared/events/types.py:20`): `event_type`, `tenant_id`, `correlation_id`, `source_module`, `payload`, `timestamp` (auto), `idempotency_key`, `ordering_key`, `schema_version`. The R1 plan omitted `correlation_id` and `source_module` — R2 includes them.

**Event contract doc** (NEW): `docs/api-contracts/events/paysync.upload.parsed.md`. Content: event_type, schema_version, payload fields (upload_id, tenant_id, status, row_count, error_count), ordering_key (upload_id), idempotency_key (`paysync:upload:{upload_id}:parsed`), publisher (`billing` module's upload service), consumers (inbox cache-invalidation handler in same module). Per `.claude/rules/event-bus.md:23`.

**Consumer** (in `modules/billing/src/events/upload_events.py`):
The consumer handler is `@idempotent_handler`-decorated per `.claude/rules/event-bus.md:11`. The handler invalidates Redis cache keys matching `paysync:inbox:list:{tenant_id}:*` so the next `GET /inbox` query bypasses stale cache and re-derives from current DB state.

**Forward-compat:** consumer must handle envelopes with `schema_version > "1.0"` gracefully by ignoring unknown payload fields (per `.claude/rules/event-bus.md`).

**Tests:**
- Unit: publication emits `EventEnvelope` with correct `event_type`, `tenant_id`, `correlation_id`, `source_module="billing"`, `ordering_key`, `idempotency_key`, `schema_version`
- Unit: consumer handler decorated with `@idempotent_handler`; duplicate event is no-op (verified by mock cache stats)
- Unit: consumer handles payload with extra unknown fields (forward-compat test)
- Integration: POST upload → parse completes → event emitted → next GET /inbox returns fresh items (cache invalidation verified via cache spy)

- [ ] Step 3b.1: Write `modules/billing/src/events/upload_events.py` with publication + `@idempotent_handler` consumer
- [ ] Step 3b.2: Call `publish_upload_parsed` from `upload.py` service at end of parse
- [ ] Step 3b.3: Write `docs/api-contracts/events/paysync.upload.parsed.md` event contract doc
- [ ] Step 3b.4: Write `modules/billing/tests/unit/test_upload_events.py` — publication shape, consumer idempotency, forward-compat
- [ ] Step 3b.5: Write integration test: upload → event → cache invalidated → inbox fresh
- [ ] Step 3b.6: Run tests — 100% on event-bus paths
- [ ] Step 3b.7: Commit — `feat(sp-1-b): paysync.upload.parsed event — EventEnvelope with correlation_id/source_module, idempotent_handler cache-invalidation consumer, contract doc`

---

### Task 4 — Contract: extend client.ts / real.ts / mock.ts in place (R2 fix to GC.7)

Modify the existing 4 files at `packages/contract/src/impls/paysync/` IN PLACE — the consolidated structure from Plan A (Codex R3-required) stays. Add CyclesClient + extend UploadsClient/InboxClient real impls.

| # | Subject | Files touched | Test added | Deliverable |
|---|---|---|---|---|
| 4.1 | Add `Cycle` + `CycleStatus` schemas | `packages/contract/src/impls/paysync/types.ts` | schema validation test | Cycle types available |
| 4.2 | Add `CyclesClient` interface + cache policy (with `{tenant_id}`) | `packages/contract/src/impls/paysync/client.ts` | type test: methods callable | Interface present |
| 4.3 | Wire `UploadsClient`/`InboxClient` `real.ts` to HTTP + add `createRealCyclesClient` | `packages/contract/src/impls/paysync/real.ts` | unit: methods build correct URLs | Real HTTP wiring |
| 4.4 | Extend `mock.ts` with `createMockCyclesClient` + fixture-fed responses for uploads/inbox | `packages/contract/src/impls/paysync/mock.ts` | unit: mocks return typed shapes | Fixture-fed mocks |
| 4.5 | Export new symbols from contract index | `packages/contract/src/index.ts` | — | `CyclesClient` + `Cycle` importable |

**CyclesClient interface** (sketch — verify against existing `paysync-api.ts` for shape):

```ts
export interface CyclesClient extends BaseClient {
  readonly name: "paysync.cycles";
  list(req: { status?: CycleStatus; limit?: number; cursor?: string }): Promise<CycleListResponse>;
  get(id: string): Promise<Cycle | null>;
  close(id: string): Promise<Cycle>;  // approver-only RBAC enforced server-side
}
```

`PAYSYNC_CYCLES_CACHE_POLICIES` includes `{tenant_id}` as first interpolation segment (per GC.2).

**Real impl** uses `fetch` with SP-0 auth header injection from `@infinityrx/auth`. URL builders point at `${API_BASE}/api/v1/billing/uploads/...` and `${API_BASE}/api/v1/billing/cycles/...`.

- [ ] Step 4.1: Extend `types.ts` with `CycleSchema`, `CycleStatusSchema`, `Cycle` type
- [ ] Step 4.2: Extend `client.ts` with `CyclesClient` interface + `PAYSYNC_CYCLES_CACHE_POLICIES`
- [ ] Step 4.3: Wire real HTTP in `real.ts` (replace `throw NOT_WIRED` stubs); add `createRealCyclesClient`
- [ ] Step 4.4: Extend `mock.ts` with `createMockCyclesClient` + load 5 cycles from `fixtures/seeds/cycles.json`; uploads/inbox mocks read from fixtures
- [ ] Step 4.5: Export new symbols from `packages/contract/src/index.ts`
- [ ] Step 4.6: Update `packages/contract/src/__tests__/paysync.test.ts` with cycle factory tests
- [ ] Step 4.7: `tsc -b` clean
- [ ] Step 4.8: Commit — `feat(sp-1-b): contract — CyclesClient + real HTTP wiring for uploads/inbox/cycles`

---

### Task 5 — Frontend: uploads surface (4 components + BFF)

| # | Subject | Files touched | Test added | Deliverable |
|---|---|---|---|---|
| 5.1 | `UploadsListPage` | `surfaces/uploads/UploadsListPage.tsx` | RTL: renders table, status badge, sha256 dedup banner | List view |
| 5.2 | `UploadDropzone` | `surfaces/uploads/UploadDropzone.tsx` | RTL: file select triggers POST, progress shown, 409 dedup handled | Upload UI |
| 5.3 | `UploadDetailPage` | `surfaces/uploads/UploadDetailPage.tsx` | RTL: parse status, row-error list (no member_id echo), link to claim viewer | Detail view |
| 5.4 | `UploadClaimViewer` | `surfaces/uploads/UploadClaimViewer.tsx` | RTL: scoped to upload_id, paginated | Scoped claim view |
| 5.5 | BFF handlers | `surfaces/uploads/bff/` route.ts files | — | Next.js route handlers |
| 5.6 | Update surface `index.ts` | `surfaces/uploads/index.ts` | — | Surface wired |

**UploadDropzone** — multipart POST to `/api/paysync/uploads` (BFF). BFF proxies to `UploadsClient.create(stream)`. Progress bar via `XMLHttpRequest.upload.onprogress`. On 409 (sha256 dedup): renders "Already uploaded — [view existing upload #N]" banner linking to existing upload's detail page.

**Error handling** (spec §8):
- Parse errors → `UploadDetailPage` row-error list; **never display `member_id` value** — show only the validation failure description. Backend already strips the value from row_errors per Task 2.3.
- RBAC denial → `RbacGate` soft-disables upload button for Auditor role (renders disabled, never hidden, per spec §5.4)
- Backend down (write path) → fail-fast, no optimistic update, error toast with `correlation_id`

- [ ] Step 5.1–5.4: Write all 4 upload UI components
- [ ] Step 5.5: Write BFF route handlers under `surfaces/uploads/bff/`
- [ ] Step 5.6: Update `surfaces/uploads/index.ts` to export real components
- [ ] Step 5.7: Write RTL tests for each component (use the happy-dom + cleanup() pattern from Plan A Inbox tests)
- [ ] Step 5.8: Run tests — all pass
- [ ] Step 5.9: Commit — `feat(sp-1-b): uploads surface — dropzone, list, detail, claim viewer + BFF`

---

### Task 6a — Frontend: cycles surface rewire (R2 split per GC.9)

| # | Subject | Files touched | Test added | Deliverable |
|---|---|---|---|---|
| 6a.1 | Copy cycles pages into module | `surfaces/cycles/` (from `portal/operator/app/admin/paysync/cycles/`) | — | Pages in module |
| 6a.2 | Replace `paysync-api` imports with `CyclesClient` | `surfaces/cycles/*.tsx` | RTL: mock toggle works | Contract-layer |
| 6a.3 | Add `RbacGate` on close action | `surfaces/cycles/CycleDetailPage.tsx` | RTL: Operator sees disabled close; Approver enabled | RBAC enforced |
| 6a.4 | Add `ProvenanceBreadcrumb` | `surfaces/cycles/CycleDetailPage.tsx` | RTL: breadcrumb renders upload chain | Provenance shown |
| 6a.5 | BFF handlers | `surfaces/cycles/bff/` | — | Route handlers |

**Cycles rewire notes:**
- Existing pages at `portal/operator/app/admin/paysync/cycles/[cycleId]/page.tsx` + `cycles/page.tsx` are COPIED (not moved) into the module; originals deleted in Plan E after E2E proves module routes work.
- Replace: `import { ... } from '@shared/lib/paysync-api'` → `import { CyclesClient } from '@infinityrx/contract'`
- `ProvenanceBreadcrumb` chain for a cycle: `[{ label: 'Upload #N', href: '/admin/paysync/uploads/{upload_id}' }, { label: 'Cycle {id}', href: '...' }]`

- [ ] Step 6a.1: Copy cycles pages into `surfaces/cycles/`
- [ ] Step 6a.2: Replace `paysync-api` imports with `CyclesClient`
- [ ] Step 6a.3: Add `RbacGate` on cycle close button
- [ ] Step 6a.4: Add `ProvenanceBreadcrumb` to `CycleDetailPage`
- [ ] Step 6a.5: Write BFF handlers under `surfaces/cycles/bff/`
- [ ] Step 6a.6: Write/update RTL tests for the rewired pages
- [ ] Step 6a.7: `npm --workspace=@infinityrx/module-paysync test` — all pass
- [ ] Step 6a.8: Commit — `feat(sp-1-b): cycles surface rewire — CyclesClient + RbacGate close + ProvenanceBreadcrumb + BFF`

---

### Task 6b — Frontend: 4 inbox cards implemented + real bff/inbox.ts call (R2 split per GC.9)

| # | Subject | Files touched | Test added | Deliverable |
|---|---|---|---|---|
| 6b.1 | `UploadPendingReviewCard` real impl | `src/inbox/cards/UploadPendingReviewCard.tsx` | RTL: renders filename, status, error_count, click handler | Card live |
| 6b.2 | `UploadValidatedCard` real impl | `src/inbox/cards/UploadValidatedCard.tsx` | RTL | Card live |
| 6b.3 | `CyclePendingCloseCard` real impl | `src/inbox/cards/CyclePendingCloseCard.tsx` | RTL | Card live |
| 6b.4 | `CycleCloseReviewCard` real impl | `src/inbox/cards/CycleCloseReviewCard.tsx` | RTL | Card live |
| 6b.5 | Replace `bff/inbox.ts` stub with real `InboxClient` call | `src/bff/inbox.ts` | RTL: hook returns items from mock client | Inbox live |

- [ ] Step 6b.1–6b.4: Implement 4 card components (each accepts `item: InboxItem` prop, renders rich content matching the kind, fires click navigation to the appropriate surface)
- [ ] Step 6b.5: Replace `bff/inbox.ts` stub with real `InboxClient.list(role)` call
- [ ] Step 6b.6: Update card stub tests to assert new rich content (the typed-stub tests from Plan A still pass since the prop shape is unchanged)
- [ ] Step 6b.7: Run tests — all pass
- [ ] Step 6b.8: Commit — `feat(sp-1-b): 4 inbox cards implemented (upload×2, cycle×2) + real InboxClient bff wire`

---

### Task 6c — Fixtures populated (R2 split per GC.9)

| # | Subject | Files touched | Test added | Deliverable |
|---|---|---|---|---|
| 6c.1 | `upload-001-healthy.csv` | `fixtures/uploads/upload-001-healthy.csv` | mock test: parser returns 20 validated rows | 20 rows valid |
| 6c.2 | `upload-002-validation-fail.csv` | `fixtures/uploads/upload-002-validation-fail.csv` | mock test: parser returns 20 row errors | 20 rows all fail |
| 6c.3 | `upload-003-half-bad.csv` | `fixtures/uploads/upload-003-half-bad.csv` | mock test: parser returns 20 valid + 10 errors | 30 rows mixed |
| 6c.4 | `seeds/users.json` | `fixtures/seeds/users.json` | — | 3 synthetic users |
| 6c.5 | `seeds/cycles.json` | `fixtures/seeds/cycles.json` | mock test: createMockCyclesClient.list returns 5 cycles | 5 synthetic cycles |
| 6c.6 | Add `paysync.cleanup_old_uploads` to operator-dev manifest | `infrastructure/manifests/operator-dev.yml` | — | Job registered |

**Synthetic data discipline** (`.claude/rules/phi-compliance.md`):
- NO real PHI under any circumstance. Names are obviously synthetic ("Test Operator", "Demo Approver" etc.).
- NDCs are real 11-digit format (validation must pass for healthy fixture) but reference generic drugs from the public RxNorm list.
- NPIs use the Luhn-valid 80840-prefixed pattern from existing synthetic-claim fixtures elsewhere in the repo.
- DOBs, addresses, SSNs not present (Upload CSVs don't carry those fields).

- [ ] Step 6c.1–6c.3: Write 3 CSV fixtures (replace the header-only stubs from Plan A Task 6 with real synthetic data)
- [ ] Step 6c.4: Write `fixtures/seeds/users.json` with 3 users (Operator/Approver/Auditor)
- [ ] Step 6c.5: Write `fixtures/seeds/cycles.json` with 5 cycles (2 open, 1 closing, 1 closed, 1 error)
- [ ] Step 6c.6: Add `- paysync.cleanup_old_uploads` to `infrastructure/manifests/operator-dev.yml` `required_jobs:` array
- [ ] Step 6c.7: Run `npm run manifest:validate` — clean
- [ ] Step 6c.8: Run `npm --workspace=@infinityrx/module-paysync test` + `npm --workspace=@infinityrx/contract test` — mocks correctly read fixtures
- [ ] Step 6c.9: Commit — `feat(sp-1-b): fixtures populated (3 CSVs, 2 seeds JSON) + cleanup_old_uploads job registered`

---

## Gate Criteria

Plan B is complete when ALL of the following are true:

- [ ] `pytest modules/billing/tests/` passes; 100% coverage on upload service (financial: Decimal parsing; security: auth/RBAC; PHI: tenant isolation, phi_access audit, member_id non-echo in row_errors); ≥99% branch coverage on all other active billing code added in this plan
- [ ] Migration `0011` runs `upgrade` and `downgrade` cleanly on a fresh schema (targets `billing` namespace; alters `billing.claim_records` to add `upload_id UUID NULL` + `amount_billed Numeric(14, 4) NULL` per R3.3; creates `billing.uploads` table; creates `idx_claims_upload`; downgrade drops in reverse order)
- [ ] `GET /api/v1/billing/inbox?role=operator` returns ≥1 item given a seeded database with an upload in `validation_failed` state
- [ ] `POST /api/v1/billing/uploads` with a duplicate file returns 409 with existing upload reference
- [ ] Cross-tenant isolation test passes for EVERY new endpoint (6 endpoints): Tenant A cannot see Tenant B data
- [ ] PHI access audit entry written when `GET /api/v1/billing/uploads/{id}` or `GET /api/v1/billing/uploads/{id}/claims` is called (verified by test inspecting the audit log)
- [ ] Auth-gate test per new route: request without Authorization header returns 401 (R3.1: replaces the MFA-gate test; MFA is enforced upstream at JWT issuance per modules/core-platform/src/auth/api/auth_router.py:152-216 — any valid JWT is implicitly MFA-verified; no `mfa_verified=False` JWT can exist in HEAD)
- [ ] `paysync.upload.parsed` event published with `EventEnvelope` carrying `correlation_id`, `source_module="billing"`, `ordering_key=str(upload.id)`, `idempotency_key="paysync:upload:{id}:parsed"`, `schema_version="1.0"`, `tenant_id` (verified by unit test); publisher is `async def` with `await bus.publish(envelope)` per R3.2
- [ ] Consumer handler decorated with `@idempotent_handler`; duplicate event is no-op (verified by unit test)
- [ ] `docs/api-contracts/events/paysync.upload.parsed.md` exists and documents event contract
- [ ] `npm --workspace=@infinityrx/module-paysync test` passes; 100% coverage on `MoneyDisplay`/`MoneyInput`/`RbacGate` retained; ≥99% branch coverage on uploads + cycles surface components
- [ ] `npm --workspace=@infinityrx/contract test` passes (new cycle factory + schema tests)
- [ ] `npm --workspace=@infinityrx/module-paysync exec -- tsc -b` clean
- [ ] `npm --workspace=@infinityrx/contract exec -- tsc -b` clean
- [ ] `npm run manifest:validate` clean (operator-dev.yml includes `paysync.cleanup_old_uploads` in `required_jobs`)
- [ ] `UploadsListPage` renders sha256 dedup banner in RTL test
- [ ] Cycles detail page shows `ProvenanceBreadcrumb` and disabled close button for Operator role in RTL test
- [ ] All 3 CSV fixtures populated with real synthetic non-PHI data (replaces Plan A header-only stubs)
- [ ] `fixtures/seeds/users.json` contains 3 synthetic users with Operator/Approver/Auditor roles
- [ ] `fixtures/seeds/cycles.json` contains 5 synthetic cycles
- [ ] `Cache-Control: no-store` verified on all responses returning `row_errors` (integration test)

---

## Deliverables

- `Upload` ORM model, migration `0011`, service, 5-endpoint router — foundational backend resource for all of SP-1
- `GET /api/v1/billing/inbox` — live Inbox feed for upload + cycle item kinds, DB-query-derived
- `paysync.upload.parsed` event with correct `EventEnvelope` shape + idempotent cache-invalidation consumer
- `UploadsClient` + `CyclesClient` + `InboxClient` real implementations against billing API
- Uploads surface (4 components + BFF) — fully functional against real backend
- Cycles surface — rewired to contract layer, RBAC-gated, provenance-breadcrumbed
- 4 Inbox card components — functional with click-through nav
- Populated CSV fixtures + user/cycle seed JSON

---

## Dependencies

- SP-1 Plan A complete on `wave/B10-w5-sp1-paysync` (HEAD `e97a1bb0`)
- `modules/billing` existing models: `ClaimRecord` (`tables.py:39`, table `claim_records`), `PaymentBatch` (`tables.py:214`), `Invoice` (`tables.py:333`), `InvoiceLineItem` (`tables.py:391`)
- `modules/billing` existing services: `ar.py`, `ap.py`, `nacha.py`, `journal.py`, `claims.py`, `routing.py`, `budget.py`, `remittance_835.py` — `upload.py` is a NEW sibling
- SP-0 auth/JWT infrastructure: `shared.auth.dependencies.get_current_user` for current user. MFA is enforced upstream at JWT issuance (modules/core-platform/src/auth/api/auth_router.py:152-216 issues JWT only on `/mfa/verify` success); no per-route MFA dependency is used or needed (R3.1)
- `shared/db/tenant_context.py:90` `TenantScopedMixin` + `install_tenant_loader` (R2: correct path)
- `shared/events/types.py:20` `EventEnvelope` (re-exported from `shared/events/__init__.py`) — required fields include `correlation_id` and `source_module`
- `modules/core-platform/src/audit/middleware.py:200` `action="phi_access"` pattern for PHI access audit emission
- `shared/db/models/phi_mixin.py` `PHIMixin` — NOT used on Upload (adds demographic encrypted columns; Upload has none of those)
- Alembic environment in `modules/billing/alembic/`

---

## Cross-references

- Spec §5.2 (Upload provenance data model), §5.4 (RBAC matrix), §5.5 (backend posture), §6.2 (uploads surface), §7.1 (canonical request flow), §8 (error handling), §9.1 (test layers), §9.3 (fixtures)
- Rules: `.claude/rules/financial-precision.md`, `.claude/rules/tenant-isolation.md`, `.claude/rules/security.md`, `.claude/rules/phi-compliance.md`, `.claude/rules/event-bus.md`, `.claude/rules/testing.md` (LESSON-001 SAVEPOINT, LESSON-004 regex anchors, LESSON-007 UUID)
- SP-1 Plan A: `docs/superpowers/plans/2026-05-16-sp1-plan-a-module-scaffold-inbox-spine.md` (HEAD `e97a1bb0`)
- SP-1 Plan C: consumes `Upload` model, `CyclesClient`, and Inbox feed
- Existing billing models (all in `modules/billing/src/models/tables.py`): `ClaimRecord` (line 39, table `claim_records`), `PaymentBatch` (line 214), `Invoice` (line 333), `InvoiceLineItem` (line 391), `JournalEntry` (line 478)
- Existing billing services: `modules/billing/src/services/{ar,ap,nacha,journal,claims,routing,budget,remittance_835}.py` (R2 fix to GC.10: `claims.py` DOES exist; `upload.py` is a NEW sibling)
- Event contract doc to be created: `docs/api-contracts/events/paysync.upload.parsed.md`
