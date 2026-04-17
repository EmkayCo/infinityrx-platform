# NPPES Load Flow

Architectural and operational documentation for the CMS NPPES (National
Plan and Provider Enumeration System) ingestion pipeline. This document
is for engineers debugging a failed load or extending the loader. For
CSV column semantics, see the NPPES V2 data dictionary on the CMS site.

## 1. Overview

NPPES is the CMS-maintained registry of every NPI (National Provider
Identifier) issued in the United States — one row per prescriber or
organization, ~9.5M active rows as of April 2026. InfinityRx uses it
for **prescriber identity validation on every adjudicated claim**:
the NPI submitted by a pharmacy in NCPDP D.0 field 411-DB is looked
up locally to confirm the prescriber exists, is still active, holds a
taxonomy consistent with the drug's category, and (where applicable)
has DEA or state-license credentials on file.

The authoritative source is the CMS file index at
`https://download.cms.gov/nppes/NPI_Files.html`, which publishes three
distinct file types the loader can ingest:

- A **monthly full-registry snapshot** (the entire ~9.5M-row registry).
- A **weekly delta** (rows changed in the preceding week, ~35k typical).
- A **weekly deactivation report** (NPIs that have been retired since
  enumeration; cumulative, ~340k rows).

Target tables, all in schema `prescriber_dir`:

| Table                           | Rows per NPI | Role                                     |
|---------------------------------|--------------|------------------------------------------|
| `prescribers`                   | 1            | Core identity + primary taxonomy + state |
| `nppes_prescriber_details`      | 1            | Extended NPPES fields (AO, credentials)  |
| `prescriber_addresses`          | 1–2          | Mailing + practice location              |
| `prescriber_taxonomies`         | 1–15         | Exploded taxonomy slots per NPI          |
| `prescriber_identifiers`        | 0–50         | Exploded "other provider identifier" slots |

## 2. Three Modes

The loader supports three distinct run modes — one per file type CMS
publishes. Each mode has its own `source_name` in
`shared.ingestion_runs`, its own checksum-dedup window, and its own
scheduler entry.

| Mode           | `source_name`        | CMS publishing cadence            | Scheduler cron       | Typical size      |
|----------------|----------------------|-----------------------------------|----------------------|-------------------|
| `weekly`       | `nppes`              | Every Tuesday                     | `0 3 * * 2`          | 50–150 MB, ~35k NPIs |
| `monthly`      | `nppes_monthly`      | Between the 10th and 12th of each month | `0 4 15 * *`   | ~6 GB zip / ~10 GB CSV, ~9.5M NPIs |
| `deactivation` | `nppes_deactivation` | Alongside the monthly dissemination | `0 5 15 * *`       | ~2.5 MB xlsx, ~340k NPIs |

Scheduler crons fire after the CMS publishing window closes so the run
always sees the newest file. The monthly and deactivation entries
stagger by one hour (15th 4 AM vs 15th 5 AM) so the two loads never
contend for the DB connection or the CMS index endpoint.

### Why three separate scheduler entries instead of one smart one

One entry per file type is deliberate. The alternative — a single
"nppes" runner that decides at tick time which file to fetch — fails
two practical tests:

1. **Debuggability.** A failed row in `shared.ingestion_runs` names
   its mode directly. You can see "nppes_monthly failed, nppes and
   nppes_deactivation succeeded" at a glance; a single-entry design
   would force you to inspect `run_type` / `error_message` /
   `source_file_name` to reconstruct what the runner was trying to do.

2. **Single responsibility.** Each mode has its own failure surface
   (monthly is disk-bound and long-running; weekly is usually a
   fast idempotent delta; deactivation is an UPDATE-only pass against
   a narrow column). Wiring them to distinct runs keeps the retry,
   alert, and throttling policies orthogonal.

The code-level payoff is equally small and equally worth it: the three
modes share the CSV pipeline — only the URL-scrape regex, the size
cap, and (for deactivation) the load path differ. See
`_MODE_CONFIG` in `shared/data_ingestion/sources/nppes.py`.

