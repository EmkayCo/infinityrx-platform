- MFA/ePHI enforcement is not explicitly tested for PaySync routes.
- RoleSwitcherChip bundle grep exists ([plan-e:150](docs/superpowers/plans/2026-05-16-sp1-plan-e-reports-setup-e2e.md:150)-[plan-e:163](docs/superpowers/plans/2026-05-16-sp1-plan-e-reports-setup-e2e.md:163)), but should also prove qa exports are unreachable in prod.

**Required before re-review**

Rewrite Plans A-D against actual repo paths/types/routes/functions; add a real `echo/` disposition task; raise coverage gates to 99%; remove gate-passing stubs; add explicit PHI, tenant, MFA, and EventEnvelope requirements with tests for every new route/event.
tokens used
108,002
I could not write `docs/superpowers/codex-sp1-review-r1.md`: the workspace is read-only and approval is disabled. I attempted the patch and it was rejected by the sandbox. Review content is below.

**Verdict: NO-GO**

Execution should not start. The spec intent is broadly covered, but the plans are not executable against the repo as written and miss mandatory project gates.

**BLOCK**

1. Invented SP-0 shell contract. Plan A says `ModuleConfig` exists at `packages/shell/src/types/module-config.ts` and is “confirmed on disk” ([plan-a:311](docs/superpowers/plans/2026-05-16-sp1-plan-a-module-scaffold-inbox-spine.md:311), [plan-a:460](docs/superpowers/plans/2026-05-16-sp1-plan-a-module-scaffold-inbox-spine.md:460)). It does not exist; `packages/shell/src` has nav/auth/qa files only.

2. Wrong billing model paths. Plan B modifies `modules/billing/src/models/claims.py` and depends on model files like `claims.py` / `journal.py` ([plan-b:81](docs/superpowers/plans/2026-05-16-sp1-plan-b-uploads-cycles.md:81), [plan-b:352](docs/superpowers/plans/2026-05-16-sp1-plan-b-uploads-cycles.md:352)). Actual billing models are in `modules/billing/src/models/tables.py`; `ClaimRecord` is there, not in `claims.py`.

3. Wrong ORM class names. Plan C says `Batch`, `InvoiceLine`, `PaymentRun`, `Carryover`, `BankSettlement`, `Reconciliation` are confirmed present ([plan-c:284](docs/superpowers/plans/2026-05-16-sp1-plan-c-batches-ar-ap.md:284)). Actual classes include `PaymentBatch`, `Payment`, `Invoice`, `InvoiceLineItem`; no `PaymentRun`/`Carryover`/`BankSettlement`/`Reconciliation` model was found.

4. Wrong backend endpoint matrix. Plan C audits `/billing/batches`, `/billing/payment-runs`, `/billing/reconciliations`, `/billing/settlements`, `/billing/manual-ap` ([plan-c:91](docs/superpowers/plans/2026-05-16-sp1-plan-c-batches-ar-ap.md:91)-[plan-c:98](docs/superpowers/plans/2026-05-16-sp1-plan-c-batches-ar-ap.md:98)). Actual billing routes are `/api/v1/billing/payment-batches/*`, `/invoices/*`, `/settlement/record`, `/ar/*`, etc. The RBAC audit would miss real mutating routes.

5. Invented NACHA function. Plan D says to call `generate_nacha_file(batch_id)` ([plan-d:124](docs/superpowers/plans/2026-05-16-sp1-plan-d-files-journal.md:124)). Actual `nacha.py` has `NACHAGenerator.generate(payments)`, no `generate_nacha_file`.

6. Hash verifier algorithm mismatch. Plan D proposes hashing `(prev_hash + action + who + when + payload)` ([plan-d:165](docs/superpowers/plans/2026-05-16-sp1-plan-d-files-journal.md:165)-[plan-d:167](docs/superpowers/plans/2026-05-16-sp1-plan-d-files-journal.md:167)). Existing core code uses `compute_entry_hash` over tenant/action/entity/created_at/previous_hash. This would create false audit failures.

