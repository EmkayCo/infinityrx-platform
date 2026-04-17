"""OFAC SDN (Specially Designated Nationals) ingestion source.

Loads the four relational CSV files that make up the OFAC SDN
distribution into shared.ofac_sdn (+ 3 child tables):

  data/reference/ofac-sdn/
    sdn.csv           -> shared.ofac_sdn          (parent, PK ent_num)
    add.csv           -> shared.ofac_sdn_addresses
    alt.csv           -> shared.ofac_sdn_aliases
    sdn_comments.csv  -> shared.ofac_sdn_comments

Wave 9 scope is local-file ingest only — files are pre-staged. The
HTTP download path stays a stub for now; OFAC moved its distribution
behind sanctionslistservice.ofac.treas.gov and the add.csv/alt.csv
endpoints currently 400 there, so driving this from HTTP requires
handling that fallback. Deferred.

OFAC file format gotchas (all four files):

  - NO HEADERS. Column order is fixed by the OFAC data dictionary.
    sdn.csv has 12 columns, add.csv has 6, alt.csv has 5,
    sdn_comments.csv has 2.
  - Encoding is latin-1, not UTF-8. Some rows contain characters that
    would blow up a utf-8 decode.
  - Sentinel value "-0- " (with trailing space) means "no value" —
    must be normalised to NULL everywhere.
  - Some quoted fields contain embedded newlines — must use csv.reader,
    not line-at-a-time parsing.
  - Fields come with surrounding whitespace inside the quotes; strip.

Upsert model:

  - Parent (ofac_sdn): flush_upsert_batch by ent_num. ON CONFLICT DO
    UPDATE so re-ingests refresh parent attributes.
  - Children (addresses / aliases / comments): flush_scoped_replace_batch
    scoped by ent_num. Delete every ent_num that appears in the
    incoming file, then re-insert. Rows for ent_nums removed from the
    source between runs stay in the table unless we explicitly prune;
    that's deliberate for now (full replace would break any downstream
    reference). If OFAC removes an entity entirely, its parent row gets
    deleted by the loader's parent prune (not implemented this wave —
    follow-up).

LESSON-004: \\A...\\Z anchors for any regex validation.
LESSON-005: All log extra keys prefixed with ingest_.
LESSON-011: Global reference table — no TenantScopedMixin.
"""

from __future__ import annotations

import csv
import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from shared.data_ingestion.base import DataSourceIngester, IngestionResult
from shared.data_ingestion.field_registry import register_field

logger = logging.getLogger(__name__)

_SOURCE_NAME = "ofac_sdn"
_DATA_DIR = Path("data/reference/ofac-sdn")
_ENCODING = "latin-1"
_BATCH_SIZE = 1_000

# Sentinel OFAC uses for "no value" — normalise to None everywhere.
# Variations seen: "-0-", "-0- " (trailing space after the dash). We
# match the stripped form.
_OFAC_NULL_SENTINELS: frozenset[str] = frozenset({"-0-", ""})

# ---------------------------------------------------------------------------
# Column layouts per OFAC data dictionary
# https://www.treasury.gov/ofac/downloads/readme.txt
# ---------------------------------------------------------------------------

_SDN_COLUMNS = (
    "ent_num", "sdn_name", "sdn_type", "program", "title",
    "call_sign", "vess_type", "tonnage", "grt", "vess_flag",
    "vess_owner", "remarks",
)
_ADD_COLUMNS = (
    "ent_num", "add_num", "address", "city_state_zip", "country",
    "add_remarks",
)
_ALT_COLUMNS = (
    "ent_num", "alt_num", "alt_type", "alt_name", "alt_remarks",
)
_COMMENTS_COLUMNS = ("ent_num", "remarks3")

# ---------------------------------------------------------------------------
# Field registry (module import time)
# ---------------------------------------------------------------------------

for _col in _SDN_COLUMNS:
    register_field(
        source=_SOURCE_NAME,
        table="shared.ofac_sdn",
        column=_col,
        description=f"OFAC SDN {_col} column (from sdn.csv, positional)",
        source_file="sdn.csv",
        source_position=str(_SDN_COLUMNS.index(_col)),
        data_type="int" if _col == "ent_num" else "str",
    )
for _col in _ADD_COLUMNS:
    register_field(
        source=_SOURCE_NAME,
        table="shared.ofac_sdn_addresses",
        column=_col,
        description=f"OFAC SDN address {_col} column (from add.csv, positional)",
        source_file="add.csv",
        source_position=str(_ADD_COLUMNS.index(_col)),
        data_type="int" if _col in ("ent_num", "add_num") else "str",
    )
for _col in _ALT_COLUMNS:
    register_field(
        source=_SOURCE_NAME,
        table="shared.ofac_sdn_aliases",
        column=_col,
        description=f"OFAC SDN alias {_col} column (from alt.csv, positional)",
        source_file="alt.csv",
        source_position=str(_ALT_COLUMNS.index(_col)),
        data_type="int" if _col in ("ent_num", "alt_num") else "str",
    )
