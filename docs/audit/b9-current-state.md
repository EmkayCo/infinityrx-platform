# B9 Current State — Discovery Report

**Date:** 2026-05-16
**Branch:** wave/B10-w5-b9-partial
**Purpose:** Pre-work audit before B9.C scaffolding. Answers the five
discovery questions from the session brief.

---

## 1. What does B9.A cover? (CLOSED)

B9.A was the meta-phase: charter locking, plan authoring, codex consults,
and cross-cutting infrastructure that all subsequent phases consume.

Delivered (C0–C14 across 3-4 sessions):

- `TableSpec` registry expansion (`Tier`, `DeltaSemantics`, `natural_key`,
  `loader_group`, `record_counts_key` fields)
- Migration generator (`scripts/gen_fdb_tier_migration.py`)
- Ingester contract test template (`tests/_fdb_contract.py`, 6 helpers)
- MTL config flag + DB-level REVOKE template
  (`infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl`)
- `setup_fdw.sh --verify` manifest-derived count (replaces hard-coded 66)
- FDW name-collision preflight script
  (`infrastructure/scripts/preflight_b9_name_collision.py`)
- Phase 09 compat baseline (`waves/B9/phase09_compat_baseline.md`)
- `DELTA_SEMANTICS` contract test + A/C/D/re-A simulation
- Write-path guard (reference DB assertion before any write)
- All wave artifacts mirrored into repo (codex consult ladder)

Gate-close: 3 rounds (R1 GO-WITH-FIXES → R2 GO-WITH-FIXES → R3 GO-WITH-FIXES),
all fixes absorbed. B9.A CLOSED.

---

## 2. What does B9.B cover? (CLOSED — unit-tests-only gate)

B9.B ingested all 107 Tier A FDB NDDF Plus tables (simple lookup/descriptor
tables, ≤ 5 columns, no FK joins beyond Phase 09).

**Delivered:**

- 11 batch files (`fdb_tier_a/batch_01.py`–`batch_11.py`) — 107 `TableSpec`
  definitions
- `fdb_tier_loader.py` — generic Tier A loader, `--mode fdb_tier_a` wired
- `alembic/versions/0009_fdb_tier_a.py` — 1,327-line migration with
  99 `PrimaryKeyConstraint` + 8 `UniqueConstraint` + 1 `Numeric(16,6)`
- `expected_reference_tables.txt` — 131 entries (24 pre-B9 + 107 new);
  B9.B header section at line 128
- 787 unit tests green (no regressions)

**Gate-close:** 3 rounds (R1→R2→R3). GO at R3. B9.B CLOSED.

**MEDIUM 3 carried forward:** Live-DB evidence (FDW verify 173/173,
migration up/down/up, row-count reconciliation against `RECORD_COUNTS.TXT`)
was explicitly deferred. See §3 below for what is and is not written.

**Scope note:** B9.B closes at 107 tables (not 113 as originally chartered).
6 NDC/GCN/MEDID-keyed tables were reclassified from Tier A to Tier B during
execution. B9.C therefore covers 72 tables (66 originally planned + 6
reclassified from B9.B).

---

## 3. B9.B deferred live-DB validation — are scripts written?

**Finding: The scripts ARE NOT written as standalone runnable artifacts.**

What exists:

| Artifact | Status |
|---|---|
| `setup_fdw.sh --verify` | EXISTS — runs manifest-driven FDW check; requires Docker+live DB; would correctly run against 131-entry manifest right now |
| Migration `0009_fdb_tier_a.py` | EXISTS — the actual migration file; requires `alembic upgrade/downgrade/upgrade` run against live Postgres |
| `tests/integration/test_fdb_record_counts_real_file.py` | EXISTS — 4 tests that skip without real FDB drop on disk |
| `tests/integration/test_phase09_compat_baseline.py` | EXISTS — skips without Docker |

What is missing (needs Docker-up session to produce evidence):

1. **FDW verify 173/173 evidence** — need `setup_fdw.sh --verify` run
   producing output showing 173 PASS, 0 FAIL (currently manifest has 131
   entries; the "173" figure in the charter refers to the FDW foreign-table
   count after B9.B, which equals 131 manifest entries × each mapped to a
   foreign table). Note: 131 manifest entries vs "173 FDW tables" discrepancy
   — the 173 figure in the codex gate-close refers to the source-table count
   in `infinityrx_reference` (66 pre-B9 + 107 B9.B = 173), while the
   manifest tracks distinct table names across source schemas.
2. **Migration up/down/up evidence** — `waves/B9/B9.B-dryrun_evidence.md`
   does not exist yet; the B9.B-charter.md describes what it should contain.
3. **Row-count reconciliation** — `waves/B9/evidence.md` does not exist yet.

**Conclusion per decision tree:** B9.B's deferred scripts are NOT written
as independent artifacts — the gate requires running `setup_fdw.sh --verify`
and `alembic upgrade/downgrade/upgrade` with Docker up. This session will
document this clearly and move to B9.C scaffolding.

---

## 4. What does B9.C cover?

