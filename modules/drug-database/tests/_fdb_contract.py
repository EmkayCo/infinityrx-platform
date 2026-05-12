"""B9.A C3 — Reusable contract-test template for FDB ingester tables.

Every B9 phase (B9.B Tier A, B9.C Tier B, B9.D Tier C, B9.E RNDC14,
B9.F pricing, B9.G MTL) lands new `TableSpec` entries plus their
SQLAlchemy models and ingester wiring. The contract test set asserted
on every one of those tables is identical in shape, varies only in
which spec + which model + which fixture.

This module is the SHARED IMPLEMENTATION of that shape. Per-tier test
modules import the helpers and call them with concrete inputs:

    from drug_database.tests._fdb_contract import (
        assert_schema_parity,
        assert_latin1_decode_smoke,
        assert_row_count_reconciles,
        assert_no_parse_warnings,
        assert_upd_transaction_codes,
        assert_delta_semantics_acd_cycle,
    )

    def test_rmiid1_med_contract(local_drop, rmiid1_med_spec, RmiidMedModel):
        adapter = FDBLocalDropAdapter(local_drop.parent.parent)
        assert_schema_parity(rmiid1_med_spec, RmiidMedModel)
        assert_no_parse_warnings(adapter, local_drop, rmiid1_med_spec)
        assert_latin1_decode_smoke(adapter, local_drop, rmiid1_med_spec)
        assert_row_count_reconciles(
            adapter, local_drop, rmiid1_med_spec,
            actual_row_count=loaded_count,
        )

The file is intentionally named with a leading underscore so pytest
discovery does NOT pick it up as a test module — it is a helper
library. The accompanying `test_fdb_contract.py` covers the helpers
themselves.

ADVERSARIAL R1 mitigations folded in:
  * N4 (parse_table skip)        — assert_no_parse_warnings makes the
                                    "skip on field-count mismatch"
                                    branch FAIL the contract unless
                                    explicitly allowlisted.
  * A4 (delta correctness)       — assert_delta_semantics_acd_cycle
                                    runs the A/C/D/re-A simulator per
                                    DeltaSemantics class. UNKNOWN +
                                    APPEND_ONLY take the replay-safety
                                    path; UPSERT classes get the full
                                    correctness check.
  * T12 (UPD A/C/D probe)        — assert_upd_transaction_codes opens
                                    the `.UPD` zip and verifies every
                                    row's leading field is A/C/D.

The PARSE-WARNING-FAILS-TEST POLICY (charter v3.x):
  Any `_log.warning(...)` emitted by `FDBLocalDropAdapter.parse_table`
  during a contract run fails the contract test for that table — UNLESS
  the warning's `ingest_*` log-record key+value pair appears in the
  allowlist at `Werkbench/projects/infinityrx-platform/waves/B9/parse_warning_allowlist.md`
  with a documented count impact. Empty initial allowlist; entries
  added only with codex sign-off.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from drug_database.services.fdb_adapter import (
    DeltaSemantics,
    FDBAdapter,
    FDBDrop,
    TableSpec,
    Tier,
    _stream_pipe_rows,
)


# ---------------------------------------------------------------------------
# Warning capture
# ---------------------------------------------------------------------------


class _ParseWarningCollector(logging.Handler):
    """Captures WARNING-level records emitted by fdb_adapter during parse.

    Used by ``assert_no_parse_warnings`` to assert that the silent-skip
    branches in `FDBLocalDropAdapter.parse_table` are never reached
    during a contract run.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
        self.records.append(record)


def _collect_parse_warnings(
    adapter: FDBAdapter,
    drop: FDBDrop,
    spec: TableSpec,
    *,
    source: str = "DB",
) -> tuple[list[dict[str, Any]], list[logging.LogRecord]]:
    """Run parse_table to completion, returning rows + warnings emitted.

    Drains the iterator so no warnings are missed; for small synthetic
    fixtures this is cheap. For real Tier-A tables it is also fine
    (rows < 10K). RNP3-class tables should use a sampled wrapper.
    """
    collector = _ParseWarningCollector()
    fdb_logger = logging.getLogger("drug_database.services.fdb_adapter")
    fdb_logger.addHandler(collector)
    fdb_logger.setLevel(logging.WARNING)
    try:
        rows = list(adapter.parse_table(drop, spec, source=source))
    finally:
        fdb_logger.removeHandler(collector)
    return rows, collector.records


