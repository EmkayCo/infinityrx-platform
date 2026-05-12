# B9.A C12 — Phase 09 Compatibility Baseline

**Captured:** 2026-05-11 22:55 EDT (Docker-resumed, post-B7.3)
**Source:** `waves/B9/baseline.md` invariant set (re-asserted after B7.3 closure)
**Database:** `infinityrx_reference` on `infinityrx-postgres` container
**FDB drop:** `data/reference/fdb/TEL251759D/06MAY2026.TEL251759D/`

This file LOCKS the Phase 09 row counts + query latency that every
B9.B-G mini-GATE-CLOSE asserts unchanged (within documented tolerance).
A regression in any of these is a hard stop — B9 must not have
disturbed pricing data while extending the reference schema.

## Locked baseline values

### Row counts

| Table | Row count | Source |
|---|---|---|
| `drug_database.fdb_ndc_price_history` | **15,635,770** | Phase 09 close; re-asserted 2026-05-11 |
| `drug_database.fdb_price_type_desc`   | **23** | Phase 09 close; re-asserted 2026-05-11 |
| `drug_database.fdb_ndc_price_type_desc` | (TBD — capture next Docker session) | RNPTYPD0_NDC_PRICE_TYPE_DESC |

Tolerance: **exact match** for `fdb_price_type_desc` (static reference,
23 rows defined by spec). Weekly delta growth allowed for
`fdb_ndc_price_history` — separately tracked in the weekly delta
ledger; mini-GATE-CLOSE asserts row count **>= baseline** and that
the (NDC, price_type, effective_date, as_of_date) primary surface
is unchanged for any sampled NDC from baseline.

### Query latency

Representative NDC lookup query:

```sql
SELECT ndc_11, price_type FROM drug_database.fdb_ndc_price_history
WHERE ndc_11 = '00781153910' LIMIT 5;
```

Captured timing: **2.116 ms** (index hit; result was 0 rows — that
NDC is not in the dataset, but the planner still uses the
`(ndc_11, ...)` covering index). Mini-GATE-CLOSE asserts the same
shape: index hit + < 50 ms even for 0-row results. A regression to
sequential scan would be visible as latency jumping into the
hundreds-of-milliseconds range.

### Default-mode behavior

`load_fdb.py --mode fdb_weekly --dry-run` on the same drop returns:
- price_type_desc_inserted = 0 (already current)
- rnp3_inserted = 0 (already current — last weekly applied)
- rnp3_duplicate_skipped = 15,635,770 (idempotency proven)
- rnp3_invalid_skipped = 0

This is the IDEMPOTENCY signal: a re-run of the same drop produces
0 net new rows. Mini-GATE-CLOSE for B9.B-G re-runs this and asserts
all four counters unchanged.

## How mini-GATE-CLOSE re-asserts this

Each B9.B-G phase close runs:

```bash
source infrastructure/scripts/switch_env.sh dev
psql infinityrx_reference -tc \
  "SELECT count(*) FROM drug_database.fdb_ndc_price_history"
psql infinityrx_reference -tc \
  "SELECT count(*) FROM drug_database.fdb_price_type_desc"
time psql infinityrx_reference -c \
  "SELECT ndc_11, price_type FROM drug_database.fdb_ndc_price_history
   WHERE ndc_11 = '00781153910' LIMIT 5"
```

Outputs are diffed against this file. Any drift fails the mini-GATE.

## When this baseline is updated

Never silently. Three legitimate triggers:

1. **Weekly delta runs against the canonical drop.** Updates the
   `fdb_ndc_price_history` row count and the delta ledger entry.
   Baseline number stays as the lower bound; new captures appear
   alongside as ledger rows.
2. **FDB schema migration (vendor side).** Future drop adds a
   column. Baseline values stay; new assertion rows append.
3. **Recovery rebase.** Operator-triggered `fdb_rebase` repopulates.
   The new row count IS the new baseline; this file is updated in
   the same commit that runs the rebase.

## Test-side enforcement

`modules/drug-database/tests/integration/test_phase09_compat_baseline.py`
(added by B9.A C12) re-asserts the row counts against a live Postgres
when Docker is up; skipped otherwise. The markdown is the
operator-readable contract; the test is the CI gate.
