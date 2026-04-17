"""HCPCS Level II (Healthcare Common Procedure Coding System) loader.

CMS publishes the Level II codeset quarterly at:

  https://www.cms.gov/medicare/coding-billing/healthcare-common-procedure-system/quarterly-update

File naming: ``{january|april|july|october}-YYYY-alpha-numeric-hcpcs-file[s]?.zip``.
Level I (CPT) is AMA-licensed and **not** in this public distribution — the
~16k records in this file are all Level II codes (A-V prefix) plus ~580
2-char modifier codes.

Inside the zip, we parse the authoritative fixed-width file
``HCPC<YYYY>_<MMM>_ANWEB.txt`` (1 record = 320 chars, 31 fields per the
included record-layout document). Some codes span multiple records for
long descriptions > 80 chars — these are aggregated by the same code with
different sequence numbers.

Row layout (1-indexed per CMS spec; 0-indexed in slice bounds below):
  [0,   5)  HCPCS code (CHAR 5, right-padded; modifiers have 3 leading spaces)
  [5,  10)  sequence number  (NUM 5)
  [10, 11)  record ID code
  [11, 91)  long description  (CHAR 80)
  [91, 119) short description (CHAR 28)
  [119, 121) pricing indicator
  [229, 230) coverage code
  [265, 268) anesthesia base units (NUM 3)
  [268, 276) added date YYYYMMDD
  [276, 284) action effective date YYYYMMDD
  [284, 292) termination date YYYYMMDD
  [292, 293) action code

The target table ``shared.hcpcs_codes`` is versioned on
``(code, is_modifier, publication_quarter)``. Each quarterly load upserts
against the unique key.

LESSON-004: \\A...\\Z regex anchors.
LESSON-005: log keys prefixed with ``ingest_``.
LESSON-011: Global reference — no TenantScopedMixin.
"""

from __future__ import annotations

import logging
import re
import zipfile
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import Table

from shared.data_ingestion.base import DataSourceIngester, IngestionResult
from shared.data_ingestion.batching import ErrorAggregator, flush_upsert_batch
from shared.data_ingestion.downloader import download_to_file

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SOURCE_NAME = "hcpcs"
_CMS_INDEX_URL = (
    "https://www.cms.gov/medicare/coding-billing/"
    "healthcare-common-procedure-system/quarterly-update"
)
_CMS_FILE_BASE = "https://www.cms.gov"

# Filename pattern: {january|april|july|october}-YYYY-alpha-numeric-hcpcs-file[s]?.zip
# Both "-file" and "-files" variants have been published by CMS across years
# (the 2024 releases used plural, most others use singular).
_MONTH_MAP = {
    "january": 1,
    "april": 4,
    "july": 7,
    "october": 10,
}

_QUARTER_ZIP_RE = re.compile(
    r"\A(january|april|july|october)-(\d{4})-alpha-numeric-hcpcs-files?\.zip\Z",
    re.IGNORECASE,
)

# Inner main-text-file pattern: HCPC<YYYY>_<3-letter month>_ANWEB.txt
_INNER_TXT_RE = re.compile(
    r"HCPC\d{4}_(?:JAN|APR|JUL|OCT)_ANWEB\.txt\Z",
    re.IGNORECASE,
)

_MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
_CACHE_DIR = Path("data/reference/hcpcs")
_BATCH_SIZE = 2_000

# Fixed-width positions (0-indexed half-open slices)
_POS_CODE = slice(0, 5)
_POS_SEQ = slice(5, 10)
_POS_LONG = slice(11, 91)
_POS_SHORT = slice(91, 119)
_POS_PRICING = slice(119, 121)
_POS_COVERAGE = slice(229, 230)
_POS_ANESTH = slice(265, 268)
_POS_ADDED = slice(268, 276)
_POS_ACTION_EFF = slice(276, 284)
_POS_TERM = slice(284, 292)
_POS_ACTION = slice(292, 293)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _effective_date_from_filename(filename: str) -> date:
    """Return the publication effective date for a quarterly zip filename."""
    m = _QUARTER_ZIP_RE.match(filename)
    if m is None:
        raise ValueError(f"Unrecognized HCPCS filename: {filename!r}")
    month = _MONTH_MAP[m.group(1).lower()]
    year = int(m.group(2))
    return date(year, month, 1)


def _publication_quarter_from_date(d: date) -> str:
    """Format publication_quarter string like "2026Q2" from an effective date."""
    quarter = (d.month - 1) // 3 + 1
    return f"{d.year}Q{quarter}"


def _choose_latest_filename(hrefs: list[str]) -> str | None:
    """Pick the newest quarterly HCPCS zip from scraped page hrefs."""
    best_date: date | None = None
    best_filename: str | None = None
    for href in hrefs:
        fn = href.rsplit("/", 1)[-1]
        try:
            ed = _effective_date_from_filename(fn)
        except ValueError:
            continue
        if best_date is None or ed > best_date:
            best_date = ed
            best_filename = fn
    return best_filename


