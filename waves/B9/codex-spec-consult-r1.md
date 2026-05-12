wave tractable, B9 ships incrementally:
C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\charter.md:51:| B9.D | Tier B — 66 
NDC/GCN-keyed tables | 25 | Coverage 116 → 182 |
C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\charter.md:53:| B9.F | Tier D — MTL 
schema-only (19 tables) | 3 | Coverage 201 → 220 |
C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\charter.md:54:| B9.G | C9 manifest 
extension + FDW verify (66 → 283 entries) + closeout | 5 | Wave SHIPPED |
C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\charter.md:55:| Codex GATE-CLOSE | 
Single round across all 220 tables | 1-2 | Verdict |
C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\charter.md:61:| SC-1 | All 217 
currently-missing FDB tables have SQLAlchemy models + alembic migrations + ingester support |
C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\charter.md:64:| SC-4 | RNP2 + 
RPRDPP0 ingest succeeds end-to-end; storage stays within disk budget; query performance acceptable on indexed columns |
C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\charter.md:66:| SC-6 | 
`infrastructure/scripts/setup_fdw.sh --verify` 283/283 PASS in both env DBs (current 66/66 + 217 new) |
C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\charter.md:67:| SC-7 | Weekly delta 
ingest path: re-running `load_fdb.py --mode fdb_weekly` is idempotent across all 220 tables (ON CONFLICT DO NOTHING or 
UPSERT per table) |
C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\charter.md:76:| R1 | 217 alembic 
migrations is unwieldy for review | Plan v1 decides: 1-per-tier OR batched migration (e.g., 1 migration per 25 
tables). NOT 1-per-table. |
C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\charter.md:77:| R2 | RNP2 + RPRDPP0 
(1.16 GB) exhausts dev Postgres disk OR query performance regresses | C0: verify disk free; add indexes per actual 
query patterns; monitor pg_stat_user_tables size growth |
C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\charter.md:82:| R7 | MTL schema 
accidentally activates (data ingest fires when it shouldn't) | Config flag `fdb_load_mtl=False` enforced via 
integration test; CI gate denies MTL data on default flag |
C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\charter.md:93:100 sessions × 4h = 
**~400 productive hours**. At 3-4 sessions/week: ~6-9 months elapsed. With multitasking + non-B9 work + holidays: 
realistically 9-12 months elapsed.



codex
## SPEC GATE VERDICT

GO-WITH-FIXES

## Concerns

1. **HIGH — B9 is too large for a single final GATE-CLOSE.**  
   D4 can remain “single B9 milestone,” but B9.B through B9.F need their own closure gates with evidence, row-count reconciliation, migration review, FDW verify, and test baseline comparison. A single final review across 220 tables will be too late to catch structural drift.

2. **HIGH — D2 needs a real performance gate, not just disk-budget verification.**  
   C0 should include: free disk + projected table/index bloat, timed full-load dry run for `RNP2_NDC_PRICE` and `RPRDPP0_PRODUCT_PRICE`, weekly delta/idempotency timing, representative `EXPLAIN ANALYZE`, and Postgres/FDW verify after indexes. “Disk free + pg_stat_user_tables monitoring” is not enough for reversing the Phase 09 1.16 GB deferral.

3. **HIGH — Effort model conflicts with recon.**  
   The charter says recon’s 34-session estimate was “Tier A only,” but recon estimates ~34 sessions for A+B+C excluding Tier D, and ~39 sessions with review overhead. If B9 is now 100 sessions, that may be valid conservatism, but the charter needs a corrected explanation.

4. **MEDIUM — MTL schema-only needs stronger wording, but not config-gated Alembic.**  
   Schema migrations should not be config-gated if landing schema is the explicit decision. The guard should be in loader registration and runtime config: MTL tables excluded from default load scopes, `fdb_load_mtl=False` default, explicit opt-in required, and integration tests assert zero MTL rows after default `load_fdb.py --mode fdb_weekly`.

5. **MEDIUM — Migration granularity should be constrained at SPEC.**  
   Deferring entirely to plan v1 is too loose. SPEC should mandate no one-table-per-migration and no single 217-table migration. Recommended: per phase/batch migrations, with RNDC14 dedicated or isolated inside Tier C due to 68-column review complexity.

6. **MEDIUM — SC-8 test strategy is underspecified.**  
   Do not require bespoke per-table tests for 217 tables. Do require generated/contract coverage for every `TableSpec`, schema/model parity for every table, row-count reconciliation for every loaded table, sampled behavioral tests per tier, and dedicated Tier C tests for RNDC14/pricing/weekly delta.

7. **LOW — Vendor-name sanity check passes.**  
   I found no banned PBM/vendor names in the charter text.

## What the Charter Got Right

The 7-phase split is the right internal shape if D4 remains locked. Tiering by complexity is coherent, and B9.E correctly isolates RNDC14 plus the two large pricing tables.

D1 is cleanly stated. Full RNDC14 ingest avoids repeated schema churn.

D3’s licensing boundary is directionally right: MTL schema can land while data load remains disabled.

The charter correctly calls out FDW expansion, weekly idempotency, row-count reconciliation, and the need for restored SPEC/PLAN/ADVERSARIAL discipline.

## Final Verdict + Next Action

GO-WITH-FIXES.

Revise charter v2 before PLAN. Required fixes: correct the recon/session-count contradiction, add a D2 performance gate, make per-phase closure gates mandatory, strengthen MTL loader safeguards, and lock migration granularity constraints at SPEC level. After that, proceed to PLAN v1.
tokens used
20,818
## SPEC GATE VERDICT

GO-WITH-FIXES

## Concerns

1. **HIGH — B9 is too large for a single final GATE-CLOSE.**  
   D4 can remain “single B9 milestone,” but B9.B through B9.F need their own closure gates with evidence, row-count reconciliation, migration review, FDW verify, and test baseline comparison. A single final review across 220 tables will be too late to catch structural drift.

2. **HIGH — D2 needs a real performance gate, not just disk-budget verification.**  
   C0 should include: free disk + projected table/index bloat, timed full-load dry run for `RNP2_NDC_PRICE` and `RPRDPP0_PRODUCT_PRICE`, weekly delta/idempotency timing, representative `EXPLAIN ANALYZE`, and Postgres/FDW verify after indexes. “Disk free + pg_stat_user_tables monitoring” is not enough for reversing the Phase 09 1.16 GB deferral.

3. **HIGH — Effort model conflicts with recon.**  
   The charter says recon’s 34-session estimate was “Tier A only,” but recon estimates ~34 sessions for A+B+C excluding Tier D, and ~39 sessions with review overhead. If B9 is now 100 sessions, that may be valid conservatism, but the charter needs a corrected explanation.

4. **MEDIUM — MTL schema-only needs stronger wording, but not config-gated Alembic.**  
   Schema migrations should not be config-gated if landing schema is the explicit decision. The guard should be in loader registration and runtime config: MTL tables excluded from default load scopes, `fdb_load_mtl=False` default, explicit opt-in required, and integration tests assert zero MTL rows after default `load_fdb.py --mode fdb_weekly`.

5. **MEDIUM — Migration granularity should be constrained at SPEC.**  
   Deferring entirely to plan v1 is too loose. SPEC should mandate no one-table-per-migration and no single 217-table migration. Recommended: per phase/batch migrations, with RNDC14 dedicated or isolated inside Tier C due to 68-column review complexity.

6. **MEDIUM — SC-8 test strategy is underspecified.**  
   Do not require bespoke per-table tests for 217 tables. Do require generated/contract coverage for every `TableSpec`, schema/model parity for every table, row-count reconciliation for every loaded table, sampled behavioral tests per tier, and dedicated Tier C tests for RNDC14/pricing/weekly delta.

7. **LOW — Vendor-name sanity check passes.**  
   I found no banned PBM/vendor names in the charter text.

## What the Charter Got Right

The 7-phase split is the right internal shape if D4 remains locked. Tiering by complexity is coherent, and B9.E correctly isolates RNDC14 plus the two large pricing tables.

D1 is cleanly stated. Full RNDC14 ingest avoids repeated schema churn.

D3’s licensing boundary is directionally right: MTL schema can land while data load remains disabled.

The charter correctly calls out FDW expansion, weekly idempotency, row-count reconciliation, and the need for restored SPEC/PLAN/ADVERSARIAL discipline.

## Final Verdict + Next Action

GO-WITH-FIXES.

Revise charter v2 before PLAN. Required fixes: correct the recon/session-count contradiction, add a D2 performance gate, make per-phase closure gates mandatory, strengthen MTL loader safeguards, and lock migration granularity constraints at SPEC level. After that, proceed to PLAN v1.
