"""FDB (First DataBank) NDDF Plus adapter — generic table surface.

Phase 8 / Phase 09 implementation. Replaces the prior 5-method stub
interface (`fetch_feed`/`parse_feed`/`parse_pricing`/`parse_interactions`/
`parse_dosing`) with a generic `TableSpec`-driven surface — codex MF5
fix per SPEC §3.7.2 (`data/reference/fdb/README.md`, locked at codex
GO commit `9aa576b`).

New shape:

  FDBAdapter (ABC):
    discover_latest_drop() -> FDBDrop
    open_table(drop, table_name, *, source) -> Iterator[bytes]
    parse_table(drop, spec, *, source) -> Iterator[dict]

  TableSpec: schema-driving dataclass (columns + coercers + filters).
  FDBDrop:   one full FDB delivery folder (drop_date + paths).

  FDBLocalDropAdapter: file-system concrete adapter for operator-
  managed drops at `data/reference/fdb/TEL251759D/`.

  Four TableSpec values for Phase 8: RNP3_NDC_PRICE (+ _UPD variant),
  RPRDPTD0_PRICE_TYPE_DESC, RNPTYPD0_NDC_PRICE_TYPE_DESC.

  parse_rnp3() typed wrapper for the hot-path RNP3 caller (15.6M rows
  weekly) — preserves IDE autocomplete + type-checker support at the
  ingester's main loop.

Why generic surface, not per-table abstractmethods (SPEC §3.7.2.2):
  * New tables become data (TableSpec values), not interface methods.
  * Single `test_parse_table_*` suite covers all tables.
  * Two-method MagicMock for tests vs. six-method.
  * Aspirational specs (DDIM, dosing) can't drift back in unused.

Discipline:
  * LESSON-004 — date regex uses `re.fullmatch(r"\\A\\d{8}\\Z", ...)`.
  * LESSON-005 — log keys prefixed `ingest_*`.
  * financial-precision.md — Decimal coercer; never float.
  * surgical-changes.md — TableSpec values only as SPEC §3.7.2 lists
    them. Additional hardening helpers (`_str11` / `_decimal_16_5` /
    etc.) deferred until a downstream unit needs them.
"""
from __future__ import annotations

import logging
import re
import zipfile
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, TypedDict

from drug_database.utils.ndc import InvalidNDCError, normalize_ndc

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class FDBDropError(RuntimeError):
    """Raised when an FDB drop folder is malformed or inconsistent.

    Concrete cases: missing NDDF_PRODUCT_INFO.TXT, drop_date in
    the file content does not match the folder name, folder name
    does not parse as ``<DDMMMYYYY>.<LICENSE>``.
    """


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_FDB_DATE_RE = re.compile(r"\A\d{8}\Z")


def _parse_fdb_date(raw: str) -> date:
    """Parse an 8-digit YYYYMMDD string into a `date`.

    LESSON-004: `re.fullmatch` with `\\A\\d{8}\\Z` rejects trailing
    newlines and partial matches. Used as the canonical `effective_date`
    coercer for RNP3 + RPRDPP0 TableSpecs.
    """
    if not _FDB_DATE_RE.fullmatch(raw):
        raise ValueError(f"FDB date '{raw}' is not 8-digit YYYYMMDD")
    return datetime.strptime(raw, "%Y%m%d").date()


def decimal_16_6(raw: str) -> Decimal:
    """Decimal coercer for NUMERIC(16,6) columns (UOM_CONVERSION_FACTOR).

    Default `Decimal` coercer is generator-mapped to `sa.Numeric(16, 5)`
    (FDB pricing precision). Some non-money columns ship with NUMERIC(16,6)
    in the DDL — most notably `RPEIUC0_UOM_CONVERSION.UOM_CONVERSION_FACTOR`.
    Using this named coercer signals the generator to emit `Numeric(16, 6)`
    instead, preserving DDL precision exactly.

    Codex B9.B GATE-CLOSE R1 MEDIUM 2 mitigation.
    """
    return Decimal(raw)


