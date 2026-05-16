# SP-1 Plan B — Upload Resource + Cycles Surface Wiring

**Date:** 2026-05-16
**Sub-project:** SP-1 PaySync Operator Portal
**Status:** Ready for execution
**Depends on:** SP-1 Plan A (module scaffold + Inbox spine complete)

---

## §10 Plan-Time Decisions Owned by This Plan

| # | Decision | Resolution |
|---|---|---|
| §10.2 | Upload file storage strategy | Local disk under `{PAYSYNC_UPLOAD_DIR}/{tenant_id}/{upload_id}/{original_filename}`; `PAYSYNC_UPLOAD_DIR` defaults to `./data/uploads` relative to the billing module working dir; 90-day retention enforced by a nightly job `paysync.cleanup_old_uploads` registered in `operator-dev.yml` `required_jobs`; files are never deleted before 90 days even if upload is superseded (provenance immutability, spec §5.2) |
| §10.3 | CSV/Excel minimum schema | 8 mandatory columns: `ndc` (11 digits), `npi` (10 digits, Luhn-checked via 80840-prefix), `claim_id` (string, unique within upload), `date_of_service` (YYYY-MM-DD), `quantity` (positive Decimal, max 4dp), `days_supply` (positive integer), `amount_billed` (Decimal ≥ 0, max 4dp), `member_id` (string, non-empty); `source_platform` optional header comment (free-text, stored on Upload row); row errors are collected per-row and never abort the parse of other rows |

---

## Goal

Wire the Upload resource end-to-end and the Cycles surface. Specifically:

1. **Backend — Upload resource** (`modules/billing/`): new SQLAlchemy model `Upload`, Alembic
   migration, file-storage writer, CSV/Excel parser dispatcher, row-error capture, sha256 dedup,
   `upload_id` FK on existing `Claim` model, FastAPI router (`GET/POST /api/v1/billing/uploads`,
   `GET /api/v1/billing/uploads/{id}`, `GET /api/v1/billing/uploads/{id}/claims`).
2. **Backend — Inbox feed endpoint**: `GET /api/v1/billing/inbox?role=<role>` returns real
   `InboxItem` payloads derived from Upload + Cycle states.
3. **Frontend — `surfaces/uploads/`**: `UploadsListPage`, `UploadDropzone`, `UploadDetailPage`,
   `UploadClaimViewer`; BFF handlers `/api/paysync/uploads/*`.
4. **Frontend — `surfaces/cycles/`**: relocate + rewire existing
   `portal/operator/app/admin/paysync/cycles/` pages into the module; replace direct
   `paysync-api.ts` imports with the contract-layer `CyclesClient`; add `ProvenanceBreadcrumb`,
   `RbacGate` on close action.
5. **Inbox wired**: `useInboxItems` calls real BFF; upload and cycle Inbox item kinds show real
   items; Inbox card components (2 upload kinds + 2 cycle kinds) fully implemented.

This plan proves the upload-driven data flow end-to-end: CSV in → Upload row → Inbox item →
UploadDetailPage → Cycle view with provenance breadcrumb.

---

## Scope

**In:**
- `modules/billing/src/models/upload.py` — `Upload` ORM model + `UploadStatus` enum
- `modules/billing/src/services/upload.py` — parser dispatcher, sha256 dedup, row-error capture, file writer
- `modules/billing/alembic/versions/0011_add_upload_resource.py` — migration adding `uploads` table + `upload_id` FK on `claims`
- `modules/billing/src/api/uploads.py` — FastAPI router (5 endpoints)
- `modules/billing/src/api/inbox.py` — FastAPI router returning `InboxItem[]`
- `modules/billing/tests/unit/test_uploads.py` — parser, dedup, row-error, supersede semantics, upload_id propagation
- `modules/billing/tests/unit/test_verify_chain_sync.py` — placeholder (real tests in Plan D)
- `modules/billing/tests/integration/test_uploads_router.py` — 5 routes × RBAC matrix (3 roles)
- `modules/billing/tests/integration/test_inbox_router.py` — real items for each kind
- `packages/contract/src/paysync/uploads-client.ts` — `RealImpl` completed
- `packages/contract/src/paysync/cycles-client.ts` — `CyclesClient` interface + `RealImpl` + `MockImpl`
- `packages/modules/paysync/src/surfaces/uploads/` — all 4 upload UI components + BFF handlers
- `packages/modules/paysync/src/surfaces/cycles/` — rewired cycles pages + BFF handlers
- `packages/modules/paysync/src/bff/inbox.ts` — replaced stub with real call
- `packages/modules/paysync/src/inbox/cards/` — 4 card components implemented (upload × 2, cycle × 2)
- `packages/modules/paysync/fixtures/uploads/` — 3 CSV fixtures populated with real synthetic data
- `packages/modules/paysync/fixtures/seeds/users.json` — 3 synthetic users (Operator/Approver/Auditor)
- `packages/modules/paysync/fixtures/seeds/cycles.json` — 5 synthetic cycles
- `infrastructure/manifests/operator-dev.yml` — add `paysync.cleanup_old_uploads` to `required_jobs`