def _parse_date_yyyymmdd(raw: str | None) -> date | None:
    """Parse CMS YYYYMMDD date field. ``00000000`` / empty → None."""
    if not raw:
        return None
    s = raw.strip()
    if not s or s == "00000000":
        return None
    try:
        return date(int(s[0:4]), int(s[4:6]), int(s[6:8]))
    except ValueError:
        return None


def _parse_int_or_none(raw: str | None) -> int | None:
    if not raw:
        return None
    s = raw.strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _strip_or_none(raw: str | None) -> str | None:
    if raw is None:
        return None
    s = raw.strip()
    return s if s else None


def _parse_fixed_width_line(line: str) -> dict[str, Any] | None:
    """Parse one raw HCPCS record into a dict. Returns None for empty lines.

    Does NOT resolve is_modifier vs regular code — that's decided by the
    caller based on whether the 5-char code field has 3 leading spaces.
    """
    if len(line) < 12 or not line.strip():
        return None

    raw_code_field = line[_POS_CODE]  # 5 chars, may have leading spaces (modifier)
    is_modifier = raw_code_field.startswith("   ")
    code = raw_code_field.strip()
    if not code:
        return None

    return {
        "code": code,
        "is_modifier": is_modifier,
        "_sequence": _parse_int_or_none(line[_POS_SEQ]) or 0,
        "long_description_fragment": _strip_or_none(line[_POS_LONG]),
        "short_description": _strip_or_none(line[_POS_SHORT]),
        "pricing_indicator": _strip_or_none(line[_POS_PRICING]),
        "coverage_code": _strip_or_none(line[_POS_COVERAGE]),
        "anesthesia_base_units": _parse_int_or_none(line[_POS_ANESTH]),
        "added_date": _parse_date_yyyymmdd(line[_POS_ADDED]),
        "action_effective_date": _parse_date_yyyymmdd(line[_POS_ACTION_EFF]),
        "termination_date": _parse_date_yyyymmdd(line[_POS_TERM]),
        "action_code": _strip_or_none(line[_POS_ACTION]),
    }


def _aggregate_continuations(
    rows: Iterator[dict[str, Any]],
) -> Iterator[dict[str, Any]]:
    """Fold continuation records (same code, higher sequence) into one row.

    CMS publishes long descriptions > 80 chars as multiple rows with the
    same HCPCS code and different sequence numbers (the "record ID code"
    at position 11 distinguishes primary vs continuation). We emit one
    aggregated row per distinct (code, is_modifier) pair, concatenating
    the description fragments in sequence order and taking the primary
    row's metadata (dates, coverage, etc.).
    """
    current_key: tuple[str, bool] | None = None
    current: dict[str, Any] | None = None
    fragments: list[str] = []

    for row in rows:
        key = (row["code"], row["is_modifier"])
        if current_key is None or key != current_key:
            if current is not None:
                current["long_description"] = " ".join(f for f in fragments if f) or None
                current.pop("long_description_fragment", None)
                current.pop("_sequence", None)
                yield current
            current_key = key
            current = dict(row)
            fragments = [row.get("long_description_fragment") or ""]
        else:
            # Continuation: append fragment. Keep primary row's metadata.
            frag = row.get("long_description_fragment") or ""
            if frag:
                fragments.append(frag)

    if current is not None:
        current["long_description"] = " ".join(f for f in fragments if f) or None
        current.pop("long_description_fragment", None)
        current.pop("_sequence", None)
        yield current


# ---------------------------------------------------------------------------
# Ingester
# ---------------------------------------------------------------------------


