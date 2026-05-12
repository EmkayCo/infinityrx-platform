Reading prompt from stdin...
OpenAI Codex v0.128.0 (research preview)
--------
workdir: C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
model: gpt-5.5
provider: openai
approval: never
sandbox: read-only
reasoning effort: none
reasoning summaries: none
session id: 019e1881-7c2c-7972-a03e-c03d56a44aa2
--------
user
You are codex acting as the PLAN GATE reviewer for the InfinityRx platform's Wave B9, round 2.

## Context

In PLAN R1 you returned **GO-WITH-FIXES** with these required changes:

| # | Required fix |
|---|---|
| F1 | Correct Tier C non-special count to **16** (not 17). Cascade into all FDW counts and cum totals. |
| F2 | Reconcile all FDW counts to **283** final (charter SC-6). Correct ladder: 66 → 179 → 245 → 261 → 262 → 264 → 283. |
| F3 | Lock migrations to the 6 SPEC-approved files. Remove part-file alternatives (no `_part1..N` variants). |
| F4 | Fix loader-mode erratum: `fdb_initial`, `fdb_weekly`, `fdb_rebase` already exist; B9.A does NOT need to add `fdb_weekly`. |
| F5 | Add a real weekly-delta schema/UPD-format threat (T12) with TRUNCATE+INSERT routing for tables that don't follow A/C/D format; cover charter R4 (new-column drift). |
| F6 | Explain the 42-vs-39 session delta OR reduce the plan back to charter budget. |

Plus two new concerns:
- HIGH: SC-1 verification said `pg_class == 220`; recon shows 3 source tables → 2 DB tables, so the right number is not 220.
- MEDIUM: `pytest --collect-only` is not a failure-count baseline; use a real failure-counting command.

Plan v2 (this revision) claims to absorb all of these. Your job in R2 is to verify each fix.

## Artifacts to read

1. `C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\plan.md` — PLAN v2 DRAFT (the document you are reviewing)
2. `C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\codex-plan-consult-r1.md` — your R1 verdict that v2 is responding to
3. `C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\charter.md` — SPEC v3 LOCKED (the contract v2 must match)
4. `C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\recon.md` — scope ground truth

## Verdict format (match this exactly)

```
## PLAN R2 GATE VERDICT

<GO | GO-WITH-FIXES | NO-GO>

## R1 fix verification

| # | Fix | Verified? | Evidence (plan line refs) | Notes |
|---|---|---|---|---|
| F1 | Tier C count 17 → 16 | YES / PARTIAL / NO | <line refs> | |
| F2 | FDW ladder to 283 | YES / PARTIAL / NO | <line refs> | |
| F3 | 6 migrations SPEC-locked | YES / PARTIAL / NO | <line refs> | |
| F4 | Loader-mode erratum | YES / PARTIAL / NO | <line refs> | |
| F5 | T12 weekly-delta threat | YES / PARTIAL / NO | <line refs> | |
| F6 | Effort math reconciled | YES / PARTIAL / NO | <line refs> | |
| F7 | SC-1 verification (pg_class count) | YES / PARTIAL / NO | <line refs> | |
| F8 | pytest baseline (real failure count) | YES / PARTIAL / NO | <line refs> | |

## Charter-vs-plan consistency

| # | Check | Pass? |
|---|---|---|
| C1 | Per-phase mini-GATE-CLOSE rows match charter v3 phase table | YES / NO |
| C2 | Migration shape matches charter §SPEC-locked migration granularity | YES / NO |
| C3 | SC-1..SC-11 all have goal-backward verification artifacts | YES / NO |
| C4 | D2 perf gate (SC-4) is real in B9.F | YES / NO |
| C5 | MTL guards (SC-5) are triple-layered in B9.G | YES / NO |

## Vendor-name sanity check

<PASS / FAIL with grep evidence>

## New concerns surfaced in v2 (if any)

<list with severity, or "None">

## Final verdict + next action

<one paragraph: if GO → proceed to codex ADVERSARIAL consult; if GO-WITH-FIXES → list required plan v3 changes; if NO-GO → explain structural problem>
```

Be rigorous. Verify each fix at concrete plan-line refs. Do not GO unless every fix is verifiable and no new HIGH-severity concerns surface.
codex
I’ll review the B9 PLAN v2 against the R1 verdict, charter, and recon, then return the exact gate format with concrete line references. Since this is a read-only review, I’ll gather line-numbered excerpts and grep for the vendor-name sanity check before deciding.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\plan.md'; Select-String -Path "'$p -Pattern '"'Tier C|283|66|179|245|261|262|264|migration|part1|part2|part3|fdb_weekly|loader|T12|weekly|TRUNCATE|INSERT|42|39|pg_class|collect-only|pytest|failure|D2|SC-4|SC-5|MTL|mini-GATE|GATE-CLOSE|SC-1|SC-11' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\recon.md'; Select-String -Path "'$p -Pattern '"'220|283|Tier C|FDW|source|tables|3 source|2 DB|pg_class|vendor|UPD|weekly|A/C/D' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\charter.md'; Select-String -Path "'$p -Pattern '"'Phase|B9\\.|migration|220|283|SC-1|SC-4|SC-5|SC-6|D2|MTL|SPEC-locked|loader|fdb_weekly|R4' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\codex-plan-consult-r1.md'; Select-String -Path "'$p -Pattern '"'F1|F2|F3|F4|F5|F6|pg_class|collect-only|GO-WITH-FIXES|Required' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\plan.md'; Select-String -Path "'$p -Pattern '"'Tier C|283|66|179|245|261|262|264|migration|part1|part2|part3|fdb_weekly|loader|T12|weekly|TRUNCATE|INSERT|42|39|pg_class|collect-only|pytest|failure|D2|SC-4|SC-5|MTL|mini-GATE|GATE-CLOSE|SC-1|SC-11' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }'` rejected: blocked by policy
2026-05-11T19:26:56.678129Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\plan.md'; Select-String -Path "'$p -Pattern '"'Tier C|283|66|179|245|261|262|264|migration|part1|part2|part3|fdb_weekly|loader|T12|weekly|TRUNCATE|INSERT|42|39|pg_class|collect-only|pytest|failure|D2|SC-4|SC-5|MTL|mini-GATE|GATE-CLOSE|SC-1|SC-11' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }'` rejected: blocked by policy
2026-05-11T19:26:56.678690Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\recon.md'; Select-String -Path "'$p -Pattern '"'220|283|Tier C|FDW|source|tables|3 source|2 DB|pg_class|vendor|UPD|weekly|A/C/D' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }'` rejected: blocked by policy
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\recon.md'; Select-String -Path "'$p -Pattern '"'220|283|Tier C|FDW|source|tables|3 source|2 DB|pg_class|vendor|UPD|weekly|A/C/D' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }'` rejected: blocked by policy
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\charter.md'; Select-String -Path "'$p -Pattern '"'Phase|B9\\.|migration|220|283|SC-1|SC-4|SC-5|SC-6|D2|MTL|SPEC-locked|loader|fdb_weekly|R4' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }'` rejected: blocked by policy
2026-05-11T19:26:56.679502Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\charter.md'; Select-String -Path "'$p -Pattern '"'Phase|B9\\.|migration|220|283|SC-1|SC-4|SC-5|SC-6|D2|MTL|SPEC-locked|loader|fdb_weekly|R4' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }'` rejected: blocked by policy
2026-05-11T19:26:56.680010Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\codex-plan-consult-r1.md'; Select-String -Path "'$p -Pattern '"'F1|F2|F3|F4|F5|F6|pg_class|collect-only|GO-WITH-FIXES|Required' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }'` rejected: blocked by policy
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\codex-plan-consult-r1.md'; Select-String -Path "'$p -Pattern '"'F1|F2|F3|F4|F5|F6|pg_class|collect-only|GO-WITH-FIXES|Required' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }'` rejected: blocked by policy
codex
The first parallel grep was blocked by the shell policy wrapper, likely because of quoting around absolute paths with spaces. I’m switching to simpler PowerShell commands from the wave directory so the reads stay within policy.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Location; Get-ChildItem' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
 succeeded in 322ms:

Path                                                                             
----                                                                             
C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9

LastWriteTime : 5/11/2026 3:14:50 PM
Length        : 9222
Name          : charter.md


LastWriteTime : 5/11/2026 3:22:04 PM
Length        : 513865
Name          : codex-plan-consult-r1.md


LastWriteTime : 5/11/2026 3:26:38 PM
Length        : 0
Name          : codex-plan-consult-r2.md


LastWriteTime : 5/11/2026 10:30:25 AM
Length        : 9368
Name          : codex-spec-consult-r1.md


LastWriteTime : 5/11/2026 3:13:55 PM
Length        : 59602
Name          : codex-spec-consult-r2.md


LastWriteTime : 5/11/2026 3:26:08 PM
Length        : 32318
Name          : plan.md


LastWriteTime : 5/11/2026 9:03:50 AM
Length        : 21690
Name          : recon.md




2026-05-11T19:27:12.734157Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path .\\plan.md -Pattern 'Tier C|283|66|179|245|261|262|264|migration|part1|part2|part3|fdb_weekly|loader|T12|weekly|TRUNCATE|INSERT|42|39|pg_class|collect-only|pytest|failure|D2|SC-4|SC-5|MTL|mini-GATE|GATE-CLOSE|SC-1|SC-11' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }'` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path .\\plan.md -Pattern 'Tier C|283|66|179|245|261|262|264|migration|part1|part2|part3|fdb_weekly|loader|T12|weekly|TRUNCATE|INSERT|42|39|pg_class|collect-only|pytest|failure|D2|SC-4|SC-5|MTL|mini-GATE|GATE-CLOSE|SC-1|SC-11' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path .\\charter.md -Pattern 'Phase|B9\\.|migration|220|283|SC-1|SC-4|SC-5|SC-6|D2|MTL|SPEC-locked|loader|fdb_weekly|R4' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path .\\codex-plan-consult-r1.md -Pattern 'F1|F2|F3|F4|F5|F6|pg_class|collect-only|GO-WITH-FIXES|Required' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path .\\recon.md -Pattern '220|283|Tier C|FDW|source|tables|3 source|2 DB|pg_class|vendor|UPD|weekly|A/C/D' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path .\\plan.md -Pattern 'Tier C|283|66|179|245|261|262|264|migration|part1|part2|part3|fdb_weekly|loader|T12|weekly|TRUNCATE|INSERT|42|39|pg_class|collect-only|pytest|failure|D2|SC-4|SC-5|MTL|mini-GATE|GATE-CLOSE|SC-1|SC-11' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }'` rejected: blocked by policy
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path .\\charter.md -Pattern 'Phase|B9\\.|migration|220|283|SC-1|SC-4|SC-5|SC-6|D2|MTL|SPEC-locked|loader|fdb_weekly|R4' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }'` rejected: blocked by policy
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path .\\codex-plan-consult-r1.md -Pattern 'F1|F2|F3|F4|F5|F6|pg_class|collect-only|GO-WITH-FIXES|Required' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }'` rejected: blocked by policy
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path .\\recon.md -Pattern '220|283|Tier C|FDW|source|tables|3 source|2 DB|pg_class|vendor|UPD|weekly|A/C/D' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }'` rejected: blocked by policy
2026-05-11T19:27:12.735225Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path .\\charter.md -Pattern 'Phase|B9\\.|migration|220|283|SC-1|SC-4|SC-5|SC-6|D2|MTL|SPEC-locked|loader|fdb_weekly|R4' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }'` rejected: blocked by policy
2026-05-11T19:27:12.736108Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path .\\codex-plan-consult-r1.md -Pattern 'F1|F2|F3|F4|F5|F6|pg_class|collect-only|GO-WITH-FIXES|Required' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }'` rejected: blocked by policy
2026-05-11T19:27:12.736964Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path .\\recon.md -Pattern '220|283|Tier C|FDW|source|tables|3 source|2 DB|pg_class|vendor|UPD|weekly|A/C/D' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }'` rejected: blocked by policy
codex
That failed again on the PowerShell formatting expression, not on file access. I’ll use `rg -n` directly for line references, which avoids the blocked formatting construct.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "Tier C|283|66|179|245|261|262|264|migration|part1|part2|part3|fdb_weekly|loader|T12|weekly|TRUNCATE|INSERT|42|39|pg_class|collect-only|pytest|failure|D2|SC-4|SC-5|MTL|mini-GATE|GATE-CLOSE|SC-1|SC-11" plan.md' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "F1|F2|F3|F4|F5|F6|pg_class|collect-only|GO-WITH-FIXES|Required" codex-plan-consult-r1.md' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"Phase|B9\\.|migration|220|283|SC-1|SC-4|SC-5|SC-6|D2|MTL|SPEC-locked|loader|fdb_weekly|R4\" charter.md" in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "220|283|Tier C|FDW|source|tables|3 source|2 DB|pg_class|vendor|UPD|weekly|A/C/D" recon.md' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
 succeeded in 371ms:
