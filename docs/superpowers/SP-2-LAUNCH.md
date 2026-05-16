# SP-2 Launch Packet — Directories Portal / Reference Data Control Plane

**Purpose:** self-contained handoff for a fresh Claude Code session window to plan + execute SP-2.
**Branch:** `wave/B10-w5`
**Status:** ✅ **Spec GO** — Codex consult passed after 3 rounds (`docs/superpowers/codex-sp2-spec-review-r1.md`). Plans not yet written.
**Created:** 2026-05-16 by the SP-1/SP-2 brainstorm session.

---

## What this is

SP-2 is the second vertical built on the SP-0 spine. Where SP-1 (PaySync) is a money-pipeline workflow, **SP-2 is a Reference Data Control Plane**: a unified browser + ingestion console over the ~15 static reference datasets the platform consumes (NPPES, NCPDP, FDB, FDA-NDC, FDA Orange/Purple Book, FDA shortages/REMS, HCPCS, ICD10-CM, CMS-ASP/NADAC, OFAC-SDN, SAM exclusions, medicaid, plus 3 confirmed loaders the agent surfaced as needing plan-writer reconciliation: rxnorm, oig_leie, dea_registrations).

Read-mostly. Operator mutations limited to: trigger ingestion, configure schedule, dismiss alerts. **No RBAC** — all authenticated users access static data (the user's decision).

---

## Artifacts

### Spec
- `docs/superpowers/specs/2026-05-16-sp2-directories-portal-design.md` (latest commit `475f9518`)
- 8 locked decisions D1-D8 (vertical, B9 dependency, datasets, IA, shippable bar, build approach, no-RBAC, deployable shape)

### Codex review
- `docs/superpowers/codex-sp2-spec-review-r1.md` (commit `6cba3c78`) — final GO. r1 + r2 were NO-GO; r3 passed.

### Plans
- **NOT YET WRITTEN.** SP-2 ends at spec. A fresh session must run the plan-writer (with the strict drafter discipline used for SP-1 r2).

---

## 8 locked scope decisions

| # | Decision | Choice |
|---|---|---|
| D1 | Vertical | Reference Data Control Plane (directories portal) |
| D2 | B9 dependency | UI-only in SP-2; B9 (FDB Tier B–D ingestion) closes as parallel B-wave. Drug surfaces mock with "pending B9" banner until B9 lands |
| D3 | Datasets in scope | **15 confirmed batch-loader sources → 6 browse clusters** (Prescribers / Pharmacies / Drugs / Codes / Pricing / Exclusions). `relay-health`, `fdb`, `bpg` have no batch loader (flagged §10). `rxnorm`, `oig_leie`, `dea_registrations` are confirmed loaders the spec couldn't bucket (flagged §10 for plan-writer) |
| D4 | IA | Search-First — Cmd+K command palette as centerpiece + federated typeahead + sidebar data-quality dashboard |
| D5 | Shippable bar | Cross-dataset round trip on synthetic data — ⌘K search → drill → provenance/freshness/audit → trigger ingestion → see delta → dismiss/escalate alert |
| D6 | Build approach | Approach A — Search spine first; per-dataset surfaces wired into search from day 1 |
| D7 | RBAC | **None.** All authenticated users access static reference data. Per user: "no RBAC needed, everyone will have access to static data." |
| D8 | Deployable shape | Module inside `portal/operator`; standalone deferred |

---

## Backend reality the spec encoded

The codex-corrected ingestion API (real backend paths):
- `/api/v1/data-ingestion/{source}/trigger` — POST
- `/api/v1/data-ingestion/{source}/status` — GET
- `/api/v1/data-ingestion/{source}/history` — GET
- `/api/v1/data-ingestion/runs/{run_id}` — GET
- `/api/v1/data-ingestion/upload/{source}` — POST (file upload)
- `/api/v1/data-ingestion/{source}/cancel` — POST
- `/api/v1/data-ingestion/field-catalog` — GET

**Auth boundary:** the backend ingestion router has NO auth dependency. The BFF is the auth gate. This aligns with D7 (no RBAC).

**Loader source naming:** `_SOURCE_NAME` underscore constants in loader files; not hyphenated keys. Some loaders use `_SOURCE` or `source_name` variants — spec flagged the inconsistency.

**Manifest filename:** `infrastructure/manifests/operator-dev.yml` (not `operator.yml` — that was a SP-1 plan typo).

**PHI posture:** **non-PHI**. NPPES, FDA, CMS, OFAC, SAM are all public reference data. SP-2 does not invoke `PHIMixin` / `EncryptedString` / `Cache-Control: no-store` — those are PaySync (claim/member) concerns, not directory concerns.

**EventEnvelope rule:** N/A for SP-2 — no new event types introduced. (If the plan-writer adds events, the SP-1 EventEnvelope rules in `.claude/rules/event-bus.md` apply.)

---

## Open spec gaps the plan-writer must resolve (§10)

1. **Ingestion API mount host** — confirm which module exposes `/api/v1/data-ingestion/*` (is it core-platform, or a dedicated module?). Spec defers to plan-writer to grep + decide.
2. **rxnorm / oig_leie / dea_registrations browse cluster assignment** — these confirmed loaders aren't in D3's 6 browse clusters. Plan-writer reconciles: either add to existing clusters or document as separate surfaces.
3. **relay-health canonical source** — no `_SOURCE_NAME` constant exists; spec flags whether this is a future loader, a manual-only source, or deprecated.
4. **medicaid/ surface label** — `medicaid` reference dir exists but doesn't fit cleanly into the 6 clusters. Plan-writer picks a placement.
5. **BPG live-API behavior in ingestion console** — BPG has no batch loader; might be a live API rather than a refreshable file. Plan-writer confirms behavior + UX treatment.

---

## Werkbench / project rules (same as SP-1)

- **Codex at every gate** — spec consult ✅ (3 rounds). Plan-writer must fire pre-execute consult before any plan execution. Per `framework/disciplines/wave-control-ledger.md`.
- **Co-Authored-By trailer** on every commit.
- **Decimal-only money** — N/A for SP-2 (no money operations), but reference-data ingestion that touches pricing (CMS-ASP, NADAC, BPG) must use Decimal at the storage boundary per `.claude/rules/financial-precision.md`.
- **Tenant isolation** — reference data is typically NOT tenant-scoped (it's shared); confirm this with the plan-writer. Per `.claude/rules/tenant-isolation.md`, if any table IS tenant-scoped it needs `TenantScopedMixin`.
- **Coverage gates:** 100% on security/auth paths; **99%** branch coverage elsewhere. (Not 95% — that was the SP-1 plan-writer's first error.)
- **Drafter discipline:** before writing any code sample in a plan, run `git show HEAD:<path>`. The SP-2 spec agent verified its citations; plan-writers must verify their own additions.
- **Test-first** per CLAUDE.md.
- **Token discipline:** Write skeleton + Edit per task. The SP-1 plan-writer hit the 32k cap multiple times on mono-blocks.

---

## Handoff prompt for fresh session (copy-paste)

```
You are continuing work on the InfinityRx PBM platform, branch wave/B10-w5.
Your job is to write SP-2 (Directories Portal / Reference Data Control Plane)
implementation plans from the spec.

START HERE — in this exact order:

1. Read docs/superpowers/SP-2-LAUNCH.md (this file).
2. Read docs/superpowers/codex-sp2-spec-review-r1.md — confirm GO verdict.
3. Read the spec: docs/superpowers/specs/2026-05-16-sp2-directories-portal-design.md
4. Read CLAUDE.md (project root) + .claude/rules/*.md.
5. Read docs/superpowers/sp1-actual-paths-inventory.md as the EXAMPLE of
   verified-from-HEAD discipline you must apply to YOUR plan paths.

6. Resolve §10 open spec gaps via grep against actual repo files:
   - grep for /api/v1/data-ingestion routes to find which module mounts them
   - grep loader files in modules/*/src/ingestion/ for _SOURCE_NAME constants
     to confirm rxnorm/oig_leie/dea_registrations location
   - Decide relay-health, medicaid, BPG dispositions

7. Decompose SP-2 into 3-5 plans following Approach A (search spine first):
   - Plan A: federated search infra + Cmd+K + ranking layer
   - Plan B: 6 browse clusters wired to search + per-dataset surfaces
   - Plan C: ingestion console + scheduled-job UI + alert dismissal
   - Plan D: data-quality dashboard + audit log viewer
   - Plan E (if needed): E2E round trip + qa-harness additions

8. For EACH plan, BEFORE writing any cited path/class/function/route,
   verify it with git show / grep / cat. Do not draft from imagination.
   The SP-1 plan-writer's r1 was NO-GO on 12 BLOCK items for exactly
   this failure — don't repeat it.

9. Commit each plan atomically:
   git commit -m "docs(sp-2): Plan X — ..." with Co-Authored-By trailer.

10. After all plans written, fire codex review:
    codex exec "Review SP-2 plans against HEAD~N..HEAD..." (template in
    SP-2-LAUNCH §8 below if you add one, otherwise model on the SP-1 r2
    review command in docs/superpowers/codex-sp1-review-r2.md).

11. If codex returns NO-GO, address findings and re-fire (up to 3 rounds).

12. Return a final report listing plans + commits + codex verdict.

You have authorization to make decisions that best fit the InfinityRx PBM
business model. The SP-1 plan rewrite at docs/superpowers/SP-1-LAUNCH.md is
a parallel deliverable from the originating session — do not touch SP-1
files.
```

---

## Cross-references

- SP-0 (foundation): `docs/superpowers/specs/2026-05-14-sp0-integration-foundation-design.md`
- SP-1 (PaySync vertical): `docs/superpowers/SP-1-LAUNCH.md` — sister vertical
- Werkbench discipline: `~/Documents/Code Projects/Werkbench/framework/disciplines/wave-control-ledger.md`
- Project rules: `.claude/rules/*.md`
- Reference data: `data/reference/` (24 dirs; 15 are batch-loader sources)
- Existing portal scaffolding: `portal/operator/app/admin/` (likely contains some directory views already — plan-writer surveys)