## 3. Core + Satellite Split

The weekly and monthly modes run a **two-phase pipeline** against
the same extracted CSV:

```
┌────────────────────────────┐   ┌──────────────────────────────────────────┐
│ Phase 1 — core upsert      │   │ Phase 2 — satellite load                 │
│ prescriber_dir.prescribers │ → │ nppes_prescriber_details                 │
│ 1 row per NPI              │   │ prescriber_addresses                     │
│ INSERT ... ON CONFLICT     │   │ prescriber_taxonomies                    │
│                            │   │ prescriber_identifiers                   │
│                            │   │ DELETE parent scope, then INSERT         │
└────────────────────────────┘   └──────────────────────────────────────────┘
```

**Why split the phases.** The two phases have fundamentally different
transactional shapes:

- **Core** is **upsert-per-NPI**. Every source row maps to exactly one
  `prescribers` row. Duplicate keys across batches are resolved by
  `ON CONFLICT ... DO UPDATE`. Late source changes re-apply cleanly on
  any future run.

- **Satellites** are **scoped-replace-per-NPI**. A single NPI has up
  to 15 taxonomy rows, up to 50 identifier rows, and up to 2 address
  rows. CSV column slots `_1`.._`N` encode an ordered list whose length
  can shrink between publications. The only correct update pattern is
  **delete all rows for that NPI, then insert the new set** — merging
  would leave stale slots from a prior publication when the current
  one has fewer entries.

**Order dependency.** Core must complete before satellites start.
Satellite rows FK (logically, not always enforced at the DB level) to
`prescribers.npi`; starting satellites before the core is populated
would orphan them. The loader enforces this by calling
`load_nppes_satellite_tables` only after `run_nppes_import` returns
cleanly. A failed core halts the run before satellites begin — a
partial-prescribers state cannot corrupt satellites, because
satellites never run.

**Partial-success state.** When only the core phase completes (e.g.,
the April 2026 monthly baseline per commit `ff82aec`), the run is
marked `status='completed_core'` in `shared.ingestion_runs` — **not**
`'completed'`. A follow-up satellite-only pass can then re-consume
the same CSV without redoing the 4-hour core phase. See the
`completed_core` note in `shared/data_ingestion/models.py`.

## 4. COPY-Staging Optimization (Wave 11.5)

### Why

The original flush primitives
(`flush_upsert_batch` / `flush_scoped_replace_batch`) send
`INSERT ... VALUES (row₁),(row₂),...(rowₙ) ON CONFLICT DO UPDATE`
as one statement per batch. On the April 2026 monthly run
(commit `ff82aec`) this sustained **~611 rows/sec** during the core
phase against the ~9.5M-row full registry — 4 hours 19 minutes for
core alone. Satellites are narrower but produce 3–5× as many rows per
NPI, so satellite wall time extrapolates to another 8–12 hours on the
same primitive. Monthly runs would not fit any maintenance window the
platform can realistically defend.

Postgres `COPY FROM STDIN` bypasses the SQL parser for the data path,
writes through a binary protocol that doesn't round-trip parameter
bindings, and avoids the per-batch replan cost. On wide / bulk
inserts it typically runs 3–10× faster than the equivalent VALUES
statement.

### Design

Two new primitives in `shared/data_ingestion/batching.py`:

- `flush_upsert_batch_copy` — drop-in replacement for
  `flush_upsert_batch`, same signature, same return semantics.
- `flush_scoped_replace_batch_copy` — drop-in replacement for
  `flush_scoped_replace_batch`, same signature, same return
  semantics.

The Postgres code path:

1. Dedup rows on `unique_key` (upsert) or within each scope on
   `unique_key` (scoped replace).
2. Fill `created_at` / `updated_at` where present.
3. `CREATE TEMP TABLE IF NOT EXISTS stg_<target> (LIKE <target>
   INCLUDING DEFAULTS) ON COMMIT DROP`; `TRUNCATE stg_<target>`.