_DROP_FOLDER_RE = re.compile(r"\A(\d{2})([A-Z]{3})(\d{4})\.([A-Z]{3}\d{6}[A-Z])\Z")
_MONTH_MAP = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def _parse_drop_folder_name(name: str) -> tuple[date, str]:
    """Parse folder name `<DDMMMYYYY>.<LICENSE>` → (drop_date, license_code).

    Example: ``06MAY2026.TEL251759D`` → (date(2026, 5, 6), "TEL251759D").
    Raises FDBDropError on malformed names.
    """
    m = _DROP_FOLDER_RE.fullmatch(name)
    if not m:
        raise FDBDropError(
            f"FDB drop folder name '{name}' does not match "
            f"<DDMMMYYYY>.<LICENSE> pattern"
        )
    dd, mmm, yyyy, license_code = m.groups()
    month = _MONTH_MAP.get(mmm)
    if month is None:
        raise FDBDropError(f"FDB drop folder month '{mmm}' is not a valid abbreviation")
    return date(int(yyyy), month, int(dd)), license_code


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FDBDrop:
    """One full FDB delivery folder (e.g. 06MAY2026.TEL251759D/).

    All paths are absolute; the adapter is responsible for resolving
    them. Tests typically construct FDBDrop with synthetic paths under
    a tempdir.
    """

    drop_date: date
    license_code: str
    db_zip_path: Path
    ddl_zip_path: Path
    upd_zip_path: Path
    highlights_zip_path: Path
    record_counts_path: Path


class Tier(Enum):
    """B9 effort-classification tier per `recon.md` §3.

    Phase 09 used a single tier implicitly (the 3 pricing-related
    TableSpecs were all hand-curated). B9 extends to 217 more tables
    classified by complexity:

      A — simple lookups, ≤5 cols, generic ingester (113 tables)
      B — NDC/GCN-keyed joins (66 tables)
      C — complex/large (>8 cols or >50 MB) including RNDC14 + pricing (19 tables)
      D — MTL (medical test lexicon), schema-only, no data load (19 tables)

    UNKNOWN is the backward-compat default for Phase 09 TableSpecs
    that pre-date the tier field. They behave as before.
    """

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    UNKNOWN = "UNKNOWN"


class DeltaSemantics(Enum):
    """How a TableSpec's weekly FDB delta should be applied.

    Codex ADVERSARIAL R1 A4 mitigation (`waves/B9/codex-adversarial-r1.md`):
    `ON CONFLICT DO NOTHING` proves replay safety but NOT delta
    correctness on mutable lookups. A D-then-re-A with changed values
    is silently ignored if the conflict key is natural-key only.

    Per-table classification:

      APPEND_ONLY                — immutable insert (pricing history; RNP3)
      UPSERT_BY_NATURAL_KEY      — most reference tables; ON CONFLICT DO UPDATE
      UPSERT_WITH_EFFECTIVE_DATE — time-bucketed; new row per (key, eff_date)
      TRUNCATE_RELOAD            — tables w/o stable natural key, full reload
      UNKNOWN                    — backward-compat default for Phase 09

    B9.A C8 contract test simulates A / C / D / re-A scenarios per
    semantics class to verify delta correctness, not just replay safety.
    """

    APPEND_ONLY = "APPEND_ONLY"
    UPSERT_BY_NATURAL_KEY = "UPSERT_BY_NATURAL_KEY"
    UPSERT_WITH_EFFECTIVE_DATE = "UPSERT_WITH_EFFECTIVE_DATE"
    TRUNCATE_RELOAD = "TRUNCATE_RELOAD"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class TableSpec:
    """Schema + parse rules for one FDB table.

    Drives `FDBAdapter.parse_table`. New tables in Phase C / Phase D
    become new TableSpec values — no FDBAdapter method needed for
    each one (SPEC §3.7.2.2).

    Fields:
      table_name: filename inside the zip (no extension); equals the
                  literal FDB table name (e.g. ``RNP3_NDC_PRICE``).
      columns:    column order — must match the DDL byte-for-byte.
      coercers:   raw_str → typed value, per column. Coercer raising
                  ValueError / InvalidOperation / InvalidNDCError causes
                  the row to be logged + skipped (does NOT abort parsing).
      nullable:   columns where empty string → None (bypasses coercer).
      sentinel_filter: row filter applied AFTER coercion. Rows where
                  the predicate returns True are SKIPPED.
                  E.g. RNP3 PRICE_TYPE='14' (NOPRC).
      has_transaction_code: True for UPD-shape files where each row is
                  prefixed with A/C/D + delimiter. parse_table extracts
                  the prefix into ``transaction_code``.
                  False for DB.zip files (treated as 'A' per §4.4).

    B9 extension fields (additive; backward-compat defaults — Phase 09
    TableSpecs unchanged):
      tier:               effort-classification per `recon.md` §3.
      record_counts_key:  key for row-count reconciliation against
                          FDB's `RECORD_COUNTS.TXT` manifest.
                          Defaults to `table_name` if None.
      loader_group:       tier-loader registration label
                          (e.g., "fdb_tier_a" — loaders register by group).
                          Defaults to None (single-tier Phase 09 behavior).
      delta_semantics:    how weekly delta is applied — per codex
                          ADVERSARIAL A4 mitigation. UNKNOWN preserves
                          Phase 09 behavior (treated as APPEND_ONLY
                          downstream for backward-compat).
      natural_key:        tuple of column names that form the table's
                          natural key (PRIMARY KEY in the emitted DDL).
                          Required for `UPSERT_BY_NATURAL_KEY` /
                          `UPSERT_WITH_EFFECTIVE_DATE` semantics —
                          Postgres `ON CONFLICT` needs a matching
                          unique constraint surface. Empty default
                          preserves Phase 09 specs (RNP3 uses a
                          composite unique covered separately by the
                          0008 migration).  Codex B9.B GATE-CLOSE
                          R1 HIGH 2 mitigation.
    """

    table_name: str
    columns: Sequence[str]
    coercers: dict[str, Callable[[str], Any]]
    nullable: frozenset[str] = field(default_factory=frozenset)
    sentinel_filter: Callable[[dict[str, Any]], bool] | None = None
    has_transaction_code: bool = False
    # B9 additive fields — defaults preserve Phase 09 behavior
    tier: Tier = Tier.UNKNOWN
    record_counts_key: str | None = None
    loader_group: str | None = None
    delta_semantics: DeltaSemantics = DeltaSemantics.UNKNOWN
    natural_key: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------


