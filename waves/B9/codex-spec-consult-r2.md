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
session id: 019e1874-cc66-7ea2-a9cb-a191aef7c85a
--------
user
You are codex acting as the SPEC GATE reviewer for the InfinityRx platform's Wave B9 charter, round 2.

## Context

Wave B9 = "FDB NDDF Plus 220-table extension". Recon was completed 2026-05-11 (`recon.md`). Charter v1 was dispatched for SPEC R1. You returned **GO-WITH-FIXES** with 6 substantive concerns (1 HIGH effort model, 2 HIGH process gates, 3 MEDIUM SPEC tightenings, 1 LOW vendor-name pass). The owner produced charter v2 which claims to absorb all 6 concerns. Your job in R2 is to verify whether v2 actually addresses each concern, and either issue **GO** (proceed to PLAN), **GO-WITH-FIXES** (one more revision needed), or **NO-GO** (structural problem).

## Artifacts (read these from disk)

1. `C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\recon.md` — scope ground truth (328 lines)
2. `C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\charter.md` — charter v2, the document you are reviewing (115 lines)
3. `C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\codex-spec-consult-r1.md` — your R1 verdict that v2 is responding to (120 lines)

## R1 concerns to verify in v2 (use these as your checklist)

| # | Sev | R1 concern | What v2 must show |
|---|---|---|---|
| 1 | HIGH | Single final GATE-CLOSE too late for 220 tables | Per-phase mini-GATE-CLOSE gates between B9.B..B9.G with explicit closure criteria |
| 2 | HIGH | D2 reversal needs real perf gate, not just disk check | C0 perf gate with timed full-load dry run for RNP2 + RPRDPP0, EXPLAIN ANALYZE, weekly delta timing |
| 3 | HIGH | Effort model contradicts recon (100 vs 34/39 sessions) | Charter explains the number consistent with recon's A+B+C+D estimate; no unexplained inflation |
| 4 | MED | MTL schema-only — DO NOT config-gate Alembic; guard at loader+config | Schema migration unconditional; runtime/loader/config guards prevent data load; CI test asserts zero MTL rows |
| 5 | MED | Migration granularity must be SPEC-locked, not deferred to plan | No 1-per-table, no 1-mega; per-phase batched migrations specified; RNDC14 standalone |
| 6 | MED | SC-8 test strategy underspecified | Contract + parity + reconciliation + sampled behavioral + dedicated Tier C tests; no 217 bespoke per-table tests |

## Verdict format (match this exactly)

```
## SPEC R2 GATE VERDICT

<GO | GO-WITH-FIXES | NO-GO>

## R1 concern verification

| # | R1 fix | Verified in v2? | Evidence (charter line ref) | Notes |
|---|---|---|---|---|
| 1 | Per-phase gates | YES / PARTIAL / NO | <line refs> | <short> |
| 2 | D2 perf gate | YES / PARTIAL / NO | <line refs> | <short> |
| 3 | Effort model | YES / PARTIAL / NO | <line refs> | <short> |
| 4 | MTL guards | YES / PARTIAL / NO | <line refs> | <short> |
| 5 | Migration granularity | YES / PARTIAL / NO | <line refs> | <short> |
| 6 | Test strategy | YES / PARTIAL / NO | <line refs> | <short> |

## New concerns surfaced in v2 (if any)

<list with severity, or "None">

## Vendor-name sanity check

<PASS / FAIL with grep evidence>

## Final verdict + next action

<one paragraph: if GO → proceed to PLAN v1 codex consult; if GO-WITH-FIXES → list required fixes; if NO-GO → explain structural problem>
```

