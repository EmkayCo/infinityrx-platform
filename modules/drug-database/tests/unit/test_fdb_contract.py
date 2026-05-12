"""B9.A C3 — Unit tests for the FDB contract-test helpers.

The helpers in `tests/_fdb_contract.py` are the shared assertion shape
that every B9.B-G phase reuses. These tests cover the helpers
themselves against synthetic fixtures so that defects in the template
surface BEFORE B9.B starts wiring 113 Tier A tables through it.
"""
from __future__ import annotations

import logging
import zipfile
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest

from drug_database.services.fdb_adapter import (
    DeltaSemantics,
    FDBDrop,
    FDBLocalDropAdapter,
    TableSpec,
    Tier,
)
# Importing the helper from `tests._fdb_contract` collides when pytest
# also collects shared/tests/ in the same run (two `tests` packages).
# Insert the tests dir on sys.path so the helper is reachable directly.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from _fdb_contract import (  # noqa: E402
    assert_delta_semantics_acd_cycle,
    assert_latin1_decode_smoke,
    assert_no_parse_warnings,
    assert_row_count_reconciles,
    assert_schema_parity,
    assert_upd_transaction_codes,
)


# ---------------------------------------------------------------------------
# Fixtures — synthetic FDB drop on disk
# ---------------------------------------------------------------------------


SIMPLE_SPEC = TableSpec(
    table_name="RFOO_TEST",
    columns=("id", "name"),
    coercers={"id": int, "name": str},
    tier=Tier.A,
    record_counts_key="RFOO",
    delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
)


def _write_zip(zip_path: Path, table_name: str, rows: list[str]) -> None:
    """Write a synthetic FDB-shaped zip with one pipe-delimited table.

    Body is latin-1, CRLF-terminated. Filename in the zip equals the
    literal table name (no extension), per FDB convention.
    """
    body = "\r\n".join(rows).encode("latin-1") + b"\r\n"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(table_name, body)


@pytest.fixture
def synthetic_drop(tmp_path: Path) -> FDBDrop:
    """A minimal but valid FDBDrop pointed at on-disk synthetic zips."""
    db_zip = tmp_path / "NDDF PLUS DB.zip"
    upd_zip = tmp_path / "NDDF PLUS UPD.zip"
    ddl_zip = tmp_path / "NDDF PLUS DDL.zip"
    highlights = tmp_path / "FDB_CLINICAL_HIGHLIGHTS.ZIP"
    record_counts = tmp_path / "RECORD_COUNTS.TXT"

    _write_zip(
        db_zip,
        "RFOO_TEST",
        ["1|alpha", "2|beta", "3|gamma"],
    )
    _write_zip(ddl_zip, "DDL_PLACEHOLDER", ["unused"])
    _write_zip(highlights, "HIGHLIGHTS_PLACEHOLDER", ["unused"])

    # UPD-shape: leading A/C/D prefix on each row.
    _write_zip(
        upd_zip,
        "RFOO_TEST",
        ["A|10|delta", "C|10|delta2", "D|10|"],
    )

    record_counts.write_text(
        "# synthetic record counts\nRFOO=3\nRBAR=0\n",
        encoding="latin-1",
    )

    return FDBDrop(
        drop_date=__import__("datetime").date(2026, 5, 6),
        license_code="TEL000000T",
        db_zip_path=db_zip,
        ddl_zip_path=ddl_zip,
        upd_zip_path=upd_zip,
        highlights_zip_path=highlights,
        record_counts_path=record_counts,
    )


@pytest.fixture
def adapter(tmp_path: Path) -> FDBLocalDropAdapter:
    return FDBLocalDropAdapter(tmp_path)


# ---------------------------------------------------------------------------
# Schema parity
# ---------------------------------------------------------------------------


@dataclass
class _FakeColumn:
    name: str


@dataclass
class _FakeModelMatches:
    """Stand-in model whose columns match SIMPLE_SPEC exactly."""

    columns = (_FakeColumn("id"), _FakeColumn("name"))