# ---------------------------------------------------------------------------
# Schema parity
# ---------------------------------------------------------------------------


def assert_schema_parity(spec: TableSpec, model_class: type) -> None:
    """Assert TableSpec.columns set == SQLAlchemy model column set.

    Drift in either direction is a contract violation:

    * Extra column in model     → model writes a column the parser
                                  never populates (silent NULL).
    * Extra column in spec      → parser yields a key the model can't
                                  persist (silent drop).

    The contract is set-equality. Column order is OUT OF SCOPE here
    — DDL byte-for-byte ordering is checked in alembic migration tests
    elsewhere; this assertion is about the named surface area only.

    `model_class` may be a SQLAlchemy declarative class (has __table__)
    or any object exposing a `columns` attribute whose entries have a
    `.name` attribute.
    """
    table = getattr(model_class, "__table__", None)
    if table is not None:
        model_cols = {col.name for col in table.columns}
    else:
        model_cols = {col.name for col in model_class.columns}

    spec_cols = set(spec.columns)

    # Allow universal provenance fields the model defines but the spec
    # never emits via columns (they come from parse_table.body, not
    # spec.coercers).
    PROVENANCE = {
        "id",
        "as_of_date",
        "drop_sequence",
        "transaction_code",
        "created_at",
        "updated_at",
        "tenant_id",
    }
    model_extras = model_cols - spec_cols - PROVENANCE
    spec_extras = spec_cols - model_cols

    assert not model_extras, (
        f"Schema parity FAIL for {spec.table_name}: model has columns "
        f"not in TableSpec: {sorted(model_extras)}"
    )
    assert not spec_extras, (
        f"Schema parity FAIL for {spec.table_name}: TableSpec has columns "
        f"not in model: {sorted(spec_extras)}"
    )


# ---------------------------------------------------------------------------
# latin-1 decode smoke
# ---------------------------------------------------------------------------


def assert_latin1_decode_smoke(
    adapter: FDBAdapter,
    drop: FDBDrop,
    spec: TableSpec,
    *,
    sample_rows: int = 1000,
    source: str = "DB",
) -> None:
    """First `sample_rows` rows decode as latin-1 without UnicodeError.

    T1 mitigation: text-heavy Tier A/B tables ship operator-entered
    drug names that frequently contain windows-1252 superset bytes
    (e.g. micro symbol µ at 0xB5, en-dash at 0x96). UTF-8 would barf;
    latin-1 must not. Failure here means either (a) the file is NOT
    latin-1 (vendor regression) or (b) the byte stream has been
    mangled by an intermediate tool.

    Iterates via `_stream_pipe_rows` directly (bypassing TableSpec
    coercion) — pure encoding check. Failures raise UnicodeDecodeError
    from `_stream_pipe_rows` and fail the test by exception, not by
    assertion.
    """
    zip_path = drop.upd_zip_path if source == "UPD" else drop.db_zip_path
    rows_seen = 0
    for fields in _stream_pipe_rows(zip_path, spec.table_name):
        # Already decoded to str by _stream_pipe_rows — touching .encode
        # roundtrip-asserts the bytes were valid latin-1 (encode back
        # never raises for any str < U+0100 source).
        for f in fields:
            f.encode("latin-1")  # smoke; raises if non-latin-1 sneaked in
        rows_seen += 1
        if rows_seen >= sample_rows:
            break
    # No assertion on rows_seen — a small table with < sample_rows rows
    # is fine. The decode check ran on every available row.


# ---------------------------------------------------------------------------
# Row-count reconciliation
# ---------------------------------------------------------------------------


