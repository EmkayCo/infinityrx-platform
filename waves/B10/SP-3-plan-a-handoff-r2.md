# SP-3 Plan A — Handoff to next session (R2 orchestrator-pattern attempt)

**Date:** 2026-05-18
**Status:** Plan A R1 NO-GO from codex; main session ran out of orchestration budget; checkpoint here.

---

## The Werkbench lesson this session surfaces

The `/werkbench` activation at the top of this session **printed the ORCHESTRATOR MODE banner** (2 retroactive waves without GO triggered it) and then the main window proceeded to do **all substantive work in-process**:

- 5 codex spec rounds (R1 → R5)
- Deep file-survey audit of `modules/reclaimrx`
- 1,240-line Plan A draft
- Codex Plan A R1 review

Per `framework/disciplines/orchestrator-protocol.md`, every one of those was a candidate for `Agent(isolation:"worktree")` dispatch. The main window should have stayed thin and consumed only the structured return blocks from subagents — not done the work itself.

**Why this matters now:** main-window context is deep (≥80% used). The codex Plan A review surfaced 8 BLOCKS that need targeted plan fixes, and the audit-revealed scope (33 tasks across migration + outbox + scheduler + accumulator + graph + 18 endpoints + contract + frontend) is genuinely too large for one plan. Continuing in this window risks shallow fixes; a fresh session orchestrating sub-sessions per the protocol will produce cleaner output.

**Discipline correction baked into this handoff:** the next session must use Agent dispatch for every substantive piece. Main window only orchestrates, reviews returns, merges sub-session ledgers via `framework/bin/merge-subsessions`, and gates progression.

---

## What's committed and where

**Spec (codex-converged, 5 rounds):**
- `docs/superpowers/specs/2026-05-18-sp3-reclaimrx-portal-design.md` — the binding spec; D1-D14 locked
- `docs/superpowers/codex-sp3-spec-review-r{1,2,3,4,5}.md` — review trail
- `waves/B10/SP-3-design-draft.md` — R5 draft (history)
- Spec commit: `f0de9aaf docs(sp-3): brainstorm spec + 5-round codex consult convergence`

**Plan A draft (NO-GO — needs rework):**
- `docs/superpowers/plans/2026-05-18-sp3-plan-a-backend-contract-scaffold.md` — 1,240 lines, R1 NO-GO from codex
- `docs/superpowers/codex-sp3-plan-a-review-r1.md` — codex review listing 8 BLOCKS + 5 CONCERNS + 2 ADVISORIES

**This handoff:** `waves/B10/SP-3-plan-a-handoff-r2.md` (this file).

---

## Codex Plan A R1 NO-GO — the 8 BLOCKS (verbatim summaries)

All 8 are factual mismatches between Plan A draft and actual `modules/reclaimrx` codebase. My audit was shallow — I grepped class/endpoint names but didn't read implementations. Codex caught it.

| # | BLOCK | Reality the plan missed | Source path codex cited |
|---|---|---|---|
| 1 | Plan adds `PaymentHold.released_by` column | Already exists | `modules/reclaimrx/src/models/tables.py:607` |
| 2 | Migration uses table names `investigation`, `payment_hold`, `accumulator_detection` + FK `investigation.id` | Real `__tablename__` values are `reclaimrx_investigations`, `reclaimrx_payment_holds`, `reclaimrx_accumulator_detections` | `tables.py:374, 491, 588` |
| 3 | Plan invents `TenantScopedBase` base class | Real models use plain `Base` + explicit `tenant_id` columns; no tenant-mixin base class exists | `modules/reclaimrx/src/models/tables.py` |
| 4 | Plan writes envelope with `"type"` and `"emitted_at"` keys | Real `EventEnvelope` requires `event_type`, `correlation_id`, `source_module` per shared types | `shared/events/types.py:43` |
| 5 | Plan uses `hold.hold_amount` field; tests only cover same-actor different-reason replay → 200 OR different-actor → 409. Missing: same-actor SAME reason replay → 200 (true idempotent) | Real PaymentHold field is `amount_threshold`; spec §7.2 requires all 3 idempotency cases | `tables.py:588`, spec §7.2 |
| 6 | Plan endpoint snippets use `user.get("roles") or []` (dict access) | Real `CurrentUser` is a dataclass with `.roles` and `.has_role()` method | `modules/reclaimrx/src/_shim/auth.py:9` |
| 7 | Plan uses Python `hash(("graph_run", str(tenant_id)))` for advisory-lock key | Python `hash()` is process-randomized by default (PYTHONHASHSEED); not cross-process stable. Need deterministic hash (e.g., crc32, fnv, or md5-derived int) | spec §7.3 + practical Postgres advisory-lock requirements |
| 8 | Tasks 9, 10, 15, 21, 30 are abbreviated as "Steps mirror prior tasks" or one-paragraph summaries without TDD steps | Violates writing-plans skill's no-placeholders rule | plan §various |

