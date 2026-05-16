# SP-1 Actual-Paths Inventory

**Purpose:** verified-from-HEAD inventory of paths/classes/functions/routes that SP-1 plans must cite correctly. Generated 2026-05-16 by the coordinator session to spare the plan-rewrite agent from re-verifying.

**Trust level:** every entry here was produced by running `grep -n` / `ls` / `cat` against the current working tree. The plan-writer must still verify before writing — this is a starting point, not a guarantee.

---

## 1. Repo packages root

| Wrong (do not use) | Right |
|---|---|
| `portal/packages/...` | `packages/...` |

`ls packages/` returns: `auth, contract, modules, qa-harness, scripts, shell, ui, README.md`. The spec §5.1 incorrectly uses `portal/packages/modules/paysync/` — that's a spec typo (CONCERN, not BLOCK). Plans should use `packages/modules/paysync/`.

## 2. `packages/shell/src/` structure

```
packages/shell/src/
  __mocks__/
  __tests__/
  _generated/
  auth/
  index.ts
  middleware.ts
  qa/
  routes/
  shell/
```

**There is no `packages/shell/src/types/` directory.** Plan A's claim that `packages/shell/src/types/module-config.ts` exists is wrong. The plan-rewrite agent must either:
- (a) `grep -rn "ModuleConfig" packages/shell/src/` to find what export currently represents the module-mount contract, OR
- (b) Add the type as part of Plan A's scope (create `packages/shell/src/types/module-config.ts` with an explicit interface).

## 3. Billing ORM classes

**Location:** all in `modules/billing/src/models/tables.py`. There is no `modules/billing/src/models/claims.py`.

| Class | Line |
|---|---|
| `BillingBase` (DeclarativeBase) | 30 |
| `ClaimRecord` | 39 |
| `RoutingRule` | 107 |
| `PaytoWaterfall` | 134 |
| `FileFormatMapping` | 147 |
| `APRecord` | 168 |
| `PaymentBatch` | 214 |
| `Payment` | 254 |
| `InvoicingConfig` | 296 |
| `Invoice` | 333 |
| `InvoiceLineItem` | 391 |
| `ARRecord` | 416 |
| `ARPayment` | 451 |
| `JournalEntry` | 478 |
| `ProgramBudget` / `ProgramBudgetAlert` / `ProgramBudgetSnapshot` | 528 / 575 / 602 |
| `FeeConfig` / `FundingConfig` / `PrefundLedger` | 629 / 662 / 684 |
| `RemittanceConfig` / `SFTPConfig` / `PaymentVendorConfig` | 713 / 729 / 754 |
| `BankAccount` / `AccountingConfig` / `BillingSequence` | 772 / 793 / 815 |

**Class-name remapping for Plan C** (codex BLOCK B3):
| Plan said | Actual |
|---|---|
| `Batch` | `PaymentBatch` |
| `PaymentRun` | also `PaymentBatch` (the API uses both names interchangeably) |
| `InvoiceLine` | `InvoiceLineItem` |
| `Carryover` | **not in billing models** — paysync-api.ts has `Carryover` type, but no ORM. Either a separate module owns it, or this is a NEW model SP-1 must add. The plan-writer must decide and document. |
| `BankSettlement` | not in billing. **`Settlement` IS in `modules/payment-processing/src/models/tables.py:138`.** |
| `Reconciliation` | not in billing. Likely tied to `Settlement` in payment-processing. |

## 4. Payment-processing ORM classes

**Location:** `modules/payment-processing/src/models/tables.py`.

| Class | Line |
|---|---|
| `VendorAdapter` | 36 |
| `Submission` | 88 |
| `Settlement` | 138 |
| `AchReturnCode` | 181 |
| `VendorHealthLog` | 195 |
| `OfacSdnEntry` | 212 |
| `OfacScreeningAlert` | 240 |
| `PayeeEnrollment` | 263 |

## 5. Billing API routes

**File:** `modules/billing/src/api/router.py`. These are the REAL routes the RBAC matrix in Plan C must cover (codex BLOCK B4).

```
POST   /claims                                            (line 93)
GET    /claims                                            (line 108)
GET    /claims/{claim_id}                                 (line 175)
GET    /routing-rules                                     (line 236)
POST   /routing-rules                                     (line 280)
PUT    /routing-rules/{rule_id}                           (line 290)
POST   /routing-rules/test                                (line 301)
GET    /ap                                                (line 316)
GET    /ap/summary                                        (line 375)
GET    /ap/{ap_id}                                        (line 429)
GET    /payment-batches                                   (line 485)
POST   /payment-batches/generate                          (line 533)
GET    /payment-batches/{batch_id}                        (line 543)
POST   /payment-batches/{batch_id}/validate               (line 592)
POST   /payment-batches/{batch_id}/approve                (line 602)
POST   /payment-batches/{batch_id}/submit                 (line 612)
POST   /payment-batches/{batch_id}/void                   (line 622)
GET    /payment-batches/{batch_id}/payments               (line 632)
POST   /settlement/record                                 (line 686)
GET    /settlement/unmatched                              (line 696)
GET    /invoicing-configs                                 (line 744)
POST   /invoicing-configs                                 (line 786)
PUT    /invoicing-configs/{config_id}                     (line 796)
GET    /invoices                                          (line 812)
POST   /invoices/generate                                 (line 871)
GET    /invoices/{invoice_id}                             (line 881)
GET    /invoices/{invoice_id}/pdf                         (line 941)
POST   /invoices/{invoice_id}/approve                     (line 951)
POST   /invoices/{invoice_id}/send                        (line 961)
POST   /invoices/{invoice_id}/void                        (line 971)
```