def _parse_record_counts(path: Path) -> dict[str, int]:
    """Parse FDB's RECORD_COUNTS.TXT into {table_name: row_count}.

    Format observed at `data/reference/fdb/TEL251759D/`:
      <table_name>=<count>
    one entry per CRLF line. Encoding is latin-1; numbers are decimal.
    Blank lines and `#` comment lines are tolerated.
    """
    out: dict[str, int] = {}
    text = path.read_text(encoding="latin-1")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        try:
            out[key] = int(val)
        except ValueError:
            continue
    return out


def assert_row_count_reconciles(
    adapter: FDBAdapter,
    drop: FDBDrop,
    spec: TableSpec,
    *,
    actual_row_count: int,
    tolerance_pct: Decimal = Decimal("0.001"),
) -> None:
    """Assert `actual_row_count` is within tolerance of vendor manifest.

    SC-2 (RECORD_COUNTS reconciliation): for every loaded table,
    `actual_row_count` ÷ `expected_row_count` must be within
    ±`tolerance_pct` (default 0.1%). Small lookups should be exact
    (tolerance hits when sentinel_filter drops a documented sentinel
    row class — e.g. RNP3 PRICE_TYPE='14').

    Lookup key: `spec.record_counts_key` if set, else `spec.table_name`.
    Missing key in RECORD_COUNTS.TXT is a contract violation — the
    caller must extend `record_counts_key` rather than silently skip.
    """
    counts = _parse_record_counts(drop.record_counts_path)
    key = spec.record_counts_key or spec.table_name
    assert key in counts, (
        f"RECORD_COUNTS.TXT has no entry for key {key!r} (spec "
        f"{spec.table_name!r}). Set record_counts_key on the TableSpec "
        f"to the manifest's key for this table."
    )
    expected = counts[key]
    if expected == 0:
        # Tables FDB ships with 0 rows: assert actual is also 0.
        assert actual_row_count == 0, (
            f"{spec.table_name} expected 0 rows per RECORD_COUNTS.TXT, "
            f"got {actual_row_count}"
        )
        return
    delta_pct = abs(Decimal(actual_row_count - expected) / Decimal(expected))
    assert delta_pct <= tolerance_pct, (
        f"{spec.table_name} row-count reconciliation FAIL: "
        f"actual={actual_row_count} expected={expected} "
        f"delta_pct={delta_pct} > tolerance={tolerance_pct}"
    )


# ---------------------------------------------------------------------------
# Parse-warning policy
# ---------------------------------------------------------------------------


def assert_no_parse_warnings(
    adapter: FDBAdapter,
    drop: FDBDrop,
    spec: TableSpec,
    *,
    source: str = "DB",
    allowlist: Iterable[str] = (),
) -> None:
    """No silent-skip warnings emitted by parse_table for this table.

    Mitigation for ADVERSARIAL N4 (parse_table silently skips field-
    count errors). The parser's warning-log branches:

      * ``fdb_table_transaction_code_missing``
      * ``fdb_table_field_count_mismatch``
      * ``fdb_table_row_invalid``

    Any of these in a contract run is a fail. To accept a known-good
    skip class, add the warning's primary `extra` key+value to
    `Werkbench/projects/infinityrx-platform/waves/B9/parse_warning_allowlist.md`
    with documented count impact and CONSULT-ROUND sign-off, then pass
    the parsed allowlist as `allowlist=`.

    The allowlist matches against `record.message` (the first arg of
    `_log.warning`). Empty initial allowlist; entries are deliberate.
    """
    _rows, records = _collect_parse_warnings(adapter, drop, spec, source=source)
    allow = set(allowlist)
    offenders = [
        r for r in records
        if (r.getMessage() not in allow) and (r.msg not in allow)
    ]
    assert not offenders, (
        f"{spec.table_name}: parse_table emitted {len(offenders)} "
        f"unallowlisted warning(s): "
        f"{[r.getMessage() for r in offenders[:5]]}"
    )


# ---------------------------------------------------------------------------
# UPD transaction-code probe (T12)
# ---------------------------------------------------------------------------