## Codex CONCERN 5 (load-bearing):

> "Plan A is oversized. 33 tasks combine schema migration, outbox, DLQ, Redis idempotency, scheduler, graph job, accumulator detector, 18 endpoints, contract layer, and frontend scaffold. Given the number of unresolved path/name mismatches, split before execution."

**This is the right path: split Plan A into A1-A5 per the user's chosen approach.**

---

## Next-session orchestrator playbook (the actual handoff)

### Step 0: Initial setup (main window — keep light)

1. Run `/werkbench` to refresh ORCHESTRATOR MODE banner.
2. Read THIS handoff (`waves/B10/SP-3-plan-a-handoff-r2.md`).
3. Read the spec ONLY to anchor: `docs/superpowers/specs/2026-05-18-sp3-reclaimrx-portal-design.md` §1-§4 (problem, goals, non-goals, locked decisions). Do NOT read the rest in main window — load it via subagents as needed.
4. **Do not read large existing files in the main window.** That's what burned this session's context.

### Step 1: Deep audit subagent (BEFORE writing any plan)

Dispatch one subagent with `isolation:"worktree"`:

```
Agent(
  description: "Deep audit of modules/reclaimrx for SP-3 Plan A rewrite",
  subagent_type: "general-purpose",
  isolation: "worktree",
  prompt: """
Read the SP-3 spec at docs/superpowers/specs/2026-05-18-sp3-reclaimrx-portal-design.md
to understand intent. Then read these files in full and produce a structured
audit doc at waves/B10/SP-3-audit-deep.md with the following sections:

1. tables.py — list every class with: __tablename__, all columns (name + type +
   nullable), all relationships, all mixins/base classes. Flag any column the
   spec asserted as NEW that already exists.

2. shared/events/types.py — EventEnvelope dataclass: list all fields with types,
   defaults, validators. Show one example of correct construction.

3. modules/reclaimrx/src/_shim/auth.py — CurrentUser dataclass: list fields,
   methods (e.g., has_role), and how it's used in dependency injection.

4. modules/reclaimrx/src/api/router.py — list every route with: HTTP method,
   path, prefix, response_model, dependencies (auth/role/tenant), schema names.
   Show the router prefix (line ~54 cited by codex).

5. packages/contract/src/ — list the actual layout (not the assumed
   clients/schemas/impls/cache split). Codex says it's under
   src/impls/prescriber-directory/* — confirm and document the real structure.

6. shared/events/dlq.py + shared/events/idempotency.py — list available classes
   and methods relevant to DLQ persistence + durable idempotency.

7. shared/scheduling/ — confirm APScheduler integration pattern; if absent,
   document what's there.

8. Spec D14 binding check: for each of the 6 required bindings (SecurityHeaders,
   RateLimit, DLQ router, processed_events cleanup, DLQ depth monitor, daily
   audit verification), confirm whether already mounted in
   modules/reclaimrx/src/main.py.

Return STATUS/REASON/ATTEMPTED/RECOMMENDATION block at the end. Write all
findings to waves/B10/SP-3-audit-deep.md so the orchestrator can consume it
via Read (one short file) instead of re-reading all the source files.
"""
)
```

Main window reads ONLY the resulting `waves/B10/SP-3-audit-deep.md`. Source files stay out of main context.

### Step 2: Plan A split — dispatch 5 plan-writer subagents in parallel

