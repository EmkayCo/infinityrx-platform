# B9 Parse-Warning Allowlist (initial: EMPTY)

**Owner:** B9 wave team
**Audit gate:** every B9.B-G mini-GATE-CLOSE re-reads this file; any
entry must reference a CONSULT-ROUND sign-off + documented count
impact + the contract test that proves the impact is bounded.

This file is the SINGLE SOURCE OF TRUTH for which `parse_table`
warning classes are accepted as known-good silent-skip behavior in
the B9 contract tests. Per `modules/drug-database/tests/_fdb_contract.py`
the helper `assert_no_parse_warnings()` defaults to ZERO tolerance —
ANY `_log.warning(...)` from `FDBLocalDropAdapter.parse_table` fails
the contract for that table.

To allowlist a warning, the wave operator runs:

```python
assert_no_parse_warnings(
    adapter, drop, spec,
    allowlist={"ingest_field_count_mismatch"},  # for example
)
```

The allowlist value is the FIRST positional arg to `_log.warning`
(message string), NOT the `extra` dict. Three known message classes
the parser can emit:

| Message string | Branch | Count impact |
|---|---|---|
| `fdb_table_transaction_code_missing` | UPD row's leading field is not A/C/D | drops the row from the load |
| `fdb_table_field_count_mismatch` | row's pipe-split field count != len(spec.columns) | drops the row |
| `fdb_table_row_invalid` | coercer raised ValueError / InvalidOperation / InvalidNDCError | drops the row |

## Approved allowlist entries

(none)

## Process for adding an entry

1. Identify the warning class via `caplog` or by running
   `assert_no_parse_warnings` and capturing the failure message.
2. Reproduce the warning locally and confirm the affected row class
   is data-shape-stable across at least 4 weekly drops (vendor isn't
   thrashing).
3. Write a short rationale ("PRICE_TYPE='14' NOPRC sentinel — 0.02%
   of RNP3 rows, documented in §4.4").
4. Add an entry to the table below with the rationale, the affected
   table(s), the rough %impact, and the link to the CONSULT-ROUND
   transcript that approved it.
5. Update the per-table contract test wrapper to pass the entry in
   the `allowlist=` set.

| Message | Table(s) | %impact | Rationale | Consult sign-off |
|---|---|---|---|---|

(empty — no entries approved as of B9.A C3)

## ADVERSARIAL N4 reminder

The N4 attack: parser silently skips field-count errors. The
contract test is what makes that branch loud. **Allowlisting is
NOT a free pass** — every entry expands the surface where the
parser can silently drop rows. Treat additions as a recorded
decision, not a routine extension.