for _col in _COMMENTS_COLUMNS:
    register_field(
        source=_SOURCE_NAME,
        table="shared.ofac_sdn_comments",
        column=_col,
        description=f"OFAC SDN comments {_col} column (from sdn_comments.csv, positional)",
        source_file="sdn_comments.csv",
        source_position=str(_COMMENTS_COLUMNS.index(_col)),
        data_type="int" if _col == "ent_num" else "str",
    )


# ---------------------------------------------------------------------------
# Parse helpers
# ---------------------------------------------------------------------------


def _normalise(value: str | None) -> str | None:
    """Strip whitespace, treat '-0-' or empty as NULL."""
    if value is None:
        return None
    stripped = value.strip()
    if stripped in _OFAC_NULL_SENTINELS:
        return None
    return stripped


def _parse_int(value: str | None) -> int | None:
    v = _normalise(value)
    if v is None:
        return None
    try:
        return int(v)
    except ValueError:
        return None


def _parse_csv_positional(
    path: Path, columns: tuple[str, ...]
) -> Iterator[dict[str, Any]]:
    """Stream a headerless OFAC CSV, yielding one dict per row.

    Uses csv.reader (not DictReader) because OFAC files have no header
    line. Column count is validated per row — a row with the wrong
    column count is logged and skipped rather than silently producing
    misaligned data.
    """
    with path.open(newline="", encoding=_ENCODING, errors="replace") as fh:
        reader = csv.reader(fh)
        for row_num, fields in enumerate(reader, start=1):
            if len(fields) != len(columns):
                logger.warning(
                    "OFAC: row column-count mismatch — skipping",
                    extra={
                        "ingest_source": _SOURCE_NAME,
                        "ofac_file": path.name,
                        "ofac_row": row_num,
                        "ofac_expected": len(columns),
                        "ofac_got": len(fields),
                    },
                )
                continue
            record: dict[str, Any] = {}
            for col, raw in zip(columns, fields, strict=True):
                if col.endswith("_num") or col == "ent_num":
                    record[col] = _parse_int(raw)
                else:
                    record[col] = _normalise(raw)
            yield record


def _row_with_payload(record: dict[str, Any]) -> dict[str, Any]:
    """Attach a JSON copy of the parsed fields as ``raw_payload``.

    json.dumps with default=str so any stray non-serialisable value
    (shouldn't happen post-normalise, but defensively) doesn't fail
    the batch.
    """
    return {**record, "raw_payload": json.dumps(record, default=str)}


def _parse_sdn(path: Path) -> Iterator[dict[str, Any]]:
    for r in _parse_csv_positional(path, _SDN_COLUMNS):
        if r.get("ent_num") is None:
            continue
        yield {"table": "ofac_sdn", "row": _row_with_payload(r)}


def _parse_addresses(path: Path) -> Iterator[dict[str, Any]]:
    for r in _parse_csv_positional(path, _ADD_COLUMNS):
        if r.get("ent_num") is None or r.get("add_num") is None:
            continue
        yield {"table": "ofac_sdn_addresses", "row": _row_with_payload(r)}


def _parse_aliases(path: Path) -> Iterator[dict[str, Any]]:
    for r in _parse_csv_positional(path, _ALT_COLUMNS):
        if r.get("ent_num") is None or r.get("alt_num") is None:
            continue
        yield {"table": "ofac_sdn_aliases", "row": _row_with_payload(r)}


def _parse_comments(path: Path) -> Iterator[dict[str, Any]]:
    for r in _parse_csv_positional(path, _COMMENTS_COLUMNS):
        if r.get("ent_num") is None:
            continue
        yield {"table": "ofac_sdn_comments", "row": _row_with_payload(r)}


# ---------------------------------------------------------------------------
# Ingester
# ---------------------------------------------------------------------------


