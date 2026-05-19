# SP-3 Plan A3 Sub-session

**Plan:** `docs/superpowers/plans/2026-05-18-sp3-plan-a3-state-machine-hold-graph.md`
**Branch:** wave/B10-w5
**Depends on:** Plan A1 (tables + migration), Plan A2 (outbox + dispatcher)

## Scope (5 slices, 8 tasks)

1. Investigation state machine (`constants.py`) — 7 states, `validate_transition()`, `InvalidTransitionError`.
2. `InvestigationService.transition()` — enforces state machine; writes audit `InvestigationActivity` row.
3. `POST /investigations/{id}/transitions` — role-gated (investigator+), 422 on invalid, 404 on not-found/cross-tenant.
4. Hold release reshape — DELETE `DELETE /holds/{hold_id}`; add `POST /holds/{id}/release` with 3-case idempotency + outbox row.
5. Accumulator consumer — `accumulator_consumer.py` wired into `CONSUMER_ROUTING`; writes `AccumulatorAnomaly`; opens investigation on high severity.
6. Graph job real impl — `graph_analysis_job.py` replaces `job_rebuild_fraud_network_graph` stub; advisory lock via `zlib.crc32`; writes `GraphRun` + `FraudRing`; outbox event.
7. `POST /graph-runs/trigger` — 202 on success, 409 `RUN_IN_PROGRESS`, 403 for viewer.
8. Coverage gate + `create_app()` integration test (LESSON-006).

## Key audit corrections encoded in plan

| Error from codex R1 | Correction |
|---|---|
| BLOCK 5: plan used `hold.hold_amount` | Use `hold.amount_threshold` (audit §1:145) |
| BLOCK 5: only 2 idempotency cases | All 3 §7.2 cases implemented: 200/409/422 |
| BLOCK 6: plan used `user.get("roles")` | Use `user.has_role("reclaimrx.investigator")` (audit §3:258) |
| BLOCK 7: Python `hash()` for advisory lock | Use `zlib.crc32(...) & 0x7FFFFFFF` (audit §9:546) |
| BLOCK 8: abbreviated task steps | Every task has explicit test-first/run-fail/implement/run-pass |

## Task order (strict)

Tasks 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8. Each must be GREEN before starting next.

## Files created/modified

| File | Action |
|---|---|
| `modules/reclaimrx/src/utils/constants.py` | REPLACE (state machine) |
| `modules/reclaimrx/src/services/investigation_service.py` | EXTEND (transition method) |
| `modules/reclaimrx/src/api/router.py` | EXTEND + DELETE old route |
| `modules/reclaimrx/src/services/payment_hold_service.py` | REPLACE release_hold() |
| `modules/reclaimrx/src/consumers/accumulator_consumer.py` | CREATE |
| `modules/reclaimrx/src/events/__init__.py` | WIRE accumulator consumer |
| `modules/reclaimrx/src/jobs/graph_analysis_job.py` | CREATE |
| `modules/reclaimrx/src/jobs/scheduled.py` | REPLACE stub |
| `modules/reclaimrx/tests/unit/test_state_machine.py` | CREATE |
| `modules/reclaimrx/tests/unit/test_investigation_service_transitions.py` | CREATE |
| `modules/reclaimrx/tests/unit/test_accumulator_consumer.py` | CREATE |
| `modules/reclaimrx/tests/unit/test_graph_job.py` | CREATE |
| `modules/reclaimrx/tests/integration/test_transitions_endpoint.py` | CREATE |
| `modules/reclaimrx/tests/integration/test_hold_release_endpoint.py` | CREATE |
| `modules/reclaimrx/tests/integration/test_graph_run_trigger.py` | CREATE |
| `modules/reclaimrx/tests/integration/test_create_app_a3_bindings.py` | CREATE |

## Pass gate

All 8 test files green. 100% coverage on A3 source files. `DELETE /holds/{id}` returns 405. Advisory lock key is `zlib.crc32`. Zero `user.get()` calls. Zero `hold_amount` references.