Once audit is in hand, dispatch 5 plan-writer subagents (parallel, single message), each writing one of:

- A1: Models + alembic 0008 + RLS + indexes (5-8 tasks)
- A2: Outbox service + dispatcher + scheduler wiring + DLQ real repo + Redis idempotency + processed_events cleanup + daily audit verification (8-10 tasks)
- A3: Investigation state machine + transitions endpoint + hold release reshape + accumulator consumer wiring + graph job real impl (8-10 tasks)
- A4: NEW endpoints (ml-scores + graph-runs + fraud-rings + recovery aggregations + dashboard summary + thresholds GET/PUT + alias) + backend require_role()/require_mfa_elevated() across all endpoints (7-9 tasks)
- A5: SP-0 contract layer for reclaimrx + frontend module scaffold + empty-state pages + event contract docs (5-7 tasks)

Each subagent gets: the spec, the deep audit doc, the relevant slice of the failed Plan A draft as reference, and instructions to follow `superpowers:writing-plans` rigorously (real test code, real implementation snippets, expand every task — no "mirror prior tasks" shortcuts). Each writes its plan to `docs/superpowers/plans/2026-05-19-sp3-plan-a{1-5}-*.md` (or 2026-05-18 if same day).

### Step 3: Codex plan-review subagents (parallel, after Step 2 returns)

5 codex consult invocations, one per plan file, each producing
`docs/superpowers/codex-sp3-plan-a{N}-review-r1.md`. Main window reads only
the verdict tables.

### Step 4: User gate

Main window summarizes 5 plan verdicts in <200 words. User approves
individually or as a set. Fixes dispatched as subagents per finding cluster.

### Step 5: Repeat for Plans B, C, D, E

Same pattern — audit (if needed) + write subagents + codex subagents + user gate.

### Step 6: Execution

Per `superpowers:subagent-driven-development` — one subagent per task,
two-stage review, fresh context per task. Main window orchestrates only.

---

## Discipline guardrails for the next session

- **Main window does not Read tables.py, router.py, types.py, or any file >300 lines.** Delegate to subagent; consume the subagent's summary.
- **No codex consults run from main window.** Each codex consult is its own subagent invocation (codex itself runs in a subprocess but the prompt-prep + result-parsing should be a subagent so the result file path is what the main window sees, not the full review text).
- **Every fan-out validated by `framework/bin/validate-fanout` BEFORE dispatch.** This was skipped this session.
- **Every fan-out preceded by `framework/bin/snapshot-wave`.** Also skipped.
- **Subagent returns MUST end with STATUS/REASON/ATTEMPTED/RECOMMENDATION block** (orchestrator protocol contract).
- **Subagents write to `waves/B10/sub-sessions/<agent_id>.md`**, merged later via `framework/bin/merge-subsessions`.
- **If a subagent goes bad, recover via `framework/bin/quarantine-subsession`** — do not delete or force-merge from main window.

---

## What the next session SHOULD NOT redo

- Spec brainstorm + 5 codex rounds — DONE, converged, committed.
- The 4,000-line existence proof of `modules/reclaimrx` — confirmed via this session's grep.
- The 33-task scope inventory — captured in the failed Plan A draft, which is still useful as a reference for the audit subagent and the 5 plan-writer subagents.

## What the next session SHOULD redo

- The deep audit (this time reading implementations, not just grepping names).
- Plan A — split into A1-A5, each correctly anchored.
- Codex Plan A consults — one per plan slice.

---

## Cross-references

- `framework/disciplines/orchestrator-protocol.md` (Werkbench)
- `framework/bin/validate-fanout`, `snapshot-wave`, `merge-subsessions`, `quarantine-subsession`
- `superpowers:dispatching-parallel-agents`, `superpowers:subagent-driven-development`
- Spec: `docs/superpowers/specs/2026-05-18-sp3-reclaimrx-portal-design.md`
- Failed Plan A: `docs/superpowers/plans/2026-05-18-sp3-plan-a-backend-contract-scaffold.md`
- Codex Plan A R1: `docs/superpowers/codex-sp3-plan-a-review-r1.md`

---

*End of handoff. Next session orchestrates from message 1.*