Be rigorous. If a fix is incomplete or papered-over, mark PARTIAL and require revision. Do not GO unless all 6 fixes are verifiable at specific charter line refs and vendor-name check passes.
codex
I’ll review the three wave artifacts directly and compare charter v2 against the R1 checklist. I’ll also run a vendor-name grep over the B9 docs so the verdict is grounded in exact line references.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\charter.md'; if (Test-Path -LiteralPath "'$p) { $i=0; Get-Content -LiteralPath $p | ForEach-Object { $i++; '"'{0,4}: {1}' -f "'$i, $_ } } else { '"'MISSING charter.md' }" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$dir='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9'; if (Get-Command rg -ErrorAction SilentlyContinue) { rg -n -i \"First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14\" "'$dir } else { Get-ChildItem -LiteralPath $dir -File | Select-String -Pattern '"'First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14' -CaseSensitive:"'$false }' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\codex-spec-consult-r1.md'; if (Test-Path -LiteralPath "'$p) { $i=0; Get-Content -LiteralPath $p | ForEach-Object { $i++; '"'{0,4}: {1}' -f "'$i, $_ } } else { '"'MISSING codex-spec-consult-r1.md' }" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\recon.md'; if (Test-Path -LiteralPath "'$p) { $i=0; Get-Content -LiteralPath $p | ForEach-Object { $i++; '"'{0,4}: {1}' -f "'$i, $_ } } else { '"'MISSING recon.md' }" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\charter.md'; if (Test-Path -LiteralPath "'$p) { $i=0; Get-Content -LiteralPath $p | ForEach-Object { $i++; '"'{0,4}: {1}' -f "'$i, $_ } } else { '"'MISSING charter.md' }"` rejected: blocked by policy
2026-05-11T19:13:02.640884Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\charter.md'; if (Test-Path -LiteralPath "'$p) { $i=0; Get-Content -LiteralPath $p | ForEach-Object { $i++; '"'{0,4}: {1}' -f "'$i, $_ } } else { '"'MISSING charter.md' }"` rejected: blocked by policy
2026-05-11T19:13:02.641476Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\codex-spec-consult-r1.md'; if (Test-Path -LiteralPath "'$p) { $i=0; Get-Content -LiteralPath $p | ForEach-Object { $i++; '"'{0,4}: {1}' -f "'$i, $_ } } else { '"'MISSING codex-spec-consult-r1.md' }"` rejected: blocked by policy
2026-05-11T19:13:02.641827Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$dir='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9'; if (Get-Command rg -ErrorAction SilentlyContinue) { rg -n -i \"First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14\" "'$dir } else { Get-ChildItem -LiteralPath $dir -File | Select-String -Pattern '"'First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14' -CaseSensitive:"'$false }'` rejected: blocked by policy
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$dir='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9'; if (Get-Command rg -ErrorAction SilentlyContinue) { rg -n -i \"First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14\" "'$dir } else { Get-ChildItem -LiteralPath $dir -File | Select-String -Pattern '"'First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14' -CaseSensitive:"'$false }'` rejected: blocked by policy
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\codex-spec-consult-r1.md'; if (Test-Path -LiteralPath "'$p) { $i=0; Get-Content -LiteralPath $p | ForEach-Object { $i++; '"'{0,4}: {1}' -f "'$i, $_ } } else { '"'MISSING codex-spec-consult-r1.md' }"` rejected: blocked by policy
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\recon.md'; if (Test-Path -LiteralPath "'$p) { $i=0; Get-Content -LiteralPath $p | ForEach-Object { $i++; '"'{0,4}: {1}' -f "'$i, $_ } } else { '"'MISSING recon.md' }"` rejected: blocked by policy
2026-05-11T19:13:02.642113Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\recon.md'; if (Test-Path -LiteralPath "'$p) { $i=0; Get-Content -LiteralPath $p | ForEach-Object { $i++; '"'{0,4}: {1}' -f "'$i, $_ } } else { '"'MISSING recon.md' }"` rejected: blocked by policy
codex
The first read attempt was rejected by the local command policy, likely because of the absolute path quoting pattern. I’m going to retry with simpler PowerShell commands from the B9 directory so I can still produce the requested line-specific review.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command Get-Location in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 322ms:

Path                                                            
----                                                            
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform



exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-ChildItem -Name' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
 succeeded in 326ms:
charter.md
codex-spec-consult-r1.md
codex-spec-consult-r2.md
recon.md

2026-05-11T19:13:19.725691Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$i=0; Get-Content .'"\\recon.md | ForEach-Object { "'$i++; '"'{0,4}: {1}' -f "'$i, $_ }'` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$i=0; Get-Content .'"\\recon.md | ForEach-Object { "'$i++; '"'{0,4}: {1}' -f "'$i, $_ }' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$i=0; Get-Content .'"\\charter.md | ForEach-Object { "'$i++; '"'{0,4}: {1}' -f "'$i, $_ }' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$i=0; Get-Content .'"\\recon.md | ForEach-Object { "'$i++; '"'{0,4}: {1}' -f "'$i, $_ }'` rejected: blocked by policy
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$i=0; Get-Content .'"\\charter.md | ForEach-Object { "'$i++; '"'{0,4}: {1}' -f "'$i, $_ }'` rejected: blocked by policy
2026-05-11T19:13:19.726471Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$i=0; Get-Content .'"\\charter.md | ForEach-Object { "'$i++; '"'{0,4}: {1}' -f "'$i, $_ }'` rejected: blocked by policy
2026-05-11T19:13:19.732365Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$i=0; Get-Content .'"\\codex-spec-consult-r1.md | ForEach-Object { "'$i++; '"'{0,4}: {1}' -f "'$i, $_ }'` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$i=0; Get-Content .'"\\codex-spec-consult-r1.md | ForEach-Object { "'$i++; '"'{0,4}: {1}' -f "'$i, $_ }' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$i=0; Get-Content .'"\\codex-spec-consult-r1.md | ForEach-Object { "'$i++; '"'{0,4}: {1}' -f "'$i, $_ }'` rejected: blocked by policy
2026-05-11T19:13:19.767559Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "if (Get-Command rg -ErrorAction SilentlyContinue) { rg -n -i \"First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14\" . } else { Get-ChildItem -File | Select-String -Pattern 'First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14' -CaseSensitive:"'$false }'` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "if (Get-Command rg -ErrorAction SilentlyContinue) { rg -n -i \"First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14\" . } else { Get-ChildItem -File | Select-String -Pattern 'First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14' -CaseSensitive:"'$false }' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "if (Get-Command rg -ErrorAction SilentlyContinue) { rg -n -i \"First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14\" . } else { Get-ChildItem -File | Select-String -Pattern 'First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14' -CaseSensitive:"'$false }'` rejected: blocked by policy
codex
Listing the directory works, but the policy is rejecting compound PowerShell pipelines. I have the artifacts present, so I’ll switch to very simple reads/searches and add line numbers from the file content manually.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content charter.md' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
 succeeded in 332ms:
# Wave B9 â€” FDB NDDF Plus 220-table extension (full scope)

**Status:** SPEC v2 (codex SPEC R1 GO-WITH-FIXES â†’ 6 substantive concerns absorbed; R2 to confirm)
**Recon:** `recon.md` (2026-05-11) â€” verified scope and effort
**Predecessor:** Phase 09 FDB pricing ingester (3 tables); Phase 11A reference DB topology; B7.2 architectural cleanup
**Authority:** Project owner locked 4 scope decisions 2026-05-11 (this document captures them)

---

## Goal

Extend FDB NDDF Plus ingest from current **3 tables â†’ all 220 tables** (217-table gap). Adjudication, formulary, reclaimrx, and future Phase 4 modules gain full FDB reference coverage. Single B9 wave milestone; multi-session execution.

## Locked decisions (2026-05-11)

| # | Decision | Rationale |
|---|---|---|
| D1 | **RNDC14 = full 68-column ingest** | Future-proof; avoids N+1 schema-extension waves as consumers surface column needs. |
| D2 | **RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE = include + load by default** | Reverses Phase 09 `fdb_load_product_prices=False` deferral. +1.16 GB storage required; needs disk + Postgres performance verification at C0. |
| D3 | **Medical Test Lexicon (MTL) = schema-only, no data load** | Honors "clinical screening NOT subscribed" memory while landing table structure for future activation. 19 tables, 103 KB raw. If licensing changes, flip a config flag. |
| D4 | **Single B9 wave for all 217 tables** | One milestone label; not split into B9/B10/B11. ~34 four-hour sessions elapsed; ~6 months wall-clock. |

## Workstreams (recon-validated effort)

| W | Scope | Tables | Effort (recon line 14 + sections 6/7) |
|---|---|---|---|
| W1 | Tier A â€” simple lookups (â‰¤5 columns, generic ingester) | 113 | ~10 sessions |
| W2 | Tier B â€” NDC/GCN-keyed joins | 66 | ~12 sessions |
| W3 | Tier C â€” complex/large + RNDC14 full + RNP2 + RPRDPP0 + perf gate | 19 | ~10 sessions (8 baseline + ~2 D2 perf gate) |
| W4 | Tier D â€” MTL schema-only (no data load) | 19 | ~3 sessions |
| W5 | C0 baseline + D2 dry-run perf test + FDW manifest extension + closeout | n/a | ~4 sessions |