4. `COPY stg_<target> (cols) FROM STDIN` — text format with `\N`
   null markers and backslash-escaped control characters.
5. Upsert: `INSERT INTO target SELECT * FROM stg ON CONFLICT
   (unique_key) DO UPDATE SET ...`. Scoped replace:
   `DELETE FROM target USING (SELECT DISTINCT scope FROM stg) s
   WHERE target.scope = s.scope; INSERT INTO target SELECT *
   FROM stg`.
6. `db.commit()` — `ON COMMIT DROP` retires the temp table.

The non-Postgres code path delegates to the original VALUES primitive.
SQLite test fixtures pass through unchanged; the optimization only
fires on the production dialect.

### Opt-in

Every existing caller of the VALUES primitives is unchanged. The NPPES
satellite loader is the first and currently only opt-in, via
`load_nppes_satellite_tables(..., use_copy=True)` — the default.
Setting `use_copy=False` forces the VALUES path on Postgres and is
used only by the bench script.

### Benchmark

Script: `scripts/bench_nppes_satellite.py`. Operator-run against the
dev Postgres. For each path it TRUNCATEs the 4 satellite tables, streams
the first N rows of a real NPPES CSV to a tmp file, times the loader
invocation, and reports per-table row counts and aggregate rows/sec.

**Observed throughput:** _TODO — populate after 11.5-3 operator run._

| Path      | rows/sec (all 4 satellite tables) | wall time at 2,000 NPIs |
|-----------|-----------------------------------|-------------------------|
| VALUES    | _TODO_                            | _TODO_                  |
| COPY      | _TODO_                            | _TODO_                  |
| Speedup   | _TODO_x                           | —                       |

Baseline to beat: the 611 rows/sec observed during the April 2026
monthly core run. The 11.5-3 commit will replace the _TODO_ cells with
the measured values from a bench run at 2,000 NPIs on dev and the
full 9.5M-NPI satellite run on the same file.

## 5. Error Handling (G6 Findings)

### What the 233 errors on the first weekly run were

The first weekly run after the Wave 11 satellite refactor surfaced
**233 errored rows / 0 skipped** against a 34,984-row weekly file.
Investigation (commit `dde30c0`) found every one of the 233 to be a
**narrow-column overflow in the VARCHAR constraints** of the
satellite tables — the same class of bug that commit `fcf3d0a` had
fixed earlier for the core `prescribers` table, but on columns that
had never been sanitized on the satellite side.

Two root causes, both in the source CSV:

1. **Foreign-provider rows populate state-code columns with region
   names**. The NPPES export stores full region names like
   `"ONTARIO"`, `"ENGLAND"`, `"MAHARASHTRA, INDIA"` in columns the
   schema defines as `VARCHAR(2)`. Under the pre-Wave-11 per-row
   loader each offender took down only its own INSERT; under the
   batched-flush path a single offender kills its entire 1,000-row
   batch.

2. **Military APO addresses put free text into fixed-width postal-
   code columns**. Strings like `"APO AP 96271"` (12 characters)
   overflow `postal_code VARCHAR(10)`. Same blast-radius amplification
   under batched flush.

### Accepted exception list

Rather than widen every constraint or truncate-at-insert, the fix is
**NULL-over-truncate at parse time**. Two sanitizers in
`modules/prescriber-directory/src/services/nppes_ingestion.py`:

- `_state_or_none(value)` — returns a 2-char US state/territory code,
  or `None` for anything else. Applied to:
    - `prescriber_addresses.state`
    - `prescriber_taxonomies.license_state_code`
    - `prescriber_identifiers.identifier_state`

- `_fit_or_none(value, max_len)` — returns `value` if it fits in
  `max_len` characters, else `None`. Applied to:
    - `prescriber_addresses.postal_code` (VARCHAR 10)
    - `prescriber_addresses.country_code` (VARCHAR 3)
    - Every VARCHAR(1) / VARCHAR(2) / VARCHAR(10) column on
      `nppes_prescriber_details` (gender, is_sole_proprietor,
      deactivation reason, name prefix/suffix, etc.)
    - `prescriber_identifiers.identifier_type_code` (VARCHAR 2)
    - `prescriber_taxonomies.is_primary` (VARCHAR 1)