class FDBAdapter(ABC):
    """Abstract interface for the FDB NDDF Plus delivery.

    Concerns: locating the latest drop; streaming individual table
    files; parsing pipe-delimited latin-1 rows into typed dicts via
    TableSpec. Loading into Postgres is delegated to the ingester
    service layer (Phase 09.7).
    """

    @abstractmethod
    def discover_latest_drop(self) -> FDBDrop:  # pragma: no cover - abstract
        """Return the FDB drop folder pointed at by ``Current/``.

        Resolves the symlink/junction; reads NDDF_PRODUCT_INFO.TXT
        (single-line YYYYMMDD) to confirm the drop date matches the
        folder name. Raises FDBDropError on mismatch.
        """

    @abstractmethod
    def open_table(
        self,
        drop: FDBDrop,
        table_name: str,
        *,
        source: str = "DB",
    ) -> Iterator[bytes]:  # pragma: no cover - abstract
        """Stream raw bytes for a single table file inside the chosen zip.

        ``source`` ∈ {"DB", "UPD"} — picks which zip to open. Streaming
        generator — never materializes the full file in memory (RNP3
        is 673 MB uncompressed).
        """

    @abstractmethod
    def parse_table(
        self,
        drop: FDBDrop,
        spec: TableSpec,
        *,
        source: str = "DB",
    ) -> Iterator[dict[str, Any]]:  # pragma: no cover - abstract
        """Parse one FDB table per the given TableSpec.

        Yields one dict per row with typed fields per spec.coercers.

        Behavior contract:
          * If spec.has_transaction_code, leading 'A'/'C'/'D' field is
            stripped and stored as ``transaction_code``. Otherwise rows
            are emitted with ``transaction_code='A'`` (DB.zip baseline,
            §4.4).
          * ``drop_sequence`` = parser line index within the file
            (0-indexed). Required for §4.4 stable same-as_of_date D+A
            ordering.
          * Rows where ``spec.sentinel_filter`` returns True are SKIPPED.
          * Rows whose field count != len(spec.columns) (after the
            optional A/C/D prefix) are LOGGED + SKIPPED with
            ``ingest_field_count_mismatch``.
          * Rows whose coercion raises ValueError / InvalidOperation /
            InvalidNDCError are LOGGED + SKIPPED with
            ``ingest_row_invalid``.
          * The yielded dict adds drop-level provenance:
            ``as_of_date = drop.drop_date``.
        """


