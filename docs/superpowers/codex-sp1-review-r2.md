# SP-1 Plan Review R2

**Date:** 2026-05-16
**Reviewer:** Codex (OpenAI v0.130.0) via `/codex review`
**Prior review:** `docs/superpowers/codex-sp1-review-r1.md` (NO-GO, 12 BLOCKs)
**Plans reviewed:** HEAD~5..HEAD on branch wave/B10-w5

---

## Verdict: GO-WITH-CHANGES

11 of 12 BLOCK items from R1 are fixed. One BLOCK remains (B11). All 4 CONCERNs addressed.
B11 is a targeted fix — resolve it in Plan A before execution starts.

---

## B1–B12 Disposition

| # | Item | Verdict | Evidence |
|---|---|---|---|
| B1 | Invented SP-0 shell contract | **FIXED** | Plan A Task 5 explicitly states `packages/shell/src/types/module-config.ts` does not exist, requires a grep first, and creates/re-exports `ModuleConfig` if absent. |
| B2 | Wrong billing model paths | **FIXED** | Plan B now targets `modules/billing/src/models/tables.py` and `ClaimRecord` (line 39), with no dependency on nonexistent `models/claims.py`. |
| B3 | Wrong ORM class names | **FIXED** | Plan C remaps `Batch`/`PaymentRun` to `PaymentBatch`, `InvoiceLine` to `InvoiceLineItem`, adds `Carryover` as new scope, and uses payment-processing `Settlement` (not invented billing class). |
| B4 | Wrong backend endpoint matrix | **FIXED** | Plan C Task 2 lists the real `modules/billing/src/api/router.py` endpoints (all 15 mutating routes with line numbers) and audits exactly those paths. |
| B5 | Invented NACHA function | **FIXED** | Plan D uses `generate_nacha_file` from `modules/payment-processing/src/services/nacha_generator.py:243` and requires reading the signature before wrapping. |
| B6 | Hash verifier algorithm mismatch | **FIXED** | Plan D's verifier imports and calls `compute_entry_hash` with the exact keyword-only args (tenant_id, action, entity_type, entity_id, created_at, previous_hash) instead of reimplementing a different hash formula. |
| B7 | PHI/member data undercontrolled | **FIXED** | Plan B adds `PHIMixin`, no-store responses, prohibits `member_id` value echoing in row_errors, requires PHI access audit entry on read endpoints, and mandates tests for all three. |
| B8 | Tenant isolation gates incomplete | **FIXED** | Plans B/C/D require dedicated cross-tenant isolation tests for every new or modified endpoint (not just uploads list). |
| B9 | Event-bus compliance missing | **FIXED** | Plan B Task 3b adds `EventEnvelope`, `ordering_key=upload_id`, `idempotency_key="paysync:upload:{upload_id}:parsed"`, `schema_version="1.0"`, `@idempotent_handler` decorator, forward-compat test, and event contract doc at `docs/api-contracts/events/paysync.upload.parsed.md`. |
| B10 | Coverage gates violate Auto-Gate | **FIXED** | Plans A–E now specify ≥99% branch coverage for other active code (was 95%), with 100% on financial/security/PHI paths. |
| B11 | Stub artifacts gate-passable | **STILL-BLOCK** | Plan A still gates on: `src/bff/inbox.ts` returning `[]`, 12 surface `index.ts` stubs, and header-only CSV + empty JSON fixture files. Plan E also introduces an `EchoRunStatusCard` stub. See fix below. |
| B12 | echo/ route handling hand-wavy | **FIXED** | Plan E Task 6 explicitly keeps and wraps `echo/` into `packages/modules/paysync/src/surfaces/echo/`, adds `EchoClient`, route registration, `echo_run_status_received` inbox kind, E2E coverage, and deletes the original only after module-route E2E verification passes. |

---

## CONCERN Disposition

| # | Concern | Verdict | Evidence |
|---|---|---|---|
| C1 | Spec path `portal/packages/` vs `packages/` | **ADDRESSED** | Plans consistently use `packages/modules/paysync/`, matching inventory §1. |
| C2 | PaySync client base URL migration | **ADDRESSED** | Plan E requires `grep -n "PAYSYNC_BASE\|baseURL\|API_BASE" portal/shared/lib/paysync-api.ts` and documents migration path in `EchoClient` comments. |
| C3 | MFA/ePHI enforcement not tested | **ADDRESSED** | Plans B/C/D now explicitly require MFA gate tests (mfa_verified=False + mfa_required=True → 403) for every new PaySync route. |
| C4 | RoleSwitcherChip CI check incomplete | **ADDRESSED** | Plan E adds both the string-grep check AND a build-manifest scan that enumerates production chunks from `build-manifest.json` — proves qa-harness exports are unreachable, not just that the string was renamed. |

---

## B11 Fix Required (before execution starts)

The stub-as-done pattern in Plan A must be tightened. Specific gates to correct:

**Plan A Gate Criteria changes needed:**

1. **`src/bff/inbox.ts` stub:** The BFF returning `[]` is acceptable as a Plan A deliverable (Plan B replaces it), but the gate must NOT phrase this as "Inbox live" or "complete." Rephrase: "BFF stub exists; real implementation in Plan B."

2. **Surface `index.ts` stubs:** The current text already requires these to be typed `SurfaceConfig` constants that satisfy the route table shape (not empty objects). This is acceptable — `tsc -b` gates them. No change needed here; the text is correct.

3. **Fixture files:** Header-only CSV stubs and empty-array JSON stubs are explicitly scoped out of Plan A gates ("real data in Plan E"). The gate criteria already states this correctly. No change needed.

4. **Plan E `EchoRunStatusCard` stub:** Plan E's Task 6 introduces this stub. The gate must require this card to be a typed stub (accepts `item: InboxItem`, renders kind + data-testid, has a unit test) — same standard as Plan A's 11 typed stubs. Add this to Plan E gate: "EchoRunStatusCard exists as typed stub (not empty file); real implementation deferred to follow-on sprint."

**Conclusion:** B11 is narrower than R1 suggested. The surface stubs and fixture stubs are correctly scoped. Only the BFF stub description and EchoRunStatusCard stub need wording tightened. This is a plan-wording fix, not a structural redesign.

---

## Summary

- **11/12 BLOCKs FIXED** (B1–B10, B12)
- **1 BLOCK REMAINS** (B11 — stub artifact phrasing; targeted fix, not redesign)
- **4/4 CONCERNs ADDRESSED**
- **Overall verdict: GO-WITH-CHANGES** — fix B11 wording in Plans A and E, then execution may proceed.

tokens used: 108,002
