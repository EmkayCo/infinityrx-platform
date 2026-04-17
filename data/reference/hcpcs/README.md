# HCPCS Level II Load Flow

Operational notes for the CMS HCPCS Level II (Healthcare Common Procedure
Coding System) ingestion. Layout spec is ``HCPC<YYYY>_recordlayout.txt``,
distributed alongside each quarterly ZIP.

## 1. Overview

HCPCS Level II is the CMS-maintained procedure / supply / drug-admin code
set used on medical claims. For InfinityRx specifically, the **J-codes**
(J0000–J9999: drugs administered by injection/infusion) are the primary
input for manufacturer copay and PAP programs that cover Part B
infusibles/injectables — ~1,400 codes of direct interest out of the full
~9k Level II set.

**Level I (CPT) codes are not loaded here** — AMA licenses CPT
descriptions separately from CMS, and the CMS quarterly file contains
only Level II (A-V prefix alpha-numeric). A Level I integration is out
of scope pending AMA licensing.

Target table: ``shared.hcpcs_codes`` (17 columns, versioned on
``(code, is_modifier, publication_quarter)``). See commit ``6855c25``
for the migration.

## 2. Publication cadence

CMS publishes quarterly:

| Quarter | Effective | Filename template |
|---|---|---|
| Q1 | January 1 | `january-<YYYY>-alpha-numeric-hcpcs-file.zip` |
| Q2 | April 1 | `april-<YYYY>-alpha-numeric-hcpcs-file.zip` |
| Q3 | July 1 | `july-<YYYY>-alpha-numeric-hcpcs-file.zip` |
| Q4 | October 1 | `october-<YYYY>-alpha-numeric-hcpcs-file.zip` |

Filename variant: a few years (notably 2023 / 2024) used the plural
``alpha-numeric-hcpcs-files.zip``. The loader's regex accepts both.

The ``publication_quarter`` column is a ``YYYYQN`` string (``2026Q2`` for
the April 2026 release) derived from the filename.

Scheduler fires quarterly: 15th of January, April, July, October at 3 AM
UTC (``0 3 15 1,4,7,10 *``). Day-15 gives a two-week buffer after the
first-week CMS posting window. The 3 AM slot staggers 1 h after the
ICD-10-CM slot so both never share a DB session at startup.

## 3. File layout

ZIP contents (April 2026 release, 2.53 MB compressed):

```
HCPC2026_APR_ANWEB.txt             5.4 MB  16,734 fixed-width records (authoritative)
HCPC2026_APR_ANWEB.xlsx            1.9 MB  same data, Excel
HCPC2026_APR_ANWEB_Transaction Report.xlsx  833 KB  quarter-over-quarter changes
HCPC2026_APR_Corrections.xlsx      11 KB   any corrections posted after release
HCPC2026_recordlayout.txt          62 KB   CMS-authored 31-field record spec
NOC codes_APR2026.xlsx             20 KB   Not-Otherwise-Classified reference
proc_notes_APR2026.txt             45 KB   narrative notes
```

The loader parses ``HCPC<YYYY>_<MMM>_ANWEB.txt`` — the ``.txt`` is
authoritative. 320-char fixed-width records, 31 fields per the record
layout. The columns we capture:

| Cols | Field | Notes |
|---|---|---|
| 1–5 | HCPCS code | 5 CHAR; modifiers have 3-space prefix + 2-char code |
| 6–10 | sequence number | continuation records share code, incrementing seq |
| 11 | record ID code | primary vs continuation marker |
| 12–91 | long description | 80 CHAR; spans continuation rows |
| 92–119 | short description | 28 CHAR |
| 120–121 | pricing indicator | |
| 230 | coverage code | |
| 266–268 | anesthesia base units | NUM 3 |
| 269–276 | added date | YYYYMMDD; ``00000000`` → NULL |
| 277–284 | action effective date | YYYYMMDD |
| 285–292 | termination date | YYYYMMDD |
| 293 | action code | |

**Continuation records**: CMS wraps long descriptions > 80 chars across
multiple rows with the same code + incrementing sequence numbers. The
loader's ``_aggregate_continuations`` helper folds them into one
aggregated row per ``(code, is_modifier)`` pair. For April 2026, 16,734
raw rows collapse to **9,068 distinct codes + 383 distinct modifiers**.

**Modifiers** live in the same table as full codes; the ``is_modifier``
flag distinguishes them. The CMS source puts modifiers in the same file
with a 3-space prefix in the code field — the loader uses that as the
modifier signal.

## 4. Versioning

The unique constraint is ``(code, is_modifier, publication_quarter)`` —
each quarterly publication adds its own rows for every changed code.
Claims dated within a quarter resolve against the row for that quarter.
Prior quarters stay intact; deprecated codes naturally stop appearing
in new publications.

A code that ceases to be valid mid-quarter will carry a real
``termination_date`` in subsequent quarters even while still nominally
present — filter by ``action_effective_date <= date_of_service <
termination_date`` (with ``termination_date`` as a high-sentinel when
NULL) for precise temporal matching.

## 5. Operations

```bash
source infrastructure/scripts/switch_env.sh dev

# Default — scrape the CMS quarterly-update page
python scripts/load_hcpcs.py

# Point at an already-downloaded ZIP
python scripts/load_hcpcs.py --source-zip \
  data/reference/hcpcs/april-2026-alpha-numeric-hcpcs-file.zip
```

Expected wall time on dev Postgres: **~2 seconds** (9k rows). If it takes
more than 30 s, something is wrong.

### Known failure modes

- **CMS URL path change** — the quarterly-update page itself has moved
  historically (the non-Wave-13 guess
  ``coding-billing/healthcare-common-procedure-system-hcpcs`` returned
  404; the correct path omits ``-hcpcs``). Keep the ``_CMS_INDEX_URL`` in
  ``shared/data_ingestion/sources/hcpcs.py`` under test by running
  ``scripts/load_hcpcs.py`` without ``--source-zip`` at least once per
  quarter-end.
- **Level I (CPT) codes appearing** — AMA licensing prevents CMS from
  distributing CPT descriptions. If the file ever changes shape to
  include them, the loader would accept them but their descriptions
  would likely be stripped — verify by running a spot-check against a
  known 5-digit numeric code.
- **``00000000`` dates** — the loader treats the all-zero date as NULL.
  If a real-world sentinel shows up as any other pattern (``19000101``
  was observed in some legacy CMS outputs), extend ``_parse_date_yyyymmdd``.

## 6. Spot-check (April 2026)

Verified against the live CMS file at commit ``c316846``:

| Code | Modifier? | Long description |
|---|---|---|
| A0021 | no | Ambulance service, outside state per mile, transport (medicaid only) |
| J1442 | no | Injection, filgrastim (g-csf), excludes biosimilars, 1 microgram |
| GA | yes | Waiver of liability statement issued as required by payer policy, individual case |

## 7. Tests

``shared/data_ingestion/tests/test_medical_codes.py`` covers HCPCS:

- Fixed-width parser: regular 5-char code, leading-space modifier,
  empty line
- Date helpers: valid YYYYMMDD, ``00000000`` sentinel, empty, malformed
- Quarter derivation: each of Q1/Q2/Q3/Q4
- Filename parsing for all four months × both `file` and `files`
  variants; unrecognized raises
- `_choose_latest_filename` picks newest across mixed variants
- `_aggregate_continuations` folds multi-row long descriptions;
  distinct codes stay separate; (code, is_modifier) keyed correctly
- Load + idempotency + multi-quarter load round-trip against SQLite

Run: `pytest shared/data_ingestion/tests/test_medical_codes.py -k Hcpcs`.