7. PHI/member data is undercontrolled. Plan B stores/displays `member_id` and row errors as “opaque” ([plan-b:142](docs/superpowers/plans/2026-05-16-sp1-plan-b-uploads-cycles.md:142), [plan-b:265](docs/superpowers/plans/2026-05-16-sp1-plan-b-uploads-cycles.md:265)). PHI rules require PHIMixin for member/patient data, PHI read audit entries, no-store, and masking (`.claude/rules/phi-compliance.md:5`, `:14`, `:18`, `:19`). Missing route-level tests.

8. Tenant isolation gates are incomplete. Plan B only names a cross-tenant test for uploads list ([plan-b:194](docs/superpowers/plans/2026-05-16-sp1-plan-b-uploads-cycles.md:194)). Rules require cross-tenant tests for every API endpoint plus TenantScopedMixin/RLS (`.claude/rules/tenant-isolation.md:4`-`:8`, `:23`).

9. Event-bus compliance is missing. Spec adds `paysync.upload.parsed` ([spec:270](docs/superpowers/specs/2026-05-16-sp1-paysync-operator-portal-design.md:270)), but no plan requires `EventEnvelope`, `ordering_key`, `idempotency_key`, `schema_version`, idempotent consumers, or event contract docs (`.claude/rules/event-bus.md:4`-`:7`, `:11`, `:21`).

10. Gate criteria violate Auto-Gate. Plans use `≥95%` for other active code ([plan-a:434](docs/superpowers/plans/2026-05-16-sp1-plan-a-module-scaffold-inbox-spine.md:434), [plan-e:308](docs/superpowers/plans/2026-05-16-sp1-plan-e-reports-setup-e2e.md:308)). CLAUDE.md requires 99% branch coverage for other active code ([CLAUDE.md:140](CLAUDE.md:140)-[CLAUDE.md:141](CLAUDE.md:141)).

11. Plan A makes stubs gate-passable. It creates route/card/fixture stubs and counts them as complete ([plan-a:384](docs/superpowers/plans/2026-05-16-sp1-plan-a-module-scaffold-inbox-spine.md:384)-[plan-a:439](docs/superpowers/plans/2026-05-16-sp1-plan-a-module-scaffold-inbox-spine.md:439)). Testing rules prohibit placeholder/stub files at gate (`.claude/rules/testing.md:19`-`:22`).

12. `echo/` route handling is hand-wavy. Actual route exists at `portal/operator/app/admin/paysync/echo/page.tsx`, and the client has Echo functions. Plan E only says “evaluate; do not delete without checking” ([plan-e:260](docs/superpowers/plans/2026-05-16-sp1-plan-e-reports-setup-e2e.md:260)-[plan-e:262](docs/superpowers/plans/2026-05-16-sp1-plan-e-reports-setup-e2e.md:262)). Not adequate.

**CONCERN**

- Spec path says `portal/packages/modules/paysync/` ([spec:67](docs/superpowers/specs/2026-05-16-sp1-paysync-operator-portal-design.md:67)); plans use `packages/modules/paysync/`. Repo supports root `packages/modules/*`.
- Existing PaySync client points at adjudication-engine `/admin/paysync`, not billing. Migration inventory is missing.
- MFA/ePHI enforcement is not explicitly tested for PaySync routes.
- RoleSwitcherChip bundle grep exists ([plan-e:150](docs/superpowers/plans/2026-05-16-sp1-plan-e-reports-setup-e2e.md:150)-[plan-e:163](docs/superpowers/plans/2026-05-16-sp1-plan-e-reports-setup-e2e.md:163)), but should also prove qa exports are unreachable in prod.

**Required before re-review**

Rewrite Plans A-D against actual repo paths/types/routes/functions; add a real `echo/` disposition task; raise coverage gates to 99%; remove gate-passing stubs; add explicit PHI, tenant, MFA, and EventEnvelope requirements with tests for every new route/event.
