# SP-3 Plan A1 — Adversarial Re-Review R2
**Reviewer:** Codex (GPT-4.1)
**Date:** 2026-05-19
**Plan:** docs/superpowers/plans/2026-05-18-sp3-plan-a1-models-migration.md (post-R1 revision)
**Prior verdict:** docs/superpowers/codex-sp3-plan-a1-review-r1.md (NO-GO, 6 BLOCKs + 3 CONCERNs)

---

## Verdict Table

| # | Concern | Severity | Plan ref | Evidence (path:line or quote) | Fix required |
|---:|---|---|---|---|---|
| 1 | R1 BLOCK 1 physical-name split resolved for new tables. | PASS | Task 2 migration naming | Plan says default schema +  prefix and no schema kwargs at plan:1400-1404; creates prefixed tables at :1462, :1523, :1588, :1641, :1704, :1756. | None. |
| 2 | R1 BLOCK 1 helper functions accept prefixed names without schema args. | PASS | Task 2 helpers |  at :1425-1429;  at :1443-1447; calls pass prefixed names at :1517-1518, :1579-1580, :1635-1636, :1698-1699, :1750-1751, :1799-1800. | None. |
| 3 | R1 BLOCK 2 executable ALTER targets are deterministic, but stale hedging language remains. | CONCERN | Task 2 ALTERs | Code targets  at :1831 and  at :1872-1874; tests use public schema at :1230, :1300-1303. **But :1807-1809 still says** "Determine whether the table is in reclaimrx schema ... or in public schema." | Remove hedging comment; state only public/default-schema prefixed targets. |
| 4 | R1 BLOCK 3 mixin consistency resolved. | PASS | Task 1.2 models | Plan abandons mixin at :44 and :58; all six new models use explicit  tenant IDs at :678, :738, :795, :853, :908, :962.  confirms TenantScopedMixin uses . | None. |
| 5 | R1 BLOCK 4 SyntaxError fixed, but import rule not fully followed in test_model_indexes.py. | CONCERN | Task 1.1 / Task 4 tests |  appears only in explanatory text at :82, not executable code. However Task 4 imports models inside test functions at :2172, :2183, :2194, :2205, :2216, :2229, :2240. | Move Task 4 imports to module scope (top of test file). |
| 6 | R1 BLOCK 5 create_all ordering resolved. | PASS | Task 1.1 fixture | Module-load model imports at :109-116; metadata assertion at :118-129; engine fixture only configures engine and runs  at :165-176. | None. |
| 7 | R1 BLOCK 7 RLS null-deny integrity resolved. | PASS | Task 3 RLS test | All six tables listed at :2005-2011; seed inserts at :2030, :2039, :2047, :2056, :2063, :2072;  at :2096, :2117, :2133; cross-tenant test at :2109-2125. | None. |
| 8 | R1 CONCERN 6 column count not consistently fixed. | CONCERN | Scope / migration comments | Correct 12-column references at :17, :471, :1341-1344; **stale wrong comment at :1803: "add 11 SP-3 columns."** | Change to 12. |
| 9 | R1 CONCERN 8 downgrade symmetry resolved. | PASS | Task 2 downgrade | Partial unique indexes dropped before tables at :1935-1941; reverse column drop order at :1918-1933; table drop order at :1943-1949. | None. |
| 10 | R1 CONCERN 9 PaymentHold idempotency deferral explicit. | PASS | PaymentHold note | Deferral note at :639-645, referencing Plan A2 §6b and Plan A3 §7.2. | None. |
| 11 | New: ORM table names match migration physical names across all 6 new + 2 existing tables. | PASS | Task 1.2 / Task 2 | ORM names at :675, :735, :792, :850, :905, :959; migration creates same at :1463, :1524, :1589, :1642, :1705, :1757; existing names grounded at modules/reclaimrx/src/models/tables.py:374 and :588. | None. |
| 12 | New: FK references use fully prefixed names. | PASS | Task 1.2 / Task 2 | ORM FKs at plan :742, :763, :820, :912; migration FKs at :1535, :1716. | None. |
| 13 | New: no executable schema=_SCHEMA or {_SCHEMA}.foo remains in plan migration. | PASS | Task 2 migration | Search found only comments/test introspection at :1130, :1402-1403, :1809; no executable schema kwarg or raw SQL interpolation remains. | None. |
| 14 | New: Alembic down_revision matches 0007. | PASS | Migration header | Plan sets  at :1376; baseline revision is . | None. |

---

## Verdict
**GO-WITH-CHANGES**

## Summary
- R1 BLOCKs 1, 3, 4 (SyntaxError), 5, 7 are fully resolved.
- R1 BLOCK 2 is resolved in executable code but one stale hedging comment at plan:1807-1809 remains — CONCERN only, not a hard blocker.
- R1 CONCERN 6 is nearly resolved; one stale "11 columns" comment at plan:1803 lingers.
- R1 CONCERNs 8 and 9 are fully resolved.
- Task 4 test file imports models inside individual test functions instead of at module load — violates the BLOCK 4 fix intent, minor concern.
- No new hard blockers introduced by the R1 edits.
- Migration naming, FK naming, RLS coverage, downgrade symmetry, and down_revision chain all check out.

## Recommendation
Do a small cleanup pass (< 15 minutes) before execution: remove the ALTER schema hedging comment at plan:1807-1809, fix the "11 SP-3 columns" comment at plan:1803 to say 12, and move the test_model_indexes.py imports (Task 4) to module scope. None of these are execution-blockers, but leaving stale contradictory text in the plan will cause confusion during code review. After that pass, Plan A1 is ready to execute.

---

*Generated by Codex adversarial re-review (R2) — 2026-05-19*
