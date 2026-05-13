# Wave History Index

Each wave's full summary lives in `docs/audit/wave-N-final-summary.md`
or a named audit doc. Pre-Wave-41.5 verbose narrative preserved at
`docs/audit/CLAUDE_archive_pre_wave_42.md`.

| Wave | Date | Scope |
|------|------|-------|
| Audit baseline | 2026-04-14 | `full-platform-audit-2026-04-14.md` — score 63/100 |
| W1 remediation | 2026-04-14 | `wave1-remediation-report.md` — score 76/100 |
| W2-W3 remediation | 2026-04-14 | `wave2-3-remediation-report.md` — score ~85/100 |
| Production hardening | 2026-04-14 | `production-hardening-report.md` — score ~90/100 |
| Wave 8 | (NCPDP) | DataQ NCPDP monthly ZIP feed |
| Wave 19 | (ai-nlp) | Schema + pgvector + monthly partitioning |
| Wave 20 | RLS | DB-level tenant isolation across 50 tables |
| Wave 24 | (reporting) | Schema + 10-table baseline |
| Wave 26 | C.1–C.26 | BRD rule catalog completion 19/19 + Phase C foundation |
| Wave 26 NCPDP | C.7-NCPDP-* | AM05 COB fix, AM07 SCC, Layer 1 ordered-view |
| Wave 27 | hardening | rule_instance_seeding helper, TIN/UEI ingest, TCP listener, change-set API |
| Wave 28 | followups | SAM.gov audit, NCPDP roster CSV, TCP TLS+metrics, registry deprecation |
| Wave 29 | DataQ | Monthly ZIP ingester (1.08M rows / 60s), 13-table schema |
| Wave 30 | DataQ spec + members | Spec-canonical re-ingest + canonical member identity layer |
| Wave 31 A+B | hardening | Load tests, observability, security audit, schema tightening |
| Wave 32 | NCPDP audit | 18 transaction codes, 29 segments, ~250 fields, 1,228 reject codes |
| Wave 33 | RelayHealth | Real wire-pair conformance: 8 fixtures, segment-ID rotation fix |
| Wave 34 | BRD audit | 28 client BRDs sanitized + extracted; rule catalog corpus-complete |
| Wave 35 | paysync foundation | 7-table schema + claims ingester + NRID router + cycle manager |
| Wave 36 | network-mgmt | 8-table schema + pay-to waterfall + AES-256-GCM banking |
| Wave 37 | NACHA + 835 | Payment batch + 835 EDI generation + admin API |
| Wave 38 | invoicing | 11 tables: invoice numbering, fee schedules, exports, email |
| Wave 39 | recon + carryovers | Cycle close orchestrator, 3-way reconciliation, bank settlement |
| Wave 40 | portal UI | PaySync + network-mgmt operator UI end-to-end |
| Wave 41 | Echo | Spec 400 generation + Payment Status File ingestion |
| Wave 41.5 | cleanup | CLAUDE.md restructure + structural review |
| Wave 41.5b | discipline + audit | Discipline foundations, tooling install, AEGIS deep audit, refactor roadmap |
| Wave 41.6 | consolidations + validation | paysync 835 conformance fix + edi-compliance retirement + local-dev seed + validation CLI/runbook + float-regression guard; see `docs/audit/wave-41-6-final-summary.md` |
| Wave 41.7 | real-bugs cleanup | UTC drift fix (4 active + 17 latent), listener perf 10s→<0.2s, ai-nlp session audit, utcnow sweep + lint guard, portal money inventory (91 components / 37 money-handling), tenant_type enum closed, DLQ alert path (LogAlertChannel + monitor), PHI Cache-Control + 4 data-path audits (J3a–d), N+1 fixture audit, feature-flag inventory; orchestration discipline codified (Rule 1 addendum + Rule 4 sub-clause + Rules 6/7) + J2 SchemaError discovery; see `docs/audit/wave-41-7-final-summary.md` |
| W41.7 werkbench | 2026-04-29 | Werkbench v1.0.0 framework | 27 Werkbench files (README + INVENTORY + universe + reconciliation + glossary + 4 evaluation + 3 disciplines + 9 integration + 4 lifecycle + queries/runbook + multica candidate) + CLAUDE.md updates (230 lines, item 11 added) + RTK install + orchestration-rules Rule 6 sub-rule + graphify hook matcher fix; 4 Tier 1 findings (markdown not in graph; claude-mem decision-tagging gap; graphify --force bug; CLAUDE.md ceiling met). X6 deferred to W41.7.werkbench-trial. See `docs/audit/wave-41-7-werkbench-final-summary.md` |
| Wave 42 | reclaimrx foundation | Hierarchy resolver + 3 ingest entry points + anomaly/case workflow |
| Wave 43 | reclaimrx rules | 25 deterministic detection rule types across 6 BRD families |
| Wave 44a | maxacc-registry | Global reference-data substrate for patient-assistance manipulation |
| Wave 44b | reclaimrx ML | (in progress) ML detection layer |
| W41.7.werkbench-discipline | 2026-04-29 | Codification of 9 discipline learnings from W41.7.werkbench post-close + recovery from initial-dispatch watchdog termination | fa32706 |
| W41.7.werkbench-trial | 2026-04-30 | Four-phase superpowers wave flow validation via R12 lint rule. SR-1/2/3 validated, SR-4 not exercised, SR-5/6 N/A; 2 real boundary violations caught and fixed; 4 W41.8 followups (H5–H8). See `docs/audit/wave-41-7-werkbench-trial-summary.md` | b1243fe |
| W41.8 | 2026-05-01 | graphify hygiene — SessionStart-triggered markdown ingestion via `/graphify --mode deep` (30-min stamp-file debounce); staged backfill (Werkbench/ → full S3, 928 markdown nodes ingested into 29,718-node graph, $11.96 cumulative cost); graphifyy 0.5.7 upgrade; graphify-surface.md doc fix; tool automation map (closes H3); H1/H2/H4 closed. See `docs/audit/wave-41-8-final-summary.md` | 26f8afd |
| Wave B8 | 2026-05-10 | Phase 11B carryovers — F1: drug-database `src/`→`drug_database/` rename (25 consumer files, 30 import lines, `type:ignore` shims dropped); F2: `tcp_listener._process` publishes `claim.adjudicated` mirroring `admin_routes.py:inject_claim` (enriched FDB pricing fields, txn_id in failure log); integration test via InMemoryEventBus capture (2 tests, always-run). Codex: SPEC 2 rounds (NO→GO-WITH-FIXES), PLAN 1 round (GO-WITH-FIXES), ADVERSARIAL skipped (mechanical wave), GATE-CLOSE 1 round. |
| Wave B7.1 | 2026-05-10 | B7+B8 cleanup wave: W2 `setup_fdw.sh --verify` net-new (66/66 PASS dev+mock, closes B7 C9 Phase 2) + SELECT grant on reference foreign tables (round-2 fix); W3 Tier 1 env-drive `ifx_prod_app` in 15 RLS-policy migrations across 9 modules (`init-multi-db.sql` preserved; DROP blocked by `pg_shdepend` 31 dependents → B7.1.1; Tier 2 GRANTs deferred); W4 hygiene bundle (12 loader rc propagation, OFAC CRLF fix, .sh chmod, gitignore patterns); W1 NPPES status doc (~4.9M < 7M target → B7.1.1). **13 commits, `7e9e1ff..e30fdfb`.** SC-2/4/5/6/7/9 PASS, SC-1/SC-3 PARTIAL, SC-8 GO-WITH-FIXES (codex 2 rounds: real SELECT-grant gap fixed; 3 false positives dismissed — Tier 2 GRANTs, claude-mem pattern, wave-history timing). |
| Wave B7.1.1 | 2026-05-10 | Phase 11A residual closure: SC-1 NPPES CLOSED (live count 9,494,438 ≥ 7M; B7.1's "in-flight ingest killed" claim was actually complete); SC-2 Tier 1 cluster cleanup — 17 core schema RLS policies re-targeted (ALTER POLICY to drop `ifx_prod_app` from TO clause; 31 → 14 dependents remaining, all Tier 2). Script preserved at `infrastructure/scripts/lib/cleanup_tier1_ifx_prod_app_policies.sql`. Tier 2 GRANT-only (14 pharmacy_dir GRANTs) + final DROP ROLE deferred to architectural wave per codex SPEC #7. **4 commits, `4ce70d0..552b67d`.** Discipline reductions: SPEC/PLAN/ADVERSARIAL skipped (2 surgical SCs); GATE-CLOSE retained. **Phase 11A essentially complete; only Tier 2 architectural wave remains.** |
| Wave B8.1.1 | 2026-05-11 | **B8.1 smoke blockers closed.** W1: `adjudication_result_to_bytes()` now calls `to_raw_transaction()` on typed Transaction before passing to `serialize_raw_segments_to_bytes()` — eliminates `AttributeError` / `internal_errors` / 28-byte reject-frame fallback for paid claims; pharmacy switch now receives 120-byte full NCPDP D.0 paid response. W2: `switch_env.sh` exports `IFX_APP_ROLE` per env (dev=ifx_dev_app, mock=ifx_mock_app, prod=ifx_prod_app) — fixes fresh-cluster `alembic upgrade head` GRANT failure without touching `init-multi-db.sql`. 2 unit regression tests added (22/22 pass). Smoke 8/8 PASS. **2 commits, `87c3721..6198e55`.** SC-1..SC-6 PASS. Codex gate-close: GO. |
| Wave B7.2 | 2026-05-10 | **Phase 11A COMPLETE.** Tier 2 architectural GRANT wave: W1 env-drive `ifx_prod_app` in 26 files (25 Tier 2 migrations + `scripts/apply_rls.py`) via `IFX_APP_ROLE`; W2 remove `ifx_prod_app` key from both `_ROLE_PAIRS` dicts (`maxacc_registry_routes.py` + `test_helpers.py`); W3 REVOKE 14 `pharmacy_dir.dataq_*` cluster GRANTs from `ifx_prod_app` + re-GRANT to `ifx_dev_app` (`pg_shdepend = 0`; `setup_fdw.sh --verify` 66/66 PASS); W4 `DROP ROLE ifx_prod_app` (`pg_authid count = 0`). 8-suite test verification: all 8 suites match C0 baseline (no regressions). Script preserved at `infrastructure/scripts/lib/cleanup_tier2_ifx_prod_app_grants.sql`. Wave artifacts at `waves/B7.2/`. **7 commits, `2964ebc..276fd99`.** SC-1..SC-5/SC-7 PASS. Codex: SPEC 2 rounds GO-WITH-FIXES (9 concerns); PLAN + ADVERSARIAL skipped; GATE-CLOSE: R1 NO-GO (artifacts not in repo) → R2 GO-WITH-FIXES → GO (C9 placeholder fill). Deferred: `tests/integration/conftest.py:149` + `shared/config.py:159` (charter v3 explicit, non-load-bearing). `ifx_prod_app` gone from live cluster + all GRANT targets + both runtime dicts. |
