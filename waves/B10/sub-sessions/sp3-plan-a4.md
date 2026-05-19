# SP-3 Plan A4 Sub-Session Brief

**Branch:** wave/B10-w5  
**Date:** 2026-05-18  
**Plan:** `docs/superpowers/plans/2026-05-18-sp3-plan-a4-endpoints-auth.md`  
**Depends on:** Plans A1 (tables), A2 (services), A3 (state machine + hold release endpoint)

## What This Plan Delivers

- 13 missing endpoints from spec §5.5 audit §4
- 5 partial-mismatch endpoint reshapes (severity filter, PHI/MFA gate, status filter, 410 deprecated route, hold list pagination)
- `require_viewer` / `require_investigator` / `require_admin` using spec role names (`reclaimrx.*`)
- `require_mfa_elevated()` stub (fail-closed 503 until core-platform session lookup wired)
- Role matrix integration test covering all 18 endpoints × 3 roles

## Critical Invariants (executor must not deviate)

- `CurrentUser` is a **dataclass** — `.roles`, `.has_role()`, `.id`, `.tenant_id`; never `.get("roles")`
- Table names are `reclaimrx_investigations`, `reclaimrx_payment_holds` (NOT short names)
- `EventEnvelope` uses `event_type=` and `correlation_id=` (NOT `type=` or `emitted_at=`)
- Advisory lock key: `zlib.crc32(f"graph_run:{tenant_id}".encode()) & 0x7FFFFFFF` (NOT `hash()`)
- All new route handlers are `async def`
- Decimal money serialized as `str()`, computed with `ROUND_HALF_UP`
- `Cache-Control: no-store` on PHI-bearing detail endpoints
- Cross-tenant isolation test per new endpoint

## Task Summary

| Task | Scope | Key gate |
|---|---|---|
| A4-T1 | Role deps + spec role names, `require_mfa_elevated()` stub | 100% coverage on `dependencies.py` |
| A4-T2 | 13 new Pydantic response schemas | Schema validation tests pass |
| A4-T3 | 10 read-only new handlers (N1, N2, N4–N8, N10–N13) | Cross-tenant isolation per handler |
| A4-T4 | `POST /graph-runs/trigger` (zlib lock, 409 in-flight) | 100% coverage on 3 lock paths |
| A4-T5 | `PUT /thresholds` admin-only + hash-chained audit | 100% coverage financial + audit |
| A4-T6 | P1/P2/P4/P5 reshapes (severity filter, PHI gate, status filter, 410) | PHI no-store + MFA gate tests |
| A4-T7 | `POST /investigations/{id}/transitions` + `/notes` | State machine matrix 100% |
| A4-T8 | `GET /rule-firings` (spec endpoint #5) | Tenant isolation + no PHI in list |
| A4-T9 | Full role matrix test + coverage report | All gates pass before marking done |

## Outcome Definition

Plan A4 is COMPLETE when:
- All 9 tasks pass their tests
- `pytest modules/reclaimrx/tests/ --cov` shows 100% on financial/PHI/auth/role paths
- No new route handler uses `sync def`
- Role matrix test (A4-T9) passes for all 18 endpoints × 3 roles
- No `user.get("roles")` anywhere in new code