**Out:**
- Batches, AR/AP, payment runs (Plan C)
- Files (NACHA/835), journal (Plan D)
- Reports, setup, E2E round trip (Plan E)
- Carryovers, bank-settlements, reconciliations surfaces (wired in Plan C/D/E)

---

## Tasks

### Task 1 — Backend: Upload ORM model + migration

| # | Subject | Files touched | Test added | Deliverable |
|---|---|---|---|---|
| 1.1 | `Upload` ORM model | `modules/billing/src/models/upload.py` | unit test: model fields + enum transitions | `Upload` importable from billing models |
| 1.2 | Add `upload_id` FK to `ClaimRecord` model | `modules/billing/src/models/tables.py` (class `ClaimRecord`, line 39) | unit test: claim_record.upload_id not null FK | FK present on existing model |
| 1.3 | Alembic migration | `modules/billing/alembic/versions/0011_add_upload_resource.py` | migration runs upgrade + downgrade cleanly | schema updated |

**`Upload` model fields** (from spec §5.2, no deviation):
- `id` — `PG_UUID(as_uuid=True)`, PK
- `tenant_id` — `PG_UUID(as_uuid=True)`, NOT NULL, FK `tenants.id`, indexed `(tenant_id, created_at)`
- `filename` — `VARCHAR(512)`, NOT NULL
- `sha256` — `CHAR(64)`, NOT NULL; unique index `(tenant_id, sha256)` for dedup
- `file_size` — `BIGINT`, NOT NULL
- `mime_type` — `VARCHAR(128)`, NOT NULL
- `uploaded_at` — `TIMESTAMP WITH TIME ZONE`, NOT NULL, server_default=now()
- `uploaded_by` — `PG_UUID(as_uuid=True)`, NOT NULL, FK `users.id`
- `source_platform` — `VARCHAR(256)`, nullable
- `supersedes_upload_id` — `PG_UUID(as_uuid=True)`, nullable, FK `uploads.id` (self-referential)
- `status` — `VARCHAR(32)`, NOT NULL, default `'parsing'`; allowed: `parsing`, `validation_failed`, `validated`, `superseded`
- `row_count` — `INTEGER`, nullable (set after parse completes)
- `error_count` — `INTEGER`, nullable (set after parse completes)
- `row_errors` — `JSONB`, nullable (list of per-row error dicts; populated after parse)
- Inherits `TenantScopedMixin` (per `.claude/rules/tenant-isolation.md`)
- Inherits `PHIMixin` (`shared/db/models/phi_mixin.py`) — `member_id` values referenced in row_errors are PHI-adjacent; PHIMixin marks this model for PHI audit logging (per `.claude/rules/phi-compliance.md`)
- Inherits `AuditMixin` (every mutation audited per `.claude/rules/hipaa-2026.md`)

**PHI controls on `member_id`:**
- `member_id` appears in uploaded CSV rows and may appear in `row_errors` JSON.
- `Upload` itself does not store `member_id` as a top-level column — it propagates into `ClaimRecord` rows (which already have PHI encryption via `EncryptedString` on existing PHI columns per `.claude/rules/phi-compliance.md`).
- `row_errors` JSONB must NEVER store full `member_id` values in error messages — store only `"member_id: value too long"` or similar non-revealing descriptions. No PHI in log messages.
- All API responses containing `row_errors` MUST include `Cache-Control: no-store` header.
- Every read of upload row_errors by an authenticated user MUST emit a PHI access audit entry with `action="phi_access"`, `entity_type="upload"`, `entity_id=<upload_id>` (per `.claude/rules/phi-compliance.md`).
- `EncryptedString` (from `shared/crypto/sqlalchemy_types.py`) is NOT required on `Upload` model directly — but any future column storing `member_id` verbatim MUST use it.