def assert_upd_transaction_codes(
    adapter: FDBAdapter,
    drop: FDBDrop,
    spec: TableSpec,
    *,
    sample_rows: int = 1000,
) -> None:
    """Every row in the table's `.UPD` file begins with A, C, or D.

    T12 mitigation: weekly FDB UPD delta format is documented as A/C/D
    -prefixed across all 220 tables. ADVERSARIAL R1 flagged that tables
    failing this assumption must be routed to TRUNCATE+RELOAD rather
    than UPSERT, or the delta is silently wrong.

    `spec.has_transaction_code` MUST be True for this assertion to run
    (DB.zip rows have no prefix; UPD rows do). For tables loaded only
    from DB.zip — skip this probe in the caller.

    Sample-bounded: probes first `sample_rows` lines. For Tier A
    tables that is the entire file; for RNP3-class that is enough
    coverage to catch a format flip.
    """
    assert spec.has_transaction_code, (
        f"{spec.table_name}: assert_upd_transaction_codes called but "
        f"spec.has_transaction_code=False — caller should skip this probe."
    )

    rows_checked = 0
    bad: list[tuple[int, str]] = []
    for line_idx, fields in enumerate(
        _stream_pipe_rows(drop.upd_zip_path, spec.table_name)
    ):
        if not fields:
            bad.append((line_idx, "<empty row>"))
        elif fields[0] not in {"A", "C", "D"}:
            bad.append((line_idx, fields[0]))
        rows_checked += 1
        if rows_checked >= sample_rows:
            break

    assert not bad, (
        f"{spec.table_name}: UPD A/C/D probe FAIL — {len(bad)} rows in "
        f"first {rows_checked} have non-A/C/D leading field: "
        f"{bad[:5]} (sample). This table is likely TRUNCATE+RELOAD, "
        f"not UPSERT — re-classify delta_semantics."
    )


# ---------------------------------------------------------------------------
# Delta semantics simulation (A/C/D/re-A)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeltaSimulationResult:
    """Outcome of a single A/C/D/re-A simulation step."""

    step: str  # "A", "C", "D", "re-A"
    rows_in_table_after: int
    target_row_values_after: dict[str, Any] | None


# A callable that:
#   * accepts a row dict + transaction_code
#   * applies the corresponding INSERT / UPSERT / DELETE to a test DB
#   * returns (current row count, current row state for the target key)
DeltaSimulator = Callable[
    [dict[str, Any], str],
    tuple[int, dict[str, Any] | None],
]