class HcpcsIngester(DataSourceIngester):
    """Quarterly full-replace loader for CMS HCPCS Level II codes."""

    source_name = _SOURCE_NAME

    def __init__(self, db_session: Any, *, source_csv: Path | None = None) -> None:
        super().__init__(db_session)
        self._source_override: Path | None = source_csv
        self._override_effective_date: date | None = None

    # ------------------------------------------------------------------
    # download
    # ------------------------------------------------------------------

    async def download(self) -> Path:
        if self._source_override is not None:
            return self._source_override
        filename = await self._resolve_latest_filename()
        if filename is None:
            raise RuntimeError(
                "Could not locate any HCPCS quarterly zip on the CMS index. "
                f"URL template {_CMS_INDEX_URL} may have changed."
            )
        url = f"{_CMS_FILE_BASE}/files/zip/{filename}"
        logger.info(
            "Downloading HCPCS Level II quarterly zip",
            extra={"ingest_source": self.source_name, "ingest_url": url},
        )
        return await download_to_file(
            url, _CACHE_DIR, max_bytes=_MAX_DOWNLOAD_BYTES, timeout_seconds=120.0
        )

    async def _resolve_latest_filename(self) -> str | None:
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "InfinityRx-HCPCS-Loader/1.0"},
        ) as client:
            resp = await client.get(_CMS_INDEX_URL)
            resp.raise_for_status()
        hrefs = re.findall(r'href="([^"]+)"', resp.text)
        return _choose_latest_filename(hrefs)

    # ------------------------------------------------------------------
    # parse
    # ------------------------------------------------------------------

    def parse(self, file_path: Path) -> Iterator[dict[str, Any]]:
        effective_date = self._resolve_effective_date(file_path)
        publication_quarter = _publication_quarter_from_date(effective_date)

        raw_rows = self._iter_raw_rows(file_path)
        for agg in _aggregate_continuations(raw_rows):
            agg["effective_date"] = effective_date
            agg["publication_quarter"] = publication_quarter
            yield agg

    def _iter_raw_rows(self, file_path: Path) -> Iterator[dict[str, Any]]:
        """Yield one parsed dict per raw line (pre-aggregation)."""
        if file_path.suffix.lower() == ".zip":
            with zipfile.ZipFile(file_path) as zf:
                inner_name = next(
                    (n for n in zf.namelist() if _INNER_TXT_RE.search(n)),
                    None,
                )
                if inner_name is None:
                    raise RuntimeError(
                        f"No HCPC<YYYY>_<MMM>_ANWEB.txt inside {file_path.name}"
                    )
                with zf.open(inner_name) as fh:
                    for raw in fh:
                        parsed = _parse_fixed_width_line(
                            raw.decode("latin-1", errors="replace").rstrip("\n")
                        )
                        if parsed is not None:
                            yield parsed
        else:
            with file_path.open("r", encoding="latin-1", errors="replace") as fh:
                for raw in fh:
                    parsed = _parse_fixed_width_line(raw.rstrip("\n"))
                    if parsed is not None:
                        yield parsed

    def _resolve_effective_date(self, file_path: Path) -> date:
        if self._override_effective_date is not None:
            return self._override_effective_date
        try:
            return _effective_date_from_filename(file_path.name)
        except ValueError:
            # Fall back to parsing the inner-file name "HCPC<YYYY>_<MMM>_ANWEB.txt"
            inner = re.match(
                r"\AHCPC(\d{4})_(JAN|APR|JUL|OCT)_ANWEB\.txt\Z",
                file_path.name,
                re.IGNORECASE,
            )
            if inner:
                year = int(inner.group(1))
                month = {"JAN": 1, "APR": 4, "JUL": 7, "OCT": 10}[
                    inner.group(2).upper()
                ]
                return date(year, month, 1)
            raise

    # ------------------------------------------------------------------
    # load
    # ------------------------------------------------------------------

    async def load(self, records: Iterator[dict[str, Any]]) -> IngestionResult:
        table = _get_target_table()
        errors = ErrorAggregator()
        processed = 0
        inserted = 0
        batch: list[dict[str, Any]] = []

        def _flush() -> None:
            nonlocal inserted
            if not batch:
                return
            ins, _dd = flush_upsert_batch(
                self._db,
                source_name=self.source_name,
                table=table,
                unique_key=["code", "is_modifier", "publication_quarter"],
                rows=batch,
                errors=errors,
            )
            inserted += ins
            batch.clear()

        for raw in records:
            processed += 1
            raw["raw_payload"] = {
                k: _json_safe(v) for k, v in raw.items() if k != "raw_payload"
            }
            batch.append(raw)
            if len(batch) >= _BATCH_SIZE:
                _flush()

        _flush()
        errors.log_summary(source_name=self.source_name)

        logger.info(
            "HCPCS load complete",
            extra={
                "ingest_source": self.source_name,
                "ingest_records_processed": processed,
                "ingest_records_inserted": inserted,
                "ingest_records_errored": errors.total_errors,
            },
        )

        return IngestionResult(
            source=self.source_name,
            status="completed",
            records_in_source=processed,
            records_processed=processed,
            records_inserted=inserted,
            records_errored=errors.total_errors,
        )


# ---------------------------------------------------------------------------
# Table + JSON helpers
# ---------------------------------------------------------------------------


def _json_safe(value: Any) -> Any:
    if isinstance(value, date):
        return value.isoformat()
    return value


_cached_table: Table | None = None


def _get_target_table() -> Table:
    global _cached_table
    if _cached_table is None:
        from sqlalchemy import (
            Boolean,
            Column,
            Date,
            DateTime,
            Integer,
            MetaData,
            String,
            Table as _Table,
            Text,
        )
        from sqlalchemy.dialects.postgresql import JSONB

        metadata = MetaData(schema="shared")
        _cached_table = _Table(
            "hcpcs_codes",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("code", String(5), nullable=False),
            Column("is_modifier", Boolean, nullable=False),
            Column("publication_quarter", String(6), nullable=False),
            Column("effective_date", Date, nullable=False),
            Column("long_description", Text),
            Column("short_description", String(28)),
            Column("pricing_indicator", String(2)),
            Column("coverage_code", String(1)),
            Column("anesthesia_base_units", Integer),
            Column("action_code", String(1)),
            Column("added_date", Date),
            Column("action_effective_date", Date),
            Column("termination_date", Date),
            Column("raw_payload", JSONB),
            Column("created_at", DateTime(timezone=True)),
            Column("updated_at", DateTime(timezone=True)),
            schema="shared",
        )
    return _cached_table


__all__ = [
    "HcpcsIngester",
    "_aggregate_continuations",
    "_choose_latest_filename",
    "_effective_date_from_filename",
    "_parse_date_yyyymmdd",
    "_parse_fixed_width_line",
    "_publication_quarter_from_date",
]