B9.C ingests 72 NDC/GCN-MEDID-keyed join tables — the "Tier B" set in the
NDDF Plus schema. These tables reference NDC (11-digit), GCN (Generic Code
Number), MEDID (medication identifier), HICL/HIC (Hierarchical Ingredient
Code), or GCN_SEQNO as their primary key or the dominant join axis.

**Why slower than Tier A:** Each table requires FK-target verification
(the referenced table must exist — in Phase 09 baseline or B9.B). Contract
tests extend with FK-integrity assertions.

**Alembic target:** `0010_fdb_tier_b.py` — single migration, SPEC-locked
per `plan.md`.

**FDW manifest growth:** 131 → 203 (+ 72 new entries).

**From DDL manifest analysis (221 tables total, 107 in Tier A, 1 NDDF_PRODUCT_INFO):**
The remaining 113 tables map to B9.C (72), B9.D (16 non-RNDC14 complex),
B9.E (1: RNDC14_NDC_MSTR), B9.F (2: RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE),
B9.G (19 MTL) = 113 accounted for. (72 + 16 + 1 + 2 + 19 = 110; 3 already
in Phase 09 = 113 ✓)

**Sample B9.C tables (from DDL manifest, NDC/GCN-keyed):**

| Table | Key columns | Description |
|---|---|---|
| `RETCNDC0` | NDC, ETC_ID | ETC → NDC linkage |
| `RETCGC0` | GCN_SEQNO, ETC_ID | ETC → GCN linkage |
| `RETCMED0` | MEDID, ETC_ID | ETC → MedID linkage |
| `RCQNDC0` | NDC, MEDID | Clinical quantity by NDC |
| `RCQDNDC0` | NDC | Clinical quantity dispensed by NDC |
| `RAPPLNA0` | NDC, APPL_NO | FDA NDC → application |
| `RAPPLSL0` | NDC | FDA NDC → NDA/ANDA |
| `RATCGC0` | GCN_SEQNO, ATC | ATC → GCN linkage |
| `RAHFSGC1` | GCN_SEQNO, AHFS8 | AHFS → GCN linkage |
| `RGCNSEQ4` | GCN_SEQNO | GCN sequence master |
| `RGCNSTR0` | GCN_SEQNO, HIC_SEQN | Ingredient strength |

---

## 5. What does B9.D–H cover at a high level?

| Phase | Scope | Table count | Notes |
|---|---|---|---|
| B9.D | Tier C non-RNDC14 — large/complex tables | 16 | > 8 cols or > 50 MB. ETC master, product master (RPRD0_PRODUCT), GCN master. Each gets column-curation note. Migration: `0011_fdb_tier_c_minus_rndc14.py` |
| B9.E | RNDC14_NDC_MSTR standalone | 1 | 68 columns, 183 MB, ~501K rows. Charter D1: ALL 68 columns ingested (no curation). Column-by-column codex review required. Migration: `0012_fdb_rndc14_ndc_mstr.py` |
| B9.F | RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE | 2 | 595 MB + 561 MB. D2 performance gate (HARD ABORT criteria on timing + storage). Flips `fdb_load_product_prices=True`. Migration: `0013_fdb_pricing_big.py` |
| B9.G | MTL (Medical Test Lexicon) — schema-only | 19 | Data does NOT load. Schema lands; DB-level REVOKE guard; FDW manifest NOT updated (excluded from default 264 count). Migration: `0014_fdb_mtl_schema.py` |
| B9.H | Cross-cutting closeout + consumer audits | — | FDW verify 264/264, row-count reconciliation, adjudication consumer audit, cross-tier behavioral suite, ship artifacts |

---

## B9.B Deferred Evidence — Next Docker-Up Session Checklist

When Docker is available with the FDB drop mounted:

1. Run: `setup_fdw.sh --verify --env dev` — expect 131 PASS, 0 FAIL
   (manifest reflects 107 B9.B tables + 24 pre-B9 = 131 entries)
2. Run migration roundtrip:
   ```
   alembic upgrade head
   alembic downgrade -1
   alembic upgrade head
   ```
   Capture output to `waves/B9/B9.B-dryrun_evidence.md`
3. Run: `pytest modules/drug-database/tests/integration/test_fdb_record_counts_real_file.py -v`
   (expects 4 tests green with real drop)
4. Run: `pytest modules/drug-database/tests/integration/test_phase09_compat_baseline.py -v`
   (Phase 09 compat — asserts row counts + query latency unchanged)
5. Row-count spot-check: query `RECORD_COUNTS.TXT` entries for 5 random
   Tier A tables; compare actual DB row counts (within ±0.1% tolerance)

These 5 steps close the B9.B live-DB gate and unblock B9.C to proceed with
full population (vs. schema-only) testing.

---

## State as of this session

- B9.A: CLOSED
- B9.B: CLOSED (unit tests) / OPEN (live-DB gate — Docker required)
- B9.C: NOT STARTED → scaffolding begins this session
- B9.D–H: NOT STARTED

**Immediate next work:** B9.C alembic migration scaffold (`0010_fdb_tier_b.py`),
schema-only `TableSpec` stubs for the 72 Tier B tables, and schema-structure
tests (verify table columns + FK targets exist). Row-population tests deferred
to Docker-up session.