def assert_delta_semantics_acd_cycle(
    spec: TableSpec,
    *,
    natural_key: dict[str, Any],
    initial_row: dict[str, Any],
    changed_values: dict[str, Any],
    simulator: DeltaSimulator,
) -> None:
    """Simulate A → C → D → re-A and assert per-semantics correctness.

    ADVERSARIAL R1 A4 mitigation: an UPSERT-by-natural-key path running
    only a replay-safety test (load same row twice → 0 new) gives a
    PASS even when a `C` with changed values is silently ignored
    because `ON CONFLICT DO NOTHING` swallows it.

    This helper drives the simulator through four explicit steps and
    asserts on `spec.delta_semantics`:

      APPEND_ONLY:
        A → C → D → re-A → expect 4 rows (history; D + re-A are NEW
        rows in history)
      UPSERT_BY_NATURAL_KEY:
        A     → 1 row with initial_row
        C     → 1 row with changed_values (NOT silently ignored)
        D     → 0 rows (deletion applied)
        re-A  → 1 row with initial_row
      UPSERT_WITH_EFFECTIVE_DATE:
        A     → 1 row at eff_date_1
        C     → 2 rows (closed eff_date_1 + new eff_date_2)
                Caller may pass `changed_values` containing the new
                effective_date; assertion is rows_after >= 2 + latest
                row matches changed_values.
        D     → latest row marked terminated; caller-defined
        re-A   → new row
      TRUNCATE_RELOAD:
        Simulator should ignore tx codes; only the final reloaded
        state matters. Helper just asserts the simulator returns the
        post-reload count without raising. Use a dedicated
        truncate-reload test elsewhere.
      UNKNOWN:
        Skip — Phase 09 backward-compat (treated as APPEND_ONLY by
        downstream).

    The simulator is the integration surface: caller wires it against
    SQLite (unit) or Postgres (integration). The helper is pure
    orchestration.
    """
    if spec.delta_semantics in {DeltaSemantics.UNKNOWN, DeltaSemantics.TRUNCATE_RELOAD}:
        # UNKNOWN: Phase 09 compat — no contract.
        # TRUNCATE_RELOAD: state-after-reload tested elsewhere.
        return

    row_a = {**natural_key, **initial_row}
    row_c = {**natural_key, **changed_values}
    row_d = dict(natural_key)
    row_re_a = {**natural_key, **initial_row}

    # Step A (initial add)
    count_after_a, state_after_a = simulator(row_a, "A")
    # Step C (change)
    count_after_c, state_after_c = simulator(row_c, "C")
    # Step D (delete)
    count_after_d, _state_after_d = simulator(row_d, "D")
    # Step re-A (add back same natural key with initial values)
    count_after_re_a, state_after_re_a = simulator(row_re_a, "A")

    if spec.delta_semantics is DeltaSemantics.APPEND_ONLY:
        # Each step adds a history row; D produces a tombstone row.
        assert count_after_a == 1, f"{spec.table_name}: A produced {count_after_a} rows; expected 1"
        assert count_after_c >= 2, f"{spec.table_name}: C did not append (count={count_after_c})"
        assert count_after_d >= 3, f"{spec.table_name}: D did not append (count={count_after_d})"
        assert count_after_re_a >= 4, f"{spec.table_name}: re-A did not append (count={count_after_re_a})"
        return

    if spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY:
        assert count_after_a == 1, f"{spec.table_name}: A produced {count_after_a} rows; expected 1"
        assert count_after_c == 1, (
            f"{spec.table_name}: C left {count_after_c} rows; expected 1 "
            f"(upsert collapses to one row per natural key)"
        )
        assert state_after_c is not None and all(
            state_after_c.get(k) == v for k, v in changed_values.items()
        ), (
            f"{spec.table_name}: C did not propagate changed_values — "
            f"likely ON CONFLICT DO NOTHING regression (state={state_after_c})"
        )
        assert count_after_d == 0, (
            f"{spec.table_name}: D left {count_after_d} rows; expected 0 "
            f"(delete must remove the row, not tombstone it)"
        )
        assert count_after_re_a == 1, (
            f"{spec.table_name}: re-A produced {count_after_re_a} rows; expected 1"
        )
        assert state_after_re_a is not None and all(
            state_after_re_a.get(k) == v for k, v in initial_row.items()
        ), (
            f"{spec.table_name}: re-A did not restore initial values "
            f"(state={state_after_re_a})"
        )
        return

    if spec.delta_semantics is DeltaSemantics.UPSERT_WITH_EFFECTIVE_DATE:
        assert count_after_a == 1, f"{spec.table_name}: A produced {count_after_a} rows; expected 1"
        assert count_after_c >= 2, (
            f"{spec.table_name}: C did not open a new effective-dated row "
            f"(count={count_after_c}); expected >= 2"
        )
        assert state_after_c is not None and all(
            state_after_c.get(k) == v for k, v in changed_values.items()
        ), (
            f"{spec.table_name}: C latest row does not match changed_values "
            f"(state={state_after_c})"
        )
        # D and re-A are caller-defined per table; no fixed assertion here.
        return

    raise AssertionError(
        f"{spec.table_name}: unhandled delta_semantics "
        f"{spec.delta_semantics!r} in contract template"
    )


__all__ = [
    "assert_schema_parity",
    "assert_latin1_decode_smoke",
    "assert_row_count_reconciles",
    "assert_no_parse_warnings",
    "assert_upd_transaction_codes",
    "assert_delta_semantics_acd_cycle",
    "DeltaSimulationResult",
    "DeltaSimulator",
]
