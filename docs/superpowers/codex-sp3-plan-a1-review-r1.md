# Codex Adversarial Review — SP-3 Plan A1 (Models + Alembic 0008 + RLS + Indexes)

**Date:** 2026-05-18
**Reviewer:** OpenAI Codex CLI (codex-cli 0.130.0, model_reasoning_effort=high)
**Plan reviewed:** `docs/superpowers/plans/2026-05-18-sp3-plan-a1-models-migration.md`
**Audit ground truth:** `waves/B10/SP-3-audit-deep.md`
**Prior NO-GO:** `docs/superpowers/codex-sp3-plan-a-review-r1.md` (8 BLOCKs on unified Plan A)
**Tokens used:** 701,753

---

## Verdict Table

| # | Concern | Severity | Plan task ref | Evidence (path:line) | Fix |
|---:|---|---|---|---|---|
| 1 | New ORM tables and Alembic tables do not describe the same physical tables. Models use `reclaimrx_*` public-style names, while migration creates unprefixed tables inside schema `reclaimrx`; FKs also diverge. | BLOCK | Task 1.2c / Task 2 | `docs/superpowers/plans/2026-05-18-sp3-plan-a1-models-migration.md:660`, `:720`, `:777`, `:835`, `:890`, `:944`, `:1430`, `:1493`, `:1561`, `:1617`, `:1682`, `:1737` | Align ORM and migration naming. Either create the prefixed ORM tables the models map to, or change models/FKs to schema-qualified unprefixed tables consistently. |
| 2 | Existing-table ALTERs target default-schema `reclaimrx_investigations` and `reclaimrx_payment_holds`, but existing Alembic pattern creates schema-scoped tables. The plan acknowledges both variants but does not resolve which table actually exists. | BLOCK | Task 2 | `docs/superpowers/plans/2026-05-18-sp3-plan-a1-models-migration.md:1814`, `:1855`; `modules/reclaimrx/alembic/versions/0007_flagged_npis.py:40`, `:71`; `modules/reclaimrx/src/models/tables.py:374`, `:588` | Make the migration target the real production tables deterministically. Do not "check both" only in tests; use the correct schema/table names or an explicit guarded migration path. |
| 3 | Tenant scoping instructions conflict. The plan claims `Base + TenantScopedMixin`, but model snippets use `Base` only with `String(36)` tenant IDs; shared `TenantScopedMixin` uses `SA_UUID(as_uuid=True)`. | BLOCK | BLOCK 3 resolution / Task 1.2c | `docs/superpowers/plans/2026-05-18-sp3-plan-a1-models-migration.md:58`, `:646`, `:663`; `shared/db/tenant_context.py:90`, `:93`; `modules/reclaimrx/src/models/tables.py:377`, `:591` | Choose one pattern and make the plan internally consistent. For this module, prefer existing `Base` + explicit `String(36)` unless the session/query stack is also updated for `TenantScopedMixin`. |
| 4 | The proposed unit test file contains invalid Python destructuring, so TDD fails before models are exercised. | BLOCK | Task 1.1 | `docs/superpowers/plans/2026-05-18-sp3-plan-a1-models-migration.md:223`, `:409` | Replace `(*_, GraphRun, *_)` / `(*_, OutboxEvent, *_)` with direct imports or single-star tuple unpacking. |
| 5 | SQLite fixture patches UUID types and calls `Base.metadata.create_all()` before importing `src.models.tables`, so new model tables may not be registered; `_UUIDString` also will not cover mixin UUID fields if mixins are used. | BLOCK | Task 1.1 / checklist 11 | `docs/superpowers/plans/2026-05-18-sp3-plan-a1-models-migration.md:99`, `:116`, `:121`, `:149` | Import/register all models before iterating metadata and before `create_all()`. Then apply UUID type substitution across the fully loaded metadata. |
| 6 | Investigation column count is wrong in plan text. The correct A1 scalar additions per spec are 12, not 11: the plan's own list includes 12. | CONCERN | Scope / Task 1.2a / Task 2 | `docs/superpowers/specs/2026-05-18-sp3-reclaimrx-portal-design.md:140`, `:153`; `docs/superpowers/plans/2026-05-18-sp3-plan-a1-models-migration.md:17`, `:476`, `:487`, `:1338`, `:1341` | Rename all "11 columns" references to "12 scalar columns" and explicitly state whether `notes` and `status_transitions` are deferred. |
| 7 | RLS null-deny test is not a reliable cross-tenant acceptance test. It resets the GUC, but seeds only 4 of 6 tables and never ensures the connection is a non-superuser/non-`BYPASSRLS` app role. | BLOCK | Task 3 | `docs/superpowers/plans/2026-05-18-sp3-plan-a1-models-migration.md:1958`, `:1965`, `:1971`, `:1979`, `:1989`, `:1995`, `:2003`, `:2021` | Seed all six tenant-owned tables, including `fraud_rings` and `accumulator_anomalies`; run assertions as the app role or `SET ROLE`; verify tenant A sees own rows and null/other tenant sees zero for every table. |
| 8 | Downgrade symmetry is incomplete. Partial unique indexes are created but not explicitly dropped before tables, and Investigation columns are dropped in the same order as upgrade, not reverse order. | CONCERN | Task 2 downgrade | `docs/superpowers/plans/2026-05-18-sp3-plan-a1-models-migration.md:1481`, `:1670`, `:1796`, `:1808`, `:1897`, `:1900`, `:1905` | Drop partial indexes explicitly before dropping tables; drop added columns in exact reverse order after dropping dependent constraints/indexes. |
| 9 | Audit says `PaymentHold` also lacks `idempotency_key`, but A1 only adds `status`. This leaves a schema gap unless intentionally deferred. | CONCERN | Scope / PaymentHold extension | `waves/B10/SP-3-audit-deep.md:157`, `:181`, `:572`; `docs/superpowers/plans/2026-05-18-sp3-plan-a1-models-migration.md:18`, `:633` | Add `PaymentHold.idempotency_key` with the required uniqueness semantics, or explicitly defer it to a named later plan with no A1 consumers depending on it. |

