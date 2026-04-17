# Follow-up: extract REMS program data from SPL free-text

**Status:** open, punted from Wave 9d
**Affects:** `shared/data_ingestion/sources/fda_rems.py`, `drug_database.drug_rems`
**Tracked in code:** see `TODO-WAVE-REMS-EXTRACT` comment in `_parse_record`

## The silent overwrite

openFDA's drug-label endpoint does not populate a top-level `rems[]` key
in the current build. Verified against the 766-record snapshot in
`data/reference/fda-rems/fda_rems.json`: **0 of 766 records have it.**

`FdaRemsIngester._parse_record` therefore always falls through to:

```python
rems_program_name = application_number  # fallback
rems_type         = None                 # no rems_list to infer from
etasu_requirements= None                 # no rems_list to build from
```

Result: every row written to `drug_database.drug_rems` currently carries
the NDA/BLA number as its `rems_program_name`, and leaves `rems_type`
and `etasu_requirements` NULL. Downstream consumers get an
"application X has a REMS" signal but nothing about what program, what
type, or what enrollment requirements apply.

This is acceptable for the immediate use case (flagging REMS-encumbered
drugs) but insufficient for the larger goal of driving REMS compliance
checks at claim adjudication time.

## Scope of the fix

1. **Extract program name from SPL free-text.**
   The label body's `warnings_and_cautions` and `boxed_warning` sections
   contain the program name phrased consistently. Patterns seen in the
   current 766-record snapshot:

   - `The ${PROGRAM_NAME} REMS` (most common)
   - `under a Risk Evaluation and Mitigation Strategy (REMS) called ${PROGRAM_NAME}`
   - `${PROGRAM_NAME} Shared System REMS` (for shared-system programs)

   Use anchored patterns (`\A...\Z` on sentence-level matches) so trailing
   newlines can't bypass validation — LESSON-004.

2. **Classify rems_type.**
   Populate one of: `Medication Guide`, `Communication Plan`, `ETASU`,
   `ETASU with Shared System`, `REMS with ETASU and Shared System`.
   Derive from the same SPL text by looking for the FDA-standard phrasing
   rather than the current keyword-match heuristic on a field that's
   always empty.

3. **Structured enrollment requirements.**
   Replace the current boolean indicator dict with a structured JSON:

   ```json
   {
     "prescriber": {
       "certification_required": true,
       "training_url": "https://...",
       "certification_program": "..."
     },
     "pharmacy": {
       "certification_required": true,
       "certification_program": "...",
       "restricted_distribution": true
     },
     "patient": {
       "enrollment_required": true,
       "counseling_required": false,
       "monitoring_required": true
     },
     "program_urls": ["https://...", "..."]
   }
   ```

4. **Populate `shared_system_name`.**
   Currently always NULL. When the SPL text mentions a shared system
   (e.g. "iPLEDGE REMS", "TIRF REMS Access Program"), capture its name.

5. **Handle revision dates properly.**
   `initial_approval_date` and `most_recent_modification_date` are both
   currently set to `effective_time` (the SPL label's effective date),
   which is wrong for the former. Parse the actual initial-approval
   date from the label history where available.

## Out of scope

- The openFDA `rems[]` key may get populated in a future openFDA
  release. If so, the fallback path should keep working but defer to
  the structured API data when present.
- Drug-level REMS lookup by NDC is handled via `drug_rems_ndc` — no
  changes needed there.

## Acceptance

- Running `python scripts/load_fda_rems.py` populates `rems_program_name`
  with a human-readable program name (not an app number) for >95% of
  rows.
- `rems_type` is non-NULL for >95% of rows.
- Spot-check: TIRF-labeled applications show `"TIRF REMS Access Program"`,
  not `"NDA021443"`.

## References

- Source loader: `shared/data_ingestion/sources/fda_rems.py` —
  `_parse_record` + the TODO-WAVE-REMS-EXTRACT comment on the
  `rems_program_name` fallback line.
- Target schema: `drug_database.drug_rems` (see migration
  `modules/drug-database/alembic/versions/` for the current column
  set).