18:Wave B9 = "FDB NDDF Plus 220-table extension". SPEC v3 is locked (you previously approved at SPEC R2 GO-WITH-FIXES → owner applied the stale-D4-row cleanup → v3 LOCKED). The next gate is PLAN v1. The owner drafted `plan.md` v1 (380 lines). Your job in PLAN R1 is to verify whether the plan is sound, complete, and ready for ADVERSARIAL review + execute, OR whether it needs revision.
61:<GO | GO-WITH-FIXES | NO-GO>
103:<one paragraph: if GO → proceed to codex ADVERSARIAL consult; if GO-WITH-FIXES → list required plan v2 changes; if NO-GO → explain structural problem>
181:**Status:** SPEC v3 LOCKED â€” codex SPEC R2 GO-WITH-FIXES (5/6 verified; D4 effort row stale-text cleanup applied per `codex-spec-consult-r2.md`). Ready for PLAN v1.
248:| SC-10 | Final B9 GATE-CLOSE GO or GO-WITH-FIXES |
299:**Codex PLAN consult:** round 1 GO-WITH-FIXES (8 concerns); plan v2 absorbs all 8 + expanded scope per user decision 2026-05-10
300:**User decision 2026-05-10:** F1 expanded scope to **full sweep** (all ~30 cross-module + script + shared/data_ingestion consumers)
309:### Inside `modules/drug-database/` (intra-module â€” F1 sweeps in C1)
315:### Outside `modules/drug-database/` (cross-module / scripts / shared â€” F1 sweeps in C2)
347:**EXPLICITLY OUT OF F1 (must NOT be touched by C2 sed):**
371:| 6 | MEDIUM C7 missing txn_id | C5 (renamed F2 step) captures `txn = persist_claim_transaction(...)` and includes `svc_txn_id` in publish failure log |
441:**Commit:** `refactor(drug-database/p11b): F1 C1 rename src/ -> drug_database/ atomic â€” sed + setuptools + alembic + conftest`
476:**Commit:** `refactor(adjudication-engine+scripts+shared-data-ingestion/p11b): F1 C2 cross-module imports drug_database.* (drop src.* shim, 25 files / 30 lines)`
480:### C3 â€” F1 verification: all 4 test suites green (SC-3, SC-4, SC-5)
490:**Commit:** none unless triage edits land. If triage edits required â†’ `fix(drug-database+shared-data-ingestion/p11b): F1 C3 post-rename test repairs`
494:### C4 â€” F2 (a): tcp_listener publish wiring (mirror admin_routes exactly with txn_id)
589:**Commit:** `feat(adjudication-engine/p11b): F2 C4 publish claim.adjudicated from tcp_listener (mirrors admin_routes with txn_id)`
593:### C5 â€” F2 (b): integration test through `_handle_connection` with InMemoryEventBus capture
619:**Commit:** `test(adjudication-engine/p11b): F2 C5 integration test â€” tcp_listener publishes claim.adjudicated via InMemoryEventBus capture`
634:**Commit:** `docs(p11b/p11b-close): F1+F2 IMPLEMENTED â€” README + memory + wave-history`
664:| T6 | F2 publish blocks TCP response | Integration test asserts timing if needed (not currently in scope) | Existing try/except already non-blocking |
675:| SPEC | 2 rounds | DONE â€” round 2 GO-WITH-FIXES, all 5 concerns absorbed in charter v3 |
676:| PLAN | â‰¤2 rounds | round 1 DONE â€” GO-WITH-FIXES, 8 concerns absorbed in plan v2; round 2 OPTIONAL â€” proceeding without if no NO-GO |
709:Wave B9 = "FDB NDDF Plus 220-table extension". Recon was completed 2026-05-11 (`recon.md`). Charter v1 was dispatched for SPEC R1. You returned **GO-WITH-FIXES** with 6 substantive concerns (1 HIGH effort model, 2 HIGH process gates, 3 MEDIUM SPEC tightenings, 1 LOW vendor-name pass). The owner produced charter v2 which claims to absorb all 6 concerns. Your job in R2 is to verify whether v2 actually addresses each concern, and either issue **GO** (proceed to PLAN), **GO-WITH-FIXES** (one more revision needed), or **NO-GO** (structural problem).
733:<GO | GO-WITH-FIXES | NO-GO>
756:<one paragraph: if GO â†’ proceed to PLAN v1 codex consult; if GO-WITH-FIXES â†’ list required fixes; if NO-GO â†’ explain structural problem>
829:**Status:** SPEC v2 (codex SPEC R1 GO-WITH-FIXES Ã¢â€ â€™ 6 substantive concerns absorbed; R2 to confirm)
896:| SC-10 | Final B9 GATE-CLOSE GO or GO-WITH-FIXES |
972:charter.md:70:| SC-10 | Final B9 GATE-CLOSE GO or GO-WITH-FIXES |
1010:codex-spec-consult-r1.md:76:Revise charter v2 before PLAN. Required fixes: correct the recon/session-count contradiction, add a D2 performance gate, make per-phase closure gates mandatory, strengthen MTL loader safeguards, and lock migration granularity constraints at SPEC level. After that, proceed to PLAN v1.
1023:codex-spec-consult-r1.md:120:Revise charter v2 before PLAN. Required fixes: correct the recon/session-count contradiction, add a D2 performance gate, make per-phase closure gates mandatory, strengthen MTL loader safeguards, and lock migration granularity constraints at SPEC level. After that, proceed to PLAN v1.
1126:recon.md:322:1. **RNDC14\_NDC\_MSTR column triage**: Which of the 68 columns does InfinityRx actually need? Full 68-column ingest vs. curated subset has significant implications for model maintainability and storage. Required before B9.3 begins.
1134:GO-WITH-FIXES
1157:GO-WITH-FIXES. v2 substantively addresses R1 concerns #1, #2, #4, #5, and #6. The only blocker is the stale D4 row at charter.md:21: replace â€œ~34 four-hour sessions elapsed; ~6 months wall-clockâ€ with language consistent with the corrected model, e.g. â€œ~39 four-hour sessions planned; ~13 weeks at 3 sessions/week, realistically 4-5 months with multitasking.â€ After that cleanup, proceed to PLAN v1 codex consult.
1162:GO-WITH-FIXES
1185:GO-WITH-FIXES. v2 substantively addresses R1 concerns #1, #2, #4, #5, and #6. The only blocker is the stale D4 row at charter.md:21: replace â€œ~34 four-hour sessions elapsed; ~6 months wall-clockâ€ with language consistent with the corrected model, e.g. â€œ~39 four-hour sessions planned; ~13 weeks at 3 sessions/week, realistically 4-5 months with multitasking.â€ After that cleanup, proceed to PLAN v1 codex consult.
1191:**Predecessor:** `charter.md` v3 LOCKED (SPEC R2 GO-WITH-FIXES, stale D4 row corrected).
1226:6. **134 pre-existing test failures baseline frozen** â€” `pytest --collect-only` count captured at B9.A C0; B9 must not regress count, must not "fix" them (charter `Out of scope` row 3). Forensic wave handles these later.
1250:- **`pytest --collect-only` baseline marker** â€” committed to `waves/B9/baseline.md` at C0; every phase mini-GATE-CLOSE re-runs and asserts count unchanged.
1268:- `pytest --collect-only` count unchanged vs. C0 baseline.
1270:- Codex PLAN consult returns GO or GO-WITH-FIXES (fixes applied + re-consult if FIXES); codex ADVERSARIAL returns no HIGH-severity unaddressed objections.
1312:- `pytest --collect-only` count unchanged vs B9.A C0 baseline Â± 113 new contract tests (counted in baseline)
1486:- SC-1: 217 tables have models + migrations + ingester (verified via `pg_class` count + alembic history scan)
1495:- SC-10: Final B9 GATE-CLOSE GO or GO-WITH-FIXES (FIXES applied iteratively until GO)
1498:**B9 final GATE-CLOSE criteria:** codex final consult returns GO. Charter SC-10 escalates only if codex returns GO-WITH-FIXES three times in a row without convergence; that triggers an architectural pause.
1508:| SC-1 | `pg_class` count of FDB-prefixed tables in `drug_database` schema == 220; `alembic history` shows migrations 0009..0014 applied | B9.H Session 2 evidence |
1535:| T10 | Test count baseline drifts (134 pre-existing failures become 135 or 200) | MED | MED | B9.A C0 captures `pytest --collect-only` count; each phase mini-GATE-CLOSE asserts count unchanged Â± new contract tests |
1544:| SPEC R1 | B9.A | Charter v1 dispatched 2026-05-11 | `codex-spec-consult-r1.md` â€” GO-WITH-FIXES |
1545:| SPEC R2 | B9.A | Charter v2 dispatched 2026-05-11 | `codex-spec-consult-r2.md` â€” GO-WITH-FIXES â†’ cleanup applied â†’ v3 LOCKED |
1547:| ADVERSARIAL R1 | B9.A | After PLAN R1 GO or GO-WITH-FIXES + fix | `codex-adversarial-r1.md` |
1915:1. **RNDC14\_NDC\_MSTR column triage**: Which of the 68 columns does InfinityRx actually need? Full 68-column ingest vs. curated subset has significant implications for model maintainability and storage. Required before B9.3 begins.
1930:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"SC-|R[1-7] \\||T[0-9]+|B9\\.[A-H]|FDW|283|284|fdb_weekly|fdb_initial|001[0-9]|migration|mini-GATE|Goal-backward|Threat model|Pre-execute|D2|MTL|RNP2|RPRDPP0|RNDC14|setup_fdw|collect-only|RECORD_COUNTS|session\" 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\plan.md'" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
1952:39:6. **134 pre-existing test failures baseline frozen** — `pytest --collect-only` count captured at B9.A C0; B9 must not regress count, must not "fix" them (charter `Out of scope` row 3). Forensic wave handles these later.
1963:63:- **`pytest --collect-only` baseline marker** — committed to `waves/B9/baseline.md` at C0; every phase mini-GATE-CLOSE re-runs and asserts count unchanged.
1970:81:- `pytest --collect-only` count unchanged vs. C0 baseline.
1989:125:- `pytest --collect-only` count unchanged vs B9.A C0 baseline ± 113 new contract tests (counted in baseline)
2056:299:- SC-1: 217 tables have models + migrations + ingester (verified via `pg_class` count + alembic history scan)
2065:308:- SC-10: Final B9 GATE-CLOSE GO or GO-WITH-FIXES (FIXES applied iteratively until GO)
2067:311:**B9 final GATE-CLOSE criteria:** codex final consult returns GO. Charter SC-10 escalates only if codex returns GO-WITH-FIXES three times in a row without convergence; that triggers an architectural pause.
2069:321:| SC-1 | `pg_class` count of FDB-prefixed tables in `drug_database` schema == 220; `alembic history` shows migrations 0009..0014 applied | B9.H Session 2 evidence |
2090:348:| T10 | Test count baseline drifts (134 pre-existing failures become 135 or 200) | MED | MED | B9.A C0 captures `pytest --collect-only` count; each phase mini-GATE-CLOSE asserts count unchanged ± new contract tests |
2092:357:| SPEC R1 | B9.A | Charter v1 dispatched 2026-05-11 | `codex-spec-consult-r1.md` — GO-WITH-FIXES |
2093:358:| SPEC R2 | B9.A | Charter v2 dispatched 2026-05-11 | `codex-spec-consult-r2.md` — GO-WITH-FIXES → cleanup applied → v3 LOCKED |
2095:360:| ADVERSARIAL R1 | B9.A | After PLAN R1 GO or GO-WITH-FIXES + fix | `codex-adversarial-r1.md` |
2199:322:1. **RNDC14\_NDC\_MSTR column triage**: Which of the 68 columns does InfinityRx actually need? Full 68-column ingest vs. curated subset has significant implications for model maintainability and storage. Required before B9.3 begins.
2230:70:| SC-10 | Final B9 GATE-CLOSE GO or GO-WITH-FIXES |
2299:shared\db\models\__init__.py:8:from shared.db.models import core as core  # noqa: F401
2300:shared\db\models\__init__.py:9:from shared.db.models.bank_holidays import BankHoliday  # noqa: F401
2301:shared\db\models\__init__.py:10:from shared.db.models.events import EventDLQEntry, ProcessedEvent  # noqa: F401
2302:shared\db\models\__init__.py:11:from shared.db.models.sessions import UserSession  # noqa: F401
2343:modules\core-platform\alembic\env.py:29:from shared.db.models import core as _core_models  # noqa: E402,F401
2557:modules\core-platform\tests\conftest.py:41:from src.audit import models as _audit_models  # noqa: F401,E402
2558:modules\core-platform\tests\conftest.py:42:from src.notifications import models as _notif_models  # noqa: F401,E402
2599:modules\edi-compliance\tests\unit\test_baa_tracking.py:23:import src.models.edi_models  # noqa: F401 — register tables on Base.metadata
2790:modules\edi-compliance\tests\conftest.py:69:import src.models.edi_models  # noqa: F401
2833:shared\data_ingestion\tests\test_cms_opt_out.py:55:# under their canonical ``src.models.*`` names. Required because
2872:shared\data_ingestion\tests\test_cms_opt_out [conflicted].py:55:# under their canonical ``src.models.*`` names. Required because
2963:shared\tests\events\test_dlq_models.py:47:    from shared.db.models import events as _events_module  # noqa: F401 — register models
3227:modules\billing\alembic\env.py:30:from src.models.tables import (  # noqa: F401
3230:shared\tests\db\conftest.py:32:from shared.db.models import core as _core_models  # noqa: F401  ensure metadata populated
3379:modules\drug-database\tests\integration\test_fdb_pricing_through_create_app.py:64:    import drug_database.models.fdb_pricing_tables  # noqa: F401
3428:modules\prescriber-directory\alembic\env.py:29:from src.models.tables import (  # noqa: F401
3429:modules\prescriber-directory\alembic\env.py:39:from src.models.nppes_tables import (  # noqa: F401
3749:modules\ncpdp-core\src\ncpdp_core\transactions\base.py:40:    Per PRD §5.7.2 the six archetypes split by (F1, AN). Layer 3 models
3762:modules\payment-processing\alembic\env.py:27:from src.models.tables import (  # noqa: F401
3764:modules\ncpdp-core\src\ncpdp_core\transactions\b1_claim_billing_response_paid.py:18:model, F1 is optionally surfaced on AM21 (ResponseStatusSegment.header_response_status)
3844:modules\ai-nlp\alembic\env.py:37:from src.models.tables import (  # noqa: F401
4051:modules\ncpdp-core\src\ncpdp_core\segments\am21_response_status.py:11:          In this Layer 2 schema, F1 is modeled as an Optional field on
4230:modules\rules-engine\alembic\env.py:39:from src.models.tables import (  # noqa: F401
4232:modules\network-management\alembic\env.py:22:from network_mgmt.models import (  # noqa: F401, E402
4300:modules\pharmacy-directory\tests\conftest.py:39:from src.models.tables import (  # noqa: F401
4328:modules\reclaimrx\alembic\env.py:30:from reclaimrx.models import (  # noqa: F401, E402
4452:modules\paysync\alembic\env.py:30:from paysync.models import (  # noqa: F401, E402
4457:modules\pharmacy-directory\alembic\env.py:32:import src.models.tables  # noqa: E402, F401  — registers existing models
4458:modules\pharmacy-directory\alembic\env.py:33:import src.models.ncpdp_tables  # noqa: E402, F401  — registers NCPDP models
4627:modules\reporting\alembic\env.py:37:from src.models.tables import (  # noqa: F401
4690:modules\adjudication-engine\alembic\env.py:38:from src.models.tables import (  # noqa: F401
4723:modules\drug-database\alembic\env.py:41:import drug_database.models.fdb_pricing_tables  # noqa: E402, F401
4724:modules\drug-database\alembic\env.py:42:import drug_database.models.ndc_tables  # noqa: E402, F401
4726:modules\drug-database\alembic\env.py:49:from drug_database.models.fdb_pricing_tables import FDBPricingBase  # noqa: E402, F401
4727:modules\drug-database\alembic\env.py:50:from drug_database.models.ndc_tables import NDCBase  # noqa: E402, F401
4921:modules\program-config\alembic\env.py:31:from src.models.tables import (  # noqa: F401
4999:GO-WITH-FIXES
5005:| 1 | Goal-backward coverage of all SCs | PARTIAL | Table exists for SC-1..SC-11 at `plan.md:315-331`, but SC-1/SC-6 artifacts use unreconciled bad counts: `pg_class == 220` and `284/284` at `plan.md:321,326`. |
5011:| 7 | Pre-execute invariants testable | YES | Invariants have concrete checks: commit/memory references, FDW verify, `df -h`, config flag location, `pytest --collect-only`, manifest parse, consult slots (`plan.md:30-44`). |
5038:- HIGH: SC-1 verification artifact says `pg_class` FDB-prefixed table count should be 220 (`plan.md:321`), but recon says 3 source tables currently map to 2 DB tables (`recon.md:91-97`). Final DB-table count needs explicit definition, likely not `220`.
5040:- MEDIUM: `pytest --collect-only` “134 failures baseline” is conceptually mismatched: collect-only captures collection count/errors, not failure count. Use a real baseline command for failures or reword.
5044:GO-WITH-FIXES. Produce PLAN v2 before ADVERSARIAL: correct Tier C non-special count to 16, reconcile all FDW/SC-1 counts to 283 final FDW entries, lock migrations to the 6 SPEC-approved files, fix the loader-mode erratum, add a real weekly-delta schema/UPD-format guard, and explain the 42-vs-39 session delta or reduce the plan back to the charter budget.
5049:GO-WITH-FIXES
5055:| 1 | Goal-backward coverage of all SCs | PARTIAL | Table exists for SC-1..SC-11 at `plan.md:315-331`, but SC-1/SC-6 artifacts use unreconciled bad counts: `pg_class == 220` and `284/284` at `plan.md:321,326`. |
5061:| 7 | Pre-execute invariants testable | YES | Invariants have concrete checks: commit/memory references, FDW verify, `df -h`, config flag location, `pytest --collect-only`, manifest parse, consult slots (`plan.md:30-44`). |
5088:- HIGH: SC-1 verification artifact says `pg_class` FDB-prefixed table count should be 220 (`plan.md:321`), but recon says 3 source tables currently map to 2 DB tables (`recon.md:91-97`). Final DB-table count needs explicit definition, likely not `220`.
5090:- MEDIUM: `pytest --collect-only` “134 failures baseline” is conceptually mismatched: collect-only captures collection count/errors, not failure count. Use a real baseline command for failures or reword.
5094:GO-WITH-FIXES. Produce PLAN v2 before ADVERSARIAL: correct Tier C non-special count to 16, reconcile all FDW/SC-1 counts to 283 final FDW entries, lock migrations to the 6 SPEC-approved files, fix the loader-mode erratum, add a real weekly-delta schema/UPD-format guard, and explain the 42-vs-39 session delta or reduce the plan back to the charter budget.

 succeeded in 372ms:
3:**Status:** PLAN v2 DRAFT — codex PLAN R1 GO-WITH-FIXES absorbed (Tier C 17→16, FDW ladder reconciled to 283, migration shape locked to 6 files, loader-mode erratum corrected, T12 schema-drift threat added, pytest baseline clarified, effort math reconciled). Pending codex PLAN R2 verification + codex ADVERSARIAL consult.
16:3. **Per-phase batched migration plan** (SPEC-locked at charter v3 §SPEC-locked migration granularity).
17:4. **D2 perf gate** specifics (charter SC-4).
18:5. **MTL loader/runtime guards** (charter SC-5; Alembic NOT config-gated).
19:6. **Codex iteration cadence** (SPEC R1+R2 done; PLAN v1 consult + ADVERSARIAL pending; mini-GATE-CLOSE consults per phase).
24:- Specific column-curation decisions for non-RNDC14 Tier B/C tables (in-phase, codex-reviewed at each mini-GATE-CLOSE).
35:2. **B7.2 Phase 11A COMPLETE** — `ifx_prod_app` gone; `pg_authid count=0`; `setup_fdw --verify 66/66` PASS in dev + mock. (Memory `project_phase11a_implemented.md`.)
37:4. **Disk budget verified** — `df -h` shows ≥ 5 GB free on the reference DB volume to absorb D2's +1.16 GB (RNP2 + RPRDPP0) plus indexes plus working space. Captured at B9.A C0.
39:6. **134 pre-existing test failures baseline frozen** — at B9.A C0 capture TWO numbers: (a) test inventory via `pytest --collect-only -q | tail -1` (collection count), and (b) failure count via a real `pytest -q --tb=no` run, counting `FAILED`/`ERROR` lines. The 134 figure is the failure count. Each phase mini-GATE-CLOSE asserts: collection count unchanged ± new contract tests added in-phase; failure count unchanged (no regression and no unauthorized fix). Forensic wave handles those failures later (charter `Out of scope` row 3).
50:B9 runs as 8 sub-phases. Each phase below specifies its scope, deliverables, success-criteria mapping (`SC-N` refs the charter), mini-GATE-CLOSE criteria, est sessions, and **commit shape** (commits are session-scoped; exact hashes filled in evidence docs as they land).
58:- **`TableSpec` registry expansion path** — adds a `TIER`, `RECORD_COUNTS_KEY`, and `LOADER_GROUP` field to existing `TableSpec` so generic ingester can: (a) tier-filter, (b) row-count reconcile, (c) loader-register by tier. Backward-compatible default values mean existing FDB pricing TableSpecs still work.
59:- **Generated migration template** — script in `modules/drug-database/scripts/gen_fdb_tier_migration.py` consumes a `TableSpec` list + tier label and emits an idempotent Alembic migration file. Single-tier batched migrations are produced by this template (charter §SPEC-locked migration granularity).
61:- **MTL loader guard** — `fdb_load_mtl=False` config flag added to settings; loader registry default-excludes MTL; integration test `test_fdb_mtl_zero_rows_under_default` asserts zero MTL rows after default `load_fdb.py --mode fdb_weekly`. Test added in B9.A so it stays green through every later phase (no MTL data loads exist yet, so the assertion is trivial-true until B9.G; the test stays present after B9.G).
62:- **`setup_fdw.sh --verify` manifest expansion mechanism** — `infrastructure/scripts/lib/expected_reference_tables.txt` grows additively as each phase lands. Correct per-phase ladder: **66 baseline → 179 (after B9.B +113) → 245 (after B9.C +66) → 261 (after B9.D +16) → 262 (after B9.E +1 RNDC14) → 264 (after B9.F +2 pricing) → 283 (after B9.G +19 MTL schema-only)**. MTL adds foreign-table entries even though no data lands. B9.H final verify: 283/283 (matches charter SC-6).
63:- **pytest baseline markers** — committed to `waves/B9/baseline.md` at C0: collection count AND failure count, captured by the commands in invariant #6. Every phase mini-GATE-CLOSE re-runs both and asserts no regression.
69:| C0 | Baseline + invariants captured | `waves/B9/baseline.md`, evidence of `df -h`, `pg_authid`, FDW verify pass, pytest collect count |
71:| C2 | Generated migration template | `modules/drug-database/scripts/gen_fdb_tier_migration.py`, scripts test |
73:| C4 | MTL config flag + zero-row CI test (passes trivially today) | `shared/config/...`, `modules/drug-database/tests/test_fdb_mtl_zero_rows_under_default.py` |
78:**B9.A mini-GATE-CLOSE criteria (charter SC-9):**
80:- Contract template + migration template + MTL guard all unit-tested green.
81:- `pytest --collect-only` count unchanged vs. C0 baseline.
82:- `setup_fdw.sh --verify` still 66/66 (no FDB tables added yet).
95:- **1 alembic migration: `0009_fdb_tier_a.py`** covering all 113 Tier A tables. Charter SPEC-locks this granularity (`charter.md:75-79`); recon §4 confirms tables are uniform enough for single-file review (`recon.md:173-180`). No part-file split.
97:- 1 partial loader registry update per session (incremental)
103:- 1 alembic migration (`0009_fdb_tier_a.py`)
106:- `setup_fdw.sh` foreign-table count: 66 → 179
110:- SC-1 (217 tables have models + migrations + ingester) — partial: +113
112:- SC-6 (FDW verify) — partial: 179/179 PASS after B9.B
113:- SC-7 (weekly idempotency) — verified for Tier A only at B9.B mini-GATE-CLOSE
115:- SC-9 (mini-GATE-CLOSE) — see below
117:**B9.B mini-GATE-CLOSE criteria:**
120:- `setup_fdw.sh --verify` 179/179 PASS both env DBs
125:- `pytest --collect-only` count unchanged vs B9.A C0 baseline ± 113 new contract tests (counted in baseline)
126:- Codex mini-GATE-CLOSE consult: GO
132:### B9.C — Tier B: 66 NDC/GCN-keyed joins (12 sessions)
141:- **1 alembic migration: `0010_fdb_tier_b.py`** covering all 66 Tier B tables. SPEC-locked single file (`charter.md:75-79`). No part-file split.
145:- 66 SQLAlchemy models in `modules/drug-database/src/.../fdb/models/tier_b/`
146:- 66 `TableSpec` entries
147:- 1 alembic migration (`0010_fdb_tier_b.py`)
148:- Contract test coverage = 66 tables + FK-integrity assertions
150:- FDW foreign-table count: 179 → 245
152:**Success criteria:** SC-1 (partial: +66, cum 179/217), SC-2, SC-6 (245/245), SC-7 (Tier B idempotent), SC-8 (per-tier sampled behavioral), SC-9.
154:**B9.C mini-GATE-CLOSE criteria:** As B9.B + FK-integrity assertion green for every Tier B table.
158:### B9.D — Tier C non-RNDC14: 16 complex/large tables (4 sessions)
160:**Scope:** All 19 Tier C tables EXCEPT the three special-handled ones (RNDC14, RNP2, RPRDPP0). That leaves **16 tables** (19 - 3 = 16). Complex tables here are > 8 columns or > 50 MB. Includes ETC master, product master (RPRD0_PRODUCT — load before RNDC14), GCN master, etc.
165:- Each Tier C table gets explicit column-curation note (which columns kept, which dropped, why) in a per-table block in `waves/B9/tier_c_curation.md`
167:- 1 batched alembic migration: `0011_fdb_tier_c_minus_rndc14.py`
173:- 1 alembic migration (`0011_fdb_tier_c_minus_rndc14.py`)
175:- FDW foreign-table count: 245 → **261**
176:- Tier C dedicated behavioral tests for the 3-4 highest-value tables (ETC master, RPRD0_PRODUCT)
178:**Success criteria:** SC-1 (partial: cum 195/217), SC-2, SC-6 (261/261), SC-7, SC-8 (dedicated Tier C tests), SC-9.
180:**B9.D mini-GATE-CLOSE criteria:** As prior + money-path audit signed off + column-curation decisions documented per table.
184:### B9.E — RNDC14 dedicated migration (2 sessions)
188:**Why standalone:** 68 columns warrant column-by-column review at mini-GATE-CLOSE. Charter D1 locks "full 68-column ingest" — no column triage / no curation; every column lands. The review focuses on type correctness, NULL semantics, and naming (Python-snake_case from FDB upper-case).
192:- Session 1: SQLAlchemy model with all 68 columns, type-mapped (numeric → Decimal where money-relevant; integers where ID; text where descriptor); migration `0012_fdb_rndc14_ndc_mstr.py`; full contract test set
198:- 1 alembic migration (`0012_fdb_rndc14_ndc_mstr.py`)
201:- FDW foreign-table count: 261 → 262
203:**Success criteria:** SC-1 (cum 196/217), SC-3 (RNDC14 all 68 cols), SC-2, SC-6 (262/262), SC-7, SC-8 (dedicated RNDC14 tests), SC-9.
205:**B9.E mini-GATE-CLOSE criteria:** Column-by-column model review (codex consult walks all 68); type correctness audit; money-path audit; NDC normalization tests green.
211:**Scope:** The two large pricing tables explicitly deferred in Phase 09, reversed per charter D2. RNP2_NDC_PRICE (595 MB, 13.2M rows) and RPRDPP0_PRODUCT_PRICE (561 MB). +1.16 GB storage. Includes the **D2 performance gate** (charter SC-4) — not just disk verification.
215:- Session 1: SQLAlchemy models for RNP2 + RPRDPP0; migration `0013_fdb_pricing_big.py`; flip `fdb_load_product_prices=True` default
218:- Session 4: Weekly delta idempotency timing (re-run `load_fdb.py --mode fdb_weekly` → 0 new rows + timing); FDW verify; storage budget verification against B9.A C0 baseline
223:- 1 alembic migration (`0013_fdb_pricing_big.py`)
225:- Performance evidence in `waves/B9/perf_b9f.md`: timed dry-run, EXPLAIN ANALYZE, storage delta, weekly delta timing
227:- FDW foreign-table count: 262 → 264
229:**Success criteria:** SC-1 (cum 198/217), SC-4 (D2 perf gate met: timed dry-run + EXPLAIN ANALYZE + storage budget + weekly delta timing all documented), SC-2, SC-6 (264/264), SC-7, SC-8 (RNP2 + RPRDPP0 dedicated behavioral), SC-9.
231:**B9.F mini-GATE-CLOSE criteria — DRACONIAN per charter SC-4:**
238:- Codex mini-GATE-CLOSE consult: GO; codex specifically reviews EXPLAIN ANALYZE output for index gaps
242:### B9.G — Tier D MTL schema-only + loader-registration safeguards (3 sessions)
244:**Scope:** 19 MTL (Medical Test Lexicon) tables. Schema lands; data does NOT load. Per charter D3 + SC-5.
248:- Session 1: 19 SQLAlchemy models in `tier_d/`; migration `0014_fdb_mtl_schema.py` (un-gated, lands schema); 19 contract tests asserting tables exist + are queryable + are EMPTY
249:- Session 2: Loader registry: explicit exclusion of MTL from `--mode fdb_initial` and `--mode fdb_weekly`; opt-in mode `--mode fdb_mtl_data` exists but requires `fdb_load_mtl=True` config flag (charter SC-5 wording)
250:- Session 3: Integration test `test_fdb_mtl_zero_rows_under_default` (from B9.A C4) now exercises the live MTL tables — must continue to assert zero rows after default load. Documentation: `docs/runbooks/fdb-mtl-opt-in.md` explains how to enable IF licensing changes.
255:- 1 alembic migration (`0014_fdb_mtl_schema.py`)
256:- Loader-registration exclusion of MTL from default modes
259:- Updated integration test asserting zero MTL rows after default load
261:- FDW foreign-table count: 264 → **283** (MTL tables ARE in FDW even though data isn't loaded — they exist as foreign-table entries pointing at empty reference tables)
263:**FDW count derivation (corrected per codex PLAN R1):** 66 baseline + 113 (B9.B) + 66 (B9.C) + 16 (B9.D — 19 Tier C minus 3 special-handled) + 1 (B9.E RNDC14) + 2 (B9.F RNP2+RPRDPP0) + 19 (B9.G MTL schema-only) = **283**. Matches charter SC-6.
265:**Success criteria:** SC-1 (cum 217/217), SC-5 (MTL zero-row test green), SC-6 (283/283), SC-9.
267:**B9.G mini-GATE-CLOSE criteria:**
272:- Codex mini-GATE-CLOSE consult: GO; codex specifically verifies that flipping `fdb_load_mtl=False` after data load DOES NOT delete data (idempotency direction check)
278:**Scope:** Reconcile `infrastructure/scripts/lib/expected_reference_tables.txt` to the true final count, run final FDW verify, produce evidence + ship artifacts + memory updates, dispatch final B9 GATE-CLOSE codex consult.
282:- Session 1: Manifest expansion — `expected_reference_tables.txt` final count locked at **283** (matches charter SC-6; codex PLAN R1 reconciled). Update Werkbench inventory + glossary if new tables/concepts warrant.
283:- Session 2: Final `setup_fdw.sh --verify` **283/283** in both env DBs; full row-count reconciliation against `RECORD_COUNTS.TXT` for all loaded tables; published in `waves/B9/evidence.md`
285:- Session 4: B9 ship artifacts (`waves/B9/ship.md`); memory entry; wave-history index update; codex final GATE-CLOSE consult; PR creation if any of the FDB schema work was branched
295:- Codex final GATE-CLOSE verdict in `waves/B9/codex-gate-close.md`
297:**Success criteria — ALL SC-1..SC-11:**
299:- SC-1: 217 tables have models + migrations + ingester (verified via `pg_class` count + alembic history scan)
300:- SC-2: RECORD_COUNTS reconciled per table (or documented tolerance / exclusion for MTL)
302:- SC-4: D2 perf gate evidence present
303:- SC-5: MTL zero-row test green
305:- SC-7: Weekly delta idempotent across all 220 tables (verified at B9.H by running `--mode fdb_weekly` → 0 new rows in all 217 + already-covered 3)
306:- SC-8: Test strategy executed (contract + parity + reconciliation + sampled behavioral + dedicated Tier C)
307:- SC-9: All B9.B..B9.G mini-GATE-CLOSE consults passed
308:- SC-10: Final B9 GATE-CLOSE GO or GO-WITH-FIXES (FIXES applied iteratively until GO)
309:- SC-11: Evidence + ship + memory + wave-history all present
311:**B9 final GATE-CLOSE criteria:** codex final consult returns GO. Charter SC-10 escalates only if codex returns GO-WITH-FIXES three times in a row without convergence; that triggers an architectural pause.
321:| SC-1 | `pg_class` count of FDB-prefixed tables in `drug_database` schema == **219** (2 already-covered + 113 + 66 + 16 + 1 + 2 + 19 = 219 DB tables; the 220 source FDB tables map to 219 DB tables because RNP3+RPRDPTD0+RNPTYPD0 collapse into 2 DB tables `fdb_ndc_price_history` + `fdb_price_type_desc`); `alembic history` shows migrations 0009..0014 applied | B9.H Session 2 evidence |
323:| SC-3 | RNDC14 SQLAlchemy model has 68 columns; codex column-by-column review verdict captured in B9.E mini-GATE-CLOSE consult | B9.E |
324:| SC-4 | `waves/B9/perf_b9f.md`: timed dry-run, EXPLAIN ANALYZE, storage delta, weekly delta timing | B9.F |
325:| SC-5 | `test_fdb_mtl_zero_rows_under_default` green; opt-in mode reviewed in codex consult | B9.G |
326:| SC-6 | `setup_fdw.sh --verify` output **283/283** in dev + mock (charter-matched) | B9.H Session 2 |
327:| SC-7 | `load_fdb.py --mode fdb_weekly` re-run logs zero new rows across all 220 tables | B9.H Session 4 |
328:| SC-8 | Test counts per category in evidence.md: 217 contract tests + 220 schema-parity + 217 row-count assertions + N sampled behavioral + dedicated Tier C suite | B9.H Session 2 |
329:| SC-9 | All 6 mini-GATE-CLOSE consult docs present (`waves/B9/codex-mini-gate-close-{B,C,D,E,F,G}.md`) with GO verdicts | continuously |
330:| SC-10 | `waves/B9/codex-gate-close.md` with GO verdict | B9.H Session 4 |
331:| SC-11 | `evidence.md`, `ship.md`, memory file, `wave-history.md` line all present and pointing at the right commits | B9.H Session 4 |
339:| T1 | latin-1 decode failures on text-heavy Tier A/B tables (recon §7 Risk 4) | MED | MED | B9.A C3 contract test includes decode smoke on first 1000 rows of text-heavy tables; failures block the migration |
340:| T2 | Money-path columns typed as `float`/`numeric` lose Decimal discipline (rules `financial-precision.md`) | MED | HIGH | B9.D money-path audit; B9.E + B9.F mandatory `Decimal` audit; codex mini-GATE-CLOSE flags any `Float` or non-explicit `Numeric` on money columns |
342:| T4 | Per-phase mini-GATE-CLOSE consults skipped under time pressure | LOW | HIGH | Each phase's commit chain explicitly lists the consult commit; gate-check tool refuses to advance the wave state if the consult file is missing |
343:| T5 | MTL accidentally loads data despite guards (charter R7) | LOW | HIGH | Triple-layer guard: schema-only migration ✓, loader-registry default exclusion ✓, integration test asserts zero rows ✓; B9.G codex consult specifically reviews the guard chain |
345:| T7 | Weekly delta idempotency broken on a specific table (ON CONFLICT clause incorrect) | MED | MED | Each phase's mini-GATE-CLOSE re-runs weekly delta; 0 new rows is the gate; per-tier sampled idempotency tests |
346:| T8 | Migration batched files become un-reviewable (~25 tables each) | LOW | MED | Generated migration template produces deterministic, ordered, alphabetized output for diff-friendly review; codex PLAN consult specifically asked to verify migration shape |
347:| T9 | FDW manifest expansion drifts from actual reference DB state | LOW | MED | `setup_fdw.sh --verify` at each phase mini-GATE-CLOSE catches drift before next phase opens |
348:| T10 | Test count baseline drifts (collection growth unexplained; or 134 pre-existing failures become 135+) | MED | MED | B9.A C0 captures TWO baselines (per invariant #6): collection count via `pytest --collect-only -q | tail -1` AND failure count via `pytest -q --tb=no` line-count of `FAILED`/`ERROR`. Each phase mini-GATE-CLOSE asserts no regression in either, ± in-phase contract tests on the collection number. |
349:| T11 | Reference DB FDW + write semantics conflict (writing to a foreign table) | LOW | HIGH | All writes go to `infinityrx_reference` directly via loader; foreign-table access in env DBs is read-only per Phase 11A pattern. B9.B C1 verifies no INSERT statement targets a foreign table. |
350:| T12 | Weekly FDB UPD delta format isn't uniformly A/C/D across all 220 tables — some tables may require TRUNCATE+INSERT instead of UPSERT (recon §7 risk implied; codex PLAN R1 surfaced) | MED | HIGH | B9.A C3 contract template includes a UPD-format probe: for each table, verify the first column of the table's `.UPD` file matches the expected A/C/D code. Tables that fail the probe are flagged as TRUNCATE+INSERT and routed through a separate idempotent reload path. Per-phase mini-GATE-CLOSE re-asserts the probe + weekly delta rerun. Charter R4 ("weekly delta breaks because NEW columns") is covered by the same probe plus a column-set parity check against the live model. |
363:| mini-GATE-CLOSE B9.B | B9.B | After Tier A all 113 tables ingested | `codex-mini-gate-close-B.md` |
364:| mini-GATE-CLOSE B9.C | B9.C | After Tier B all 66 tables ingested | `codex-mini-gate-close-C.md` |
365:| mini-GATE-CLOSE B9.D | B9.D | After Tier C non-RNDC14 all 16 ingested | `codex-mini-gate-close-D.md` |
366:| mini-GATE-CLOSE B9.E | B9.E | After RNDC14 column-by-column review | `codex-mini-gate-close-E.md` |
367:| mini-GATE-CLOSE B9.F | B9.F | After D2 perf gate evidence captured | `codex-mini-gate-close-F.md` |
368:| mini-GATE-CLOSE B9.G | B9.G | After MTL schema-only + guards ship | `codex-mini-gate-close-G.md` |
369:| GATE-CLOSE | B9.H | Wave shipping artifacts assembled | `codex-gate-close.md` |
371:**Total codex consults projected:** 12 (2 SPEC done + PLAN R1 done + PLAN R2 + ADVERSARIAL + 6 mini-GATE-CLOSE + final GATE-CLOSE = 12).
378:- 134 pre-existing test failures (forensic wave handles these; charter §Out of scope)
380:- MTL data ingest (schema only; flip flag in a later wave IF licensing changes)
391:1. **FDW final count: 283 vs 284** → **RESOLVED: 283.** Tier C arithmetic bug (`19 - 3 = 16, not 17`) cascaded to 284. Plan v2 corrects all references: 66 → 179 → 245 → 261 → 262 → 264 → 283.
393:3. **Loader-orchestration modes: existing vs new** → **RESOLVED:** existing `scripts/load_fdb.py` already declares `fdb_initial`, `fdb_weekly`, `fdb_rebase`. B9.A C4 does NOT need to add `fdb_weekly`. It may need to add tier-specific modes (`fdb_tier_a`, `fdb_tier_b`, `fdb_mtl_data`) if per-tier loaders are desired; PLAN v2 leaves that as a B9.A C1 design decision (additive to existing modes).
395:## Effort math reconciliation (charter 39 vs plan 42)
399:- **Charter §Workstreams view (39 sessions):** counts only productive ingest work — W1 Tier A (10) + W2 Tier B (12) + W3 Tier C incl. perf gate (10) + W4 Tier D (3) + W5 cross-cutting/closeout (4) = **39**.
400:- **Plan §Phased commit chain view (42 sessions):** counts every phase including B9.A meta-phase (charter v3 + plan v1/v2 + codex SPEC R2 + PLAN R1 + ADVERSARIAL + infra scaffolding = 3 sessions) and B9.H closeout (4 sessions). 3 + B (10) + C (12) + D (4) + E (2) + F (4) + G (3) + H (4) = **42**.
402:The 3-session delta is the B9.A meta-phase which the workstream view excludes by design (it's not table-ingest work). Both views are accurate. Charter's "~39" is the productive-work commitment; PLAN's 42 is the calendar-aware total including framework gates.
411:- At each mini-GATE-CLOSE: full sign-off sheet committed

 succeeded in 365ms:
1:# Wave B9 — FDB NDDF Plus 220-table extension (full scope)
5:**Predecessor:** Phase 09 FDB pricing ingester (3 tables); Phase 11A reference DB topology; B7.2 architectural cleanup
12:Extend FDB NDDF Plus ingest from current **3 tables → all 220 tables** (217-table gap). Adjudication, formulary, reclaimrx, and future Phase 4 modules gain full FDB reference coverage. Single B9 wave milestone; multi-session execution.
19:| D2 | **RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE = include + load by default** | Reverses Phase 09 `fdb_load_product_prices=False` deferral. +1.16 GB storage required; needs disk + Postgres performance verification at C0. |
20:| D3 | **Medical Test Lexicon (MTL) = schema-only, no data load** | Honors "clinical screening NOT subscribed" memory while landing table structure for future activation. 19 tables, 103 KB raw. If licensing changes, flip a config flag. |
29:| W3 | Tier C — complex/large + RNDC14 full + RNP2 + RPRDPP0 + perf gate | 19 | ~10 sessions (8 baseline + ~2 D2 perf gate) |
30:| W4 | Tier D — MTL schema-only (no data load) | 19 | ~3 sessions |
31:| W5 | C0 baseline + D2 dry-run perf test + FDW manifest extension + closeout | n/a | ~4 sessions |
33:**Total: ~39 sessions** (recon's A+B+C estimate is 34; +3 Tier D + ~2 D2 perf gate = 39). With codex review cadence already baked into per-phase budget. **Charter v1's 100-session figure was a misread; v2 corrects to recon's actual numbers.** Wall-clock at 3 sessions/week: ~13 weeks (~3 months).
40:- Phase 4 forward feature work
42:## Phased execution + per-phase closure gates (HIGH #1 codex fix)
44:B9 ships incrementally **with mandatory per-phase closure gates** — each phase (B9.B..B9.F) gets its own evidence + row-count reconciliation + migration review + FDW verify + test baseline comparison + mini-GATE-CLOSE consult. A single final GATE-CLOSE across 220 tables would catch drift too late.
46:| Phase | Sub-scope | Sessions | Closure gate |
48:| B9.A | Charter v2 + plan v1 + codex SPEC R2 / PLAN / ADVERSARIAL | 2-3 | Plan v1 locked |
49:| B9.B | Tier A — 113 simple lookups via generic table-driven ingester | 10 | **B9.B mini-GATE-CLOSE** — evidence + row-count manifest + FDW verify 116/116 + ingester contract tests |
50:| B9.C | Tier B — 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** — same scope + per-tier sampled behavioral tests |
51:| B9.D | Tier C non-RNDC14 — 17 complex tables | 4 | **B9.D mini-GATE-CLOSE** |
52:| B9.E | RNDC14 dedicated migration (68 cols) | 2 | **B9.E mini-GATE-CLOSE** — column-by-column model review |
53:| B9.F | RNP2 + RPRDPP0 + C0 perf gate (D2 reversal) | 4 | **B9.F mini-GATE-CLOSE** — perf test results + EXPLAIN ANALYZE + storage budget verification |
54:| B9.G | Tier D MTL schema-only + loader-registration safeguards | 3 | **B9.G mini-GATE-CLOSE** — integration test asserts zero MTL rows after default `load_fdb.py --mode fdb_weekly` |
55:| B9.H | Manifest extension (66 → 283 FDW entries) + final closeout artifacts | 4 | **Final B9 GATE-CLOSE** — full cross-tier consult |
61:| SC-1 | All 217 currently-missing FDB tables have SQLAlchemy models + alembic migrations + ingester support |
62:| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected ± documented tolerance (MTL excluded — schema-only) |
63:| SC-3 | RNDC14 ingest covers all 68 columns with column-curation review at B9.E mini-GATE-CLOSE |
64:| SC-4 | **D2 performance gate**: timed full-load dry run of RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE measured; representative `EXPLAIN ANALYZE` on indexed query patterns captured; Postgres + FDW verify completes within 5min after indexes built; weekly delta idempotency timing documented |
65:| SC-5 | MTL schema lands but **runtime/loader guards** prevent data load: `fdb_load_mtl=False` default; MTL tables excluded from default loader registry; integration test asserts **zero MTL rows** after default `load_fdb.py --mode fdb_weekly`. Alembic migration itself is NOT config-gated (per codex SPEC R1 #4). |
66:| SC-6 | `setup_fdw.sh --verify` 283/283 PASS in both env DBs |
67:| SC-7 | Weekly delta ingest path idempotent across all 220 tables (ON CONFLICT DO NOTHING or UPSERT per table; verified by re-running) |
69:| SC-9 | Each of B9.B..B9.G passes a mini-GATE-CLOSE consult before next phase opens |
70:| SC-10 | Final B9 GATE-CLOSE GO or GO-WITH-FIXES |
71:| SC-11 | Evidence + ship + memory + wave-history + B9 phased-progress dashboard |
73:## SPEC-locked migration granularity (codex SPEC R1 #5 fix)
75:**Migration granularity is SPEC-locked**, not deferred to plan:
76:- **NO** one-table-per-migration (213 migrations would be unmaintainable)
77:- **NO** single 217-table migration (atomicity ruined; review intractable)
78:- **YES** per-phase batched migrations (`0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14`, `0012_fdb_rndc14`, `0013_fdb_pricing_big` for RNP2+RPRDPP0, `0014_fdb_mtl_schema`)
79:- **RNDC14 migration MUST be standalone** (`0012_fdb_rndc14`) — 68 cols warrant dedicated review at B9.E mini-GATE-CLOSE
85:| R1 | 217 alembic migrations is unwieldy for review | SPEC-locked above to ~6 per-phase batched migrations + RNDC14 standalone. |
88:| R4 | FDB weekly delta breaks because some tables ship NEW columns | Schema version detection + drift logging; halt ingest on unrecognized column |
90:| R6 | 6-month wall-clock invites scope drift / charter decay | Phased execution table is contract; each phase has explicit closure gate |
91:| R7 | MTL schema accidentally activates (data ingest fires when it shouldn't) | Config flag `fdb_load_mtl=False` enforced via integration test; CI gate denies MTL data on default flag |

 succeeded in 381ms:
5:**Goal:** Scope FDB NDDF Plus 220-table extension beyond the 3-table Phase 09 baseline
11:- The FDB drop contains exactly **220 data tables** in `NDDF Plus DB/NDDF PLUS DB.zip`, all with matching ANSI DDL. The current ingester covers **3 tables** (RNP3\_NDC\_PRICE, RPRDPTD0\_PRICE\_TYPE\_DESC, RNPTYPD0\_NDC\_PRICE\_TYPE\_DESC) mapped to **2 DB tables** (`fdb_ndc_price_history`, `fdb_price_type_desc`). Gap: **217 tables**.
12:- Tables span six FDB modules: NDDF BASICS 3.0 (98 tables), MEDNAMES 3.0 (63), ETC 1.0 (16), TALL MAN PLUS 2.0 (15), XRF 1.0 (9), MTL 1.0 (19). MTL (Medical Test Lexicon) is the only module without a clear adjudication use case — treat as a product decision.
13:- The generic `TableSpec`-driven adapter (`FDBLocalDropAdapter.parse_table`) already works for any pipe-delimited FDB table. The ingest architecture is **extension-ready**: new tables become new `TableSpec` constants + SQLAlchemy models + a migration, no adapter surgery required.
14:- Tier classification: **113 Tier A** (simple desc/lookup), **66 Tier B** (NDC/GCN-keyed joins), **19 Tier C** (complex/large, including the 68-column NDC master and two pricing tables each >500 MB), **19 Tier D** (MTL, pending product decision). Total raw effort estimate: ~120h; with codex review cadence ~156h (~39 four-hour sessions). B9 must be phased across multiple sub-waves.
15:- The FDW `LIMIT TO` allowlist in `setup_fdw.sh` currently names 2 FDB tables. Adding 217 more requires a structured FDW manifest expansion — this is a one-time setup change, not per-deployment.
16:- Two Tier C tables dominate storage risk: `RNP2_NDC_PRICE` (595 MB uncompressed, 13.2M rows) and `RPRDPP0_PRODUCT_PRICE` (561 MB). Both are pricing variants already noted in the Phase 09 ingester as deferred. Ingesting them requires an explicit go/no-go decision before B9.2.
35:NDDF Plus DB/NDDF PLUS DB.zip      <- 220 data table files (pipe-delimited, latin-1)
37:NDDF Plus UPD/NDDF PLUS UPD.zip    <- weekly delta (A/C/D prefixed rows)
43:- DB zip entries: **220**
44:- ANSI DDL `CREATE TABLE` statements: **220** (+ 1 meta: `NDDF_PRODUCT_INFO`)
72:| RTMDFID1\_TM\_ROUTED\_DF\_MED | 4 | 209 KB | MED\_ID, source, confusion\_flag, tall-man name |
87:| `modules/drug-database/drug_database/models/fdb_pricing_tables.py` | 2 ORM models |
88:| `modules/drug-database/alembic/versions/0008_fdb_pricing.py` | 1 migration covering 2 tables |
91:**Currently ingested FDB tables → DB tables:**
95:| RNP3\_NDC\_PRICE | `drug_database.fdb_ndc_price_history` | 13.2M rows; append-only, A/C/D UPD semantics |
99:**Coverage gap: 217 of 220 FDB tables have no DB mapping.**
101:Key high-value uncovered tables:
114:**FDW manifest impact:** `setup_fdw.sh` uses `IMPORT FOREIGN SCHEMA ... LIMIT TO (...)` with a dynamic list. Currently 2 FDB table names are in scope for drug\_database. B9 full coverage would expand this list by 217 entries.
121:- **Tier A** — Pure reference/description tables. Typically code → description, ≤ 5 columns, < 2 MB uncompressed, name suffix `D0`–`D9` pattern or a small static lookup. No NDC normalization, no join design, no money columns.
122:- **Tier B** — NDC-keyed, GCN-keyed, or MedID-keyed link/crossref tables. Simple join design. May include NDC normalization (re-use existing `normalize_ndc`). 2–7 columns typical.
123:- **Tier C** — Complex tables: > 8 columns, or large pricing tables (> 50 MB), or key structural masters (RNDC14 at 68 cols). Require careful column mapping, money-path review (financial-precision.md), or parent-key join design with existing ingested tables.
124:- **Tier D** — Medical Test Lexicon (MTL 1.0). 19 tables covering lab analytes, panels, specimen IDs. Structurally simple (most are tiny) but the business question — do adjudication rules need lab linkage? — must be answered before ingest design begins.
130:| C — Complex/large | 19 | 90 min | 28.5h | RNDC14 (68 cols), two 500 MB+ pricing tables, ETC master |
131:| D — MTL (product decision) | 19 | 30 min | 9.5h | Small tables, pending go/no-go |
134:**Tier C table inventory (all 19):**
166:| A — One big migration | All 217 tables in `0009_fdb_full.py` | REJECTED — one migration failure blocks everything; impossible to review |
169:| D — Tiered phasing with batch migrations | One migration per sub-wave (B9.1 = Tier A, B9.2 = Tier B, B9.3 = Tier C) | RECOMMENDED |
173:- `0009_fdb_tier_a.py` — 113 Tier A tables (all small; one migration is reviewable because models are uniform 2–5-col descriptors)
174:- `0010_fdb_tier_b.py` — 66 Tier B tables (NDC/GCN-keyed)
175:- `0011_fdb_tier_c.py` — 19 Tier C tables (but RNDC14 should be its own migration `0011a` given 68-col complexity)
176:- `0012_fdb_tier_d.py` — 19 MTL tables (only if product go decision is made)
180:- Tier A tables are structurally uniform (code/desc pattern); 113 in one migration is reviewable.
181:- Tier C needs its own slot because `RNDC14_NDC_MSTR` at 68 columns is a significant schema decision that may require discussion about which columns to retain vs. drop (storage vs. value tradeoff).
192:| E — Generic table-driven ingester | Config file (YAML/dict) maps table names → TableSpec; one ingester loops all tables | RECOMMENDED for Tier A and B |
193:| F — Per-table service | One `fdb_<table>_ingester.py` per table, matching Phase 09 pattern | Appropriate for Tier C tables with complex logic |
198:**For Tier A + B (179 tables):**
206:**For Tier C (19 tables):**
207:Complex tables need per-table logic:
209:- `RNP2_NDC_PRICE` and `RPRDPP0_PRODUCT_PRICE`: pricing tables need go/no-go decision and Decimal handling audit (financial-precision.md)
210:- Other Tier C tables can share a thin wrapper around the generic ingester with overridden coercers
213:MTL tables are tiny (total uncompressed: ~103 KB). If the product decision is "yes", they fit cleanly into the generic ingester. If "no", skip entirely. No architectural complexity.
223:| Tier A: 113 tables × 20 min | 37.7h |
224:| Tier B: 66 tables × 40 min | 44.0h |
225:| Tier C: 19 tables × 90 min | 28.5h |
226:| Tier D: 19 tables × 30 min (if go) | 9.5h |
228:| FDW manifest expansion (setup_fdw.sh + testing) | 4h |
236:- B9.1 (Tier A, 113 tables): ~10 sessions
237:- B9.2 (Tier B, 66 tables): ~12 sessions
238:- B9.3 (Tier C, 19 tables): ~8 sessions
243:**Realistic wall-clock:** 3–4 months for B9.1 through B9.3. Consider whether B9 is actually two waves (B9 = Tier A+B; B10 = Tier C) for milestone hygiene.
252:**Risk 2 — Two 500 MB+ pricing tables require explicit go/no-go (HIGH)**
253:`RNP2_NDC_PRICE` (595 MB, 13.2M rows legacy pricing) and `RPRDPP0_PRODUCT_PRICE` (561 MB) were explicitly deferred in Phase 09 (`fdb_load_product_prices=False` config flag). Loading both adds ~1.1 GB uncompressed to the reference DB weekly. Risk: storage growth and ingest window extension. Mitigation: Decide at B9.3 charter whether these are in scope. If yes, add dedicated EXPLAIN ANALYZE runbook.
255:**Risk 3 — FDW LIMIT TO list maintenance drift (MEDIUM)**
256:`setup_fdw.sh` uses a dynamic `LIMIT TO` allowlist. Adding 217 table names to this list is a one-time change, but the list must stay in sync with the actual schema. If a new FDB drop adds tables, the FDW will silently omit them. Mitigation: Auto-generate the LIMIT TO list from the ORM `metadata.tables` at setup time rather than maintaining a manual list.
259:Current FDB ingest: RNP3 (13.2M rows) takes ~minutes. Adding 217 tables including NDC master (501K rows), ETC NDC mapping (616K rows), and MedName tables adds significant volume to the weekly UPD cycle. The UPD zip must also be verified to contain all tables (not just pricing). Mitigation: Profile UPD zip contents against DB zip contents. Validate that `NDDF Plus UPD/` has a matching file for each table before committing to weekly ingest for all 220.
261:**Risk 5 — UPD zip may not contain all tables (MEDIUM)**
262:The current adapter only reads from UPD for RNP3 (pricing). Some FDB reference tables (e.g., description tables) may ship full-replacement in UPD rather than A/C/D delta. Mitigation: Inspect the UPD zip structure early in B9.1. If some tables are full-replacement (no A/C/D prefix), the ingester must detect this and use TRUNCATE+INSERT rather than ON CONFLICT DO NOTHING.
265:The existing adapter handles latin-1 decoding for RNP3 (numeric-heavy). Text-heavy tables (drug names, descriptions, brand names) are more likely to have characters in the latin-1 extended range (0x80–0xFF). Mitigation: Audit the first 1000 rows of text-column tables (RMIID1\_MED, RNDC14\_NDC\_MSTR brand fields) for decoding failures before schema finalization.
268:At 217 new models, the per-test `create_all()` time in SQLite fixtures will grow. Currently 2 FDB models; adding 217 means each test session creates 219 tables. Risk: slow CI. Mitigation: Split the `FDBPricingBase` into module-level declarative bases (`FDBBasicsBase`, `FDBMedNamesBase`, etc.) so tests only create\_all for the module under test. Plan this in B9.0 before any model files are written.
279:- Audit UPD zip structure: verify which tables ship as delta vs. full-replacement
282:### B9.1 — Tier A: 113 simple lookup tables (target ~10 sessions)
287:- 113 ORM model classes in `fdb_lookup_tables.py` (batched by module)
288:- Integration test: load against real DB zip, verify row counts vs RECORD\_COUNTS.TXT for all 113 tables
289:- FDW manifest update: add 113 table names to `setup_fdw.sh` LIMIT TO list
292:### B9.2 — Tier B: 66 NDC/GCN-keyed tables (target ~12 sessions)
296:- ORM models in `fdb_link_tables.py`
299:- FDW manifest update: +66 entries
302:### B9.3 — Tier C: 19 complex tables (target ~8 sessions)
306:- One migration per Tier C table (or `0011_fdb_tier_c.py` + `0011a_fdb_ndc_master.py` for RNDC14 separately)
309:- FDW manifest update: +19 entries
312:### B9.4 — Tier D: MTL (19 tables) — CONDITIONAL on product decision
315:- All 19 MTL tables are tiny (total 103 KB) — one session if go decision is made
326:3. **MTL go/no-go**: Does any planned adjudication rule or reclaimrx detection require lab test linkage (NDDF MTL 1.0)? If yes, B9.4 is in scope. If no, all 19 MTL tables are permanently skipped.
328:4. **Wave boundary — is B9 one wave or two?**: 34 sessions is 3–4 months. Consider splitting at the Tier A/B boundary: B9 = Tier A (113 tables, ~10 sessions, quick wins), B10 = Tier B+C (85 tables, ~20 sessions, full coverage). This gives a shippable milestone in ~6 weeks rather than waiting 4 months for the full wave.

codex
I’ve got the main evidence now. One thing already stands out: v2 corrected the final SC-1 artifact to 219 DB tables at line 321, but there is still older wording at line 299 saying “217 tables have models + migrations + ingester,” which may or may not be acceptable as shorthand for the missing-table gap. I’m checking the exact charter consistency and vendor-name pass before finalizing the verdict.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "First|DataBank|Databank|FDB|NDDF|First Databank|First DataBank|FirstDataBank" plan.md charter.md recon.md codex-plan-consult-r1.md' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "''^'"\\| B9\\.|mini-GATE-CLOSE|Closure gate|Phase|SC-1|SC-2|SC-3|SC-4|SC-5|SC-6|SC-7|SC-8|SC-9|SC-10|SC-11|0009|0010|0011|0012|0013|0014|part\" plan.md charter.md" in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "_part|part[0-9]|part1|part2|part3|0009_|0010_|0011_|0012_|0013_|0014_" plan.md' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "failure count|FAILED|ERROR|pytest -q|collect-only|baseline|134" plan.md' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
 succeeded in 410ms:
charter.md:5:**Predecessor:** Phase 09 FDB pricing ingester (3 tables); Phase 11A reference DB topology; B7.2 architectural cleanup
charter.md:12:Extend FDB NDDF Plus ingest from current **3 tables → all 220 tables** (217-table gap). Adjudication, formulary, reclaimrx, and future Phase 4 modules gain full FDB reference coverage. Single B9 wave milestone; multi-session execution.
charter.md:19:| D2 | **RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE = include + load by default** | Reverses Phase 09 `fdb_load_product_prices=False` deferral. +1.16 GB storage required; needs disk + Postgres performance verification at C0. |
charter.md:40:- Phase 4 forward feature work
charter.md:42:## Phased execution + per-phase closure gates (HIGH #1 codex fix)
charter.md:44:B9 ships incrementally **with mandatory per-phase closure gates** — each phase (B9.B..B9.F) gets its own evidence + row-count reconciliation + migration review + FDW verify + test baseline comparison + mini-GATE-CLOSE consult. A single final GATE-CLOSE across 220 tables would catch drift too late.
charter.md:46:| Phase | Sub-scope | Sessions | Closure gate |
charter.md:48:| B9.A | Charter v2 + plan v1 + codex SPEC R2 / PLAN / ADVERSARIAL | 2-3 | Plan v1 locked |
charter.md:49:| B9.B | Tier A — 113 simple lookups via generic table-driven ingester | 10 | **B9.B mini-GATE-CLOSE** — evidence + row-count manifest + FDW verify 116/116 + ingester contract tests |
charter.md:50:| B9.C | Tier B — 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** — same scope + per-tier sampled behavioral tests |
charter.md:51:| B9.D | Tier C non-RNDC14 — 17 complex tables | 4 | **B9.D mini-GATE-CLOSE** |
charter.md:52:| B9.E | RNDC14 dedicated migration (68 cols) | 2 | **B9.E mini-GATE-CLOSE** — column-by-column model review |
charter.md:53:| B9.F | RNP2 + RPRDPP0 + C0 perf gate (D2 reversal) | 4 | **B9.F mini-GATE-CLOSE** — perf test results + EXPLAIN ANALYZE + storage budget verification |
charter.md:54:| B9.G | Tier D MTL schema-only + loader-registration safeguards | 3 | **B9.G mini-GATE-CLOSE** — integration test asserts zero MTL rows after default `load_fdb.py --mode fdb_weekly` |
charter.md:55:| B9.H | Manifest extension (66 → 283 FDW entries) + final closeout artifacts | 4 | **Final B9 GATE-CLOSE** — full cross-tier consult |
charter.md:61:| SC-1 | All 217 currently-missing FDB tables have SQLAlchemy models + alembic migrations + ingester support |
charter.md:62:| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected ± documented tolerance (MTL excluded — schema-only) |
charter.md:63:| SC-3 | RNDC14 ingest covers all 68 columns with column-curation review at B9.E mini-GATE-CLOSE |
charter.md:64:| SC-4 | **D2 performance gate**: timed full-load dry run of RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE measured; representative `EXPLAIN ANALYZE` on indexed query patterns captured; Postgres + FDW verify completes within 5min after indexes built; weekly delta idempotency timing documented |
charter.md:65:| SC-5 | MTL schema lands but **runtime/loader guards** prevent data load: `fdb_load_mtl=False` default; MTL tables excluded from default loader registry; integration test asserts **zero MTL rows** after default `load_fdb.py --mode fdb_weekly`. Alembic migration itself is NOT config-gated (per codex SPEC R1 #4). |
charter.md:66:| SC-6 | `setup_fdw.sh --verify` 283/283 PASS in both env DBs |
charter.md:67:| SC-7 | Weekly delta ingest path idempotent across all 220 tables (ON CONFLICT DO NOTHING or UPSERT per table; verified by re-running) |
charter.md:68:| SC-8 | **Test coverage strategy** (per codex SPEC R1 #6): contract coverage for every `TableSpec`; schema/model parity for every table; row-count reconciliation for every loaded table; sampled behavioral tests per tier; dedicated Tier C tests for RNDC14 / RNP2 / RPRDPP0 / weekly delta. **No bespoke per-table behavioral tests** for the 217 tables — too heavy. |
charter.md:69:| SC-9 | Each of B9.B..B9.G passes a mini-GATE-CLOSE consult before next phase opens |
charter.md:70:| SC-10 | Final B9 GATE-CLOSE GO or GO-WITH-FIXES |
charter.md:71:| SC-11 | Evidence + ship + memory + wave-history + B9 phased-progress dashboard |
charter.md:78:- **YES** per-phase batched migrations (`0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14`, `0012_fdb_rndc14`, `0013_fdb_pricing_big` for RNP2+RPRDPP0, `0014_fdb_mtl_schema`)
charter.md:79:- **RNDC14 migration MUST be standalone** (`0012_fdb_rndc14`) — 68 cols warrant dedicated review at B9.E mini-GATE-CLOSE
charter.md:89:| R5 | Tier C complex tables have foreign keys that don't validate after partial ingest | Defer FK constraints to phase-end; verify referential integrity at C8 |
charter.md:90:| R6 | 6-month wall-clock invites scope drift / charter decay | Phased execution table is contract; each phase has explicit closure gate |
charter.md:106:The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification — preserving B7-style checkpoint cadence inside the single B9 milestone.
plan.md:17:4. **D2 perf gate** specifics (charter SC-4).
plan.md:18:5. **MTL loader/runtime guards** (charter SC-5; Alembic NOT config-gated).
plan.md:19:6. **Codex iteration cadence** (SPEC R1+R2 done; PLAN v1 consult + ADVERSARIAL pending; mini-GATE-CLOSE consults per phase).
plan.md:24:- Specific column-curation decisions for non-RNDC14 Tier B/C tables (in-phase, codex-reviewed at each mini-GATE-CLOSE).
plan.md:35:2. **B7.2 Phase 11A COMPLETE** — `ifx_prod_app` gone; `pg_authid count=0`; `setup_fdw --verify 66/66` PASS in dev + mock. (Memory `project_phase11a_implemented.md`.)
plan.md:36:3. **Reference DB topology stable** — `infinityrx_reference` schemas `drug_database / drug_db / reference / shared` exist; current FDB tables `fdb_ndc_price_history` + `fdb_price_type_desc` present and queryable through FDW. (Phase 11A C9.)
plan.md:38:5. **`fdb_load_product_prices` config flag still in code** — Phase 09 deferral flag location identified; B9.F will flip default to `True` and document.
plan.md:39:6. **134 pre-existing test failures baseline frozen** — at B9.A C0 capture TWO numbers: (a) test inventory via `pytest --collect-only -q | tail -1` (collection count), and (b) failure count via a real `pytest -q --tb=no` run, counting `FAILED`/`ERROR` lines. The 134 figure is the failure count. Each phase mini-GATE-CLOSE asserts: collection count unchanged ± new contract tests added in-phase; failure count unchanged (no regression and no unauthorized fix). Forensic wave handles those failures later (charter `Out of scope` row 3).
plan.md:48:## Phased commit chain
plan.md:50:B9 runs as 8 sub-phases. Each phase below specifies its scope, deliverables, success-criteria mapping (`SC-N` refs the charter), mini-GATE-CLOSE criteria, est sessions, and **commit shape** (commits are session-scoped; exact hashes filled in evidence docs as they land).
plan.md:62:- **`setup_fdw.sh --verify` manifest expansion mechanism** — `infrastructure/scripts/lib/expected_reference_tables.txt` grows additively as each phase lands. Correct per-phase ladder: **66 baseline → 179 (after B9.B +113) → 245 (after B9.C +66) → 261 (after B9.D +16) → 262 (after B9.E +1 RNDC14) → 264 (after B9.F +2 pricing) → 283 (after B9.G +19 MTL schema-only)**. MTL adds foreign-table entries even though no data lands. B9.H final verify: 283/283 (matches charter SC-6).
plan.md:63:- **pytest baseline markers** — committed to `waves/B9/baseline.md` at C0: collection count AND failure count, captured by the commands in invariant #6. Every phase mini-GATE-CLOSE re-runs both and asserts no regression.
plan.md:78:**B9.A mini-GATE-CLOSE criteria (charter SC-9):**
plan.md:95:- **1 alembic migration: `0009_fdb_tier_a.py`** covering all 113 Tier A tables. Charter SPEC-locks this granularity (`charter.md:75-79`); recon §4 confirms tables are uniform enough for single-file review (`recon.md:173-180`). No part-file split.
plan.md:97:- 1 partial loader registry update per session (incremental)
plan.md:103:- 1 alembic migration (`0009_fdb_tier_a.py`)
plan.md:110:- SC-1 (217 tables have models + migrations + ingester) — partial: +113
plan.md:111:- SC-2 (RECORD_COUNTS reconciliation) — every loaded Tier A table: actual ÷ expected within ±0.1% tolerance (small lookups should be exact)
plan.md:112:- SC-6 (FDW verify) — partial: 179/179 PASS after B9.B
plan.md:113:- SC-7 (weekly idempotency) — verified for Tier A only at B9.B mini-GATE-CLOSE
plan.md:114:- SC-8 (test strategy) — contract + parity + reconciliation + sampled behavioral for ~10 random Tier A tables
plan.md:115:- SC-9 (mini-GATE-CLOSE) — see below
plan.md:117:**B9.B mini-GATE-CLOSE criteria:**
plan.md:126:- Codex mini-GATE-CLOSE consult: GO
plan.md:139:- FK relationship verified per table: target table must exist (in Phase 11A baseline or B9.B if Tier B references a Tier A table)
plan.md:141:- **1 alembic migration: `0010_fdb_tier_b.py`** covering all 66 Tier B tables. SPEC-locked single file (`charter.md:75-79`). No part-file split.
plan.md:147:- 1 alembic migration (`0010_fdb_tier_b.py`)
plan.md:152:**Success criteria:** SC-1 (partial: +66, cum 179/217), SC-2, SC-6 (245/245), SC-7 (Tier B idempotent), SC-8 (per-tier sampled behavioral), SC-9.
plan.md:154:**B9.C mini-GATE-CLOSE criteria:** As B9.B + FK-integrity assertion green for every Tier B table.
plan.md:167:- 1 batched alembic migration: `0011_fdb_tier_c_minus_rndc14.py`
plan.md:173:- 1 alembic migration (`0011_fdb_tier_c_minus_rndc14.py`)
plan.md:178:**Success criteria:** SC-1 (partial: cum 195/217), SC-2, SC-6 (261/261), SC-7, SC-8 (dedicated Tier C tests), SC-9.
plan.md:180:**B9.D mini-GATE-CLOSE criteria:** As prior + money-path audit signed off + column-curation decisions documented per table.
plan.md:188:**Why standalone:** 68 columns warrant column-by-column review at mini-GATE-CLOSE. Charter D1 locks "full 68-column ingest" — no column triage / no curation; every column lands. The review focuses on type correctness, NULL semantics, and naming (Python-snake_case from FDB upper-case).
plan.md:192:- Session 1: SQLAlchemy model with all 68 columns, type-mapped (numeric → Decimal where money-relevant; integers where ID; text where descriptor); migration `0012_fdb_rndc14_ndc_mstr.py`; full contract test set
plan.md:198:- 1 alembic migration (`0012_fdb_rndc14_ndc_mstr.py`)
plan.md:203:**Success criteria:** SC-1 (cum 196/217), SC-3 (RNDC14 all 68 cols), SC-2, SC-6 (262/262), SC-7, SC-8 (dedicated RNDC14 tests), SC-9.
plan.md:205:**B9.E mini-GATE-CLOSE criteria:** Column-by-column model review (codex consult walks all 68); type correctness audit; money-path audit; NDC normalization tests green.
plan.md:211:**Scope:** The two large pricing tables explicitly deferred in Phase 09, reversed per charter D2. RNP2_NDC_PRICE (595 MB, 13.2M rows) and RPRDPP0_PRODUCT_PRICE (561 MB). +1.16 GB storage. Includes the **D2 performance gate** (charter SC-4) — not just disk verification.
plan.md:215:- Session 1: SQLAlchemy models for RNP2 + RPRDPP0; migration `0013_fdb_pricing_big.py`; flip `fdb_load_product_prices=True` default
plan.md:223:- 1 alembic migration (`0013_fdb_pricing_big.py`)
plan.md:229:**Success criteria:** SC-1 (cum 198/217), SC-4 (D2 perf gate met: timed dry-run + EXPLAIN ANALYZE + storage budget + weekly delta timing all documented), SC-2, SC-6 (264/264), SC-7, SC-8 (RNP2 + RPRDPP0 dedicated behavioral), SC-9.
plan.md:231:**B9.F mini-GATE-CLOSE criteria — DRACONIAN per charter SC-4:**
plan.md:238:- Codex mini-GATE-CLOSE consult: GO; codex specifically reviews EXPLAIN ANALYZE output for index gaps
plan.md:244:**Scope:** 19 MTL (Medical Test Lexicon) tables. Schema lands; data does NOT load. Per charter D3 + SC-5.
plan.md:248:- Session 1: 19 SQLAlchemy models in `tier_d/`; migration `0014_fdb_mtl_schema.py` (un-gated, lands schema); 19 contract tests asserting tables exist + are queryable + are EMPTY
plan.md:249:- Session 2: Loader registry: explicit exclusion of MTL from `--mode fdb_initial` and `--mode fdb_weekly`; opt-in mode `--mode fdb_mtl_data` exists but requires `fdb_load_mtl=True` config flag (charter SC-5 wording)
plan.md:255:- 1 alembic migration (`0014_fdb_mtl_schema.py`)
plan.md:263:**FDW count derivation (corrected per codex PLAN R1):** 66 baseline + 113 (B9.B) + 66 (B9.C) + 16 (B9.D — 19 Tier C minus 3 special-handled) + 1 (B9.E RNDC14) + 2 (B9.F RNP2+RPRDPP0) + 19 (B9.G MTL schema-only) = **283**. Matches charter SC-6.
plan.md:265:**Success criteria:** SC-1 (cum 217/217), SC-5 (MTL zero-row test green), SC-6 (283/283), SC-9.
plan.md:267:**B9.G mini-GATE-CLOSE criteria:**
plan.md:269:- `0014_fdb_mtl_schema.py` apply + reverse + apply: clean
plan.md:272:- Codex mini-GATE-CLOSE consult: GO; codex specifically verifies that flipping `fdb_load_mtl=False` after data load DOES NOT delete data (idempotency direction check)
plan.md:282:- Session 1: Manifest expansion — `expected_reference_tables.txt` final count locked at **283** (matches charter SC-6; codex PLAN R1 reconciled). Update Werkbench inventory + glossary if new tables/concepts warrant.
plan.md:297:**Success criteria — ALL SC-1..SC-11:**
plan.md:299:- SC-1: 217 tables have models + migrations + ingester (verified via `pg_class` count + alembic history scan)
plan.md:300:- SC-2: RECORD_COUNTS reconciled per table (or documented tolerance / exclusion for MTL)
plan.md:301:- SC-3: RNDC14 ingest covers all 68 columns
plan.md:302:- SC-4: D2 perf gate evidence present
plan.md:303:- SC-5: MTL zero-row test green
plan.md:304:- SC-6: `setup_fdw.sh --verify` final count PASS in dev + mock
plan.md:305:- SC-7: Weekly delta idempotent across all 220 tables (verified at B9.H by running `--mode fdb_weekly` → 0 new rows in all 217 + already-covered 3)
plan.md:306:- SC-8: Test strategy executed (contract + parity + reconciliation + sampled behavioral + dedicated Tier C)
plan.md:307:- SC-9: All B9.B..B9.G mini-GATE-CLOSE consults passed
plan.md:308:- SC-10: Final B9 GATE-CLOSE GO or GO-WITH-FIXES (FIXES applied iteratively until GO)
plan.md:309:- SC-11: Evidence + ship + memory + wave-history all present
plan.md:311:**B9 final GATE-CLOSE criteria:** codex final consult returns GO. Charter SC-10 escalates only if codex returns GO-WITH-FIXES three times in a row without convergence; that triggers an architectural pause.
plan.md:319:| SC | Verification artifact | Phase landing |
plan.md:321:| SC-1 | `pg_class` count of FDB-prefixed tables in `drug_database` schema == **219** (2 already-covered + 113 + 66 + 16 + 1 + 2 + 19 = 219 DB tables; the 220 source FDB tables map to 219 DB tables because RNP3+RPRDPTD0+RNPTYPD0 collapse into 2 DB tables `fdb_ndc_price_history` + `fdb_price_type_desc`); `alembic history` shows migrations 0009..0014 applied | B9.H Session 2 evidence |
plan.md:322:| SC-2 | `waves/B9/evidence.md` table: per-table actual vs. expected row count, tolerance column, PASS/FAIL column | B9.H Session 2 |
plan.md:323:| SC-3 | RNDC14 SQLAlchemy model has 68 columns; codex column-by-column review verdict captured in B9.E mini-GATE-CLOSE consult | B9.E |
plan.md:324:| SC-4 | `waves/B9/perf_b9f.md`: timed dry-run, EXPLAIN ANALYZE, storage delta, weekly delta timing | B9.F |
plan.md:325:| SC-5 | `test_fdb_mtl_zero_rows_under_default` green; opt-in mode reviewed in codex consult | B9.G |
plan.md:326:| SC-6 | `setup_fdw.sh --verify` output **283/283** in dev + mock (charter-matched) | B9.H Session 2 |
plan.md:327:| SC-7 | `load_fdb.py --mode fdb_weekly` re-run logs zero new rows across all 220 tables | B9.H Session 4 |
plan.md:328:| SC-8 | Test counts per category in evidence.md: 217 contract tests + 220 schema-parity + 217 row-count assertions + N sampled behavioral + dedicated Tier C suite | B9.H Session 2 |
plan.md:329:| SC-9 | All 6 mini-GATE-CLOSE consult docs present (`waves/B9/codex-mini-gate-close-{B,C,D,E,F,G}.md`) with GO verdicts | continuously |
plan.md:330:| SC-10 | `waves/B9/codex-gate-close.md` with GO verdict | B9.H Session 4 |
plan.md:331:| SC-11 | `evidence.md`, `ship.md`, memory file, `wave-history.md` line all present and pointing at the right commits | B9.H Session 4 |
plan.md:340:| T2 | Money-path columns typed as `float`/`numeric` lose Decimal discipline (rules `financial-precision.md`) | MED | HIGH | B9.D money-path audit; B9.E + B9.F mandatory `Decimal` audit; codex mini-GATE-CLOSE flags any `Float` or non-explicit `Numeric` on money columns |
plan.md:342:| T4 | Per-phase mini-GATE-CLOSE consults skipped under time pressure | LOW | HIGH | Each phase's commit chain explicitly lists the consult commit; gate-check tool refuses to advance the wave state if the consult file is missing |
plan.md:345:| T7 | Weekly delta idempotency broken on a specific table (ON CONFLICT clause incorrect) | MED | MED | Each phase's mini-GATE-CLOSE re-runs weekly delta; 0 new rows is the gate; per-tier sampled idempotency tests |
plan.md:347:| T9 | FDW manifest expansion drifts from actual reference DB state | LOW | MED | `setup_fdw.sh --verify` at each phase mini-GATE-CLOSE catches drift before next phase opens |
plan.md:348:| T10 | Test count baseline drifts (collection growth unexplained; or 134 pre-existing failures become 135+) | MED | MED | B9.A C0 captures TWO baselines (per invariant #6): collection count via `pytest --collect-only -q | tail -1` AND failure count via `pytest -q --tb=no` line-count of `FAILED`/`ERROR`. Each phase mini-GATE-CLOSE asserts no regression in either, ± in-phase contract tests on the collection number. |
plan.md:349:| T11 | Reference DB FDW + write semantics conflict (writing to a foreign table) | LOW | HIGH | All writes go to `infinityrx_reference` directly via loader; foreign-table access in env DBs is read-only per Phase 11A pattern. B9.B C1 verifies no INSERT statement targets a foreign table. |
plan.md:350:| T12 | Weekly FDB UPD delta format isn't uniformly A/C/D across all 220 tables — some tables may require TRUNCATE+INSERT instead of UPSERT (recon §7 risk implied; codex PLAN R1 surfaced) | MED | HIGH | B9.A C3 contract template includes a UPD-format probe: for each table, verify the first column of the table's `.UPD` file matches the expected A/C/D code. Tables that fail the probe are flagged as TRUNCATE+INSERT and routed through a separate idempotent reload path. Per-phase mini-GATE-CLOSE re-asserts the probe + weekly delta rerun. Charter R4 ("weekly delta breaks because NEW columns") is covered by the same probe plus a column-set parity check against the live model. |
plan.md:356:| Round | Phase | Dispatch trigger | Verdict file |
plan.md:363:| mini-GATE-CLOSE B9.B | B9.B | After Tier A all 113 tables ingested | `codex-mini-gate-close-B.md` |
plan.md:364:| mini-GATE-CLOSE B9.C | B9.C | After Tier B all 66 tables ingested | `codex-mini-gate-close-C.md` |
plan.md:365:| mini-GATE-CLOSE B9.D | B9.D | After Tier C non-RNDC14 all 16 ingested | `codex-mini-gate-close-D.md` |
plan.md:366:| mini-GATE-CLOSE B9.E | B9.E | After RNDC14 column-by-column review | `codex-mini-gate-close-E.md` |
plan.md:367:| mini-GATE-CLOSE B9.F | B9.F | After D2 perf gate evidence captured | `codex-mini-gate-close-F.md` |
plan.md:368:| mini-GATE-CLOSE B9.G | B9.G | After MTL schema-only + guards ship | `codex-mini-gate-close-G.md` |
plan.md:371:**Total codex consults projected:** 12 (2 SPEC done + PLAN R1 done + PLAN R2 + ADVERSARIAL + 6 mini-GATE-CLOSE + final GATE-CLOSE = 12).
plan.md:377:- Phase 4 portal feature work (forward feature work; charter §Out of scope)
plan.md:392:2. **Migration count: 5 vs 6 vs 9-10** → **RESOLVED: 6.** Charter SPEC-locked the 6 files; v2 removes the part-file alternatives. Locked shape: `0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14` (16 tables), `0012_fdb_rndc14`, `0013_fdb_pricing_big`, `0014_fdb_mtl_schema`.
plan.md:400:- **Plan §Phased commit chain view (42 sessions):** counts every phase including B9.A meta-phase (charter v3 + plan v1/v2 + codex SPEC R2 + PLAN R1 + ADVERSARIAL + infra scaffolding = 3 sessions) and B9.H closeout (4 sessions). 3 + B (10) + C (12) + D (4) + E (2) + F (4) + G (3) + H (4) = **42**.
plan.md:411:- At each mini-GATE-CLOSE: full sign-off sheet committed

 succeeded in 421ms:
charter.md:1:# Wave B9 — FDB NDDF Plus 220-table extension (full scope)
charter.md:5:**Predecessor:** Phase 09 FDB pricing ingester (3 tables); Phase 11A reference DB topology; B7.2 architectural cleanup
charter.md:12:Extend FDB NDDF Plus ingest from current **3 tables → all 220 tables** (217-table gap). Adjudication, formulary, reclaimrx, and future Phase 4 modules gain full FDB reference coverage. Single B9 wave milestone; multi-session execution.
charter.md:61:| SC-1 | All 217 currently-missing FDB tables have SQLAlchemy models + alembic migrations + ingester support |
charter.md:62:| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected ± documented tolerance (MTL excluded — schema-only) |
charter.md:88:| R4 | FDB weekly delta breaks because some tables ship NEW columns | Schema version detection + drift logging; halt ingest on unrecognized column |
plan.md:5:**Recon ground truth:** `recon.md` (2026-05-11) — 217 gap tables, 6 FDB modules, 4 effort tiers.
plan.md:6:**Scope:** All 217 currently-missing FDB NDDF Plus tables (3 already covered) reach the platform as ingested or schema-only across phases B9.A → B9.H.
plan.md:36:3. **Reference DB topology stable** — `infinityrx_reference` schemas `drug_database / drug_db / reference / shared` exist; current FDB tables `fdb_ndc_price_history` + `fdb_price_type_desc` present and queryable through FDW. (Phase 11A C9.)
plan.md:40:7. **FDB drop manifest reachable** — `data/reference/fdb/TEL251759D/RECORD_COUNTS.TXT` present and parseable (recon §1.5 verified — re-verify at C0).
plan.md:58:- **`TableSpec` registry expansion path** — adds a `TIER`, `RECORD_COUNTS_KEY`, and `LOADER_GROUP` field to existing `TableSpec` so generic ingester can: (a) tier-filter, (b) row-count reconcile, (c) loader-register by tier. Backward-compatible default values mean existing FDB pricing TableSpecs still work.
plan.md:82:- `setup_fdw.sh --verify` still 66/66 (no FDB tables added yet).
plan.md:90:**Scope:** All 113 Tier A tables ingested via generic `TableSpec`-driven adapter with no per-table custom code. These are recon's "simple desc/lookup" tier — short tables (mostly < 10K rows, all ≤ 5 columns) covering brand/route/strength/form/manufacturer descriptors and small lookup tables across NDDF BASICS, MEDNAMES, ETC, TALL MAN PLUS, XRF.
plan.md:128:**Risk:** 113 tables × ~12/session is aggressive. Mitigation: each session targets contiguous functional groups (e.g., all NDDF BASICS lookups one session; all ETC lookups another) to keep review cohesion. If a session lands fewer tables, the next absorbs the overflow — total session count flexes within the charter's 10-session band.
plan.md:186:**Scope:** RNDC14_NDC_MSTR alone — the canonical FDB NDC master, 68 columns, 183 MB, ~501K rows. Highest single-table value in the wave.
plan.md:188:**Why standalone:** 68 columns warrant column-by-column review at mini-GATE-CLOSE. Charter D1 locks "full 68-column ingest" — no column triage / no curation; every column lands. The review focuses on type correctness, NULL semantics, and naming (Python-snake_case from FDB upper-case).
plan.md:285:- Session 4: B9 ship artifacts (`waves/B9/ship.md`); memory entry; wave-history index update; codex final GATE-CLOSE consult; PR creation if any of the FDB schema work was branched
plan.md:321:| SC-1 | `pg_class` count of FDB-prefixed tables in `drug_database` schema == **219** (2 already-covered + 113 + 66 + 16 + 1 + 2 + 19 = 219 DB tables; the 220 source FDB tables map to 219 DB tables because RNP3+RPRDPTD0+RNPTYPD0 collapse into 2 DB tables `fdb_ndc_price_history` + `fdb_price_type_desc`); `alembic history` shows migrations 0009..0014 applied | B9.H Session 2 evidence |
plan.md:350:| T12 | Weekly FDB UPD delta format isn't uniformly A/C/D across all 220 tables — some tables may require TRUNCATE+INSERT instead of UPSERT (recon §7 risk implied; codex PLAN R1 surfaced) | MED | HIGH | B9.A C3 contract template includes a UPD-format probe: for each table, verify the first column of the table's `.UPD` file matches the expected A/C/D code. Tables that fail the probe are flagged as TRUNCATE+INSERT and routed through a separate idempotent reload path. Per-phase mini-GATE-CLOSE re-asserts the probe + weekly delta rerun. Charter R4 ("weekly delta breaks because NEW columns") is covered by the same probe plus a column-set parity check against the live model. |
plan.md:383:- New external data sources beyond NDDF Plus (FDB Atomic, FDB MedKnowledge: separate waves)
recon.md:5:**Goal:** Scope FDB NDDF Plus 220-table extension beyond the 3-table Phase 09 baseline
recon.md:11:- The FDB drop contains exactly **220 data tables** in `NDDF Plus DB/NDDF PLUS DB.zip`, all with matching ANSI DDL. The current ingester covers **3 tables** (RNP3\_NDC\_PRICE, RPRDPTD0\_PRICE\_TYPE\_DESC, RNPTYPD0\_NDC\_PRICE\_TYPE\_DESC) mapped to **2 DB tables** (`fdb_ndc_price_history`, `fdb_price_type_desc`). Gap: **217 tables**.
recon.md:12:- Tables span six FDB modules: NDDF BASICS 3.0 (98 tables), MEDNAMES 3.0 (63), ETC 1.0 (16), TALL MAN PLUS 2.0 (15), XRF 1.0 (9), MTL 1.0 (19). MTL (Medical Test Lexicon) is the only module without a clear adjudication use case — treat as a product decision.
recon.md:13:- The generic `TableSpec`-driven adapter (`FDBLocalDropAdapter.parse_table`) already works for any pipe-delimited FDB table. The ingest architecture is **extension-ready**: new tables become new `TableSpec` constants + SQLAlchemy models + a migration, no adapter surgery required.
recon.md:15:- The FDW `LIMIT TO` allowlist in `setup_fdw.sh` currently names 2 FDB tables. Adding 217 more requires a structured FDW manifest expansion — this is a one-time setup change, not per-deployment.
recon.md:17:- The `RNDC14_NDC_MSTR` table (68 columns, 183 MB, ~501K rows) is the platform's most valuable single gap target — it is the canonical FDB NDC master containing labeler, brand name, GCDF, route, DEA schedule, packaging, and product status fields that adjudication, formulary, and reclaimrx all need.
recon.md:21:## Section 1 — FDB drop inventory
recon.md:34:FDB_CLINICAL_HIGHLIGHTS.ZIP        <- clinical screening, NOT subscribed
recon.md:35:NDDF Plus DB/NDDF PLUS DB.zip      <- 220 data table files (pipe-delimited, latin-1)
recon.md:36:NDDF Plus DDL/NDDF PLUS DDL.zip    <- 46 DDL files (ANSI, Oracle, SQL Server, Sybase)
recon.md:37:NDDF Plus UPD/NDDF PLUS UPD.zip    <- weekly delta (A/C/D prefixed rows)
recon.md:38:NDDF_PRODUCT_INFO.TXT              <- single-line YYYYMMDD data cutoff date
recon.md:44:- ANSI DDL `CREATE TABLE` statements: **220** (+ 1 meta: `NDDF_PRODUCT_INFO`)
recon.md:48:**FDB module breakdown:**
recon.md:52:| NDDF BASICS 3.0 / Generic Formulation and Ingredient | 50 | GCN, GCNSEQNO, HIC, strength, route, dosage form |
recon.md:53:| NDDF BASICS 3.0 / Packaged Product | 30 | NDC master, FDA application, OBC, labeler |
recon.md:54:| NDDF BASICS 3.0 / Pricing | 11 | RNP2, RNP3, RPRDPP0, price attr |
recon.md:55:| NDDF BASICS 3.0 / Miscellaneous Therapeutic Class | 7 | AHFS, ATC, HIC therapeutic class |
recon.md:56:| NDDF MEDNAMES 3.0 | 63 | MedID, routed med, dose form med, search terms |
recon.md:57:| NDDF ETC 1.0 | 16 | Enhanced Therapeutic Classification hierarchy |
recon.md:58:| NDDF XRF 1.0 | 9 | Clinical quantity crossrefs, script QQ |
recon.md:60:| NDDF MTL 1.0 | 19 | Medical Test Lexicon — separate domain |
recon.md:64:| Table | Cols | Uncompressed | First-field sample |
recon.md:80:**Python files covering FDB:**
recon.md:91:**Currently ingested FDB tables → DB tables:**
recon.md:93:| FDB Table | DB Table | Notes |
recon.md:99:**Coverage gap: 217 of 220 FDB tables have no DB mapping.**
recon.md:103:| FDB Table | Cols | Rows (RECORD\_COUNTS) | Business value |
recon.md:114:**FDW manifest impact:** `setup_fdw.sh` uses `IMPORT FOREIGN SCHEMA ... LIMIT TO (...)` with a dynamic list. Currently 2 FDB table names are in scope for drug\_database. B9 full coverage would expand this list by 217 entries.
recon.md:199:The existing `TableSpec` dataclass + `FDBLocalDropAdapter.parse_table` already provides a generic parse-any-table capability. The only missing piece is:
recon.md:201:2. A generic `FDBBulkIngester` that iterates the registry, calling `parse_table` + bulk upsert for each
recon.md:250:The NDC master has 68 columns, many of which are FDB-internal flags with unclear business relevance. Without column curation, the DB table will be bloated and the ORM model unwieldy. Risk: table design gets revisited post-ingest, requiring a costly migration. Mitigation: Before B9.3, produce a column-by-column triage (keep / drop / defer) based on adjudication, formulary, and reclaimrx requirements.
recon.md:256:`setup_fdw.sh` uses a dynamic `LIMIT TO` allowlist. Adding 217 table names to this list is a one-time change, but the list must stay in sync with the actual schema. If a new FDB drop adds tables, the FDW will silently omit them. Mitigation: Auto-generate the LIMIT TO list from the ORM `metadata.tables` at setup time rather than maintaining a manual list.
recon.md:259:Current FDB ingest: RNP3 (13.2M rows) takes ~minutes. Adding 217 tables including NDC master (501K rows), ETC NDC mapping (616K rows), and MedName tables adds significant volume to the weekly UPD cycle. The UPD zip must also be verified to contain all tables (not just pricing). Mitigation: Profile UPD zip contents against DB zip contents. Validate that `NDDF Plus UPD/` has a matching file for each table before committing to weekly ingest for all 220.
recon.md:262:The current adapter only reads from UPD for RNP3 (pricing). Some FDB reference tables (e.g., description tables) may ship full-replacement in UPD rather than A/C/D delta. Mitigation: Inspect the UPD zip structure early in B9.1. If some tables are full-replacement (no A/C/D prefix), the ingester must detect this and use TRUNCATE+INSERT rather than ON CONFLICT DO NOTHING.
recon.md:268:At 217 new models, the per-test `create_all()` time in SQLite fixtures will grow. Currently 2 FDB models; adding 217 means each test session creates 219 tables. Risk: slow CI. Mitigation: Split the `FDBPricingBase` into module-level declarative bases (`FDBBasicsBase`, `FDBMedNamesBase`, etc.) so tests only create\_all for the module under test. Plan this in B9.0 before any model files are written.
recon.md:277:- Design the `FDBBulkIngester` (generic ingester for Tier A+B) — implementation-ready spec
recon.md:284:- Implement `FDBBulkIngester` generic infrastructure (~200 lines)
recon.md:326:3. **MTL go/no-go**: Does any planned adjudication rule or reclaimrx detection require lab test linkage (NDDF MTL 1.0)? If yes, B9.4 is in scope. If no, all 19 MTL tables are permanently skipped.
codex-plan-consult-r1.md:18:Wave B9 = "FDB NDDF Plus 220-table extension". SPEC v3 is locked (you previously approved at SPEC R2 GO-WITH-FIXES → owner applied the stale-D4-row cleanup → v3 LOCKED). The next gate is PLAN v1. The owner drafted `plan.md` v1 (380 lines). Your job in PLAN R1 is to verify whether the plan is sound, complete, and ready for ADVERSARIAL review + execute, OR whether it needs revision.
codex-plan-consult-r1.md:179:# Wave B9 â€” FDB NDDF Plus 220-table extension (full scope)
codex-plan-consult-r1.md:183:**Predecessor:** Phase 09 FDB pricing ingester (3 tables); Phase 11A reference DB topology; B7.2 architectural cleanup
codex-plan-consult-r1.md:190:Extend FDB NDDF Plus ingest from current **3 tables â†’ all 220 tables** (217-table gap). Adjudication, formulary, reclaimrx, and future Phase 4 modules gain full FDB reference coverage. Single B9 wave milestone; multi-session execution.
codex-plan-consult-r1.md:239:| SC-1 | All 217 currently-missing FDB tables have SQLAlchemy models + alembic migrations + ingester support |
codex-plan-consult-r1.md:240:| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected Â± documented tolerance (MTL excluded â€” schema-only) |
codex-plan-consult-r1.md:266:| R4 | FDB weekly delta breaks because some tables ship NEW columns | Schema version detection + drift logging; halt ingest on unrecognized column |
codex-plan-consult-r1.md:601:2. Set env: `IFX_NCPDP_LISTEN_TENANT_ID`, `IFX_NCPDP_LISTEN_PROGRAM_ID`, `FDB_PRICING_ENRICHMENT_ENABLED=false` (default-dict path â€” no FDB DB needed)
codex-plan-consult-r1.md:611:- Same flow but `FDB_PRICING_ENRICHMENT_ENABLED=true` + real `DATABASE_URL_SYNC` reachable
codex-plan-consult-r1.md:613:- Asserts FDB pricing fields populated with real values
codex-plan-consult-r1.md:649:| SC-7 | New integration test passes; InMemoryEventBus captures published envelope with FDB fields (None-default values acceptable) | C5 |
codex-plan-consult-r1.md:685:- B9 (FDB NDDF Plus 220-table)
codex-plan-consult-r1.md:709:Wave B9 = "FDB NDDF Plus 220-table extension". Recon was completed 2026-05-11 (`recon.md`). Charter v1 was dispatched for SPEC R1. You returned **GO-WITH-FIXES** with 6 substantive concerns (1 HIGH effort model, 2 HIGH process gates, 3 MEDIUM SPEC tightenings, 1 LOW vendor-name pass). The owner produced charter v2 which claims to absorb all 6 concerns. Your job in R2 is to verify whether v2 actually addresses each concern, and either issue **GO** (proceed to PLAN), **GO-WITH-FIXES** (one more revision needed), or **NO-GO** (structural problem).
codex-plan-consult-r1.md:765:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$dir='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9'; if (Get-Command rg -ErrorAction SilentlyContinue) { rg -n -i \"First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14\" "'$dir } else { Get-ChildItem -LiteralPath $dir -File | Select-String -Pattern '"'First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14' -CaseSensitive:"'$false }' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
codex-plan-consult-r1.md:774:2026-05-11T19:13:02.641827Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$dir='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9'; if (Get-Command rg -ErrorAction SilentlyContinue) { rg -n -i \"First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14\" "'$dir } else { Get-ChildItem -LiteralPath $dir -File | Select-String -Pattern '"'First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14' -CaseSensitive:"'$false }'` rejected: blocked by policy
codex-plan-consult-r1.md:776:`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$dir='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9'; if (Get-Command rg -ErrorAction SilentlyContinue) { rg -n -i \"First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14\" "'$dir } else { Get-ChildItem -LiteralPath $dir -File | Select-String -Pattern '"'First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14' -CaseSensitive:"'$false }'` rejected: blocked by policy
codex-plan-consult-r1.md:817:2026-05-11T19:13:19.767559Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "if (Get-Command rg -ErrorAction SilentlyContinue) { rg -n -i \"First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14\" . } else { Get-ChildItem -File | Select-String -Pattern 'First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14' -CaseSensitive:"'$false }'` rejected: blocked by policy
codex-plan-consult-r1.md:819:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "if (Get-Command rg -ErrorAction SilentlyContinue) { rg -n -i \"First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14\" . } else { Get-ChildItem -File | Select-String -Pattern 'First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14' -CaseSensitive:"'$false }' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
codex-plan-consult-r1.md:821:`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "if (Get-Command rg -ErrorAction SilentlyContinue) { rg -n -i \"First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14\" . } else { Get-ChildItem -File | Select-String -Pattern 'First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14' -CaseSensitive:"'$false }'` rejected: blocked by policy
codex-plan-consult-r1.md:827:# Wave B9 Ã¢â‚¬â€ FDB NDDF Plus 220-table extension (full scope)
codex-plan-consult-r1.md:831:**Predecessor:** Phase 09 FDB pricing ingester (3 tables); Phase 11A reference DB topology; B7.2 architectural cleanup
codex-plan-consult-r1.md:838:Extend FDB NDDF Plus ingest from current **3 tables Ã¢â€ â€™ all 220 tables** (217-table gap). Adjudication, formulary, reclaimrx, and future Phase 4 modules gain full FDB reference coverage. Single B9 wave milestone; multi-session execution.
codex-plan-consult-r1.md:887:| SC-1 | All 217 currently-missing FDB tables have SQLAlchemy models + alembic migrations + ingester support |
codex-plan-consult-r1.md:888:| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected Ã‚Â± documented tolerance (MTL excluded Ã¢â‚¬â€ schema-only) |
codex-plan-consult-r1.md:914:| R4 | FDB weekly delta breaks because some tables ship NEW columns | Schema version detection + drift logging; halt ingest on unrecognized column |
codex-plan-consult-r1.md:944:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n -i "First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14|100-session|34|39|mini-GATE|GATE-CLOSE|EXPLAIN ANALYZE|bespoke|migration" charter.md codex-spec-consult-r1.md recon.md' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
codex-plan-consult-r1.md:946:charter.md:1:# Wave B9 â€” FDB NDDF Plus 220-table extension (full scope)
codex-plan-consult-r1.md:947:charter.md:5:**Predecessor:** Phase 09 FDB pricing ingester (3 tables); Phase 11A reference DB topology; B7.2 architectural cleanup
codex-plan-consult-r1.md:948:charter.md:12:Extend FDB NDDF Plus ingest from current **3 tables â†’ all 220 tables** (217-table gap). Adjudication, formulary, reclaimrx, and future Phase 4 modules gain full FDB reference coverage. Single B9 wave milestone; multi-session execution.
codex-plan-consult-r1.md:965:charter.md:61:| SC-1 | All 217 currently-missing FDB tables have SQLAlchemy models + alembic migrations + ingester support |
codex-plan-consult-r1.md:966:charter.md:62:| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected Â± documented tolerance (MTL excluded â€” schema-only) |
codex-plan-consult-r1.md:982:charter.md:88:| R4 | FDB weekly delta breaks because some tables ship NEW columns | Schema version detection + drift logging; halt ingest on unrecognized column |
codex-plan-consult-r1.md:989:codex-spec-consult-r1.md:11:currently-missing FDB tables have SQLAlchemy models + alembic migrations + ingester support |
codex-plan-consult-r1.md:1024:recon.md:5:**Goal:** Scope FDB NDDF Plus 220-table extension beyond the 3-table Phase 09 baseline
codex-plan-consult-r1.md:1025:recon.md:11:- The FDB drop contains exactly **220 data tables** in `NDDF Plus DB/NDDF PLUS DB.zip`, all with matching ANSI DDL. The current ingester covers **3 tables** (RNP3\_NDC\_PRICE, RPRDPTD0\_PRICE\_TYPE\_DESC, RNPTYPD0\_NDC\_PRICE\_TYPE\_DESC) mapped to **2 DB tables** (`fdb_ndc_price_history`, `fdb_price_type_desc`). Gap: **217 tables**.
codex-plan-consult-r1.md:1026:recon.md:12:- Tables span six FDB modules: NDDF BASICS 3.0 (98 tables), MEDNAMES 3.0 (63), ETC 1.0 (16), TALL MAN PLUS 2.0 (15), XRF 1.0 (9), MTL 1.0 (19). MTL (Medical Test Lexicon) is the only module without a clear adjudication use case â€” treat as a product decision.
codex-plan-consult-r1.md:1027:recon.md:13:- The generic `TableSpec`-driven adapter (`FDBLocalDropAdapter.parse_table`) already works for any pipe-delimited FDB table. The ingest architecture is **extension-ready**: new tables become new `TableSpec` constants + SQLAlchemy models + a migration, no adapter surgery required.
codex-plan-consult-r1.md:1029:recon.md:15:- The FDW `LIMIT TO` allowlist in `setup_fdw.sh` currently names 2 FDB tables. Adding 217 more requires a structured FDW manifest expansion â€” this is a one-time setup change, not per-deployment.
codex-plan-consult-r1.md:1031:recon.md:17:- The `RNDC14_NDC_MSTR` table (68 columns, 183 MB, ~501K rows) is the platform's most valuable single gap target â€” it is the canonical FDB NDC master containing labeler, brand name, GCDF, route, DEA schedule, packaging, and product status fields that adjudication, formulary, and reclaimrx all need.
codex-plan-consult-r1.md:1032:recon.md:21:## Section 1 â€” FDB drop inventory
codex-plan-consult-r1.md:1034:recon.md:34:FDB_CLINICAL_HIGHLIGHTS.ZIP        <- clinical screening, NOT subscribed
codex-plan-consult-r1.md:1035:recon.md:35:NDDF Plus DB/NDDF PLUS DB.zip      <- 220 data table files (pipe-delimited, latin-1)
codex-plan-consult-r1.md:1036:recon.md:36:NDDF Plus DDL/NDDF PLUS DDL.zip    <- 46 DDL files (ANSI, Oracle, SQL Server, Sybase)
codex-plan-consult-r1.md:1037:recon.md:37:NDDF Plus UPD/NDDF PLUS UPD.zip    <- weekly delta (A/C/D prefixed rows)
codex-plan-consult-r1.md:1038:recon.md:38:NDDF_PRODUCT_INFO.TXT              <- single-line YYYYMMDD data cutoff date
codex-plan-consult-r1.md:1039:recon.md:44:- ANSI DDL `CREATE TABLE` statements: **220** (+ 1 meta: `NDDF_PRODUCT_INFO`)
codex-plan-consult-r1.md:1040:recon.md:48:**FDB module breakdown:**
codex-plan-consult-r1.md:1041:recon.md:52:| NDDF BASICS 3.0 / Generic Formulation and Ingredient | 50 | GCN, GCNSEQNO, HIC, strength, route, dosage form |
codex-plan-consult-r1.md:1042:recon.md:53:| NDDF BASICS 3.0 / Packaged Product | 30 | NDC master, FDA application, OBC, labeler |
codex-plan-consult-r1.md:1043:recon.md:54:| NDDF BASICS 3.0 / Pricing | 11 | RNP2, RNP3, RPRDPP0, price attr |
codex-plan-consult-r1.md:1044:recon.md:55:| NDDF BASICS 3.0 / Miscellaneous Therapeutic Class | 7 | AHFS, ATC, HIC therapeutic class |
codex-plan-consult-r1.md:1045:recon.md:56:| NDDF MEDNAMES 3.0 | 63 | MedID, routed med, dose form med, search terms |
codex-plan-consult-r1.md:1046:recon.md:57:| NDDF ETC 1.0 | 16 | Enhanced Therapeutic Classification hierarchy |
codex-plan-consult-r1.md:1047:recon.md:58:| NDDF XRF 1.0 | 9 | Clinical quantity crossrefs, script QQ |
codex-plan-consult-r1.md:1048:recon.md:60:| NDDF MTL 1.0 | 19 | Medical Test Lexicon â€” separate domain |
codex-plan-consult-r1.md:1055:recon.md:80:**Python files covering FDB:**
codex-plan-consult-r1.md:1062:recon.md:91:**Currently ingested FDB tables â†’ DB tables:**
codex-plan-consult-r1.md:1063:recon.md:93:| FDB Table | DB Table | Notes |
codex-plan-consult-r1.md:1067:recon.md:99:**Coverage gap: 217 of 220 FDB tables have no DB mapping.**
codex-plan-consult-r1.md:1068:recon.md:103:| FDB Table | Cols | Rows (RECORD\_COUNTS) | Business value |
codex-plan-consult-r1.md:1070:recon.md:114:**FDW manifest impact:** `setup_fdw.sh` uses `IMPORT FOREIGN SCHEMA ... LIMIT TO (...)` with a dynamic list. Currently 2 FDB table names are in scope for drug\_database. B9 full coverage would expand this list by 217 entries.
codex-plan-consult-r1.md:1093:recon.md:199:The existing `TableSpec` dataclass + `FDBLocalDropAdapter.parse_table` already provides a generic parse-any-table capability. The only missing piece is:
codex-plan-consult-r1.md:1095:recon.md:201:2. A generic `FDBBulkIngester` that iterates the registry, calling `parse_table` + bulk upsert for each
codex-plan-consult-r1.md:1103:recon.md:250:The NDC master has 68 columns, many of which are FDB-internal flags with unclear business relevance. Without column curation, the DB table will be bloated and the ORM model unwieldy. Risk: table design gets revisited post-ingest, requiring a costly migration. Mitigation: Before B9.3, produce a column-by-column triage (keep / drop / defer) based on adjudication, formulary, and reclaimrx requirements.
codex-plan-consult-r1.md:1105:recon.md:256:`setup_fdw.sh` uses a dynamic `LIMIT TO` allowlist. Adding 217 table names to this list is a one-time change, but the list must stay in sync with the actual schema. If a new FDB drop adds tables, the FDW will silently omit them. Mitigation: Auto-generate the LIMIT TO list from the ORM `metadata.tables` at setup time rather than maintaining a manual list.
codex-plan-consult-r1.md:1106:recon.md:259:Current FDB ingest: RNP3 (13.2M rows) takes ~minutes. Adding 217 tables including NDC master (501K rows), ETC NDC mapping (616K rows), and MedName tables adds significant volume to the weekly UPD cycle. The UPD zip must also be verified to contain all tables (not just pricing). Mitigation: Profile UPD zip contents against DB zip contents. Validate that `NDDF Plus UPD/` has a matching file for each table before committing to weekly ingest for all 220.
codex-plan-consult-r1.md:1107:recon.md:262:The current adapter only reads from UPD for RNP3 (pricing). Some FDB reference tables (e.g., description tables) may ship full-replacement in UPD rather than A/C/D delta. Mitigation: Inspect the UPD zip structure early in B9.1. If some tables are full-replacement (no A/C/D prefix), the ingester must detect this and use TRUNCATE+INSERT rather than ON CONFLICT DO NOTHING.
codex-plan-consult-r1.md:1109:recon.md:268:At 217 new models, the per-test `create_all()` time in SQLite fixtures will grow. Currently 2 FDB models; adding 217 means each test session creates 219 tables. Risk: slow CI. Mitigation: Split the `FDBPricingBase` into module-level declarative bases (`FDBBasicsBase`, `FDBMedNamesBase`, etc.) so tests only create\_all for the module under test. Plan this in B9.0 before any model files are written.
codex-plan-consult-r1.md:1111:recon.md:277:- Design the `FDBBulkIngester` (generic ingester for Tier A+B) â€” implementation-ready spec
codex-plan-consult-r1.md:1112:recon.md:284:- Implement `FDBBulkIngester` generic infrastructure (~200 lines)
codex-plan-consult-r1.md:1128:recon.md:326:3. **MTL go/no-go**: Does any planned adjudication rule or reclaimrx detection require lab test linkage (NDDF MTL 1.0)? If yes, B9.4 is in scope. If no, all 19 MTL tables are permanently skipped.
codex-plan-consult-r1.md:1153:PASS. Grep evidence shows consistent use of `FDB` / `NDDF Plus` / `NDDF`; no `FirstDataBank` casing issue surfaced in the checked B9 docs. Relevant lines include charter.md:1, charter.md:12, recon.md:5, recon.md:11, recon.md:21, recon.md:35-36.
codex-plan-consult-r1.md:1181:PASS. Grep evidence shows consistent use of `FDB` / `NDDF Plus` / `NDDF`; no `FirstDataBank` casing issue surfaced in the checked B9 docs. Relevant lines include charter.md:1, charter.md:12, recon.md:5, recon.md:11, recon.md:21, recon.md:35-36.
codex-plan-consult-r1.md:1192:**Recon ground truth:** `recon.md` (2026-05-11) â€” 217 gap tables, 6 FDB modules, 4 effort tiers.
codex-plan-consult-r1.md:1193:**Scope:** All 217 currently-missing FDB NDDF Plus tables (3 already covered) reach the platform as ingested or schema-only across phases B9.A â†’ B9.H.
codex-plan-consult-r1.md:1223:3. **Reference DB topology stable** â€” `infinityrx_reference` schemas `drug_database / drug_db / reference / shared` exist; current FDB tables `fdb_ndc_price_history` + `fdb_price_type_desc` present and queryable through FDW. (Phase 11A C9.)
codex-plan-consult-r1.md:1227:7. **FDB drop manifest reachable** â€” `data/reference/fdb/TEL251759D/RECORD_COUNTS.TXT` present and parseable (recon Â§1.5 verified â€” re-verify at C0).
codex-plan-consult-r1.md:1245:- **`TableSpec` registry expansion path** â€” adds a `TIER`, `RECORD_COUNTS_KEY`, and `LOADER_GROUP` field to existing `TableSpec` so generic ingester can: (a) tier-filter, (b) row-count reconcile, (c) loader-register by tier. Backward-compatible default values mean existing FDB pricing TableSpecs still work.
codex-plan-consult-r1.md:1269:- `setup_fdw.sh --verify` still 66/66 (no FDB tables added yet).
codex-plan-consult-r1.md:1277:**Scope:** All 113 Tier A tables ingested via generic `TableSpec`-driven adapter with no per-table custom code. These are recon's "simple desc/lookup" tier â€” short tables (mostly < 10K rows, all â‰¤ 5 columns) covering brand/route/strength/form/manufacturer descriptors and small lookup tables across NDDF BASICS, MEDNAMES, ETC, TALL MAN PLUS, XRF.
codex-plan-consult-r1.md:1315:**Risk:** 113 tables Ã— ~12/session is aggressive. Mitigation: each session targets contiguous functional groups (e.g., all NDDF BASICS lookups one session; all ETC lookups another) to keep review cohesion. If a session lands fewer tables, the next absorbs the overflow â€” total session count flexes within the charter's 10-session band.
codex-plan-consult-r1.md:1373:**Scope:** RNDC14_NDC_MSTR alone â€” the canonical FDB NDC master, 68 columns, 183 MB, ~501K rows. Highest single-table value in the wave.
codex-plan-consult-r1.md:1375:**Why standalone:** 68 columns warrant column-by-column review at mini-GATE-CLOSE. Charter D1 locks "full 68-column ingest" â€” no column triage / no curation; every column lands. The review focuses on type correctness, NULL semantics, and naming (Python-snake_case from FDB upper-case).
codex-plan-consult-r1.md:1472:- Session 4: B9 ship artifacts (`waves/B9/ship.md`); memory entry; wave-history index update; codex final GATE-CLOSE consult; PR creation if any of the FDB schema work was branched
codex-plan-consult-r1.md:1508:| SC-1 | `pg_class` count of FDB-prefixed tables in `drug_database` schema == 220; `alembic history` shows migrations 0009..0014 applied | B9.H Session 2 evidence |
codex-plan-consult-r1.md:1568:- New external data sources beyond NDDF Plus (FDB Atomic, FDB MedKnowledge: separate waves)
codex-plan-consult-r1.md:1576:1. **FDW final count: 283 vs 284.** Charter says 283; PLAN's tier-additive derivation gives 284 (66 + 113 + 66 + 17 + 1 + 2 + 19 = 284). The charter figure may have netted the 3 already-covered FDB pricing tables differently. Codex PLAN consult should reconcile before B9.B opens.
codex-plan-consult-r1.md:1598:**Goal:** Scope FDB NDDF Plus 220-table extension beyond the 3-table Phase 09 baseline
codex-plan-consult-r1.md:1604:- The FDB drop contains exactly **220 data tables** in `NDDF Plus DB/NDDF PLUS DB.zip`, all with matching ANSI DDL. The current ingester covers **3 tables** (RNP3\_NDC\_PRICE, RPRDPTD0\_PRICE\_TYPE\_DESC, RNPTYPD0\_NDC\_PRICE\_TYPE\_DESC) mapped to **2 DB tables** (`fdb_ndc_price_history`, `fdb_price_type_desc`). Gap: **217 tables**.
codex-plan-consult-r1.md:1605:- Tables span six FDB modules: NDDF BASICS 3.0 (98 tables), MEDNAMES 3.0 (63), ETC 1.0 (16), TALL MAN PLUS 2.0 (15), XRF 1.0 (9), MTL 1.0 (19). MTL (Medical Test Lexicon) is the only module without a clear adjudication use case â€” treat as a product decision.
codex-plan-consult-r1.md:1606:- The generic `TableSpec`-driven adapter (`FDBLocalDropAdapter.parse_table`) already works for any pipe-delimited FDB table. The ingest architecture is **extension-ready**: new tables become new `TableSpec` constants + SQLAlchemy models + a migration, no adapter surgery required.
codex-plan-consult-r1.md:1608:- The FDW `LIMIT TO` allowlist in `setup_fdw.sh` currently names 2 FDB tables. Adding 217 more requires a structured FDW manifest expansion â€” this is a one-time setup change, not per-deployment.
codex-plan-consult-r1.md:1610:- The `RNDC14_NDC_MSTR` table (68 columns, 183 MB, ~501K rows) is the platform's most valuable single gap target â€” it is the canonical FDB NDC master containing labeler, brand name, GCDF, route, DEA schedule, packaging, and product status fields that adjudication, formulary, and reclaimrx all need.
codex-plan-consult-r1.md:1614:## Section 1 â€” FDB drop inventory
codex-plan-consult-r1.md:1627:FDB_CLINICAL_HIGHLIGHTS.ZIP        <- clinical screening, NOT subscribed
codex-plan-consult-r1.md:1628:NDDF Plus DB/NDDF PLUS DB.zip      <- 220 data table files (pipe-delimited, latin-1)
codex-plan-consult-r1.md:1629:NDDF Plus DDL/NDDF PLUS DDL.zip    <- 46 DDL files (ANSI, Oracle, SQL Server, Sybase)
codex-plan-consult-r1.md:1630:NDDF Plus UPD/NDDF PLUS UPD.zip    <- weekly delta (A/C/D prefixed rows)
codex-plan-consult-r1.md:1631:NDDF_PRODUCT_INFO.TXT              <- single-line YYYYMMDD data cutoff date
codex-plan-consult-r1.md:1637:- ANSI DDL `CREATE TABLE` statements: **220** (+ 1 meta: `NDDF_PRODUCT_INFO`)
codex-plan-consult-r1.md:1641:**FDB module breakdown:**
codex-plan-consult-r1.md:1645:| NDDF BASICS 3.0 / Generic Formulation and Ingredient | 50 | GCN, GCNSEQNO, HIC, strength, route, dosage form |
codex-plan-consult-r1.md:1646:| NDDF BASICS 3.0 / Packaged Product | 30 | NDC master, FDA application, OBC, labeler |
codex-plan-consult-r1.md:1647:| NDDF BASICS 3.0 / Pricing | 11 | RNP2, RNP3, RPRDPP0, price attr |
codex-plan-consult-r1.md:1648:| NDDF BASICS 3.0 / Miscellaneous Therapeutic Class | 7 | AHFS, ATC, HIC therapeutic class |
codex-plan-consult-r1.md:1649:| NDDF MEDNAMES 3.0 | 63 | MedID, routed med, dose form med, search terms |
codex-plan-consult-r1.md:1650:| NDDF ETC 1.0 | 16 | Enhanced Therapeutic Classification hierarchy |
codex-plan-consult-r1.md:1651:| NDDF XRF 1.0 | 9 | Clinical quantity crossrefs, script QQ |
codex-plan-consult-r1.md:1653:| NDDF MTL 1.0 | 19 | Medical Test Lexicon â€” separate domain |
codex-plan-consult-r1.md:1657:| Table | Cols | Uncompressed | First-field sample |
codex-plan-consult-r1.md:1673:**Python files covering FDB:**
codex-plan-consult-r1.md:1684:**Currently ingested FDB tables â†’ DB tables:**
codex-plan-consult-r1.md:1686:| FDB Table | DB Table | Notes |
codex-plan-consult-r1.md:1692:**Coverage gap: 217 of 220 FDB tables have no DB mapping.**
codex-plan-consult-r1.md:1696:| FDB Table | Cols | Rows (RECORD\_COUNTS) | Business value |
codex-plan-consult-r1.md:1707:**FDW manifest impact:** `setup_fdw.sh` uses `IMPORT FOREIGN SCHEMA ... LIMIT TO (...)` with a dynamic list. Currently 2 FDB table names are in scope for drug\_database. B9 full coverage would expand this list by 217 entries.
codex-plan-consult-r1.md:1792:The existing `TableSpec` dataclass + `FDBLocalDropAdapter.parse_table` already provides a generic parse-any-table capability. The only missing piece is:
codex-plan-consult-r1.md:1794:2. A generic `FDBBulkIngester` that iterates the registry, calling `parse_table` + bulk upsert for each
codex-plan-consult-r1.md:1843:The NDC master has 68 columns, many of which are FDB-internal flags with unclear business relevance. Without column curation, the DB table will be bloated and the ORM model unwieldy. Risk: table design gets revisited post-ingest, requiring a costly migration. Mitigation: Before B9.3, produce a column-by-column triage (keep / drop / defer) based on adjudication, formulary, and reclaimrx requirements.
codex-plan-consult-r1.md:1849:`setup_fdw.sh` uses a dynamic `LIMIT TO` allowlist. Adding 217 table names to this list is a one-time change, but the list must stay in sync with the actual schema. If a new FDB drop adds tables, the FDW will silently omit them. Mitigation: Auto-generate the LIMIT TO list from the ORM `metadata.tables` at setup time rather than maintaining a manual list.
codex-plan-consult-r1.md:1852:Current FDB ingest: RNP3 (13.2M rows) takes ~minutes. Adding 217 tables including NDC master (501K rows), ETC NDC mapping (616K rows), and MedName tables adds significant volume to the weekly UPD cycle. The UPD zip must also be verified to contain all tables (not just pricing). Mitigation: Profile UPD zip contents against DB zip contents. Validate that `NDDF Plus UPD/` has a matching file for each table before committing to weekly ingest for all 220.
codex-plan-consult-r1.md:1855:The current adapter only reads from UPD for RNP3 (pricing). Some FDB reference tables (e.g., description tables) may ship full-replacement in UPD rather than A/C/D delta. Mitigation: Inspect the UPD zip structure early in B9.1. If some tables are full-replacement (no A/C/D prefix), the ingester must detect this and use TRUNCATE+INSERT rather than ON CONFLICT DO NOTHING.
codex-plan-consult-r1.md:1861:At 217 new models, the per-test `create_all()` time in SQLite fixtures will grow. Currently 2 FDB models; adding 217 means each test session creates 219 tables. Risk: slow CI. Mitigation: Split the `FDBPricingBase` into module-level declarative bases (`FDBBasicsBase`, `FDBMedNamesBase`, etc.) so tests only create\_all for the module under test. Plan this in B9.0 before any model files are written.
codex-plan-consult-r1.md:1870:- Design the `FDBBulkIngester` (generic ingester for Tier A+B) â€” implementation-ready spec
codex-plan-consult-r1.md:1877:- Implement `FDBBulkIngester` generic infrastructure (~200 lines)
codex-plan-consult-r1.md:1919:3. **MTL go/no-go**: Does any planned adjudication rule or reclaimrx detection require lab test linkage (NDDF MTL 1.0)? If yes, B9.4 is in scope. If no, all 19 MTL tables are permanently skipped.
codex-plan-consult-r1.md:1936:6:**Scope:** All 217 currently-missing FDB NDDF Plus tables (3 already covered) reach the platform as ingested or schema-only across phases B9.A → B9.H.
codex-plan-consult-r1.md:1949:36:3. **Reference DB topology stable** — `infinityrx_reference` schemas `drug_database / drug_db / reference / shared` exist; current FDB tables `fdb_ndc_price_history` + `fdb_price_type_desc` present and queryable through FDW. (Phase 11A C9.)
codex-plan-consult-r1.md:1953:40:7. **FDB drop manifest reachable** — `data/reference/fdb/TEL251759D/RECORD_COUNTS.TXT` present and parseable (recon §1.5 verified — re-verify at C0).
codex-plan-consult-r1.md:1959:58:- **`TableSpec` registry expansion path** — adds a `TIER`, `RECORD_COUNTS_KEY`, and `LOADER_GROUP` field to existing `TableSpec` so generic ingester can: (a) tier-filter, (b) row-count reconcile, (c) loader-register by tier. Backward-compatible default values mean existing FDB pricing TableSpecs still work.
codex-plan-consult-r1.md:1971:82:- `setup_fdw.sh --verify` still 66/66 (no FDB tables added yet).
codex-plan-consult-r1.md:1991:128:**Risk:** 113 tables × ~12/session is aggressive. Mitigation: each session targets contiguous functional groups (e.g., all NDDF BASICS lookups one session; all ETC lookups another) to keep review cohesion. If a session lands fewer tables, the next absorbs the overflow — total session count flexes within the charter's 10-session band.
codex-plan-consult-r1.md:2012:186:**Scope:** RNDC14_NDC_MSTR alone — the canonical FDB NDC master, 68 columns, 183 MB, ~501K rows. Highest single-table value in the wave.
codex-plan-consult-r1.md:2013:188:**Why standalone:** 68 columns warrant column-by-column review at mini-GATE-CLOSE. Charter D1 locks "full 68-column ingest" — no column triage / no curation; every column lands. The review focuses on type correctness, NULL semantics, and naming (Python-snake_case from FDB upper-case).
codex-plan-consult-r1.md:2069:321:| SC-1 | `pg_class` count of FDB-prefixed tables in `drug_database` schema == 220; `alembic history` shows migrations 0009..0014 applied | B9.H Session 2 evidence |
codex-plan-consult-r1.md:2105:389:1. **FDW final count: 283 vs 284.** Charter says 283; PLAN's tier-additive derivation gives 284 (66 + 113 + 66 + 17 + 1 + 2 + 19 = 284). The charter figure may have netted the 3 already-covered FDB pricing tables differently. Codex PLAN consult should reconcile before B9.B opens.
codex-plan-consult-r1.md:2119:5:**Goal:** Scope FDB NDDF Plus 220-table extension beyond the 3-table Phase 09 baseline
codex-plan-consult-r1.md:2120:11:- The FDB drop contains exactly **220 data tables** in `NDDF Plus DB/NDDF PLUS DB.zip`, all with matching ANSI DDL. The current ingester covers **3 tables** (RNP3\_NDC\_PRICE, RPRDPTD0\_PRICE\_TYPE\_DESC, RNPTYPD0\_NDC\_PRICE\_TYPE\_DESC) mapped to **2 DB tables** (`fdb_ndc_price_history`, `fdb_price_type_desc`). Gap: **217 tables**.
codex-plan-consult-r1.md:2121:12:- Tables span six FDB modules: NDDF BASICS 3.0 (98 tables), MEDNAMES 3.0 (63), ETC 1.0 (16), TALL MAN PLUS 2.0 (15), XRF 1.0 (9), MTL 1.0 (19). MTL (Medical Test Lexicon) is the only module without a clear adjudication use case — treat as a product decision.
codex-plan-consult-r1.md:2122:13:- The generic `TableSpec`-driven adapter (`FDBLocalDropAdapter.parse_table`) already works for any pipe-delimited FDB table. The ingest architecture is **extension-ready**: new tables become new `TableSpec` constants + SQLAlchemy models + a migration, no adapter surgery required.
codex-plan-consult-r1.md:2124:15:- The FDW `LIMIT TO` allowlist in `setup_fdw.sh` currently names 2 FDB tables. Adding 217 more requires a structured FDW manifest expansion — this is a one-time setup change, not per-deployment.
codex-plan-consult-r1.md:2127:35:NDDF Plus DB/NDDF PLUS DB.zip      <- 220 data table files (pipe-delimited, latin-1)
codex-plan-consult-r1.md:2129:44:- ANSI DDL `CREATE TABLE` statements: **220** (+ 1 meta: `NDDF_PRODUCT_INFO`)
codex-plan-consult-r1.md:2130:54:| NDDF BASICS 3.0 / Pricing | 11 | RNP2, RNP3, RPRDPP0, price attr |
codex-plan-consult-r1.md:2131:60:| NDDF MTL 1.0 | 19 | Medical Test Lexicon — separate domain |
codex-plan-consult-r1.md:2136:91:**Currently ingested FDB tables → DB tables:**
codex-plan-consult-r1.md:2140:99:**Coverage gap: 217 of 220 FDB tables have no DB mapping.**
codex-plan-consult-r1.md:2142:114:**FDW manifest impact:** `setup_fdw.sh` uses `IMPORT FOREIGN SCHEMA ... LIMIT TO (...)` with a dynamic list. Currently 2 FDB table names are in scope for drug\_database. B9 full coverage would expand this list by 217 entries.
codex-plan-consult-r1.md:2175:250:The NDC master has 68 columns, many of which are FDB-internal flags with unclear business relevance. Without column curation, the DB table will be bloated and the ORM model unwieldy. Risk: table design gets revisited post-ingest, requiring a costly migration. Mitigation: Before B9.3, produce a column-by-column triage (keep / drop / defer) based on adjudication, formulary, and reclaimrx requirements.
codex-plan-consult-r1.md:2177:256:`setup_fdw.sh` uses a dynamic `LIMIT TO` allowlist. Adding 217 table names to this list is a one-time change, but the list must stay in sync with the actual schema. If a new FDB drop adds tables, the FDW will silently omit them. Mitigation: Auto-generate the LIMIT TO list from the ORM `metadata.tables` at setup time rather than maintaining a manual list.
codex-plan-consult-r1.md:2178:259:Current FDB ingest: RNP3 (13.2M rows) takes ~minutes. Adding 217 tables including NDC master (501K rows), ETC NDC mapping (616K rows), and MedName tables adds significant volume to the weekly UPD cycle. The UPD zip must also be verified to contain all tables (not just pricing). Mitigation: Profile UPD zip contents against DB zip contents. Validate that `NDDF Plus UPD/` has a matching file for each table before committing to weekly ingest for all 220.
codex-plan-consult-r1.md:2179:262:The current adapter only reads from UPD for RNP3 (pricing). Some FDB reference tables (e.g., description tables) may ship full-replacement in UPD rather than A/C/D delta. Mitigation: Inspect the UPD zip structure early in B9.1. If some tables are full-replacement (no A/C/D prefix), the ingester must detect this and use TRUNCATE+INSERT rather than ON CONFLICT DO NOTHING.
codex-plan-consult-r1.md:2181:268:At 217 new models, the per-test `create_all()` time in SQLite fixtures will grow. Currently 2 FDB models; adding 217 means each test session creates 219 tables. Risk: slow CI. Mitigation: Split the `FDBPricingBase` into module-level declarative bases (`FDBBasicsBase`, `FDBMedNamesBase`, etc.) so tests only create\_all for the module under test. Plan this in B9.0 before any model files are written.
codex-plan-consult-r1.md:2201:326:3. **MTL go/no-go**: Does any planned adjudication rule or reclaimrx detection require lab test linkage (NDDF MTL 1.0)? If yes, B9.4 is in scope. If no, all 19 MTL tables are permanently skipped.
codex-plan-consult-r1.md:2221:61:| SC-1 | All 217 currently-missing FDB tables have SQLAlchemy models + alembic migrations + ingester support |
codex-plan-consult-r1.md:2222:62:| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected ± documented tolerance (MTL excluded — schema-only) |
codex-plan-consult-r1.md:2241:88:| R4 | FDB weekly delta breaks because some tables ship NEW columns | Schema version detection + drift logging; halt ingest on unrecognized column |
codex-plan-consult-r1.md:3069:shared\fdb\client.py:229:        mode = os.environ.get("IFX_FDB_CLIENT", "stub").lower()
codex-plan-consult-r1.md:3308:modules\drug-database\tests\unit\test_fdb_pricing_service.py:39:from drug_database.models.fdb_pricing_tables import FDBNDCPriceHistory, FDBPricingBase
codex-plan-consult-r1.md:3313:modules\drug-database\tests\unit\test_fdb_pricing_models.py:1:"""Unit tests for FDBPricingBase ORM models (Phase 09 / 09.2 deliverable).
codex-plan-consult-r1.md:3380:modules\drug-database\tests\integration\test_fdb_pricing_through_create_app.py:89:    from drug_database.models.fdb_pricing_tables import FDBPricingBase
codex-plan-consult-r1.md:3381:modules\drug-database\tests\integration\test_fdb_pricing_through_create_app.py:103:    from drug_database.models.fdb_pricing_tables import FDBPricingBase
codex-plan-consult-r1.md:3384:modules\drug-database\tests\integration\test_fdb_pricing_through_create_app.py:204:    """FDBPricingIngester instantiates and exposes .run(mode=...).
codex-plan-consult-r1.md:4725:modules\drug-database\alembic\env.py:44:# Import FDB pricing models so FDBPricingBase.metadata is included in
codex-plan-consult-r1.md:4726:modules\drug-database\alembic\env.py:49:from drug_database.models.fdb_pricing_tables import FDBPricingBase  # noqa: E402, F401
codex-plan-consult-r1.md:4810:modules\drug-database\drug_database\services\fdb_pricing_ingester.py:64:from drug_database.models.fdb_pricing_tables import FDBNDCPriceHistory, FDBPriceTypeDesc
codex-plan-consult-r1.md:4811:modules\drug-database\drug_database\services\fdb_pricing_ingester.py:77:FDBIngestionMode = Literal["fdb_initial", "fdb_weekly", "fdb_rebase"]
codex-plan-consult-r1.md:4812:modules\drug-database\drug_database\services\fdb_pricing_ingester.py:82:    """Per-mode summary returned by FDBPricingIngester.run().
codex-plan-consult-r1.md:4813:modules\drug-database\drug_database\services\fdb_pricing_ingester.py:89:    mode: FDBIngestionMode
codex-plan-consult-r1.md:4815:modules\drug-database\drug_database\services\fdb_pricing_ingester.py:132:        mode: FDBIngestionMode,
codex-plan-consult-r1.md:4824:modules\drug-database\drug_database\services\fdb_pricing_ingester.py:306:        mode: FDBIngestionMode,
codex-plan-consult-r1.md:4829:modules\drug-database\drug_database\services\fdb_pricing.py:61:from drug_database.models.fdb_pricing_tables import FDBNDCPriceHistory
codex-plan-consult-r1.md:4887:modules\drug-database\drug_database\models\fdb_pricing_tables.py:1:"""FDB pricing ORM models — mirror of alembic migration 0008_fdb_pricing.
codex-plan-consult-r1.md:4890:modules\drug-database\drug_database\models\fdb_pricing_tables.py:194:    """Unified FDB price-type catalog (modern RPRDPTD0 + legacy RNPTYPD0).
codex-plan-consult-r1.md:5020:| FDW count 283 vs 284 | **283 is right.** Recon: 220 FDB source tables, 3 already covered, 217-table gap (`recon.md:11,99`). FDW baseline has 66 entries and B9 adds 217, so 66 + 217 = 283. Plan’s 284 comes from a Tier C arithmetic bug: “19 except RNDC14/RNP2/RPRDPP0” is 16, not 17 (`plan.md:158-160,263-265`). Correct sequence: 66→179→245→261→262→264→283. | `recon.md:11,14,99,114`; `plan.md:62,158-160,261-265,282-283,389`; `charter.md:55,66`. |
codex-plan-consult-r1.md:5038:- HIGH: SC-1 verification artifact says `pg_class` FDB-prefixed table count should be 220 (`plan.md:321`), but recon says 3 source tables currently map to 2 DB tables (`recon.md:91-97`). Final DB-table count needs explicit definition, likely not `220`.
codex-plan-consult-r1.md:5070:| FDW count 283 vs 284 | **283 is right.** Recon: 220 FDB source tables, 3 already covered, 217-table gap (`recon.md:11,99`). FDW baseline has 66 entries and B9 adds 217, so 66 + 217 = 283. Plan’s 284 comes from a Tier C arithmetic bug: “19 except RNDC14/RNP2/RPRDPP0” is 16, not 17 (`plan.md:158-160,263-265`). Correct sequence: 66→179→245→261→262→264→283. | `recon.md:11,14,99,114`; `plan.md:62,158-160,261-265,282-283,389`; `charter.md:55,66`. |
codex-plan-consult-r1.md:5088:- HIGH: SC-1 verification artifact says `pg_class` FDB-prefixed table count should be 220 (`plan.md:321`), but recon says 3 source tables currently map to 2 DB tables (`recon.md:91-97`). Final DB-table count needs explicit definition, likely not `220`.

 succeeded in 390ms:
95:- **1 alembic migration: `0009_fdb_tier_a.py`** covering all 113 Tier A tables. Charter SPEC-locks this granularity (`charter.md:75-79`); recon §4 confirms tables are uniform enough for single-file review (`recon.md:173-180`). No part-file split.
103:- 1 alembic migration (`0009_fdb_tier_a.py`)
141:- **1 alembic migration: `0010_fdb_tier_b.py`** covering all 66 Tier B tables. SPEC-locked single file (`charter.md:75-79`). No part-file split.
147:- 1 alembic migration (`0010_fdb_tier_b.py`)
167:- 1 batched alembic migration: `0011_fdb_tier_c_minus_rndc14.py`
173:- 1 alembic migration (`0011_fdb_tier_c_minus_rndc14.py`)
192:- Session 1: SQLAlchemy model with all 68 columns, type-mapped (numeric → Decimal where money-relevant; integers where ID; text where descriptor); migration `0012_fdb_rndc14_ndc_mstr.py`; full contract test set
198:- 1 alembic migration (`0012_fdb_rndc14_ndc_mstr.py`)
215:- Session 1: SQLAlchemy models for RNP2 + RPRDPP0; migration `0013_fdb_pricing_big.py`; flip `fdb_load_product_prices=True` default
223:- 1 alembic migration (`0013_fdb_pricing_big.py`)
248:- Session 1: 19 SQLAlchemy models in `tier_d/`; migration `0014_fdb_mtl_schema.py` (un-gated, lands schema); 19 contract tests asserting tables exist + are queryable + are EMPTY
255:- 1 alembic migration (`0014_fdb_mtl_schema.py`)
269:- `0014_fdb_mtl_schema.py` apply + reverse + apply: clean
392:2. **Migration count: 5 vs 6 vs 9-10** → **RESOLVED: 6.** Charter SPEC-locked the 6 files; v2 removes the part-file alternatives. Locked shape: `0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14` (16 tables), `0012_fdb_rndc14`, `0013_fdb_pricing_big`, `0014_fdb_mtl_schema`.

 succeeded in 389ms:
3:**Status:** PLAN v2 DRAFT — codex PLAN R1 GO-WITH-FIXES absorbed (Tier C 17→16, FDW ladder reconciled to 283, migration shape locked to 6 files, loader-mode erratum corrected, T12 schema-drift threat added, pytest baseline clarified, effort math reconciled). Pending codex PLAN R2 verification + codex ADVERSARIAL consult.
39:6. **134 pre-existing test failures baseline frozen** — at B9.A C0 capture TWO numbers: (a) test inventory via `pytest --collect-only -q | tail -1` (collection count), and (b) failure count via a real `pytest -q --tb=no` run, counting `FAILED`/`ERROR` lines. The 134 figure is the failure count. Each phase mini-GATE-CLOSE asserts: collection count unchanged ± new contract tests added in-phase; failure count unchanged (no regression and no unauthorized fix). Forensic wave handles those failures later (charter `Out of scope` row 3).
62:- **`setup_fdw.sh --verify` manifest expansion mechanism** — `infrastructure/scripts/lib/expected_reference_tables.txt` grows additively as each phase lands. Correct per-phase ladder: **66 baseline → 179 (after B9.B +113) → 245 (after B9.C +66) → 261 (after B9.D +16) → 262 (after B9.E +1 RNDC14) → 264 (after B9.F +2 pricing) → 283 (after B9.G +19 MTL schema-only)**. MTL adds foreign-table entries even though no data lands. B9.H final verify: 283/283 (matches charter SC-6).
63:- **pytest baseline markers** — committed to `waves/B9/baseline.md` at C0: collection count AND failure count, captured by the commands in invariant #6. Every phase mini-GATE-CLOSE re-runs both and asserts no regression.
69:| C0 | Baseline + invariants captured | `waves/B9/baseline.md`, evidence of `df -h`, `pg_authid`, FDW verify pass, pytest collect count |
81:- `pytest --collect-only` count unchanged vs. C0 baseline.
125:- `pytest --collect-only` count unchanged vs B9.A C0 baseline ± 113 new contract tests (counted in baseline)
139:- FK relationship verified per table: target table must exist (in Phase 11A baseline or B9.B if Tier B references a Tier A table)
218:- Session 4: Weekly delta idempotency timing (re-run `load_fdb.py --mode fdb_weekly` → 0 new rows + timing); FDW verify; storage budget verification against B9.A C0 baseline
235:- Storage delta vs. C0 baseline: ≤ +1.4 GB total (1.16 GB raw + index headroom)
263:**FDW count derivation (corrected per codex PLAN R1):** 66 baseline + 113 (B9.B) + 66 (B9.C) + 16 (B9.D — 19 Tier C minus 3 special-handled) + 1 (B9.E RNDC14) + 2 (B9.F RNP2+RPRDPP0) + 19 (B9.G MTL schema-only) = **283**. Matches charter SC-6.
348:| T10 | Test count baseline drifts (collection growth unexplained; or 134 pre-existing failures become 135+) | MED | MED | B9.A C0 captures TWO baselines (per invariant #6): collection count via `pytest --collect-only -q | tail -1` AND failure count via `pytest -q --tb=no` line-count of `FAILED`/`ERROR`. Each phase mini-GATE-CLOSE asserts no regression in either, ± in-phase contract tests on the collection number. |
378:- 134 pre-existing test failures (forensic wave handles these; charter §Out of scope)

codex
## PLAN R2 GATE VERDICT

GO-WITH-FIXES

## R1 fix verification

| # | Fix | Verified? | Evidence (plan line refs) | Notes |
|---|---|---|---|---|
| F1 | Tier C count 17 → 16 | YES | `plan.md:158-160`, `plan.md:175`, `plan.md:263`, `plan.md:365`, `plan.md:391` | Corrected to 16 everywhere material in PLAN v2. |
| F2 | FDW ladder to 283 | YES | `plan.md:62`, `plan.md:106`, `plan.md:150`, `plan.md:175`, `plan.md:201`, `plan.md:227`, `plan.md:261-263`, `plan.md:282-283`, `plan.md:326`, `plan.md:391` | Ladder is now 66 → 179 → 245 → 261 → 262 → 264 → 283. |
| F3 | 6 migrations SPEC-locked | YES | `plan.md:95`, `plan.md:141`, `plan.md:167`, `plan.md:192`, `plan.md:215`, `plan.md:248`, `plan.md:392` | No `_part1..N` variants found; explicit “No part-file split” for A/B. |
| F4 | Loader-mode erratum | YES | `plan.md:61`, `plan.md:249`, `plan.md:393` | Correctly states `fdb_initial`, `fdb_weekly`, `fdb_rebase` already exist; B9 adds MTL opt-in only if needed. |
| F5 | T12 weekly-delta threat | YES | `plan.md:350` | Adds UPD A/C/D probe, TRUNCATE+INSERT routing, mini-gate recheck, and R4 new-column drift coverage. |
| F6 | Effort math reconciled | YES | `plan.md:395-402` | Explains 39 productive sessions vs 42 calendar-aware sessions. |
| F7 | SC-1 verification (pg_class count) | YES | `plan.md:321` | Corrected to `pg_class == 219`, with explicit 220 source → 219 DB-table mapping. |
| F8 | pytest baseline (real failure count) | YES | `plan.md:39`, `plan.md:63`, `plan.md:348` | Uses collection count plus real `pytest -q --tb=no` failure/error count. |

## Charter-vs-plan consistency

| # | Check | Pass? |
|---|---|---|
| C1 | Per-phase mini-GATE-CLOSE rows match charter v3 phase table | NO |
| C2 | Migration shape matches charter §SPEC-locked migration granularity | YES |
| C3 | SC-1..SC-11 all have goal-backward verification artifacts | YES |
| C4 | D2 perf gate (SC-4) is real in B9.F | YES |
| C5 | MTL guards (SC-5) are triple-layered in B9.G | YES |

## Vendor-name sanity check

PASS with grep evidence: `rg -n "First|DataBank|Databank|FirstDataBank" plan.md charter.md recon.md` shows no problematic vendor-name variants in PLAN v2; PLAN uses `FDB` / `NDDF Plus` consistently, e.g. `plan.md:5-6`, `plan.md:350`, `plan.md:383`.

## New concerns surfaced in v2 (if any)

- MEDIUM: Charter v3 phase table is now stale against the corrected PLAN v2 arithmetic. `charter.md:51` still says “Tier C non-RNDC14 — 17 complex tables,” while PLAN v2 correctly says 16 at `plan.md:158-160`. `charter.md:49` also still says Tier A closure FDW verify `116/116`, while the corrected ladder requires `179/179` after B9.B (`plan.md:106`, `plan.md:120`). This blocks strict charter-vs-plan consistency, even though PLAN v2’s corrected numbers are right.

## Final verdict + next action

GO-WITH-FIXES. PLAN v2 verifies all eight R1 fixes, but it cannot proceed to ADVERSARIAL while the locked charter phase table still conflicts with the corrected plan on B9.B FDW count and B9.D Tier C count. Required next change: apply a narrow charter v3 erratum or PLAN v3 consistency note that explicitly supersedes `charter.md:49` to `179/179` and `charter.md:51` to 16 Tier C non-RNDC14 tables, then rerun PLAN R2 or proceed if your governance allows documented charter errata.
tokens used
52,515
## PLAN R2 GATE VERDICT

GO-WITH-FIXES

## R1 fix verification

| # | Fix | Verified? | Evidence (plan line refs) | Notes |
|---|---|---|---|---|
| F1 | Tier C count 17 → 16 | YES | `plan.md:158-160`, `plan.md:175`, `plan.md:263`, `plan.md:365`, `plan.md:391` | Corrected to 16 everywhere material in PLAN v2. |
| F2 | FDW ladder to 283 | YES | `plan.md:62`, `plan.md:106`, `plan.md:150`, `plan.md:175`, `plan.md:201`, `plan.md:227`, `plan.md:261-263`, `plan.md:282-283`, `plan.md:326`, `plan.md:391` | Ladder is now 66 → 179 → 245 → 261 → 262 → 264 → 283. |
| F3 | 6 migrations SPEC-locked | YES | `plan.md:95`, `plan.md:141`, `plan.md:167`, `plan.md:192`, `plan.md:215`, `plan.md:248`, `plan.md:392` | No `_part1..N` variants found; explicit “No part-file split” for A/B. |
| F4 | Loader-mode erratum | YES | `plan.md:61`, `plan.md:249`, `plan.md:393` | Correctly states `fdb_initial`, `fdb_weekly`, `fdb_rebase` already exist; B9 adds MTL opt-in only if needed. |
| F5 | T12 weekly-delta threat | YES | `plan.md:350` | Adds UPD A/C/D probe, TRUNCATE+INSERT routing, mini-gate recheck, and R4 new-column drift coverage. |
| F6 | Effort math reconciled | YES | `plan.md:395-402` | Explains 39 productive sessions vs 42 calendar-aware sessions. |
| F7 | SC-1 verification (pg_class count) | YES | `plan.md:321` | Corrected to `pg_class == 219`, with explicit 220 source → 219 DB-table mapping. |
| F8 | pytest baseline (real failure count) | YES | `plan.md:39`, `plan.md:63`, `plan.md:348` | Uses collection count plus real `pytest -q --tb=no` failure/error count. |

## Charter-vs-plan consistency

| # | Check | Pass? |
|---|---|---|
| C1 | Per-phase mini-GATE-CLOSE rows match charter v3 phase table | NO |
| C2 | Migration shape matches charter §SPEC-locked migration granularity | YES |
| C3 | SC-1..SC-11 all have goal-backward verification artifacts | YES |
| C4 | D2 perf gate (SC-4) is real in B9.F | YES |
| C5 | MTL guards (SC-5) are triple-layered in B9.G | YES |

## Vendor-name sanity check

PASS with grep evidence: `rg -n "First|DataBank|Databank|FirstDataBank" plan.md charter.md recon.md` shows no problematic vendor-name variants in PLAN v2; PLAN uses `FDB` / `NDDF Plus` consistently, e.g. `plan.md:5-6`, `plan.md:350`, `plan.md:383`.

## New concerns surfaced in v2 (if any)

- MEDIUM: Charter v3 phase table is now stale against the corrected PLAN v2 arithmetic. `charter.md:51` still says “Tier C non-RNDC14 — 17 complex tables,” while PLAN v2 correctly says 16 at `plan.md:158-160`. `charter.md:49` also still says Tier A closure FDW verify `116/116`, while the corrected ladder requires `179/179` after B9.B (`plan.md:106`, `plan.md:120`). This blocks strict charter-vs-plan consistency, even though PLAN v2’s corrected numbers are right.

## Final verdict + next action

GO-WITH-FIXES. PLAN v2 verifies all eight R1 fixes, but it cannot proceed to ADVERSARIAL while the locked charter phase table still conflicts with the corrected plan on B9.B FDW count and B9.D Tier C count. Required next change: apply a narrow charter v3 erratum or PLAN v3 consistency note that explicitly supersedes `charter.md:49` to `179/179` and `charter.md:51` to 16 Tier C non-RNDC14 tables, then rerun PLAN R2 or proceed if your governance allows documented charter errata.
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\plan.md' -Pattern '116/116','179/179','17 complex','16 complex','FDW ladder','66 baseline','Tier C non-RNDC14'"` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"v3\\.1|Erratum|116/116|179/179|17 complex|16 complex|16 complex tables\" \"C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\charter.md\"" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"116/116|179/179|17 complex|16 complex|FDW ladder|66 baseline|Tier C non-RNDC14\" \"C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\plan.md\"" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 355ms:
3:**Status:** PLAN v2 DRAFT — codex PLAN R1 GO-WITH-FIXES absorbed (Tier C 17→16, FDW ladder reconciled to 283, migration shape locked to 6 files, loader-mode erratum corrected, T12 schema-drift threat added, pytest baseline clarified, effort math reconciled). Pending codex PLAN R2 verification + codex ADVERSARIAL consult.
62:- **`setup_fdw.sh --verify` manifest expansion mechanism** — `infrastructure/scripts/lib/expected_reference_tables.txt` grows additively as each phase lands. Correct per-phase ladder: **66 baseline → 179 (after B9.B +113) → 245 (after B9.C +66) → 261 (after B9.D +16) → 262 (after B9.E +1 RNDC14) → 264 (after B9.F +2 pricing) → 283 (after B9.G +19 MTL schema-only)**. MTL adds foreign-table entries even though no data lands. B9.H final verify: 283/283 (matches charter SC-6).
112:- SC-6 (FDW verify) — partial: 179/179 PASS after B9.B
120:- `setup_fdw.sh --verify` 179/179 PASS both env DBs
158:### B9.D — Tier C non-RNDC14: 16 complex/large tables (4 sessions)
263:**FDW count derivation (corrected per codex PLAN R1):** 66 baseline + 113 (B9.B) + 66 (B9.C) + 16 (B9.D — 19 Tier C minus 3 special-handled) + 1 (B9.E RNDC14) + 2 (B9.F RNP2+RPRDPP0) + 19 (B9.G MTL schema-only) = **283**. Matches charter SC-6.
365:| mini-GATE-CLOSE B9.D | B9.D | After Tier C non-RNDC14 all 16 ingested | `codex-mini-gate-close-D.md` |

 succeeded in 364ms:
3:**Status:** SPEC v3.1 LOCKED — SPEC v3 + erratum applied after codex PLAN R2 surfaced arithmetic drift between charter and PLAN v2. Erratum: B9.B closure-gate FDW count `116/116` → `179/179`; B9.D scope "17 complex tables" → "16 complex tables" (19 Tier C minus 3 special-handled). No scope change; arithmetic correction only. See `codex-plan-consult-r2.md`. Ready for PLAN v2 → ADVERSARIAL.
49:| B9.B | Tier A — 113 simple lookups via generic table-driven ingester | 10 | **B9.B mini-GATE-CLOSE** — evidence + row-count manifest + FDW verify 179/179 + ingester contract tests |
51:| B9.D | Tier C non-RNDC14 — 16 complex tables | 4 | **B9.D mini-GATE-CLOSE** (FDW 261/261) |

codex
## PLAN GATE FINAL VERDICT

GO

## Evidence

- charter.md:3 — v3.1 erratum note present
- charter.md:49 — 179/179 (corrected)
- charter.md:51 — 16 complex tables (corrected)
- Plan v2 vs charter v3.1 consistency: PASS

## Next action

Proceed to codex ADVERSARIAL consult.
tokens used
25,188
## PLAN GATE FINAL VERDICT

GO

## Evidence

- charter.md:3 — v3.1 erratum note present
- charter.md:49 — 179/179 (corrected)
- charter.md:51 — 16 complex tables (corrected)
- Plan v2 vs charter v3.1 consistency: PASS

## Next action

Proceed to codex ADVERSARIAL consult.
