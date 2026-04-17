# ICD-10-CM Load Flow

Operational notes for the CMS ICD-10-CM (International Classification of
Diseases, Clinical Modification) ingestion. For CSV column semantics, see
the CMS-published ``icd10OrderFiles.pdf`` inside the descriptions ZIP.

## 1. Overview

ICD-10-CM is the CDC-maintained / CMS-distributed diagnosis-code set used
on every medical claim. InfinityRx uses it to validate diagnosis codes on
claim intake (NCPDP D.0 field 424-DH for pharmacy claims, CMS-1500 Box 21
for medical claims) and to map diagnosis → coverage rule for manufacturer
copay programs that gate on specific indications.

Authoritative source: CDC NCHS publishes the content. CMS is the
operational distribution point used by industry.

Target table: ``shared.icd10_cm_codes`` (10 columns, versioned on
``(code, effective_date)``). See commit ``6855c25`` for the migration.

## 2. Publication cadence

CMS publishes twice per fiscal year:

| File | Effective | Example URL |
|---|---|---|
| Annual FY release | October 1 | `https://www.cms.gov/files/zip/<FY>-code-descriptions-tabular-order.zip` |
| April mid-year update | April 1 | `https://www.cms.gov/files/zip/april-1-<YYYY>-code-descriptions-tabular-order.zip` |

The ``<FY>`` in the annual URL is the federal fiscal year, which starts
Oct 1 of the prior calendar year (FY2026 = Oct 1, 2025 – Sep 30, 2026).
The loader derives ``effective_date`` from the filename:

- ``april-1-YYYY-…zip`` → ``YYYY-04-01``
- ``YYYY-…zip`` (annual)  → ``(YYYY - 1)-10-01``

Scheduler fires twice a year: 15th of April and 15th of October at 2 AM
UTC (``0 2 15 4,10 *``). Day-15 gives a two-week buffer after the CMS
posting date so the file is reliably downloadable.

## 3. File layout

Downloaded ZIP contents (April 2026 example, 2.24 MB compressed):

```
Code Descriptions/
├── icd10cm_codes_2026.txt           6.4 MB   74,719 billable leaves, 2-col flat
├── icd10cm_order_2026.txt          14.7 MB   98,186 rows (billable + parent headers)
├── icd10cm_codes_addenda_2026.txt  summary   changes since prior publication
├── icd10cm_order_addenda_2026.txt  summary
├── icd10cmCodesFile.pdf            reference
└── icd10OrderFiles.pdf             reference — spec for the order file
```

The loader parses ``icd10cm_order_<YYYY>.txt`` (richer of the two) —
fixed-width, 5-column layout:

| Cols | Field | Notes |
|---|---|---|
| 1–5 | ordinal number | zero-padded |
| 7–13 | ICD-10-CM code | 7 chars right-padded; A-Z prefix + 1–4-char subdivision |
| 15 | billable flag | `0` = parent header, `1` = billable leaf |
| 17–76 | short description | 60 chars, truncated with abbreviations |
| 78+ | long description | free text to EOL |

Of 98,186 rows, 74,719 are billable leaves and 23,467 are parent category
headers. Both are loaded — headers are useful for hierarchical UI
rendering, and leaves are what claim-adjudication code matches against.

## 4. Versioning

The unique constraint is ``(code, effective_date)`` — multiple effective
dates for the same code are the norm, not the exception. A 2025 claim
adjudicated today resolves its diagnosis descriptions against the row
with ``max(effective_date) ≤ 2025-XX-XX``. Upgrade paths:

- New publication adds a new (code, effective_date) row per code. Prior
  publications stay intact.
- Running the same load twice is idempotent (full-key collision).
- Codes deleted in a new publication are NOT marked as such in the
  current schema — they simply stop appearing in new publications.
  Downstream filters by ``effective_date <= date_of_service`` handle this
  correctly without extra fields.

## 5. Operations

```bash
source infrastructure/scripts/switch_env.sh dev

# Default — scrape the CMS index for the newest publication
python scripts/load_icd10.py

# Point at an already-downloaded ZIP (must have the canonical CMS
# filename so effective_date can be derived)
python scripts/load_icd10.py --source-zip \
  data/reference/icd10-cm/april-1-2026-code-descriptions-tabular-order.zip
```

Expected wall time on dev Postgres: **10 seconds** (98k rows). If the run
takes more than a minute, either the DB is under load or the 5,000-row
batch size is contending with a lock — check the run row in
``shared.ingestion_runs``.

### Known failure modes

- **CMS URL changes** — the scraper finds the current filename by regex
  over ``href="…"`` tokens on the index page. If CMS moves to a new path
  template, update ``_APRIL_ZIP_RE`` / ``_ANNUAL_ZIP_RE`` in
  ``shared/data_ingestion/sources/icd10_cm.py``.
- **Non-canonical filename on disk** — the filename-based effective_date
  derivation fails with a clear ``ValueError``. Rename the ZIP to match
  the canonical CMS pattern, or invoke the ingester directly with an
  explicit ``_override_effective_date``.
- **Non-zero ``records_errored``** — the parser currently logs every
  failure via ``ErrorAggregator``. Check ``error_samples`` on the
  ``shared.ingestion_runs`` row for kind + message.

## 6. Spot-check (April 2026)

Verified against the live CMS file at commit ``c316846``:

| Code | Billable | Long description |
|---|---|---|
| E119 | yes | Type 2 diabetes mellitus without complications |
| I10 | yes | Essential (primary) hypertension |
| Z0000 | yes | Encounter for general adult medical examination without abnormal findings |
| Z000 | no (parent) | Encounter for general adult medical examination |

## 7. Tests

``shared/data_ingestion/tests/test_medical_codes.py`` carries the
ICD-10-CM coverage:

- Parser: billable-leaf, parent-header, empty, malformed-ordinal rows
- Filename → effective_date derivation for both annual and April patterns
- `_choose_latest_filename` prefers April over annual in same year and
  picks the newest annual when no April exists
- Load + idempotency round-trip against a SQLite-backed test DB

Run: `pytest shared/data_ingestion/tests/test_medical_codes.py -k icd`.