NULL semantics are safe for every one of these columns downstream —
a partial state or zip code is not usable for matching anyway, and
consumers already branch on NULL. The alternative (silent truncation)
would produce plausible-looking but invalid codes that would silently
corrupt matching.

After the G6 fix a re-run against the same 34,984-row file reported
**0 errored / 0 skipped**. The accepted exception list is the set
above — any non-zero `records_errored` on a future run should be
investigated as a new root cause, not assumed benign.

### How to distinguish new errors from accepted ones

`records_errored` in `shared.ingestion_runs` is the canonical count
(it takes its value from `ErrorAggregator.total_errors` after G6).
When it is non-zero:

1. Query `error_samples` on the run row (JSONB). The aggregator
   records up to 5 samples with `kind` and `message`.
2. The `kind` field buckets the failure:
    - `"validation"` — per-row sanitizer rejected the value. With
      the G6 sanitizers in place these should not recur; if they do,
      a new column type is overflowing.
    - `"luhn"` — NPI failed the Luhn check. These are upstream data
      errors; CMS occasionally publishes a malformed NPI.
    - `"upsert:<table>"` / `"scoped_replace:<table>"` — VALUES-path
      batch failure.
    - `"upsert_copy:<table>"` / `"scoped_replace_copy:<table>"` —
      COPY-path batch failure. The full exception text is in
      `message`; inspect the staging-table DDL and compare column
      types against the target if an unexpected type-cast failure
      appears.
    - `"row_build"` — the `_build_*` helpers raised. Usually a
      missing CSV column after a CMS schema change; the `raw_row`
      sample in `error_samples` names the NPI.
3. Compare the top-N error buckets logged at the end of the run
   (`ingest_error_kind`, `ingest_error_count`) against the accepted
   list above. Anything outside that list is a new root cause.

## 6. Operations

### CLI — actual help text from `scripts/load_nppes.py --help`

```
usage: load_nppes.py [-h] [--mode {weekly,monthly,deactivation}] [--dry-run]
                     [--sample]

Load CMS NPPES data

options:
  -h, --help            show this help message and exit
  --mode {weekly,monthly,deactivation}
                        Which CMS file to fetch. Default: weekly.
  --dry-run             Parse only - no DB writes. Reports yielded counts.
  --sample              Use the bundled synthetic sample CSV instead of
                        downloading (weekly mode only).
```

Manual invocation for each mode:

```bash
source infrastructure/scripts/switch_env.sh dev

# Weekly delta (default mode)
python scripts/load_nppes.py

# Monthly full-registry snapshot — expect 4+ hours on current primitives,
# less once COPY is measured.
python scripts/load_nppes.py --mode monthly

# Weekly deactivation report — UPDATE-only, under 60 seconds
python scripts/load_nppes.py --mode deactivation

# Parse-only sanity check against the bundled 10-row synthetic sample
python scripts/load_nppes.py --sample --dry-run
```

### Interpreting `shared.ingestion_runs`

One row is written per run, per `source_name`. Columns to watch:

- `status` — `running` during the pass, transitions to one of:
    - `completed` — all phases finished cleanly.
    - `completed_core` — core phase finished; at least one dependent
      phase was deferred or killed. See the April 2026 monthly row for
      the canonical example. A follow-up run fills in the remainder.
    - `failed` — download / parse / core load raised.
    - `skipped_unchanged` — checksum matched the last successful run;
      no DB writes occurred.
    - `cancelled` — operator or supervisor terminated the run.
- `records_in_source` — row count in the extracted CSV.
- `records_processed` — rows the loader iterated over.
- `records_inserted` + `records_updated` — DB-side mutations.
- `records_errored` — canonical error count after G6; see §5 for
  interpretation.