# ---------------------------------------------------------------------------
# Streaming primitive
# ---------------------------------------------------------------------------


def _stream_pipe_rows(
    zip_path: Path, table_name: str, *, chunk_bytes: int = 2 * 1024 * 1024,
) -> Iterator[list[str]]:
    """Stream one row at a time from a table inside an FDB zip.

    Verified format (SPEC §2.2):
      * pipe (|) delimiter
      * latin-1 encoding (Windows-1252 superset)
      * CRLF (\\r\\n) line terminator
      * no header row
      * filename = literal table name (no extension)

    Yields list[str] of raw fields. No type coercion — callers decode
    via TableSpec.coercers in `parse_table`.

    Memory budget: peak is bounded by ``chunk_bytes`` + one row buffer.
    Default 2 MB chunk handles RNP3's 673 MB uncompressed body without
    materializing the file.
    """
    with zipfile.ZipFile(zip_path) as z:
        target = next(
            (n for n in z.namelist() if n.endswith(f"/{table_name}") or n == table_name),
            None,
        )
        if target is None:
            raise FileNotFoundError(
                f"FDB table '{table_name}' not found in zip '{zip_path.name}'"
            )
        with z.open(target) as f:
            buf = b""
            for chunk in iter(lambda: f.read(chunk_bytes), b""):
                buf += chunk
                *lines, buf = buf.split(b"\r\n")
                for line in lines:
                    if not line:
                        continue
                    yield line.decode("latin-1").split("|")
            # Trailing line without CRLF terminator (defensive — FDB
            # files do terminate, but guard against operator-edited
            # samples).
            if buf:
                yield buf.decode("latin-1").split("|")


# ---------------------------------------------------------------------------
# Concrete adapter — local file system
# ---------------------------------------------------------------------------