**Migration rules:**
- `upload_id` FK on `ClaimRecord` is NULLABLE initially (existing claims have no upload; new claims require it at the service layer, not DB layer, so old data isn't broken)
- Index: `(upload_id)` on `claims` table for `GET /uploads/{id}/claims` query performance

- [ ] Step 1.1: Write `modules/billing/src/models/upload.py` with `Upload` model + `UploadStatus` enum; inherit `PHIMixin` + `TenantScopedMixin` + `AuditMixin`
- [ ] Step 1.2: Add `upload_id` nullable FK column to `ClaimRecord` in `modules/billing/src/models/tables.py` (line 39)
- [ ] Step 1.3: Write Alembic migration `0011_add_upload_resource.py`; verify upgrade + downgrade run cleanly on a fresh schema
- [ ] Step 1.4: Write unit tests for model fields, enum transitions, and PHIMixin inheritance
- [ ] Step 1.5: Run `modules/billing` tests — all pass
- [ ] Step 1.6: Commit — `feat(sp-1-b): Upload ORM model + alembic 0011 (upload_id FK on ClaimRecord in tables.py)`

---

### Task 2 — Backend: Upload service (parser + storage)

| # | Subject | Files touched | Test added | Deliverable |
|---|---|---|---|---|
| 2.1 | File writer + sha256 dedup | `modules/billing/src/services/upload.py` | unit: sha256 match returns existing upload | Dedup works |
| 2.2 | CSV parser dispatcher | `modules/billing/src/services/upload.py` | unit: valid CSV → Upload validated, claims written with upload_id | Claims tagged |
| 2.3 | Row-error capture | `modules/billing/src/services/upload.py` | unit: bad rows captured, status=validation_failed when all rows bad; partial bad → validated with error_count | Per-row errors |
| 2.4 | Excel parser dispatcher | `modules/billing/src/services/upload.py` | unit: `.xlsx` dispatches to openpyxl reader, same output shape | Excel supported |
| 2.5 | Supersede semantics | `modules/billing/src/services/upload.py` | unit: supersedes_upload_id set, old upload status → superseded, old claims NOT deleted | Immutable provenance |

**CSV minimum schema validation** (§10.3 resolution):

```python
REQUIRED_COLUMNS = {
    'ndc', 'npi', 'claim_id', 'date_of_service',
    'quantity', 'days_supply', 'amount_billed', 'member_id',
}
```

Validation per row:
- `ndc`: exactly 11 digits (`re.fullmatch(r'\A\d{11}\Z', value)` per LESSON-004)
- `npi`: exactly 10 digits + Luhn check with 80840 prefix validation
- `date_of_service`: `datetime.date.fromisoformat(value)` — no try/except swallowing
- `quantity`, `amount_billed`: `Decimal(str(value))` — must be ≥ 0, ≤ 4 decimal places; ROUND_HALF_UP
- `days_supply`: positive integer ≥ 1
- `member_id`: non-empty string, length ≤ 64

Row errors are stored as `List[Dict[str, str]]` on the upload row in a JSON column
`row_errors: JSONB` — added to migration `0011`. Never logged (may contain PHI-adjacent data
per `.claude/rules/phi-compliance.md`). Error messages in `row_errors` MUST describe the
validation failure without echoing the `member_id` value itself (e.g., `"member_id too long"`
not `"member_id 'ABC123...' exceeds 64 chars"`). This prevents PHI leakage into error storage.

**Storage layout** (§10.2 resolution):
```
{PAYSYNC_UPLOAD_DIR}/{tenant_id}/{upload_id}/{original_filename}
```
`PAYSYNC_UPLOAD_DIR` defaults to `./data/uploads`. Directory created on first write. File is
written atomically: write to `.tmp` suffix, rename on success. If billing module crashes mid-write,
the `.tmp` file is orphaned and cleaned up by the nightly cleanup job.

**Financial precision:** `amount_billed` and `quantity` stored as `Numeric(18, 4)` in claims —
no float at any stage. `Decimal(str(raw_value))` at parse time.

- [ ] Step 2.1: Write `modules/billing/src/services/upload.py` with all 5 service functions
- [ ] Step 2.2: Write `modules/billing/tests/unit/test_uploads.py` covering all unit cases in table above
- [ ] Step 2.3: Run unit tests — 100% branch coverage on service (financial + security paths)
- [ ] Step 2.4: Commit — `feat(sp-1-b): Upload service — parser, sha256 dedup, row-error capture, supersede`

---

### Task 3 — Backend: Upload + Inbox API routers

| # | Subject | Files touched | Test added | Deliverable |
|---|---|---|---|---|
| 3.1 | Upload router (5 endpoints) | `modules/billing/src/api/uploads.py` | integration: 5 routes × 3 roles | `POST /uploads`, `GET /uploads`, `GET /uploads/{id}`, `GET /uploads/{id}/claims`, `DELETE` (supersede only — no hard delete) |
| 3.2 | Inbox router | `modules/billing/src/api/inbox.py` | integration: each Inbox kind appears for correct data state | `GET /inbox?role=<role>` |
| 3.3 | Mount routers on billing app | `modules/billing/src/main.py` | integration: health check + auth-gated route responds | Routers live in production app |

**RBAC enforcement on upload router** (spec §5.4):
- `POST /uploads` — Operator + Approver; Auditor → 403
- `GET /uploads`, `GET /uploads/{id}` — all roles
- `GET /uploads/{id}/claims` — all roles
- `POST /uploads/{id}/supersede` — Operator + Approver; Auditor → 403

**Inbox endpoint logic:**
Returns `InboxItem[]` filtered by `role` query param. Derives items from:
- Uploads with `status=parsing` or `status=validation_failed` → `upload_pending_review` (Operator)
- Uploads with `status=validated` and no downstream batch yet → `upload_validated_awaiting_batching` (Operator)
- Cycles with `window_closed=true` and `status=open` → `cycle_pending_close` (Operator)
- Cycles with `status=closing` → `cycle_close_review` (Approver)

Items carry `upload_id` where derivable. `priority='high'` when upload has `error_count > 0` or
cycle window has been closed for > 24 hours.

**Auth:** all routes use `Depends(get_current_user)` per `.claude/rules/security.md` and SP-0
SD-1. Role checked against JWT `roles` claim.

**Tenant isolation:** all queries include `WHERE tenant_id = :current_tenant_id` via
`TenantScopedMixin` + `install_tenant_loader`. Per `.claude/rules/tenant-isolation.md`.

**Cross-tenant isolation (mandatory per `.claude/rules/tenant-isolation.md:23`):**
EVERY new endpoint in this plan (5 upload endpoints + 1 inbox endpoint + every BFF route)
MUST have a dedicated cross-tenant isolation test: create 2 tenants, seed data for both,
authenticate as Tenant A, assert zero Tenant B records appear in the response. This is not
optional. The cross-tenant test is a separate named test function for each endpoint, not a
shared helper.

**PHI access audit on upload row_errors read:** `GET /uploads/{id}` and
`GET /uploads/{id}/claims` MUST emit a PHI access audit entry with `action="phi_access"`,
`entity_type="upload"`, `entity_id=<upload_id>`, `user_id`, `tenant_id`. Add a test that
verifies the audit entry is written for each of these two endpoints.

**MFA / ePHI enforcement test:** add one test per new route that confirms a request with a
valid JWT but `mfa_verified=False` in the token claims returns 403 when
`tenant.mfa_required=True`. This verifies the MFA gate is enforced for ePHI-adjacent routes.

**Integration test pattern:** 3 roles × every new endpoint; plus dedicated cross-tenant test
per endpoint; plus PHI audit test per read endpoint; plus MFA gate test per endpoint.
Per `.claude/rules/testing.md` LESSON-001 SAVEPOINT pattern.

- [ ] Step 3.1: Write `modules/billing/src/api/uploads.py`
- [ ] Step 3.2: Write `modules/billing/src/api/inbox.py`
- [ ] Step 3.3: Mount routers in `modules/billing/src/main.py`
- [ ] Step 3.4: Write `modules/billing/tests/integration/test_uploads_router.py` — RBAC matrix (3 roles × 5 endpoints) + cross-tenant test per endpoint + PHI audit test for read endpoints + MFA gate test per endpoint
- [ ] Step 3.5: Write `modules/billing/tests/integration/test_inbox_router.py` — real items for each kind + cross-tenant test + MFA gate test
- [ ] Step 3.6: Run `modules/billing` full test suite — all pass, 100% on auth/RBAC/PHI paths
- [ ] Step 3.7: Commit — `feat(sp-1-b): billing Upload + Inbox routers, RBAC-gated, tenant-isolated, PHI-audited`

---

### Task 3b — Backend: `paysync.upload.parsed` event (EventEnvelope compliance)

The spec (§5.5 and spec line 270) requires a `paysync.upload.parsed` event when an upload
completes parsing. This task wires the event-bus publication and consumer per
`.claude/rules/event-bus.md`.

**Event publication** (in `modules/billing/src/services/upload.py`, at end of parse step):

```python
from shared.events.bus import EventBus
from shared.events.envelope import EventEnvelope

envelope = EventEnvelope(
    event_type="paysync.upload.parsed",
    payload={
        "upload_id": str(upload.id),
        "tenant_id": str(upload.tenant_id),
        "status": upload.status,
        "row_count": upload.row_count,
        "error_count": upload.error_count,
    },
    ordering_key=str(upload.id),                          # per event-bus rule: entity ID
    idempotency_key=f"paysync:upload:{upload.id}:parsed", # per event-bus rule: business-level key
    schema_version="1.0",                                 # per event-bus rule: required
    tenant_id=str(upload.tenant_id),                      # per event-bus rule: required on envelope
)
await event_bus.publish(envelope)
```

**Event contract doc:** `docs/api-contracts/events/paysync.upload.parsed.md` — created in this
task. Content: event type, schema version, payload fields, ordering key, idempotency key,
publisher (billing/upload service), consumers (paysync module Inbox feed derivation).

**Consumer** (in `modules/billing/src/api/inbox.py` or a dedicated consumer module):
The consumer handler MUST be wrapped with `@idempotent_handler` decorator per
`.claude/rules/event-bus.md:11`. The handler derives the Inbox item from the event payload.

**Unknown fields:** consumer must handle `schema_version` > `"1.0"` gracefully by ignoring
unknown payload fields (forward-compat, per `.claude/rules/event-bus.md`).

**Tests:**
- Unit: `upload.service.parse_complete` publishes `EventEnvelope` with correct `ordering_key`,
  `idempotency_key`, `schema_version`, `tenant_id`
- Unit: consumer handler decorated with `idempotent_handler`; duplicate event is no-op
- Unit: consumer handles payload with extra unknown fields (forward-compat test)
- Integration: POST upload → event emitted → Inbox endpoint returns `upload_pending_review` item

- [ ] Step 3b.1: Add `paysync.upload.parsed` event publication to upload service using `EventEnvelope` with all required fields
- [ ] Step 3b.2: Write `@idempotent_handler`-decorated consumer in inbox/upload consumer module
- [ ] Step 3b.3: Write `docs/api-contracts/events/paysync.upload.parsed.md` event contract doc
- [ ] Step 3b.4: Write unit tests for event publication + consumer (including forward-compat test)
- [ ] Step 3b.5: Write integration test: upload → event → Inbox item
- [ ] Step 3b.6: Run tests — all pass, 100% on event-bus paths
- [ ] Step 3b.7: Commit — `feat(sp-1-b): paysync.upload.parsed event — EventEnvelope, ordering_key, idempotent_handler, contract doc`

---

### Task 4 — Contract: UploadsClient + CyclesClient real implementations

| # | Subject | Files touched | Test added | Deliverable |
|---|---|---|---|---|
| 4.1 | `UploadsClient` `RealImpl` | `packages/contract/src/paysync/uploads-client.ts` | type test: return types assignable to `Upload` | Real HTTP calls to billing |
| 4.2 | `CyclesClient` interface + impls | `packages/contract/src/paysync/cycles-client.ts` | mock returns fixture data | Both impls present |
| 4.3 | `InboxClient` `RealImpl` | `packages/contract/src/paysync/inbox-client.ts` | type test | Real `/inbox` call |

Pattern: each client follows existing `paysync-api.ts` conventions in `portal/shared/lib/`.
`RealImpl` wraps `fetch` with the SP-0 auth header injection from `packages/auth`. `MockImpl`
returns typed fixture data from `packages/modules/paysync/fixtures/`.

**Shared `Upload` response type** (placed in `packages/contract/src/paysync/types.ts`):
```ts
export type UploadStatus = 'parsing' | 'validation_failed' | 'validated' | 'superseded';

export type Upload = {
  id: string;
  tenant_id: string;
  filename: string;
  sha256: string;
  file_size: number;
  mime_type: string;
  uploaded_at: string;
  uploaded_by: string;
  source_platform: string | null;
  supersedes_upload_id: string | null;
  status: UploadStatus;
  row_count: number | null;
  error_count: number | null;
};
```

- [ ] Step 4.1: Complete `UploadsClient` `RealImpl` + `MockImpl`
- [ ] Step 4.2: Write `CyclesClient` interface + both impls
- [ ] Step 4.3: Complete `InboxClient` `RealImpl`
- [ ] Step 4.4: Add `Upload` type + `UploadStatus` to `packages/contract/src/paysync/types.ts`
- [ ] Step 4.5: `tsc -b` clean
- [ ] Step 4.6: Commit — `feat(sp-1-b): contract UploadsClient + CyclesClient real/mock impls`

---

### Task 5 — Frontend: uploads surface

| # | Subject | Files touched | Test added | Deliverable |
|---|---|---|---|---|
| 5.1 | `UploadsListPage` | `surfaces/uploads/UploadsListPage.tsx` | RTL: renders table, status badge, sha256 dedup banner | List view |
| 5.2 | `UploadDropzone` | `surfaces/uploads/UploadDropzone.tsx` | RTL: file select triggers POST, progress shown, 409 dedup handled | Upload UI |
| 5.3 | `UploadDetailPage` | `surfaces/uploads/UploadDetailPage.tsx` | RTL: parse status, row-error list, link to claim viewer | Detail view |
| 5.4 | `UploadClaimViewer` | `surfaces/uploads/UploadClaimViewer.tsx` | RTL: scoped to upload_id, reuses `PaginatedTable` | Scoped claim view |
| 5.5 | BFF handlers | `surfaces/uploads/bff/` (route.ts files) | — | Next.js route handlers |
| 5.6 | Update surface `index.ts` | `surfaces/uploads/index.ts` | — | Surface wired |

**UploadDropzone** — multipart POST to `/api/paysync/uploads` (BFF). BFF proxies to
`UploadsClient.create(stream)`. Progress bar uses `XMLHttpRequest.upload.onprogress`. On 409
response from backend (sha256 dedup): renders "Already uploaded — [view existing upload #N]"
banner linking to existing upload's detail page.

**Error handling** (spec §8):
- Parse errors → `UploadDetailPage` row-error list; `member_id` is a PHI field and MUST NOT be displayed in the row-error list — show only the validation failure description (e.g., "Row 12: member_id too long"). `Cache-Control: no-store` on every response containing `row_errors`. Reading row_errors emits a PHI access audit entry (per `.claude/rules/phi-compliance.md`).
- RBAC denial → `RbacGate` soft-disables upload button for Auditor role
- Backend down (write path) → fail-fast, no optimistic update, error toast with correlation_id

- [ ] Step 5.1–5.4: Write all 4 upload UI components
- [ ] Step 5.5: Write BFF route handlers under `surfaces/uploads/bff/`
- [ ] Step 5.6: Update `surfaces/uploads/index.ts` to export real components
- [ ] Step 5.7: Write RTL tests for each component
- [ ] Step 5.8: Run tests — all pass
- [ ] Step 5.9: Commit — `feat(sp-1-b): uploads surface — dropzone, list, detail, claim viewer`

---

### Task 6 — Frontend: cycles surface rewire + inbox cards

| # | Subject | Files touched | Test added | Deliverable |
|---|---|---|---|---|
| 6.1 | Relocate cycles pages | `surfaces/cycles/` (move from `portal/operator/app/admin/paysync/cycles/`) | — | Pages in module |
| 6.2 | Replace `paysync-api` imports | `surfaces/cycles/*.tsx` | RTL: mock toggle works | Contract-layer |
| 6.3 | Add `RbacGate` on close action | `surfaces/cycles/CycleDetailPage.tsx` | RTL: Operator sees disabled close, Approver enabled | RBAC enforced |
| 6.4 | Add `ProvenanceBreadcrumb` | `surfaces/cycles/CycleDetailPage.tsx` | RTL: breadcrumb renders upload chain | Provenance shown |
| 6.5 | BFF handlers | `surfaces/cycles/bff/` | — | Route handlers |
| 6.6 | Inbox cards (4 kinds) | `src/inbox/cards/UploadPendingReviewCard.tsx`, `UploadValidatedCard.tsx`, `CyclePendingCloseCard.tsx`, `CycleCloseReviewCard.tsx` | RTL: renders key fields, click handler fires | Cards functional |
| 6.7 | `useInboxItems` wired | `src/bff/inbox.ts` replaced with real call | RTL: hook returns items from mock client | Inbox live |

**Cycles rewire notes:**
- Existing pages at `portal/operator/app/admin/paysync/cycles/[cycleId]/page.tsx` and
  `portal/operator/app/admin/paysync/cycles/page.tsx` are copied (not moved) into the module in
  Plan B; the originals are deleted in Plan E after E2E confirms the module routes work.
  This avoids breaking the portal during incremental wiring.
- Replace: `import { ... } from '@shared/lib/paysync-api'` → `import { CyclesClient } from '@infinityrx/contract/paysync/cycles-client'`
- `ProvenanceBreadcrumb` chain for a cycle: `[{ label: 'Upload #N', href: '/admin/paysync/uploads/{upload_id}' }, { label: 'Cycle {id}', href: '...' }]`

**Fixtures populated** (Plan B fills real synthetic data):
- `fixtures/uploads/upload-001-healthy.csv` — 20 rows, all columns valid, NDC/NPI Luhn-correct
- `fixtures/uploads/upload-002-validation-fail.csv` — 20 rows all failing (bad NDC, bad dates)
- `fixtures/uploads/upload-003-half-bad.csv` — 30 rows, 10 with bad NDC
- `fixtures/seeds/users.json` — 3 users (synthetic names, no real data)
- `fixtures/seeds/cycles.json` — 5 cycles in states: 2 open, 1 closing, 1 closed, 1 error

- [ ] Step 6.1: Copy cycles pages into `surfaces/cycles/`
- [ ] Step 6.2: Replace `paysync-api` imports with `CyclesClient`
- [ ] Step 6.3: Add `RbacGate` on cycle close button
- [ ] Step 6.4: Add `ProvenanceBreadcrumb` to `CycleDetailPage`
- [ ] Step 6.5: Write BFF handlers
- [ ] Step 6.6: Implement 4 inbox card components
- [ ] Step 6.7: Replace `src/bff/inbox.ts` stub with real call to `InboxClient`
- [ ] Step 6.8: Populate fixture CSV + JSON files with real synthetic non-PHI data
- [ ] Step 6.9: Write/update RTL tests
- [ ] Step 6.10: Run all tests — pass
- [ ] Step 6.11: Commit — `feat(sp-1-b): cycles surface rewire + 4 inbox cards + fixtures`

---

## Gate Criteria

Plan B is complete when ALL of the following are true:

- [ ] `modules/billing` full test suite passes; 100% coverage on upload service (financial: Decimal parsing; security: auth/RBAC; PHI: tenant isolation, PHI access audit, member_id non-echo in row_errors); **≥99% branch coverage** on all other active billing code added in this plan (CLAUDE.md Auto-Gate)
- [ ] Migration `0011` runs `upgrade` and `downgrade` cleanly on a fresh schema
- [ ] `GET /api/v1/billing/inbox?role=operator` returns ≥1 item given a seeded database with an upload in `validation_failed` state
- [ ] `POST /api/v1/billing/uploads` with a duplicate file returns 409 with existing upload reference
- [ ] Cross-tenant isolation test passes for EVERY new endpoint (6 endpoints): Tenant A cannot see Tenant B data
- [ ] PHI access audit entry written when `GET /uploads/{id}` or `GET /uploads/{id}/claims` is called (verified by test)
- [ ] MFA gate test: request with `mfa_verified=False` JWT + `mfa_required=True` tenant returns 403 on every new route
- [ ] `paysync.upload.parsed` event published with `EventEnvelope`, correct `ordering_key`, `idempotency_key`, `schema_version="1.0"`, `tenant_id` (verified by unit test)
- [ ] Consumer handler decorated with `@idempotent_handler`; duplicate event is a no-op (verified by unit test)
- [ ] `docs/api-contracts/events/paysync.upload.parsed.md` exists and documents event contract
- [ ] `npm --workspace=@infinityrx/module-paysync test` passes; 100% coverage on `MoneyDisplay`/`MoneyInput`/`RbacGate`; **≥99% branch coverage** on uploads + cycles surface components
- [ ] `tsc -b` clean across workspace
- [ ] `UploadsListPage` renders sha256 dedup banner in RTL test
- [ ] Cycles detail page shows `ProvenanceBreadcrumb` and disabled close button for Operator role in RTL test
- [ ] All 3 CSV fixtures populated with real synthetic non-PHI data (no placeholder headers only)
- [ ] `fixtures/seeds/users.json` contains 3 users with Operator/Approver/Auditor roles
- [ ] `Cache-Control: no-store` verified on all responses returning `row_errors` (integration test)

---

## Deliverables

- `Upload` ORM model, migration, service, and 5-endpoint router — the foundational backend resource for all of SP-1
- `GET /api/v1/billing/inbox` — live Inbox feed for upload + cycle item kinds
- `UploadsClient` + `CyclesClient` + `InboxClient` real implementations
- Uploads surface (4 components + BFF) — fully functional against real backend
- Cycles surface — rewired to contract layer, RBAC-gated, provenance-breadcrumbed
- 4 Inbox card components (upload × 2, cycle × 2) — functional with click-through nav
- Populated CSV fixtures + user/cycle seed JSON

---

## Dependencies

- SP-1 Plan A complete (package skeleton, primitives, Inbox taxonomy, contract stubs)
- `modules/billing` existing models in `modules/billing/src/models/tables.py` — specifically `ClaimRecord` (line 39), `PaymentBatch` (line 214), `Invoice` (line 333), `InvoiceLineItem` (line 391) — no separate `claims.py` or `journal.py` files
- SP-0 auth/JWT infrastructure (`get_current_user` dependency available in billing module)
- `shared/db/models/tenant_scoped_mixin.py` and `install_tenant_loader` (per `.claude/rules/tenant-isolation.md`)
- `shared/db/models/phi_mixin.py` `PHIMixin` — required on `Upload` model (member_id PHI proximity)
- `shared/crypto/sqlalchemy_types.py` `EncryptedString` — not used on `Upload` model directly, but required on any future column storing `member_id` verbatim
- `shared/events/envelope.py` `EventEnvelope` and `shared/events/bus.py` `EventBus` — required for `paysync.upload.parsed` event
- Alembic environment in `modules/billing/alembic/`

---

## Cross-references

- Spec §5.2 (Upload provenance data model), §5.4 (RBAC matrix), §5.5 (backend posture), §6.2 (uploads surface), §7.1 (canonical request flow), §8 (error handling), §9.1 (test layers), §9.3 (fixtures)
- Rules: `.claude/rules/financial-precision.md`, `.claude/rules/tenant-isolation.md`, `.claude/rules/security.md`, `.claude/rules/phi-compliance.md`, `.claude/rules/testing.md` (LESSON-001 SAVEPOINT, LESSON-004 regex anchors, LESSON-007 UUID)
- SP-1 Plan A: `docs/superpowers/plans/2026-05-16-sp1-plan-a-module-scaffold-inbox-spine.md`
- SP-1 Plan C: consumes `Upload` model, `CyclesClient`, and Inbox feed
- Existing billing models (all in `modules/billing/src/models/tables.py`): `ClaimRecord` (line 39), `PaymentBatch` (line 214), `Invoice` (line 333), `InvoiceLineItem` (line 391), `JournalEntry` (line 478)
- Existing billing services: `modules/billing/src/services/{nacha,ar,ap}.py` (no separate `claims.py` — claim logic lives in the router and tables.py)
- Event contract doc to be created: `docs/api-contracts/events/paysync.upload.parsed.md`