class OfacSdnIngester(DataSourceIngester):
    """OFAC SDN ingester — local-file only in Wave 9.

    LESSON-011: Global reference data — no TenantScopedMixin.
    """

    source_name = _SOURCE_NAME

    async def download(self) -> Path:
        """Wave 9: files are pre-staged. Return the local data dir.

        Follow-up: HTTP wiring against sanctionslistservice.ofac.treas.gov
        with fallback handling for the intermittent 400s on add.csv/alt.csv.
        """
        if not _DATA_DIR.is_dir():
            raise FileNotFoundError(
                f"OFAC SDN data dir missing: {_DATA_DIR}. Stage the 4 CSVs "
                "before running ingestion."
            )
        return _DATA_DIR

    def parse(self, file_path: Path) -> Iterator[dict[str, Any]]:
        """Stream records from all 4 OFAC CSVs in topological order.

        Parent (sdn.csv) yields first so load()'s first-non-parent record
        trigger can flush the parent buffer before any child INSERT needs
        the FK-target row to exist.
        """
        sdn = file_path / "sdn.csv"
        add = file_path / "add.csv"
        alt = file_path / "alt.csv"
        com = file_path / "sdn_comments.csv"

        for p, parser in (
            (sdn, _parse_sdn),
            (add, _parse_addresses),
            (alt, _parse_aliases),
            (com, _parse_comments),
        ):
            if not p.is_file():
                logger.warning(
                    "OFAC: expected file missing — skipping",
                    extra={"ingest_source": self.source_name, "ofac_file": str(p)},
                )
                continue
            yield from parser(p)

    async def load(self, records: Iterator[dict[str, Any]]) -> IngestionResult:
        """Flush parent first, then child scopes.

        Pattern: buffer ``ofac_sdn`` rows in memory until the first
        non-parent record arrives; flush parent via flush_upsert_batch;
        then stream children into per-table lists and flush each with
        flush_scoped_replace_batch in one pass at the end. OFAC totals
        are small (~65K rows across all 4 tables) so a one-shot child
        flush is simpler than NCPDP-style per-batch cross-scope tracking
        and avoids the duplicate-DELETE-across-batches problem.
        """
        from shared.data_ingestion.batching import (
            ErrorAggregator,
            flush_scoped_replace_batch,
            flush_upsert_batch,
        )
        from shared.db.models.ofac_sdn import (
            OfacSdn,
            OfacSdnAddress,
            OfacSdnAlias,
            OfacSdnComment,
        )

        sdn_table = OfacSdn.__table__
        addresses_table = OfacSdnAddress.__table__
        aliases_table = OfacSdnAlias.__table__
        comments_table = OfacSdnComment.__table__

        errors = ErrorAggregator()
        parent_buffer: list[dict[str, Any]] = []
        child_buffers: dict[str, list[dict[str, Any]]] = {
            "ofac_sdn_addresses": [],
            "ofac_sdn_aliases": [],
            "ofac_sdn_comments": [],
        }
        processed = 0
        inserted = 0
        skipped = 0
        parent_flushed = False

        def _flush_parent() -> None:
            nonlocal parent_flushed, inserted, skipped
            if parent_flushed:
                return
            parent_flushed = True
            for i in range(0, len(parent_buffer), _BATCH_SIZE):
                chunk = parent_buffer[i : i + _BATCH_SIZE]
                ins, dd = flush_upsert_batch(
                    self._db,
                    source_name=self.source_name,
                    table=sdn_table,
                    unique_key=["ent_num"],
                    rows=chunk,
                    errors=errors,
                )
                inserted += ins
                skipped += dd
            parent_buffer.clear()

        for record in records:
            tbl = record.get("table")
            row = record.get("row")
            if not tbl or not row:
                errors.record("empty_record", "missing table or row")
                continue
            processed += 1

            if tbl == "ofac_sdn":
                if parent_flushed:
                    errors.record(
                        "parent_after_flush",
                        "parent row after parent buffer flushed",
                        raw_row=row,
                    )
                    continue
                parent_buffer.append(row)
                continue

            if not parent_flushed:
                _flush_parent()

            if tbl in child_buffers:
                child_buffers[tbl].append(row)
            else:
                errors.record("unknown_table", f"no config for {tbl}", raw_row=row)

        _flush_parent()

        child_specs = {
            "ofac_sdn_addresses": (
                addresses_table, ["ent_num"], ["ent_num", "add_num"],
            ),
            "ofac_sdn_aliases": (
                aliases_table, ["ent_num"], ["ent_num", "alt_num"],
            ),
            "ofac_sdn_comments": (
                comments_table, ["ent_num"], ["ent_num"],
            ),
        }
        for name, rows in child_buffers.items():
            if not rows:
                continue
            table, scope_key, unique_key = child_specs[name]
            ins, dd = flush_scoped_replace_batch(
                self._db,
                source_name=self.source_name,
                table=table,
                scope_key=scope_key,
                unique_key=unique_key,
                rows=rows,
                errors=errors,
            )
            inserted += ins
            skipped += dd

        errors.log_summary(source_name=self.source_name)

        logger.info(
            "OFAC SDN load complete",
            extra={
                "ingest_source": self.source_name,
                "ingest_records_processed": processed,
                "ingest_records_inserted": inserted,
                "ingest_records_skipped": skipped,
                "ingest_records_errored": errors.total_errors,
            },
        )

        return IngestionResult(
            source=self.source_name,
            status="completed",
            records_processed=processed,
            records_inserted=inserted,
            records_skipped=skipped,
            records_errored=errors.total_errors,
        )


__all__ = [
    "_ADD_COLUMNS",
    "_ALT_COLUMNS",
    "_COMMENTS_COLUMNS",
    "_SDN_COLUMNS",
    "OfacSdnIngester",
    "_normalise",
    "_parse_addresses",
    "_parse_aliases",
    "_parse_comments",
    "_parse_csv_positional",
    "_parse_int",
    "_parse_sdn",
]