class FDBLocalDropAdapter(FDBAdapter):
    """File-system FDBAdapter for operator-managed drops.

    The vendor (FDB) delivers via FTP. Operator downloads + extracts to
    ``data/reference/fdb/TEL251759D/<DATE>.TEL251759D/`` and updates the
    ``Current/`` pointer. This adapter consumes from there; it does NOT
    automate the FTP fetch (operator concern; deferred to a future wave).
    """

    def __init__(self, root: Path) -> None:
        # root = data/reference/fdb/TEL251759D/
        self._root = root

    # ------------------------------------------------------------------
    # discover_latest_drop
    # ------------------------------------------------------------------

    def discover_latest_drop(self) -> FDBDrop:
        current = self._root / "Current"
        # Resolve symlink/NTFS-junction; on Windows the resolution is
        # handled by Path.resolve() since 3.6.
        resolved = current.resolve()

        drop_date, license_code = _parse_drop_folder_name(resolved.name)

        # Cross-check NDDF_PRODUCT_INFO.TXT (single-line YYYYMMDD).
        product_info_path = resolved / "NDDF_PRODUCT_INFO.TXT"
        product_info = product_info_path.read_text().strip()
        if not _FDB_DATE_RE.fullmatch(product_info):
            raise FDBDropError(
                f"NDDF_PRODUCT_INFO.TXT contents '{product_info}' "
                f"does not match expected YYYYMMDD format"
            )
        # Folder name encodes the vendor DELIVERY date. NDDF_PRODUCT_INFO
        # encodes the data CUTOFF date — vendor builds the drop a few days
        # before shipping it, so cutoff < delivery is normal. Wave B7 found
        # both 06MAY2026 and 29APR2026 drops had inner dates 6 days earlier.
        # Allow a tolerance of 30 days (weekly drops with normal delivery
        # lag stay well under). A future-dated cutoff (cutoff > delivery)
        # is suspicious — keep that as an error.
        info_date = datetime.strptime(product_info, "%Y%m%d").date()
        delta_days = (drop_date - info_date).days
        if delta_days < 0:
            # Inner date is AFTER delivery date — vendor data inconsistency
            raise FDBDropError(
                f"NDDF_PRODUCT_INFO.TXT date {product_info} is AFTER "
                f"folder name drop_date {drop_date.isoformat()} — refusing"
            )
        if delta_days > 30:
            raise FDBDropError(
                f"NDDF_PRODUCT_INFO.TXT date {product_info} is more than "
                f"30 days before folder name drop_date {drop_date.isoformat()} "
                f"({delta_days} days) — drops should ship weekly"
            )
        if delta_days > 0:
            _log.warning(
                "FDB drop %s has data cutoff %s (%d day delivery lag) — "
                "expected for normal vendor schedule",
                drop_date.isoformat(), info_date.isoformat(), delta_days,
            )

        return FDBDrop(
            drop_date=drop_date,
            license_code=license_code,
            db_zip_path=resolved / "NDDF Plus DB" / "NDDF PLUS DB.zip",
            ddl_zip_path=resolved / "NDDF Plus DDL" / "NDDF PLUS DDL.zip",
            upd_zip_path=resolved / "NDDF Plus UPD" / "NDDF PLUS UPD.zip",
            highlights_zip_path=resolved / "FDB_CLINICAL_HIGHLIGHTS.ZIP",
            record_counts_path=resolved / "RECORD_COUNTS.TXT",
        )

    # ------------------------------------------------------------------
    # open_table
    # ------------------------------------------------------------------

    def open_table(
        self,
        drop: FDBDrop,
        table_name: str,
        *,
        source: str = "DB",
    ) -> Iterator[bytes]:
        zip_path = drop.upd_zip_path if source == "UPD" else drop.db_zip_path
        with zipfile.ZipFile(zip_path) as z:
            target = next(
                (n for n in z.namelist() if n.endswith(f"/{table_name}") or n == table_name),
                None,
            )
            if target is None:
                raise FileNotFoundError(
                    f"FDB table '{table_name}' not found in {zip_path.name}"
                )
            with z.open(target) as f:
                yield from iter(lambda: f.read(2 * 1024 * 1024), b"")

    # ------------------------------------------------------------------
    # parse_table — generic body (works for any TableSpec)
    # ------------------------------------------------------------------

    def parse_table(
        self,
        drop: FDBDrop,
        spec: TableSpec,
        *,
        source: str = "DB",
    ) -> Iterator[dict[str, Any]]:
        rows_yielded = 0
        rows_skipped_filter = 0
        zip_path = drop.upd_zip_path if source == "UPD" else drop.db_zip_path
        expected_cols = len(spec.columns)

        for line_idx, fields in enumerate(_stream_pipe_rows(zip_path, spec.table_name)):
            # Strip transaction-code prefix for UPD-shape files.
            if spec.has_transaction_code:
                if not fields or fields[0] not in {"A", "C", "D"}:
                    _log.warning(
                        "fdb_table_transaction_code_missing",
                        extra={
                            "ingest_table": spec.table_name,
                            "ingest_line": line_idx,
                        },
                    )
                    continue
                transaction_code = fields[0]
                fields = fields[1:]
            else:
                transaction_code = "A"  # DB.zip rows treated as Add per §4.4.

            if len(fields) != expected_cols:
                _log.warning(
                    "fdb_table_field_count_mismatch",
                    extra={
                        "ingest_table": spec.table_name,
                        "ingest_field_count": len(fields),
                        "ingest_expected": expected_cols,
                        "ingest_row_sample": "|".join(fields)[:200],
                    },
                )
                continue

            try:
                row: dict[str, Any] = {
                    col: (
                        None
                        if (col in spec.nullable and not raw)
                        else spec.coercers[col](raw)
                    )
                    for col, raw in zip(spec.columns, fields, strict=True)
                }
            except (ValueError, InvalidOperation, InvalidNDCError) as e:
                _log.warning(
                    "fdb_table_row_invalid",
                    extra={
                        "ingest_table": spec.table_name,
                        "ingest_error": type(e).__name__,
                        "ingest_message": str(e),
                    },
                )
                continue

            # Sentinel filter (e.g. RNP3 PRICE_TYPE='14' NOPRC).
            if spec.sentinel_filter and spec.sentinel_filter(row):
                rows_skipped_filter += 1
                continue

            row["transaction_code"] = transaction_code
            row["drop_sequence"] = line_idx
            row["as_of_date"] = drop.drop_date
            yield row
            rows_yielded += 1

        _log.info(
            "fdb_table_parse_complete",
            extra={
                "ingest_table": spec.table_name,
                "ingest_rows_yielded": rows_yielded,
                "ingest_rows_skipped_filter": rows_skipped_filter,
            },
        )