@dataclass
class _FakeModelExtraInSpec:
    """Model missing 'name' — spec has a column the model doesn't."""

    columns = (_FakeColumn("id"),)


@dataclass
class _FakeModelExtraInModel:
    """Model has an extra column not in spec; not a provenance name."""

    columns = (_FakeColumn("id"), _FakeColumn("name"), _FakeColumn("price"))


@dataclass
class _FakeModelProvenanceOnlyExtras:
    """Model adds provenance columns only — should NOT fail parity."""

    columns = (
        _FakeColumn("id"),
        _FakeColumn("name"),
        _FakeColumn("as_of_date"),
        _FakeColumn("drop_sequence"),
        _FakeColumn("transaction_code"),
        _FakeColumn("created_at"),
        _FakeColumn("tenant_id"),
    )


def test_schema_parity_matches() -> None:
    assert_schema_parity(SIMPLE_SPEC, _FakeModelMatches)


def test_schema_parity_provenance_extras_are_ignored() -> None:
    """Provenance columns added by parse_table are not parity violations."""
    assert_schema_parity(SIMPLE_SPEC, _FakeModelProvenanceOnlyExtras)


def test_schema_parity_fails_when_spec_has_extra_column() -> None:
    with pytest.raises(AssertionError, match="TableSpec has columns not in model"):
        assert_schema_parity(SIMPLE_SPEC, _FakeModelExtraInSpec)


def test_schema_parity_fails_when_model_has_extra_non_provenance_column() -> None:
    with pytest.raises(AssertionError, match="model has columns not in TableSpec"):
        assert_schema_parity(SIMPLE_SPEC, _FakeModelExtraInModel)


# ---------------------------------------------------------------------------
# latin-1 decode smoke
# ---------------------------------------------------------------------------


def test_latin1_decode_smoke_passes_on_valid_latin1(
    adapter: FDBLocalDropAdapter, synthetic_drop: FDBDrop
) -> None:
    # All rows are pure ASCII (subset of latin-1) — passes.
    assert_latin1_decode_smoke(adapter, synthetic_drop, SIMPLE_SPEC, sample_rows=10)