**RBAC matrix mapping (for Plan C):**
- Operator: GET on all; POST `/claims`, POST `/payment-batches/{id}/validate`
- Approver: POST `/payment-batches/{id}/approve|submit|void`, POST `/invoices/{id}/approve|send|void`, POST `/settlement/record`, POST `/routing-rules`, PUT `/routing-rules/{id}`, POST `/invoicing-configs`, PUT `/invoicing-configs/{id}`
- Auditor: GET only

The plan-writer should re-confirm against `modules/billing/src/api/router.py` and grep for any routes added since this inventory.

## 6. Payment-processing API routes

**File:** `modules/payment-processing/src/api/router.py`.

```
GET    /vendors                                           (line 59)
POST   /vendors                                           (line 73)
PUT    /vendors/{vendor_id}                               (line 109)
GET    /vendors/{vendor_id}/health                        (line 129)
GET    /submissions                                       (line 149)
GET    /submissions/{submission_id}                       (line 162)
POST   /submissions/{submission_id}/retry                 (line 174)
GET    /settlements                                       (line 205)
GET    /settlements/pending                               (line 218)
POST   /settlements/{settlement_id}/manual                (line 232)
GET    /returns                                           (line 257)
POST   /returns                                           (line 271)
GET    /returns/codes                                     (line 314)
GET    /enrollments                                       (line 343)
POST   /enrollments                                       (line 354)
GET    /enrollments/unenrolled                            (line 391)
GET    /dashboard                                         (line 410)
GET    /dashboard/reconciliation                          (line 430)
```

## 7. NACHA generators

**Two implementations:**

| Path | Symbol | Signature |
|---|---|---|
| `modules/billing/src/services/nacha.py:18` | `class NACHAPayment` | dataclass |
| `modules/billing/src/services/nacha.py:29` | `class NACHAGenerator` | `def generate(self, payments: list[NACHAPayment]) -> str` (line 60) |
| `modules/payment-processing/src/services/nacha_generator.py:47-85` | `NachaEntryDetail`, `NachaBatchConfig`, `NachaFileConfig`, `NachaGenerationResult` | dataclasses |
| `modules/payment-processing/src/services/nacha_generator.py:243` | `def generate_nacha_file(...)` | top-level function |

**Plan D was right about the function name (`generate_nacha_file`), wrong about the module** (it's in `payment-processing`, not `billing`). Plan D should import from `payment-processing.services.nacha_generator`. Codex flagged this as "invented" — it isn't, just mis-located.

## 8. Hash chain — `compute_entry_hash`

**File:** `modules/core-platform/src/audit/hash_chain.py`

**Signature (keyword-only):**
```python
def compute_entry_hash(
    *,
    tenant_id: UUID,
    action: str,
    entity_type: str | None,
    entity_id: str | None,
    created_at: datetime,
    previous_hash: str | None,
) -> str:
```

**Plan D BLOCK B6 fix:** sync hash-chain verifier must call `compute_entry_hash` with these exact kwargs in this exact order. Reading each `AuditEntry` row and recomputing its hash with the prior entry's hash as `previous_hash`. Plan D's `(prev_hash + action + who + when + payload)` formula will produce different hashes and false audit failures.

## 9. `echo/` route disposition (codex BLOCK B12)

**File:** `portal/operator/app/admin/paysync/echo/page.tsx`
**Description (from the file's own comment):** "Echo Spec 400 operations page — Wave 41 M6. Lists Spec 400 runs with status, totals, sha256 hashes; provides a manual-trigger button for the daily candor pipeline; surfaces recent status file ingestions. Wired to the Wave 41 admin API."

**Backend symbols** (in `portal/shared/lib/paysync-api.ts`):
- `EchoRunStatus` type (pending_submission | submitted | status_received | reconciled | failed)
- `EchoSpec400Run` interface
- `EchoSpec400ListQuery` interface
- `EchoStatusFileIngestion` interface
- `listEchoRuns()`, `listEchoIngestions()`, `runEchoCandor()` functions
- API path: `${PAYSYNC_BASE}/echo/spec-400-runs`

**Verdict for the plan-rewrite agent:** This is REAL operational functionality, not a debug route. **KEEP it.** Wrap into `packages/modules/paysync/src/surfaces/echo/` (NEW surface, add to the surface mapping in Plan A/B/E). Add an Inbox item kind `echo_run_status_received` or similar. Update Plan E §6 task to "wrap echo/ into module" instead of "evaluate before deleting."

## 10. Existing PaySync client base path (CONCERN)

The CONCERN says "Existing PaySync client points at adjudication-engine `/admin/paysync`, not billing." This means `portal/shared/lib/paysync-api.ts` has its base path pointing somewhere other than the billing service. Run `grep -n "PAYSYNC_BASE\|baseURL\|API_BASE" portal/shared/lib/paysync-api.ts` to find the actual base and document the migration path in a plan (likely Plan B or Plan E).