- `error_samples` — up to 5 JSONB samples with `kind` / `message`.
- `error_message` — free-form note; used to explain partial-success
  `completed_core` rows.
- `download_seconds` / `parse_seconds` / `load_seconds` — per-phase
  timing. A jump in any single phase is usually the first signal when
  investigating a regression.

### Known failure modes and recovery

**Core succeeds, satellites fail.** The run row will be marked
`completed_core` with `error_message` explaining which satellite
phase bailed. The core data is usable on its own — every downstream
consumer of the core `prescribers` table is unaffected. To fill in
the satellites without redoing the 4-hour core:

1. Keep the extracted CSV — do not let the loader cleanup path unlink
   it. (For the April 2026 baseline the file is cached at
   `data/reference/nppes/NPPES_Data_Dissemination_April_2026_V2/`.)
2. In a Python shell under `source infrastructure/scripts/switch_env.sh
   dev`, call `load_nppes_satellite_tables(session, csv_path)`
   directly with the cached CSV path. This is the same entry point the
   ingester uses internally.
3. On clean completion, update the original run row:
   `UPDATE shared.ingestion_runs SET status='completed',
   error_message=NULL WHERE id='<run_id>'`.

**CMS URL pattern changes.** CMS has in the past renamed files
(version suffixes, date formats). Three regexes scrape the index
page for the current mode's zip:

- `_WEEKLY_ZIP_RE` in `shared/data_ingestion/sources/nppes.py:57`
- `_MONTHLY_ZIP_RE` at the same path, line 63
- `_DEACT_ZIP_RE` at the same path, line 69

All three follow the LESSON-004 discipline of `\A...\Z` anchors in
other security-sensitive regex sites, but these specific regexes are
used in a `findall` over HTML and do not anchor; widen the pattern
rather than anchoring when CMS introduces a new version suffix.

**Disk pressure.** The monthly file is ~6 GB zipped and ~10 GB
uncompressed. The loader extracts to `data/reference/nppes/` (not
`/tmp`) — controlled by `_CACHE_DIR` in
`shared/data_ingestion/sources/nppes.py:79`. The extracted directory
is retained after a successful load for re-runs (see partial-success
recovery above); prune it after the next monthly succeeds if space
is tight.

## 7. Future Work

### Other loaders as COPY candidates

The COPY primitives are opt-in and the NPPES satellite loader is the
only current consumer. A survey of the other loaders for retrofit
potential, ordered by expected payoff:

- **RxNorm** — plausible candidate. The full RxNorm release is wide
  (~30 columns), loads several million rows across the RXN* /
  RXNREL / RXNSAT files, and currently runs on the VALUES primitives.
  Retrofit **after** the NPPES bench (§4) proves the speedup is
  meaningful, then measure against an RxNorm full load before
  committing.
- **FDA NDC / OIG LEIE** — likely not worth the retrofit. NDC has
  ~100k active rows; LEIE adds ~70k records per month. Both finish
  in well under a minute on the VALUES path; the COPY primitive's
  fixed overhead (CREATE TEMP TABLE + the extra INSERT..SELECT hop)
  eats the gain at this scale.
- **Everything else** (SAM exclusions, CMS ASP, FDA REMS, FDA Drug
  Shortages, etc.) — too small. Keep on VALUES.

The general rule: retrofit a loader to COPY when its VALUES
throughput is the bottleneck for a maintenance-window constraint,
not just because COPY is available.

### `raw_payload` JSONB — deferred

A JSONB column on `nppes_prescriber_details` that stores the full
CSV row as parsed would let us recover fields we haven't modeled
explicitly, and would future-proof against CMS schema additions.
Deferred because: (a) the NPPES V2 schema has been stable for
several years, (b) the JSONB would roughly double the table size
and slow both COPY and satellite scans, and (c) any field we
actually need can be promoted from CSV to a typed column with a
one-line `_build_detail` change. Revisit if CMS announces a V3
schema revision, or if a consumer needs a column we've historically
discarded.