# ---------------------------------------------------------------------------
# Phase 8 TableSpec values (SPEC §3.7.2)
# ---------------------------------------------------------------------------


RNP3_NDC_PRICE = TableSpec(
    table_name="RNP3_NDC_PRICE",
    columns=("ndc", "price_type", "effective_date_raw", "price_raw"),
    coercers={
        "ndc": normalize_ndc,                  # → 11-digit normalized NDC
        "price_type": str,                     # 2-char legacy NPT_TYPE
        "effective_date_raw": _parse_fdb_date, # YYYYMMDD → date
        "price_raw": Decimal,                  # NUMERIC(16,5) — never float
    },
    sentinel_filter=lambda r: r["price_type"] == "14",  # NOPRC — skip
    has_transaction_code=False,                # DB.zip
)

RNP3_NDC_PRICE_UPD = replace(RNP3_NDC_PRICE, has_transaction_code=True)


RPRDPTD0_PRICE_TYPE_DESC = TableSpec(
    table_name="RPRDPTD0_PRICE_TYPE_DESC",
    columns=(
        "price_type_id",
        "short_desc",
        "long_desc",
        "npt_type",
        "price_type_definition",
    ),
    coercers={
        "price_type_id": int,
        "short_desc": str,
        "long_desc": str,
        "npt_type": str,
        "price_type_definition": str,
    },
    nullable=frozenset({"long_desc", "npt_type", "price_type_definition"}),
    has_transaction_code=False,
)


RNPTYPD0_NDC_PRICE_TYPE_DESC = TableSpec(  # legacy 2-char-only catalog
    table_name="RNPTYPD0_NDC_PRICE_TYPE_DESC",
    columns=("npt_type", "short_desc"),
    coercers={"npt_type": str, "short_desc": str},
    has_transaction_code=False,
)


# ---------------------------------------------------------------------------
# Hot-path typed wrapper (SPEC §3.7.2.1)
# ---------------------------------------------------------------------------


class _RNP3Row(TypedDict):
    """Typed row shape for RNP3_NDC_PRICE consumers (hot path).

    Field renames vs. raw TableSpec output:
      ndc → ndc_11   (matches schema column name)
      effective_date_raw → effective_date
      price_raw → price
    """

    ndc_11: str
    price_type: str
    effective_date: date
    price: Decimal
    transaction_code: str  # 'A' for DB.zip; 'A'/'C'/'D' for UPD.zip
    drop_sequence: int
    as_of_date: date


def parse_rnp3(
    adapter: FDBAdapter,
    drop: FDBDrop,
    *,
    source: str = "DB",
) -> Iterator[_RNP3Row]:
    """Hot-path RNP3 wrapper — typed return for the ingester's main loop.

    For all other tables, callers use ``adapter.parse_table(drop, spec)``
    directly and treat the returned dicts as ``Mapping[str, Any]``.
    """
    spec = RNP3_NDC_PRICE_UPD if source == "UPD" else RNP3_NDC_PRICE
    for row in adapter.parse_table(drop, spec, source=source):
        yield _RNP3Row(
            ndc_11=row["ndc"],
            price_type=row["price_type"],
            effective_date=row["effective_date_raw"],
            price=row["price_raw"],
            transaction_code=row.get("transaction_code", "A"),
            drop_sequence=row["drop_sequence"],
            as_of_date=row["as_of_date"],
        )


__all__ = [
    "FDBAdapter",
    "FDBDrop",
    "FDBDropError",
    "FDBLocalDropAdapter",
    "RNP3_NDC_PRICE",
    "RNP3_NDC_PRICE_UPD",
    "RNPTYPD0_NDC_PRICE_TYPE_DESC",
    "RPRDPTD0_PRICE_TYPE_DESC",
    "TableSpec",
    "parse_rnp3",
]