**Total: ~39 sessions** (recon's A+B+C estimate is 34; +3 Tier D + ~2 D2 perf gate = 39). With codex review cadence already baked into per-phase budget. **Charter v1's 100-session figure was a misread; v2 corrects to recon's actual numbers.** Wall-clock at 3 sessions/week: ~13 weeks (~3 months).

## Out of scope (deferred)

- Clinical screening DATA ingest (only schema lands per D3)
- B8.2 followups (build_response docstring already shipped `1c28e44`)
- 134 pre-existing test failures (forensic wave)
- Phase 4 forward feature work

## Phased execution + per-phase closure gates (HIGH #1 codex fix)

B9 ships incrementally **with mandatory per-phase closure gates** â€” each phase (B9.B..B9.F) gets its own evidence + row-count reconciliation + migration review + FDW verify + test baseline comparison + mini-GATE-CLOSE consult. A single final GATE-CLOSE across 220 tables would catch drift too late.

| Phase | Sub-scope | Sessions | Closure gate |
|---|---|---|---|
| B9.A | Charter v2 + plan v1 + codex SPEC R2 / PLAN / ADVERSARIAL | 2-3 | Plan v1 locked |
| B9.B | Tier A â€” 113 simple lookups via generic table-driven ingester | 10 | **B9.B mini-GATE-CLOSE** â€” evidence + row-count manifest + FDW verify 116/116 + ingester contract tests |
| B9.C | Tier B â€” 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** â€” same scope + per-tier sampled behavioral tests |
| B9.D | Tier C non-RNDC14 â€” 17 complex tables | 4 | **B9.D mini-GATE-CLOSE** |
| B9.E | RNDC14 dedicated migration (68 cols) | 2 | **B9.E mini-GATE-CLOSE** â€” column-by-column model review |
| B9.F | RNP2 + RPRDPP0 + C0 perf gate (D2 reversal) | 4 | **B9.F mini-GATE-CLOSE** â€” perf test results + EXPLAIN ANALYZE + storage budget verification |
| B9.G | Tier D MTL schema-only + loader-registration safeguards | 3 | **B9.G mini-GATE-CLOSE** â€” integration test asserts zero MTL rows after default `load_fdb.py --mode fdb_weekly` |
| B9.H | Manifest extension (66 â†’ 283 FDW entries) + final closeout artifacts | 4 | **Final B9 GATE-CLOSE** â€” full cross-tier consult |

## Success criteria

| SC | Description |
|---|---|
| SC-1 | All 217 currently-missing FDB tables have SQLAlchemy models + alembic migrations + ingester support |
| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected Â± documented tolerance (MTL excluded â€” schema-only) |
| SC-3 | RNDC14 ingest covers all 68 columns with column-curation review at B9.E mini-GATE-CLOSE |
| SC-4 | **D2 performance gate**: timed full-load dry run of RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE measured; representative `EXPLAIN ANALYZE` on indexed query patterns captured; Postgres + FDW verify completes within 5min after indexes built; weekly delta idempotency timing documented |
| SC-5 | MTL schema lands but **runtime/loader guards** prevent data load: `fdb_load_mtl=False` default; MTL tables excluded from default loader registry; integration test asserts **zero MTL rows** after default `load_fdb.py --mode fdb_weekly`. Alembic migration itself is NOT config-gated (per codex SPEC R1 #4). |
| SC-6 | `setup_fdw.sh --verify` 283/283 PASS in both env DBs |
| SC-7 | Weekly delta ingest path idempotent across all 220 tables (ON CONFLICT DO NOTHING or UPSERT per table; verified by re-running) |
| SC-8 | **Test coverage strategy** (per codex SPEC R1 #6): contract coverage for every `TableSpec`; schema/model parity for every table; row-count reconciliation for every loaded table; sampled behavioral tests per tier; dedicated Tier C tests for RNDC14 / RNP2 / RPRDPP0 / weekly delta. **No bespoke per-table behavioral tests** for the 217 tables â€” too heavy. |
| SC-9 | Each of B9.B..B9.G passes a mini-GATE-CLOSE consult before next phase opens |
| SC-10 | Final B9 GATE-CLOSE GO or GO-WITH-FIXES |
| SC-11 | Evidence + ship + memory + wave-history + B9 phased-progress dashboard |

## SPEC-locked migration granularity (codex SPEC R1 #5 fix)

**Migration granularity is SPEC-locked**, not deferred to plan:
- **NO** one-table-per-migration (213 migrations would be unmaintainable)
- **NO** single 217-table migration (atomicity ruined; review intractable)
- **YES** per-phase batched migrations (`0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14`, `0012_fdb_rndc14`, `0013_fdb_pricing_big` for RNP2+RPRDPP0, `0014_fdb_mtl_schema`)
- **RNDC14 migration MUST be standalone** (`0012_fdb_rndc14`) â€” 68 cols warrant dedicated review at B9.E mini-GATE-CLOSE

## Risks

| # | Risk | Mit |
|---|---|---|
| R1 | 217 alembic migrations is unwieldy for review | SPEC-locked above to ~6 per-phase batched migrations + RNDC14 standalone. |
| R2 | RNP2 + RPRDPP0 (1.16 GB) exhausts dev Postgres disk OR query performance regresses | C0: verify disk free; add indexes per actual query patterns; monitor pg_stat_user_tables size growth |
| R3 | RNDC14 68 columns include latin-1 quirks (mixed-case names, accented chars, NULL sentinels) | Per-column normalization pass in ingester; latin-1 â†’ UTF-8 with replacement strategy documented |
| R4 | FDB weekly delta breaks because some tables ship NEW columns | Schema version detection + drift logging; halt ingest on unrecognized column |
| R5 | Tier C complex tables have foreign keys that don't validate after partial ingest | Defer FK constraints to phase-end; verify referential integrity at C8 |
| R6 | 6-month wall-clock invites scope drift / charter decay | Phased execution table is contract; each phase has explicit closure gate |
| R7 | MTL schema accidentally activates (data ingest fires when it shouldn't) | Config flag `fdb_load_mtl=False` enforced via integration test; CI gate denies MTL data on default flag |

## Discipline

- **codex SPEC consult:** 1-3 rounds against this charter (full discipline restored given scope size)
- **codex PLAN consult:** 1-2 rounds against plan v1
- **ADVERSARIAL:** 2-3 rounds (large surface, novel scope, $11.96+ codex cost expected)
- **codex GATE-CLOSE:** 1-2 rounds at wave close (and possibly per-phase mini-closes)

## Estimated wall-clock (v2 corrected)

**~39 sessions Ã— 4h = ~156 productive hours.** At 3 sessions/week: **~13 weeks (~3 months elapsed)**. With multitasking + non-B9 work: realistically 4-5 months elapsed. (Charter v1's 100-session figure was wrong â€” corrected per codex SPEC R1 #3; recon's actual estimate was always 34 sessions for A+B+C, not "Tier A only".)

## Note on scope vs recon recommendation

The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification â€” preserving B7-style checkpoint cadence inside the single B9 milestone.

---

## Resume next session

1. `/werkbench`
2. Read this charter
3. Codex SPEC consult round 1 (against this v1)
4. Iterate to GO; then plan v1

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n -i "First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14|100-session|34|39|mini-GATE|GATE-CLOSE|EXPLAIN ANALYZE|bespoke|migration" charter.md codex-spec-consult-r1.md recon.md' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
 succeeded in 738ms:
charter.md:1:# Wave B9 — FDB NDDF Plus 220-table extension (full scope)
charter.md:5:**Predecessor:** Phase 09 FDB pricing ingester (3 tables); Phase 11A reference DB topology; B7.2 architectural cleanup
charter.md:12:Extend FDB NDDF Plus ingest from current **3 tables → all 220 tables** (217-table gap). Adjudication, formulary, reclaimrx, and future Phase 4 modules gain full FDB reference coverage. Single B9 wave milestone; multi-session execution.
charter.md:18:| D1 | **RNDC14 = full 68-column ingest** | Future-proof; avoids N+1 schema-extension waves as consumers surface column needs. |
charter.md:19:| D2 | **RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE = include + load by default** | Reverses Phase 09 `fdb_load_product_prices=False` deferral. +1.16 GB storage required; needs disk + Postgres performance verification at C0. |
charter.md:20:| D3 | **Medical Test Lexicon (MTL) = schema-only, no data load** | Honors "clinical screening NOT subscribed" memory while landing table structure for future activation. 19 tables, 103 KB raw. If licensing changes, flip a config flag. |
charter.md:21:| D4 | **Single B9 wave for all 217 tables** | One milestone label; not split into B9/B10/B11. ~34 four-hour sessions elapsed; ~6 months wall-clock. |
charter.md:29:| W3 | Tier C — complex/large + RNDC14 full + RNP2 + RPRDPP0 + perf gate | 19 | ~10 sessions (8 baseline + ~2 D2 perf gate) |
charter.md:30:| W4 | Tier D — MTL schema-only (no data load) | 19 | ~3 sessions |
charter.md:33:**Total: ~39 sessions** (recon's A+B+C estimate is 34; +3 Tier D + ~2 D2 perf gate = 39). With codex review cadence already baked into per-phase budget. **Charter v1's 100-session figure was a misread; v2 corrects to recon's actual numbers.** Wall-clock at 3 sessions/week: ~13 weeks (~3 months).
charter.md:39:- 134 pre-existing test failures (forensic wave)
charter.md:44:B9 ships incrementally **with mandatory per-phase closure gates** — each phase (B9.B..B9.F) gets its own evidence + row-count reconciliation + migration review + FDW verify + test baseline comparison + mini-GATE-CLOSE consult. A single final GATE-CLOSE across 220 tables would catch drift too late.
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
charter.md:68:| SC-8 | **Test coverage strategy** (per codex SPEC R1 #6): contract coverage for every `TableSpec`; schema/model parity for every table; row-count reconciliation for every loaded table; sampled behavioral tests per tier; dedicated Tier C tests for RNDC14 / RNP2 / RPRDPP0 / weekly delta. **No bespoke per-table behavioral tests** for the 217 tables — too heavy. |
charter.md:69:| SC-9 | Each of B9.B..B9.G passes a mini-GATE-CLOSE consult before next phase opens |
charter.md:70:| SC-10 | Final B9 GATE-CLOSE GO or GO-WITH-FIXES |
charter.md:73:## SPEC-locked migration granularity (codex SPEC R1 #5 fix)
charter.md:75:**Migration granularity is SPEC-locked**, not deferred to plan:
charter.md:76:- **NO** one-table-per-migration (213 migrations would be unmaintainable)
charter.md:77:- **NO** single 217-table migration (atomicity ruined; review intractable)
charter.md:78:- **YES** per-phase batched migrations (`0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14`, `0012_fdb_rndc14`, `0013_fdb_pricing_big` for RNP2+RPRDPP0, `0014_fdb_mtl_schema`)
charter.md:79:- **RNDC14 migration MUST be standalone** (`0012_fdb_rndc14`) — 68 cols warrant dedicated review at B9.E mini-GATE-CLOSE
charter.md:85:| R1 | 217 alembic migrations is unwieldy for review | SPEC-locked above to ~6 per-phase batched migrations + RNDC14 standalone. |
charter.md:86:| R2 | RNP2 + RPRDPP0 (1.16 GB) exhausts dev Postgres disk OR query performance regresses | C0: verify disk free; add indexes per actual query patterns; monitor pg_stat_user_tables size growth |
charter.md:87:| R3 | RNDC14 68 columns include latin-1 quirks (mixed-case names, accented chars, NULL sentinels) | Per-column normalization pass in ingester; latin-1 → UTF-8 with replacement strategy documented |
charter.md:88:| R4 | FDB weekly delta breaks because some tables ship NEW columns | Schema version detection + drift logging; halt ingest on unrecognized column |
charter.md:91:| R7 | MTL schema accidentally activates (data ingest fires when it shouldn't) | Config flag `fdb_load_mtl=False` enforced via integration test; CI gate denies MTL data on default flag |
charter.md:98:- **codex GATE-CLOSE:** 1-2 rounds at wave close (and possibly per-phase mini-closes)
charter.md:102:**~39 sessions × 4h = ~156 productive hours.** At 3 sessions/week: **~13 weeks (~3 months elapsed)**. With multitasking + non-B9 work: realistically 4-5 months elapsed. (Charter v1's 100-session figure was wrong — corrected per codex SPEC R1 #3; recon's actual estimate was always 34 sessions for A+B+C, not "Tier A only".)
charter.md:106:The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification — preserving B7-style checkpoint cadence inside the single B9 milestone.
codex-spec-consult-r1.md:4:C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\charter.md:53:| B9.F | Tier D — MTL 
codex-spec-consult-r1.md:8:C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\charter.md:55:| Codex GATE-CLOSE | 
codex-spec-consult-r1.md:11:currently-missing FDB tables have SQLAlchemy models + alembic migrations + ingester support |
codex-spec-consult-r1.md:12:C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\charter.md:64:| SC-4 | RNP2 + 
codex-spec-consult-r1.md:13:RPRDPP0 ingest succeeds end-to-end; storage stays within disk budget; query performance acceptable on indexed columns |
codex-spec-consult-r1.md:17:ingest path: re-running `load_fdb.py --mode fdb_weekly` is idempotent across all 220 tables (ON CONFLICT DO NOTHING or 
codex-spec-consult-r1.md:20:migrations is unwieldy for review | Plan v1 decides: 1-per-tier OR batched migration (e.g., 1 migration per 25 
codex-spec-consult-r1.md:22:C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\charter.md:77:| R2 | RNP2 + RPRDPP0 
codex-spec-consult-r1.md:25:C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\charter.md:82:| R7 | MTL schema 
codex-spec-consult-r1.md:26:accidentally activates (data ingest fires when it shouldn't) | Config flag `fdb_load_mtl=False` enforced via 
codex-spec-consult-r1.md:27:integration test; CI gate denies MTL data on default flag |
codex-spec-consult-r1.md:41:1. **HIGH — B9 is too large for a single final GATE-CLOSE.**  
codex-spec-consult-r1.md:42:   D4 can remain “single B9 milestone,” but B9.B through B9.F need their own closure gates with evidence, row-count reconciliation, migration review, FDW verify, and test baseline comparison. A single final review across 220 tables will be too late to catch structural drift.
codex-spec-consult-r1.md:45:   C0 should include: free disk + projected table/index bloat, timed full-load dry run for `RNP2_NDC_PRICE` and `RPRDPP0_PRODUCT_PRICE`, weekly delta/idempotency timing, representative `EXPLAIN ANALYZE`, and Postgres/FDW verify after indexes. “Disk free + pg_stat_user_tables monitoring” is not enough for reversing the Phase 09 1.16 GB deferral.
codex-spec-consult-r1.md:48:   The charter says recon’s 34-session estimate was “Tier A only,” but recon estimates ~34 sessions for A+B+C excluding Tier D, and ~39 sessions with review overhead. If B9 is now 100 sessions, that may be valid conservatism, but the charter needs a corrected explanation.
codex-spec-consult-r1.md:50:4. **MEDIUM — MTL schema-only needs stronger wording, but not config-gated Alembic.**  
codex-spec-consult-r1.md:51:   Schema migrations should not be config-gated if landing schema is the explicit decision. The guard should be in loader registration and runtime config: MTL tables excluded from default load scopes, `fdb_load_mtl=False` default, explicit opt-in required, and integration tests assert zero MTL rows after default `load_fdb.py --mode fdb_weekly`.
codex-spec-consult-r1.md:53:5. **MEDIUM — Migration granularity should be constrained at SPEC.**  
codex-spec-consult-r1.md:54:   Deferring entirely to plan v1 is too loose. SPEC should mandate no one-table-per-migration and no single 217-table migration. Recommended: per phase/batch migrations, with RNDC14 dedicated or isolated inside Tier C due to 68-column review complexity.
codex-spec-consult-r1.md:57:   Do not require bespoke per-table tests for 217 tables. Do require generated/contract coverage for every `TableSpec`, schema/model parity for every table, row-count reconciliation for every loaded table, sampled behavioral tests per tier, and dedicated Tier C tests for RNDC14/pricing/weekly delta.
codex-spec-consult-r1.md:64:The 7-phase split is the right internal shape if D4 remains locked. Tiering by complexity is coherent, and B9.E correctly isolates RNDC14 plus the two large pricing tables.
codex-spec-consult-r1.md:66:D1 is cleanly stated. Full RNDC14 ingest avoids repeated schema churn.
codex-spec-consult-r1.md:68:D3’s licensing boundary is directionally right: MTL schema can land while data load remains disabled.
codex-spec-consult-r1.md:76:Revise charter v2 before PLAN. Required fixes: correct the recon/session-count contradiction, add a D2 performance gate, make per-phase closure gates mandatory, strengthen MTL loader safeguards, and lock migration granularity constraints at SPEC level. After that, proceed to PLAN v1.
codex-spec-consult-r1.md:85:1. **HIGH — B9 is too large for a single final GATE-CLOSE.**  
codex-spec-consult-r1.md:86:   D4 can remain “single B9 milestone,” but B9.B through B9.F need their own closure gates with evidence, row-count reconciliation, migration review, FDW verify, and test baseline comparison. A single final review across 220 tables will be too late to catch structural drift.
codex-spec-consult-r1.md:89:   C0 should include: free disk + projected table/index bloat, timed full-load dry run for `RNP2_NDC_PRICE` and `RPRDPP0_PRODUCT_PRICE`, weekly delta/idempotency timing, representative `EXPLAIN ANALYZE`, and Postgres/FDW verify after indexes. “Disk free + pg_stat_user_tables monitoring” is not enough for reversing the Phase 09 1.16 GB deferral.
codex-spec-consult-r1.md:92:   The charter says recon’s 34-session estimate was “Tier A only,” but recon estimates ~34 sessions for A+B+C excluding Tier D, and ~39 sessions with review overhead. If B9 is now 100 sessions, that may be valid conservatism, but the charter needs a corrected explanation.
codex-spec-consult-r1.md:94:4. **MEDIUM — MTL schema-only needs stronger wording, but not config-gated Alembic.**  
codex-spec-consult-r1.md:95:   Schema migrations should not be config-gated if landing schema is the explicit decision. The guard should be in loader registration and runtime config: MTL tables excluded from default load scopes, `fdb_load_mtl=False` default, explicit opt-in required, and integration tests assert zero MTL rows after default `load_fdb.py --mode fdb_weekly`.
codex-spec-consult-r1.md:97:5. **MEDIUM — Migration granularity should be constrained at SPEC.**  
codex-spec-consult-r1.md:98:   Deferring entirely to plan v1 is too loose. SPEC should mandate no one-table-per-migration and no single 217-table migration. Recommended: per phase/batch migrations, with RNDC14 dedicated or isolated inside Tier C due to 68-column review complexity.
codex-spec-consult-r1.md:101:   Do not require bespoke per-table tests for 217 tables. Do require generated/contract coverage for every `TableSpec`, schema/model parity for every table, row-count reconciliation for every loaded table, sampled behavioral tests per tier, and dedicated Tier C tests for RNDC14/pricing/weekly delta.
codex-spec-consult-r1.md:108:The 7-phase split is the right internal shape if D4 remains locked. Tiering by complexity is coherent, and B9.E correctly isolates RNDC14 plus the two large pricing tables.
codex-spec-consult-r1.md:110:D1 is cleanly stated. Full RNDC14 ingest avoids repeated schema churn.
codex-spec-consult-r1.md:112:D3’s licensing boundary is directionally right: MTL schema can land while data load remains disabled.
codex-spec-consult-r1.md:120:Revise charter v2 before PLAN. Required fixes: correct the recon/session-count contradiction, add a D2 performance gate, make per-phase closure gates mandatory, strengthen MTL loader safeguards, and lock migration granularity constraints at SPEC level. After that, proceed to PLAN v1.
recon.md:5:**Goal:** Scope FDB NDDF Plus 220-table extension beyond the 3-table Phase 09 baseline
recon.md:11:- The FDB drop contains exactly **220 data tables** in `NDDF Plus DB/NDDF PLUS DB.zip`, all with matching ANSI DDL. The current ingester covers **3 tables** (RNP3\_NDC\_PRICE, RPRDPTD0\_PRICE\_TYPE\_DESC, RNPTYPD0\_NDC\_PRICE\_TYPE\_DESC) mapped to **2 DB tables** (`fdb_ndc_price_history`, `fdb_price_type_desc`). Gap: **217 tables**.
recon.md:12:- Tables span six FDB modules: NDDF BASICS 3.0 (98 tables), MEDNAMES 3.0 (63), ETC 1.0 (16), TALL MAN PLUS 2.0 (15), XRF 1.0 (9), MTL 1.0 (19). MTL (Medical Test Lexicon) is the only module without a clear adjudication use case — treat as a product decision.
recon.md:13:- The generic `TableSpec`-driven adapter (`FDBLocalDropAdapter.parse_table`) already works for any pipe-delimited FDB table. The ingest architecture is **extension-ready**: new tables become new `TableSpec` constants + SQLAlchemy models + a migration, no adapter surgery required.
recon.md:14:- Tier classification: **113 Tier A** (simple desc/lookup), **66 Tier B** (NDC/GCN-keyed joins), **19 Tier C** (complex/large, including the 68-column NDC master and two pricing tables each >500 MB), **19 Tier D** (MTL, pending product decision). Total raw effort estimate: ~120h; with codex review cadence ~156h (~39 four-hour sessions). B9 must be phased across multiple sub-waves.
recon.md:15:- The FDW `LIMIT TO` allowlist in `setup_fdw.sh` currently names 2 FDB tables. Adding 217 more requires a structured FDW manifest expansion — this is a one-time setup change, not per-deployment.
recon.md:16:- Two Tier C tables dominate storage risk: `RNP2_NDC_PRICE` (595 MB uncompressed, 13.2M rows) and `RPRDPP0_PRODUCT_PRICE` (561 MB). Both are pricing variants already noted in the Phase 09 ingester as deferred. Ingesting them requires an explicit go/no-go decision before B9.2.
recon.md:17:- The `RNDC14_NDC_MSTR` table (68 columns, 183 MB, ~501K rows) is the platform's most valuable single gap target — it is the canonical FDB NDC master containing labeler, brand name, GCDF, route, DEA schedule, packaging, and product status fields that adjudication, formulary, and reclaimrx all need.
recon.md:21:## Section 1 — FDB drop inventory
recon.md:23:**Drop location:** `data/reference/fdb/TEL251759D/`
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
recon.md:66:| RNDC14\_NDC\_MSTR | 68 | 183 MB | NDC, labeler, GCN, brand, DEA, packaging |
recon.md:67:| RNP2\_NDC\_PRICE | 4 | 595 MB | NDC, price\_type, effective\_date, price |
recon.md:68:| RPRDPP0\_PRODUCT\_PRICE | 7 | 561 MB | product, price\_type, effective\_date, price, currency |
recon.md:70:| RETCTBL0\_ETC\_ID | 12 | 348 KB | ETC\_ID, name, leaf flag, parent, hierarchy level |
recon.md:71:| RMTLLAB0\_LAB\_ID | 5 | 6 KB | LAB\_ID, description, analyte, specimen, type |
recon.md:74:**RECORD\_COUNTS.TXT:** Present, contains row count for every table name in the drop (verified counts align with zip). Example: `RNPALL|013213617` (all pricing rows), `RNDC14_NDC_MSTR` implied by `RNDCALL|000501107`.
recon.md:80:**Python files covering FDB:**
recon.md:84:| `modules/drug-database/drug_database/services/fdb_adapter.py` | Generic adapter + 4 TableSpec constants |
recon.md:85:| `modules/drug-database/drug_database/services/fdb_pricing.py` | Point-in-time pricing lookup (SWP/SWD/WAC) |
recon.md:86:| `modules/drug-database/drug_database/services/fdb_pricing_ingester.py` | Orchestration: price\_type\_desc + RNP3 ingest |
recon.md:87:| `modules/drug-database/drug_database/models/fdb_pricing_tables.py` | 2 ORM models |
recon.md:88:| `modules/drug-database/alembic/versions/0008_fdb_pricing.py` | 1 migration covering 2 tables |
recon.md:89:| `scripts/load_fdb.py` | CLI entry point (registered in run\_reference\_loaders.sh) |
recon.md:91:**Currently ingested FDB tables → DB tables:**
recon.md:93:| FDB Table | DB Table | Notes |
recon.md:95:| RNP3\_NDC\_PRICE | `drug_database.fdb_ndc_price_history` | 13.2M rows; append-only, A/C/D UPD semantics |
recon.md:96:| RPRDPTD0\_PRICE\_TYPE\_DESC | `drug_database.fdb_price_type_desc` | 20 rows; modern catalog |
recon.md:97:| RNPTYPD0\_NDC\_PRICE\_TYPE\_DESC | `drug_database.fdb_price_type_desc` | 21 rows; legacy codes with synthetic IDs |
recon.md:99:**Coverage gap: 217 of 220 FDB tables have no DB mapping.**
recon.md:103:| FDB Table | Cols | Rows (RECORD\_COUNTS) | Business value |
recon.md:105:| RNDC14\_NDC\_MSTR | 68 | ~501K | NDC master — labeler, brand, GCN, route, DEA, packaging |
recon.md:114:**FDW manifest impact:** `setup_fdw.sh` uses `IMPORT FOREIGN SCHEMA ... LIMIT TO (...)` with a dynamic list. Currently 2 FDB table names are in scope for drug\_database. B9 full coverage would expand this list by 217 entries.
recon.md:123:- **Tier C** — Complex tables: > 8 columns, or large pricing tables (> 50 MB), or key structural masters (RNDC14 at 68 cols). Require careful column mapping, money-path review (financial-precision.md), or parent-key join design with existing ingested tables.
recon.md:124:- **Tier D** — Medical Test Lexicon (MTL 1.0). 19 tables covering lab analytes, panels, specimen IDs. Structurally simple (most are tiny) but the business question — do adjudication rules need lab linkage? — must be answered before ingest design begins.
recon.md:130:| C — Complex/large | 19 | 90 min | 28.5h | RNDC14 (68 cols), two 500 MB+ pricing tables, ETC master |
recon.md:131:| D — MTL (product decision) | 19 | 30 min | 9.5h | Small tables, pending go/no-go |
recon.md:138:| RNDC14\_NDC\_MSTR | 68 | 183 MB | Highest value; complex column mapping |
recon.md:139:| RNP2\_NDC\_PRICE | 4 | 595 MB | Pricing variant; go/no-go needed (Phase 09 deferred) |
recon.md:140:| RPRDPP0\_PRODUCT\_PRICE | 7 | 561 MB | Product-level pricing; Phase 09 deferred |
recon.md:141:| RPRD0\_PRODUCT | 7 | 32 MB | Product master; load before RNDC14 |
recon.md:147:| RETCTBL0\_ETC\_ID | 12 | 348 KB | ETC hierarchy master |
recon.md:166:| A — One big migration | All 217 tables in `0009_fdb_full.py` | REJECTED — one migration failure blocks everything; impossible to review |
recon.md:167:| B — One migration per tier | 4 migrations (0009–0012) | Reasonable for small projects; still 66+ models per migration |
recon.md:168:| C — One migration per table | 217 migrations | Too many migration files; untenable maintenance |
recon.md:169:| D — Tiered phasing with batch migrations | One migration per sub-wave (B9.1 = Tier A, B9.2 = Tier B, B9.3 = Tier C) | RECOMMENDED |
recon.md:171:**Recommendation: Option D — Tiered phasing with batch migrations.**
recon.md:173:- `0009_fdb_tier_a.py` — 113 Tier A tables (all small; one migration is reviewable because models are uniform 2–5-col descriptors)
recon.md:174:- `0010_fdb_tier_b.py` — 66 Tier B tables (NDC/GCN-keyed)
recon.md:175:- `0011_fdb_tier_c.py` — 19 Tier C tables (but RNDC14 should be its own migration `0011a` given 68-col complexity)
recon.md:176:- `0012_fdb_tier_d.py` — 19 MTL tables (only if product go decision is made)
recon.md:179:- Each migration maps to a sub-wave gate. If B9.2 fails QA, B9.1 is already in prod.
recon.md:180:- Tier A tables are structurally uniform (code/desc pattern); 113 in one migration is reviewable.
recon.md:181:- Tier C needs its own slot because `RNDC14_NDC_MSTR` at 68 columns is a significant schema decision that may require discussion about which columns to retain vs. drop (storage vs. value tradeoff).
recon.md:193:| F — Per-table service | One `fdb_<table>_ingester.py` per table, matching Phase 09 pattern | Appropriate for Tier C tables with complex logic |
recon.md:199:The existing `TableSpec` dataclass + `FDBLocalDropAdapter.parse_table` already provides a generic parse-any-table capability. The only missing piece is:
recon.md:200:1. A `TableSpec` registry (a Python dict: `table_name → TableSpec`) in `fdb_adapter.py`
recon.md:201:2. A generic `FDBBulkIngester` that iterates the registry, calling `parse_table` + bulk upsert for each
recon.md:208:- `RNDC14_NDC_MSTR` (68 cols): requires explicit column-selection decision, NDC normalization, money column handling (price-related fields), and a dedicated EXPLAIN ANALYZE runbook
recon.md:209:- `RNP2_NDC_PRICE` and `RPRDPP0_PRODUCT_PRICE`: pricing tables need go/no-go decision and Decimal handling audit (financial-precision.md)
recon.md:212:**For Tier D (MTL):**
recon.md:213:MTL tables are tiny (total uncompressed: ~103 KB). If the product decision is "yes", they fit cleanly into the generic ingester. If "no", skip entirely. No architectural complexity.
recon.md:239:- B9.4 (Tier D, MTL — if go): ~3 sessions
recon.md:241:**Total: ~34 sessions** (excluding Tier D). This is a multi-month effort at 2–3 sessions/week.
recon.md:249:**Risk 1 — RNDC14\_NDC\_MSTR column explosion (HIGH)**
recon.md:250:The NDC master has 68 columns, many of which are FDB-internal flags with unclear business relevance. Without column curation, the DB table will be bloated and the ORM model unwieldy. Risk: table design gets revisited post-ingest, requiring a costly migration. Mitigation: Before B9.3, produce a column-by-column triage (keep / drop / defer) based on adjudication, formulary, and reclaimrx requirements.
recon.md:253:`RNP2_NDC_PRICE` (595 MB, 13.2M rows legacy pricing) and `RPRDPP0_PRODUCT_PRICE` (561 MB) were explicitly deferred in Phase 09 (`fdb_load_product_prices=False` config flag). Loading both adds ~1.1 GB uncompressed to the reference DB weekly. Risk: storage growth and ingest window extension. Mitigation: Decide at B9.3 charter whether these are in scope. If yes, add dedicated EXPLAIN ANALYZE runbook.
recon.md:256:`setup_fdw.sh` uses a dynamic `LIMIT TO` allowlist. Adding 217 table names to this list is a one-time change, but the list must stay in sync with the actual schema. If a new FDB drop adds tables, the FDW will silently omit them. Mitigation: Auto-generate the LIMIT TO list from the ORM `metadata.tables` at setup time rather than maintaining a manual list.
recon.md:259:Current FDB ingest: RNP3 (13.2M rows) takes ~minutes. Adding 217 tables including NDC master (501K rows), ETC NDC mapping (616K rows), and MedName tables adds significant volume to the weekly UPD cycle. The UPD zip must also be verified to contain all tables (not just pricing). Mitigation: Profile UPD zip contents against DB zip contents. Validate that `NDDF Plus UPD/` has a matching file for each table before committing to weekly ingest for all 220.
recon.md:262:The current adapter only reads from UPD for RNP3 (pricing). Some FDB reference tables (e.g., description tables) may ship full-replacement in UPD rather than A/C/D delta. Mitigation: Inspect the UPD zip structure early in B9.1. If some tables are full-replacement (no A/C/D prefix), the ingester must detect this and use TRUNCATE+INSERT rather than ON CONFLICT DO NOTHING.
recon.md:265:The existing adapter handles latin-1 decoding for RNP3 (numeric-heavy). Text-heavy tables (drug names, descriptions, brand names) are more likely to have characters in the latin-1 extended range (0x80–0xFF). Mitigation: Audit the first 1000 rows of text-column tables (RMIID1\_MED, RNDC14\_NDC\_MSTR brand fields) for decoding failures before schema finalization.
recon.md:268:At 217 new models, the per-test `create_all()` time in SQLite fixtures will grow. Currently 2 FDB models; adding 217 means each test session creates 219 tables. Risk: slow CI. Mitigation: Split the `FDBPricingBase` into module-level declarative bases (`FDBBasicsBase`, `FDBMedNamesBase`, etc.) so tests only create\_all for the module under test. Plan this in B9.0 before any model files are written.
recon.md:276:- Charter v1: column triage for RNDC14, pricing table go/no-go decision, MTL go/no-go decision
recon.md:277:- Design the `FDBBulkIngester` (generic ingester for Tier A+B) — implementation-ready spec
recon.md:284:- Implement `FDBBulkIngester` generic infrastructure (~200 lines)
recon.md:285:- Add 113 `TableSpec` entries to registry in `fdb_adapter.py`
recon.md:286:- One alembic migration `0009_fdb_tier_a.py`
recon.md:287:- 113 ORM model classes in `fdb_lookup_tables.py` (batched by module)
recon.md:295:- Migration `0010_fdb_tier_b.py`
recon.md:296:- ORM models in `fdb_link_tables.py`
recon.md:298:- Integration test: verify NDC join correctness against existing `fdb_ndc_price_history`
recon.md:304:- Pre-work: RNDC14 column triage document (owner sign-off required before coding)
recon.md:305:- Pricing table go/no-go confirmation (RNP2, RPRDPP0)
recon.md:306:- One migration per Tier C table (or `0011_fdb_tier_c.py` + `0011a_fdb_ndc_master.py` for RNDC14 separately)
recon.md:308:- EXPLAIN ANALYZE runbook for RNDC14 and any table > 10M rows
recon.md:312:### B9.4 — Tier D: MTL (19 tables) — CONDITIONAL on product decision
recon.md:315:- All 19 MTL tables are tiny (total 103 KB) — one session if go decision is made
recon.md:316:- Migration `0012_fdb_tier_d.py`, generic ingester handles all 19
recon.md:322:1. **RNDC14\_NDC\_MSTR column triage**: Which of the 68 columns does InfinityRx actually need? Full 68-column ingest vs. curated subset has significant implications for model maintainability and storage. Required before B9.3 begins.
recon.md:324:2. **Pricing table go/no-go (RNP2 + RPRDPP0)**: Both were explicitly deferred in Phase 09. RNP2 is the legacy pricing file (overlaps with RNP3 data); RPRDPP0 is product-level pricing (vs. RNP3's NDC-level). Decision needed: are either of these required for adjudication accuracy, or is RNP3 sufficient?
recon.md:326:3. **MTL go/no-go**: Does any planned adjudication rule or reclaimrx detection require lab test linkage (NDDF MTL 1.0)? If yes, B9.4 is in scope. If no, all 19 MTL tables are permanently skipped.
recon.md:328:4. **Wave boundary — is B9 one wave or two?**: 34 sessions is 3–4 months. Consider splitting at the Tier A/B boundary: B9 = Tier A (113 tables, ~10 sessions, quick wins), B10 = Tier B+C (85 tables, ~20 sessions, full coverage). This gives a shippable milestone in ~6 weeks rather than waiting 4 months for the full wave.

codex
## SPEC R2 GATE VERDICT

GO-WITH-FIXES

## R1 concern verification

| # | R1 fix | Verified in v2? | Evidence (charter line ref) | Notes |
|---|---|---|---|---|
| 1 | Per-phase gates | YES | charter.md:44, 49-55, 69, 106 | Mandatory mini-GATE-CLOSE gates are specified for B9.B..B9.G with evidence, reconciliation, migration review, FDW verify, test baseline comparison, and phase-specific criteria. |
| 2 | D2 perf gate | YES | charter.md:19, 53, 64, 86 | C0/B9.F now requires timed full-load dry run, `EXPLAIN ANALYZE`, FDW/Postgres verify, storage budget verification, and weekly delta timing. |
| 3 | Effort model | PARTIAL | charter.md:21, 33, 102, 106 | The 100-session error is corrected to ~39 sessions at lines 33 and 102, consistent with recon. But D4 still says “~34 four-hour sessions elapsed; ~6 months wall-clock” at line 21, which conflicts with the corrected 13-week / 4-5 month framing and uses “elapsed” incorrectly. |
| 4 | MTL guards | YES | charter.md:20, 54, 65, 91 | Schema-only is preserved; Alembic is explicitly not config-gated; loader/runtime guards and zero-row integration/CI checks are required. |
| 5 | Migration granularity | YES | charter.md:73-79, 85 | SPEC locks no one-table-per-migration, no single mega-migration, per-phase batched migrations, and standalone RNDC14. |
| 6 | Test strategy | YES | charter.md:49-54, 64-69 | Contract, parity, reconciliation, sampled behavioral, and dedicated Tier C tests are specified; bespoke per-table behavioral tests are explicitly rejected. |

## New concerns surfaced in v2 (if any)

- LOW/MEDIUM — Stale D4 effort/wall-clock text remains at charter.md:21. It conflicts with the corrected effort model at charter.md:33 and charter.md:102. This is likely a copy-forward artifact, but SPEC should not advance with contradictory schedule language in a locked decision row.

## Vendor-name sanity check

PASS. Grep evidence shows consistent use of `FDB` / `NDDF Plus` / `NDDF`; no `FirstDataBank` casing issue surfaced in the checked B9 docs. Relevant lines include charter.md:1, charter.md:12, recon.md:5, recon.md:11, recon.md:21, recon.md:35-36.

## Final verdict + next action

GO-WITH-FIXES. v2 substantively addresses R1 concerns #1, #2, #4, #5, and #6. The only blocker is the stale D4 row at charter.md:21: replace “~34 four-hour sessions elapsed; ~6 months wall-clock” with language consistent with the corrected model, e.g. “~39 four-hour sessions planned; ~13 weeks at 3 sessions/week, realistically 4-5 months with multitasking.” After that cleanup, proceed to PLAN v1 codex consult.
tokens used
28,617
## SPEC R2 GATE VERDICT

GO-WITH-FIXES

## R1 concern verification

| # | R1 fix | Verified in v2? | Evidence (charter line ref) | Notes |
|---|---|---|---|---|
| 1 | Per-phase gates | YES | charter.md:44, 49-55, 69, 106 | Mandatory mini-GATE-CLOSE gates are specified for B9.B..B9.G with evidence, reconciliation, migration review, FDW verify, test baseline comparison, and phase-specific criteria. |
| 2 | D2 perf gate | YES | charter.md:19, 53, 64, 86 | C0/B9.F now requires timed full-load dry run, `EXPLAIN ANALYZE`, FDW/Postgres verify, storage budget verification, and weekly delta timing. |
| 3 | Effort model | PARTIAL | charter.md:21, 33, 102, 106 | The 100-session error is corrected to ~39 sessions at lines 33 and 102, consistent with recon. But D4 still says “~34 four-hour sessions elapsed; ~6 months wall-clock” at line 21, which conflicts with the corrected 13-week / 4-5 month framing and uses “elapsed” incorrectly. |
| 4 | MTL guards | YES | charter.md:20, 54, 65, 91 | Schema-only is preserved; Alembic is explicitly not config-gated; loader/runtime guards and zero-row integration/CI checks are required. |
| 5 | Migration granularity | YES | charter.md:73-79, 85 | SPEC locks no one-table-per-migration, no single mega-migration, per-phase batched migrations, and standalone RNDC14. |
| 6 | Test strategy | YES | charter.md:49-54, 64-69 | Contract, parity, reconciliation, sampled behavioral, and dedicated Tier C tests are specified; bespoke per-table behavioral tests are explicitly rejected. |

## New concerns surfaced in v2 (if any)

- LOW/MEDIUM — Stale D4 effort/wall-clock text remains at charter.md:21. It conflicts with the corrected effort model at charter.md:33 and charter.md:102. This is likely a copy-forward artifact, but SPEC should not advance with contradictory schedule language in a locked decision row.

## Vendor-name sanity check

PASS. Grep evidence shows consistent use of `FDB` / `NDDF Plus` / `NDDF`; no `FirstDataBank` casing issue surfaced in the checked B9 docs. Relevant lines include charter.md:1, charter.md:12, recon.md:5, recon.md:11, recon.md:21, recon.md:35-36.

## Final verdict + next action

GO-WITH-FIXES. v2 substantively addresses R1 concerns #1, #2, #4, #5, and #6. The only blocker is the stale D4 row at charter.md:21: replace “~34 four-hour sessions elapsed; ~6 months wall-clock” with language consistent with the corrected model, e.g. “~39 four-hour sessions planned; ~13 weeks at 3 sessions/week, realistically 4-5 months with multitasking.” After that cleanup, proceed to PLAN v1 codex consult.