def test_latin1_decode_smoke_handles_high_bytes(
    tmp_path: Path, adapter: FDBLocalDropAdapter
) -> None:
    """Bytes 0x80-0xFF are valid latin-1 (windows-1252 superset)."""
    db_zip = tmp_path / "NDDF PLUS DB.zip"
    # \xb5 = µ (micro sign); \x96 = en-dash in windows-1252.
    body = b"1|alpha\xb5\r\n2|beta\x96gamma\r\n"
    with zipfile.ZipFile(db_zip, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("RFOO_TEST", body)

    drop = FDBDrop(
        drop_date=__import__("datetime").date(2026, 5, 6),
        license_code="TEL000000T",
        db_zip_path=db_zip,
        ddl_zip_path=tmp_path / "ddl.zip",
        upd_zip_path=tmp_path / "upd.zip",
        highlights_zip_path=tmp_path / "h.zip",
        record_counts_path=tmp_path / "rc.txt",
    )

    assert_latin1_decode_smoke(adapter, drop, SIMPLE_SPEC, sample_rows=10)


# ---------------------------------------------------------------------------
# Row-count reconciliation
# ---------------------------------------------------------------------------


def test_row_count_reconciles_exact_match(
    adapter: FDBLocalDropAdapter, synthetic_drop: FDBDrop
) -> None:
    assert_row_count_reconciles(
        adapter, synthetic_drop, SIMPLE_SPEC, actual_row_count=3
    )


def test_row_count_reconciles_within_tolerance(
    adapter: FDBLocalDropAdapter, synthetic_drop: FDBDrop
) -> None:
    # RECORD_COUNTS says 3; tolerance 33% (Decimal) accepts 2 or 4.
    assert_row_count_reconciles(
        adapter, synthetic_drop, SIMPLE_SPEC,
        actual_row_count=4, tolerance_pct=Decimal("0.34"),
    )


def test_row_count_reconcile_fails_outside_tolerance(
    adapter: FDBLocalDropAdapter, synthetic_drop: FDBDrop
) -> None:
    with pytest.raises(AssertionError, match="row-count reconciliation FAIL"):
        assert_row_count_reconciles(
            adapter, synthetic_drop, SIMPLE_SPEC, actual_row_count=10
        )


def test_row_count_reconcile_fails_when_key_missing(
    adapter: FDBLocalDropAdapter, synthetic_drop: FDBDrop
) -> None:
    """Spec whose record_counts_key isn't in the manifest must FAIL loudly."""
    missing_key_spec = TableSpec(
        table_name="RBAZ_NOT_IN_MANIFEST",
        columns=("id",),
        coercers={"id": int},
        tier=Tier.A,
        record_counts_key="RBAZ",  # not in synthetic RECORD_COUNTS.TXT
    )
    with pytest.raises(AssertionError, match="no entry for key"):
        assert_row_count_reconciles(
            adapter, synthetic_drop, missing_key_spec, actual_row_count=0
        )


def test_row_count_zero_expected_requires_actual_zero(
    adapter: FDBLocalDropAdapter, synthetic_drop: FDBDrop
) -> None:
    rbar_spec = TableSpec(
        table_name="RBAR_TEST",
        columns=("id",),
        coercers={"id": int},
        tier=Tier.A,
        record_counts_key="RBAR",
    )
    # RBAR=0 in synthetic manifest. actual=0 passes.
    assert_row_count_reconciles(
        adapter, synthetic_drop, rbar_spec, actual_row_count=0
    )
    # actual=1 fails.
    with pytest.raises(AssertionError, match="expected 0 rows"):
        assert_row_count_reconciles(
            adapter, synthetic_drop, rbar_spec, actual_row_count=1
        )


# ---------------------------------------------------------------------------
# Parse-warning policy
# ---------------------------------------------------------------------------


def test_no_parse_warnings_on_clean_table(
    adapter: FDBLocalDropAdapter, synthetic_drop: FDBDrop
) -> None:
    """Clean rows emit no parse_table warnings."""
    assert_no_parse_warnings(adapter, synthetic_drop, SIMPLE_SPEC)


def test_no_parse_warnings_FAILS_on_field_count_mismatch(
    tmp_path: Path, adapter: FDBLocalDropAdapter
) -> None:
    """A row with wrong field count must FAIL the contract, not silently skip."""
    db_zip = tmp_path / "NDDF PLUS DB.zip"
    _write_zip(
        db_zip,
        "RFOO_TEST",
        [
            "1|alpha",        # OK — 2 fields
            "2|beta|extra",   # BAD — 3 fields, expected 2
        ],
    )
    drop = FDBDrop(
        drop_date=__import__("datetime").date(2026, 5, 6),
        license_code="TEL000000T",
        db_zip_path=db_zip,
        ddl_zip_path=tmp_path / "ddl.zip",
        upd_zip_path=tmp_path / "upd.zip",
        highlights_zip_path=tmp_path / "h.zip",
        record_counts_path=tmp_path / "rc.txt",
    )
    with pytest.raises(AssertionError, match="unallowlisted warning"):
        assert_no_parse_warnings(adapter, drop, SIMPLE_SPEC)


def test_no_parse_warnings_allowlist_accepts_known_skip_class(
    tmp_path: Path, adapter: FDBLocalDropAdapter
) -> None:
    """An explicit allowlist entry suppresses the contract failure."""
    db_zip = tmp_path / "NDDF PLUS DB.zip"
    _write_zip(
        db_zip,
        "RFOO_TEST",
        ["1|alpha", "2|beta|extra"],
    )
    drop = FDBDrop(
        drop_date=__import__("datetime").date(2026, 5, 6),
        license_code="TEL000000T",
        db_zip_path=db_zip,
        ddl_zip_path=tmp_path / "ddl.zip",
        upd_zip_path=tmp_path / "upd.zip",
        highlights_zip_path=tmp_path / "h.zip",
        record_counts_path=tmp_path / "rc.txt",
    )
    # `_log.warning("ingest_field_count_mismatch", extra={...})` — msg is the
    # first positional arg of the log call. Allowlist matches against that.
    assert_no_parse_warnings(
        adapter, drop, SIMPLE_SPEC,
        allowlist={"fdb_table_field_count_mismatch"},
    )


# ---------------------------------------------------------------------------
# UPD A/C/D transaction-code probe (T12)
# ---------------------------------------------------------------------------


def test_upd_transaction_codes_pass_when_all_acd(
    adapter: FDBLocalDropAdapter, synthetic_drop: FDBDrop
) -> None:
    """The synthetic UPD has A/C/D-prefixed rows — passes."""
    spec_with_tx = TableSpec(
        table_name="RFOO_TEST",
        columns=("id", "name"),
        coercers={"id": int, "name": str},
        has_transaction_code=True,
        tier=Tier.A,
        record_counts_key="RFOO",
    )
    assert_upd_transaction_codes(adapter, synthetic_drop, spec_with_tx)


def test_upd_transaction_codes_fail_on_non_acd_prefix(
    tmp_path: Path, adapter: FDBLocalDropAdapter
) -> None:
    """A non-A/C/D leading field must FAIL — table is TRUNCATE+RELOAD shape."""
    upd_zip = tmp_path / "NDDF PLUS UPD.zip"
    _write_zip(
        upd_zip,
        "RFOO_TEST",
        ["A|1|alpha", "X|2|beta"],  # X is not a valid tx code
    )
    drop = FDBDrop(
        drop_date=__import__("datetime").date(2026, 5, 6),
        license_code="TEL000000T",
        db_zip_path=tmp_path / "db.zip",
        ddl_zip_path=tmp_path / "ddl.zip",
        upd_zip_path=upd_zip,
        highlights_zip_path=tmp_path / "h.zip",
        record_counts_path=tmp_path / "rc.txt",
    )
    spec_with_tx = TableSpec(
        table_name="RFOO_TEST",
        columns=("id", "name"),
        coercers={"id": int, "name": str},
        has_transaction_code=True,
        tier=Tier.A,
    )
    with pytest.raises(AssertionError, match="UPD A/C/D probe FAIL"):
        assert_upd_transaction_codes(adapter, drop, spec_with_tx)


def test_upd_probe_refuses_to_run_on_non_upd_spec(
    adapter: FDBLocalDropAdapter, synthetic_drop: FDBDrop
) -> None:
    """Caller error: probing a DB-only spec is a programming bug, not a data bug."""
    with pytest.raises(AssertionError, match="caller should skip this probe"):
        assert_upd_transaction_codes(adapter, synthetic_drop, SIMPLE_SPEC)


# ---------------------------------------------------------------------------
# Delta semantics simulation (A/C/D/re-A)
# ---------------------------------------------------------------------------


class _InMemoryUpsertStore:
    """Trivial UPSERT_BY_NATURAL_KEY simulator backed by a dict."""

    def __init__(self, natural_key_fields: tuple[str, ...]) -> None:
        self._rows: dict[tuple, dict] = {}
        self._key = natural_key_fields

    def _key_of(self, row: dict) -> tuple:
        return tuple(row[k] for k in self._key)

    def __call__(self, row: dict, tx: str) -> tuple[int, dict | None]:
        k = self._key_of(row)
        if tx == "A":
            self._rows[k] = dict(row)
        elif tx == "C":
            # Real UPSERT path — overwrite.
            self._rows[k] = dict(row)
        elif tx == "D":
            self._rows.pop(k, None)
        return len(self._rows), dict(self._rows[k]) if k in self._rows else None


class _BrokenUpsertStore(_InMemoryUpsertStore):
    """Simulates the regression A4 guards against: ON CONFLICT DO NOTHING."""

    def __call__(self, row: dict, tx: str) -> tuple[int, dict | None]:
        k = self._key_of(row)
        if tx == "A":
            self._rows.setdefault(k, dict(row))  # NOTHING on conflict
        elif tx == "C":
            self._rows.setdefault(k, dict(row))  # BUG: C is silently dropped
        elif tx == "D":
            self._rows.pop(k, None)
        return len(self._rows), dict(self._rows[k]) if k in self._rows else None


def test_delta_semantics_upsert_by_natural_key_passes_correct_impl() -> None:
    spec = TableSpec(
        table_name="RFOO",
        columns=("id", "name"),
        coercers={"id": int, "name": str},
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    )
    sim = _InMemoryUpsertStore(natural_key_fields=("id",))
    assert_delta_semantics_acd_cycle(
        spec,
        natural_key={"id": 42},
        initial_row={"name": "alpha"},
        changed_values={"name": "BETA"},
        simulator=sim,
    )


def test_delta_semantics_upsert_FAILS_on_silent_conflict_do_nothing() -> None:
    """A4 regression detector: C step is silently swallowed → contract FAILS."""
    spec = TableSpec(
        table_name="RFOO",
        columns=("id", "name"),
        coercers={"id": int, "name": str},
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    )
    sim = _BrokenUpsertStore(natural_key_fields=("id",))
    with pytest.raises(AssertionError, match="did not propagate changed_values"):
        assert_delta_semantics_acd_cycle(
            spec,
            natural_key={"id": 42},
            initial_row={"name": "alpha"},
            changed_values={"name": "BETA"},
            simulator=sim,
        )


def test_delta_semantics_unknown_is_skipped() -> None:
    """UNKNOWN preserves Phase 09 behavior — no contract."""
    spec = TableSpec(
        table_name="RFOO",
        columns=("id",),
        coercers={"id": int},
        delta_semantics=DeltaSemantics.UNKNOWN,
    )

    def _should_not_be_called(row, tx):  # pragma: no cover
        raise AssertionError("UNKNOWN delta_semantics should skip simulation")

    assert_delta_semantics_acd_cycle(
        spec,
        natural_key={"id": 1},
        initial_row={},
        changed_values={},
        simulator=_should_not_be_called,
    )


def test_delta_semantics_append_only_expects_history_growth() -> None:
    spec = TableSpec(
        table_name="RNP3_NDC_PRICE",
        columns=("ndc_11", "price"),
        coercers={"ndc_11": str, "price": Decimal},
        delta_semantics=DeltaSemantics.APPEND_ONLY,
    )

    rows: list[dict] = []

    def append_sim(row: dict, tx: str) -> tuple[int, dict | None]:
        rows.append({**row, "_tx": tx})
        return len(rows), rows[-1]

    assert_delta_semantics_acd_cycle(
        spec,
        natural_key={"ndc_11": "00000000001"},
        initial_row={"price": Decimal("1.00")},
        changed_values={"price": Decimal("2.00")},
        simulator=append_sim,
    )
    assert len(rows) == 4  # A + C + D + re-A all appended


def test_delta_semantics_effective_date_expects_two_rows_after_C() -> None:
    spec = TableSpec(
        table_name="RFOO_EFFDATED",
        columns=("id", "value", "eff_date"),
        coercers={"id": int, "value": str, "eff_date": str},
        delta_semantics=DeltaSemantics.UPSERT_WITH_EFFECTIVE_DATE,
    )

    rows: list[dict] = []

    def eff_sim(row: dict, tx: str) -> tuple[int, dict | None]:
        if tx in {"A", "C"}:
            rows.append(dict(row))
        elif tx == "D":
            pass  # caller-defined; ignored here
        return len(rows), rows[-1] if rows else None

    assert_delta_semantics_acd_cycle(
        spec,
        natural_key={"id": 1},
        initial_row={"value": "old", "eff_date": "20260101"},
        changed_values={"value": "new", "eff_date": "20260501"},
        simulator=eff_sim,
    )
    assert len(rows) >= 2