---

## Verdict

**NO-GO**

---

## Summary of BLOCKs (6 total)

| Block | Root cause |
|---|---|
| BLOCK 1 | ORM model `__tablename__` uses public-schema prefixed names (`reclaimrx_fraud_rings`) but migration creates unprefixed tables in `reclaimrx` schema — these refer to different physical tables |
| BLOCK 2 | ALTER TABLE in migration targets public-schema `reclaimrx_investigations` / `reclaimrx_payment_holds` but existing tables may live in `reclaimrx` schema — plan hedges with dual schema check in tests instead of fixing the migration |
| BLOCK 3 | Plan claims `Base + TenantScopedMixin` in scope section but model code uses `Base` only with `String(36)` — `TenantScopedMixin` from `shared/db/tenant_context.py` uses `SA_UUID(as_uuid=True)` which conflicts with existing module pattern |
| BLOCK 4 | Python syntax error in test file: `(*_, GraphRun, *_) = _import_models()` and `(*_, OutboxEvent, *_) = models[5]` are invalid — TDD step 1 would fail to even collect |
| BLOCK 5 | `Base.metadata.create_all(eng)` called before `_import_models()` is ever invoked — new models may not be registered in metadata at fixture setup time |
| BLOCK 6 | RLS null-deny test seeds only 4 of 6 new tables and uses a superuser connection — superusers bypass RLS by default, so the test does not prove the app role sees zero rows |

---

## Prior BLOCKs Status (from R1 NO-GO on unified Plan A)

| Prior BLOCK | Resolution in A1 | Status |
|---|---|---|
| BLOCK 1: PaymentHold.released_by already exists | A1 explicitly does NOT re-add it — only adds `status` | RESOLVED |
| BLOCK 2: Migration wrong table names | A1 partially fixes ORM names, but schema split still unresolved (new BLOCK 1+2 above) | PARTIALLY RESOLVED, NEW ISSUE |
| BLOCK 3: TenantScopedBase invented | A1 claims to use `Base + TenantScopedMixin` but code uses `Base` only | PARTIALLY RESOLVED, INTERNAL INCONSISTENCY |
| BLOCK 5: hold.hold_amount does not exist | A1 adds `hold_amount` as new Investigation column explicitly | RESOLVED |

---

## Recommendation

**Recommendation:** Fix the 6 BLOCKs before dispatching the executor — the most critical is BLOCK 1 (ORM/migration naming split) because an executor following the plan verbatim will create tables the application cannot find via ORM queries, which silently corrupts the data layer. BLOCK 4 (Python syntax error in TDD step) is the second highest blast radius because it prevents TDD from detecting any of the other issues at test-first time.
