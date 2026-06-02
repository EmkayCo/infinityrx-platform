# Rebuild vs Finish — Operator Portal Decision — 2026-05-21

**Question:** Is it faster to rebuild the operator portal frontend, or finish the existing one?

**Answer: FINISH. Do not rebuild.**

Evidence below. Detail per cluster in `docs/audit/depth-reaudit-{financial,claims,directory,analytics}-2026-05-21.md`.

---

## Built-vs-designed depth — 230 designed surfaces

| State | Count | % | Meaning |
|---|---|---|---|
| BUILT + WIRED | 90 | 39% | Done, reachable, matches design |
| BUILT, unwired | 13 | 6% | Component exists; needs a mount page + nav (~1d each) |
| SCAFFOLD | 39 | 17% | Basic version exists; needs upgrade to designed depth |
| NOT BUILT | 88 | 38% | No component |

Per cluster:
| Cluster | Designed | Wired | Unwired | Scaffold | Not built | Effort (pd) |
|---|---|---|---|---|---|---|
| Financial (billing/paysync/payments) | 49 | 15 | 11 | 16 | 7 | 38–52 |
| Claims/adjudication | 58 | 14 | 1 | 3 | 40 | 110–130 |
| Directory/member/FWA | 54 | 28 | 1 | 9 | 16 | ~103 |
| Analytics/admin/AI | 69 | 33 | 0 | 11 | 25 | 68–108 |
| **Total** | **230** | **90** | **13** | **39** | **88** | **~320–400** |

---

## Why finish, not rebuild

1. **The hard foundation is built and reusable.** Cross-cutting shell — command palette (cmdk), notification center (SSE from core-platform), 4 dashboard presets, drag-drop customizable widget grid (@dnd-kit), and the **shared WizardContainer framework** (already powering billing 6-step, payment-batch 5-step, investigation 5-step, report, client-onboarding wizards) — all BUILT_WIRED. A rebuild re-derives all of this from zero.
2. **The directories cluster is a complete, correct reference.** `@infinityrx/module-directories` (dist-compiled npm package, in manifest, BFF routes, portal wrappers): drug/pharmacy/prescriber search+detail, ingestion console, quality dashboard, audit viewer, exclusion screening, command-palette integration. This proves the platform's "done" pattern works end-to-end.
3. **38% NOT_BUILT is mostly intentionally-deferred Phase-5 modules** (switch-connectivity, rules-engine visual pipeline builder, prior-auth, program-config launch wizard, rebate) — per portal PRD §4.2 "Coming Soon." Planned future work, not decay.
4. **Reusability confirmed.** Financial-cluster audit: paysync primitives (MoneyDisplay, HashChainBadge, RbacGate, ProvenanceBreadcrumb) + the built wizards are genuine, salvageable work. Rebuild discards ~60% of real value.
5. **Rebuild is strictly slower.** Finish = build the missing ~55%. Rebuild = re-build the working 45% PLUS the missing 55%.

The earlier "wizard not built" read was a false alarm — that sub-agent only scanned `packages/modules/paysync`. The wizard framework lives in `portal/shared` and is in active use.

---

## The real problems (narrow, fixable — not "rotten frontend")

1. **3 competing nav systems.** Live sidebar = `portal/operator/components/layout/nav-config.ts` (hand-authored). `packages/shell/src/_generated/manifest.json` + each `module.config.ts` navTree are orphaned/not consumed. Pick one source of truth.
2. **Financial route drift.** `/billing/*`, `/accounting/*`, `/admin/paysync/*` — three trees over one billing domain. BillingCycleWizard redirects to `/billing/` while nav points at `/accounting/`; operators land in the wrong section. Consolidate to one (recommend `/admin/paysync/*` per the paysync brand + RBAC/audit layer).
3. **13 built-but-unwired surfaces** (mostly paysync: cycles, batches, invoices, reconciliations, carryovers, bank-settlements, payment-runs, journal) + nav links to unmounted routes → 404s.
4. **Upload bugs** (the trigger): nav entry missing for the wired uploads page; `.txt` blocked by client allowlist; CSV fails on Next.js 10MB body limit; upload-list GET 403s on x-tenant-id/JWT mismatch.
5. **39 scaffolds** to upgrade to designed depth; **88 surfaces** to build (mostly Phase-5).
6. **reclaimrx split personality** — 13 working portal routes but the npm package exports only `config` (empty sub-indexes), absent from manifest; investigation wizard uses mock data + a dead `/wizard` link.

---

## Recommended sequencing (finish, in waves)

- **F0 — Foundation cleanup (days):** pick one nav source; resolve `/billing` vs `/accounting` vs `/admin/paysync` drift (consolidate to paysync); fix the 4 upload bugs.
- **F1 — Wire the 13 built-unwired surfaces (~2 weeks):** mount pages + BFF + nav. Highest leverage; uploads vertical is the proven template.
- **F2 — Upgrade 39 scaffolds to designed depth.**
- **F3 — Build the 88 NOT_BUILT,** scoped as proper phases — most are the known Phase-5 modules (treat each as its own brainstorm→spec→plan→build).

Roughly half of the ~320–400pd is already-planned Phase-5 module work.

---

_Generated 2026-05-21 from 4 read-only depth re-audits. No code modified._
