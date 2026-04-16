"""RxNorm DataSourceIngester — NLM normalized drug nomenclature.

Downloads RxNorm from NLM (full release with UMLS_API_KEY, or the no-auth
prescribable subset as fallback), extracts the ZIP, and streams four
pipe-delimited RRF files into drug_database via shared batching primitives:

  RXNCONSO.RRF (18 fields) → drug_database.rxnorm_concepts
  RXNREL.RRF   (16 fields) → drug_database.rxnorm_relationships
  RXNSAT.RRF   (13 fields) → drug_database.rxnorm_attributes
  RXNSTY.RRF   ( 6 fields) → drug_database.rxnorm_semantic_types

After the main upserts commit, two derived crosswalk tables are built via
SQL INSERT…SELECT…ON CONFLICT DO UPDATE (Postgres-only):

  rxnorm_ndc_crosswalk   <- RXNSAT ATN='NDC' joined to RXNCONSO preferred atoms
  rxnorm_atc_crosswalk   <- RXNSAT ATN='ATC' UNION RXNCONSO SAB='ATC'

RXNCONSO column layout (0-indexed, | delimiter, trailing pipe):
  [0]  RXCUI       concept unique ID        ← key field
  [1]  LAT         language
  [2]  TS          term status
  [3]  LUI         lexical unique id
  [4]  STT         string type
  [5]  SUI         string unique id
  [6]  ISPREF      Y/N preferred atom
  [7]  RXAUI       atom unique id
  [8]  SAUI        source atom id
  [9]  SCUI        source concept id
  [10] SDUI        source descriptor id
  [11] SAB         source abbreviation      ← e.g. RXNORM, ATC
  [12] TTY         term type                ← e.g. IN, SBD, SCD, PT
  [13] CODE        source-specific code
  [14] STR         drug name / description  ← stored as str_ (Python reserved)
  [15] SRL         source restriction level
  [16] SUPPRESS    suppressible flag
  [17] CVF         content view flag

NDCs are NOT in RXNCONSO.RRF — they appear in RXNSAT.RRF with ATN='NDC'
and are surfaced via the rxnorm_ndc_crosswalk derived table.

LESSON-011: Global reference data — no TenantScopedMixin.
LESSON-004: \\A...\\Z anchors for regex (none needed in this module).
LESSON-005: log extra keys prefixed with ingest_.
No floats anywhere.
"""

from __future__ import annotations

import logging
import os
import sys
import zipfile
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text

from shared.data_ingestion.base import DataSourceIngester, IngestionResult
from shared.data_ingestion.downloader import download_to_file
from shared.data_ingestion.field_registry import register_field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SOURCE_NAME = "rxnorm"

_UMLS_DOWNLOAD_URL = (
    "https://uts-ws.nlm.nih.gov/download"
    "?url=https://download.nlm.nih.gov/umls/kss/rxnorm/RxNorm_full_current.zip"
    "&apiKey={api_key}"
)
_PRESCRIBABLE_URL = (
    "https://download.nlm.nih.gov/umls/kss/rxnorm/RxNorm_weekly_prescribe_current.zip"
)

_CACHE_DIR = Path("/tmp/ifx_ingest/rxnorm")
_MAX_DOWNLOAD_BYTES = 800 * 1024 * 1024  # full release ~400 MB

_BATCH_SIZE = 1_000

# RRF field specs (0-indexed list of names; "str" → "str_" to avoid
# clobbering Python's built-in).
_RXNCONSO_FIELDS = [
    "rxcui", "lat", "ts", "lui", "stt", "sui", "ispref",
    "rxaui", "saui", "scui", "sdui", "sab", "tty", "code",
    "str", "srl", "suppress", "cvf",
]
_RXNREL_FIELDS = [
    "rxcui1", "rxaui1", "stype1", "rel", "rxcui2", "rxaui2",
    "stype2", "rela", "rui", "srui", "sab", "sl", "rg",
    "dir", "suppress", "cvf",
]
_RXNSAT_FIELDS = [
    "rxcui", "lui", "sui", "rxaui", "stype", "code",
    "atui", "satui", "atn", "sab", "atv", "suppress", "cvf",
]
_RXNSTY_FIELDS = [
    "rxcui", "tui", "stn", "sty", "atui", "cvf",
]

_FILE_FIELD_MAP: dict[str, list[str]] = {
    "RXNCONSO.RRF": _RXNCONSO_FIELDS,
    "RXNREL.RRF": _RXNREL_FIELDS,
    "RXNSAT.RRF": _RXNSAT_FIELDS,
    "RXNSTY.RRF": _RXNSTY_FIELDS,
}

# ---------------------------------------------------------------------------
# Field registry — run at module import time
# ---------------------------------------------------------------------------

_TABLE_PREFIX = "drug_database"

for _col, _desc in [
    ("rxcui", "RxNorm Concept Unique Identifier"),
    ("lat", "Language (ENG=English)"),
    ("ts", "Term status"),
    ("lui", "Lexical unique identifier"),
    ("stt", "String type"),
    ("sui", "String unique identifier"),
    ("ispref", "Atom is preferred for this language (Y/N)"),
    ("rxaui", "RxNorm Atom Unique Identifier"),
    ("saui", "Source atom unique identifier"),
    ("scui", "Source concept unique identifier"),
    ("sdui", "Source descriptor unique identifier"),
    ("sab", "Source abbreviation (e.g. RXNORM, ATC, VANDF)"),
    ("tty", "Term type (e.g. IN, SBD, SCD, PT)"),
    ("code", "Source-specific code for the concept"),
    ("str", "String (drug name or description)"),
    ("srl", "Source restriction level"),
    ("suppress", "Suppressible flag (O, E, Y, N)"),
    ("cvf", "Content view flag"),
]:
    register_field(
        source=_SOURCE_NAME,
        table=f"{_TABLE_PREFIX}.rxnorm_concepts",
        column=_col if _col != "str" else "str_",
        description=_desc,
        source_file="RXNCONSO.RRF",
        source_position=_col.upper(),
        data_type="str",
    )

for _col, _desc in [
    ("rxcui1", "RxCUI of first concept in relationship"),
    ("rxaui1", "RXAUI of first atom"),
    ("stype1", "Identifier type of first concept (AUI or CUI)"),
    ("rel", "Relationship label (e.g. RN, RB, CHD, PAR)"),
    ("rxcui2", "RxCUI of second concept in relationship"),
    ("rxaui2", "RXAUI of second atom"),
    ("stype2", "Identifier type of second concept"),
    ("rela", "Additional relationship label (e.g. has_ingredient)"),
    ("rui", "Relationship unique identifier"),
    ("srui", "Source relationship unique identifier"),
    ("sab", "Source abbreviation for relationship"),
    ("sl", "Source of relationship labels"),
    ("rg", "Relationship group"),
    ("dir", "Directionality flag (Y/N)"),
    ("suppress", "Suppressible flag"),
    ("cvf", "Content view flag"),
]:
    register_field(
        source=_SOURCE_NAME,
        table=f"{_TABLE_PREFIX}.rxnorm_relationships",
        column=_col,
        description=_desc,
        source_file="RXNREL.RRF",
        source_position=_col.upper(),
        data_type="str",
    )

for _col, _desc in [
    ("rxcui", "RxCUI of concept this attribute belongs to"),
    ("lui", "Lexical unique identifier"),
    ("sui", "String unique identifier"),
    ("rxaui", "RXAUI of atom this attribute belongs to"),
    ("stype", "Type of identifier (AUI or CUI)"),
    ("code", "Source-specific code"),
    ("atui", "Attribute unique identifier"),
    ("satui", "Source attribute unique identifier"),
    ("atn", "Attribute name (e.g. NDC, ATC, RXCUI)"),
    ("sab", "Source abbreviation"),
    ("atv", "Attribute value (NDC or ATC code when relevant)"),
    ("suppress", "Suppressible flag"),
    ("cvf", "Content view flag"),
]:
    register_field(
        source=_SOURCE_NAME,
        table=f"{_TABLE_PREFIX}.rxnorm_attributes",
        column=_col,
        description=_desc,
        source_file="RXNSAT.RRF",
        source_position=_col.upper(),
        data_type="str",
    )

for _col, _desc in [
    ("rxcui", "RxCUI of concept with this semantic type"),
    ("tui", "Type unique identifier (TUI)"),
    ("stn", "Semantic type tree number"),
    ("sty", "Semantic type name"),
    ("atui", "Attribute unique identifier"),
    ("cvf", "Content view flag"),
]:
    register_field(
        source=_SOURCE_NAME,
        table=f"{_TABLE_PREFIX}.rxnorm_semantic_types",
        column=_col,
        description=_desc,
        source_file="RXNSTY.RRF",
        source_position=_col.upper(),
        data_type="str",
    )


# ---------------------------------------------------------------------------
# Parser helpers
# ---------------------------------------------------------------------------


def _parse_rrf_line(line: str, fields: list[str], file_key: str) -> dict[str, Any]:
    """Parse a single pipe-delimited RRF line into a dict.

    RRF files have a trailing pipe on each line; split produces an extra
    empty string at the end which we ignore. Empty strings become None.
    The "str" field is remapped to "str_" because str is a Python built-in.
    """
    parts = line.rstrip("\n").split("|")
    record: dict[str, Any] = {"_file": file_key}
    for i, field_name in enumerate(fields):
        val = parts[i] if i < len(parts) else ""
        key = "str_" if field_name == "str" else field_name
        record[key] = val if val else None
    return record


def _stream_rrf_file(
    rrf_path: Path,
    fields: list[str],
    file_key: str,
) -> Iterator[dict[str, Any]]:
    """Stream a single RRF file, yielding one dict per non-empty line."""
    with rrf_path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            yield _parse_rrf_line(line, fields, file_key)


def _find_rrf_file(directory: Path, filename: str) -> Path | None:
    """Find the RRF file by name, preferring the largest match.

    The UMLS full-release ZIP bundles two copies of every RRF file — one
    under ``rrf/`` (full release) and one under ``prescribe/rrf/``
    (prescribable subset). A stale sample file may also sit at the
    extraction root from a previous run. Picking the first ``rglob`` hit
    is non-deterministic and previously selected a 527-byte sample over
    the 131 MB real file, silently dropping all rxnorm_concepts rows.

    We pick the largest file instead — any real RRF dwarfs a sample and
    a full-release copy dwarfs the prescribable-subset copy, so this
    degrades gracefully to whichever download actually succeeded.
    """
    candidates: list[Path] = list(directory.rglob(filename))
    if not candidates:
        lower = filename.lower()
        candidates = [c for c in directory.rglob("*") if c.name.lower() == lower]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_size)


def _dialect_name(session: Any) -> str:
    """Return the SQLAlchemy dialect name bound to ``session`` (e.g. 'postgresql').

    Tolerant of MagicMock sessions used in unit tests: returns ``'unknown'``
    when the bind chain isn't real (prevents AttributeError in mock paths).
    """
    bind = getattr(session, "bind", None)
    dialect = getattr(bind, "dialect", None) if bind is not None else None
    name = getattr(dialect, "name", None)
    return name if isinstance(name, str) else "unknown"


def _is_postgres(session: Any) -> bool:
    return _dialect_name(session) == "postgresql"


def _extract_zip(zip_path: Path, dest_dir: Path) -> Path:
    """Extract ZIP to dest_dir, return dest_dir."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)
    logger.info(
        "RxNorm: ZIP extracted",
        extra={
            "ingest_source": _SOURCE_NAME,
            "ingest_zip": str(zip_path),
            "ingest_dest": str(dest_dir),
        },
    )
    return dest_dir


# ---------------------------------------------------------------------------
# Ingester class
# ---------------------------------------------------------------------------


class RxNormIngester(DataSourceIngester):
    """RxNorm ingester (full release or prescribable subset).

    Download tries the authenticated full release first (requires
    UMLS_API_KEY); on any error or when the env var is unset it falls
    back to the no-auth prescribable subset.

    Parse streams each RRF file line-by-line — never loads a full file
    into memory; the full release is ~15M records / ~4 GB.

    Load routes each record to one of four target tables via the
    ``_file`` key tag and flushes in BATCH_SIZE-sized chunks using
    ``flush_upsert_batch`` from the shared batching module. After all
    four tables commit, two derived crosswalk tables are built with
    SQL INSERT…SELECT (Postgres only).
    """

    source_name = _SOURCE_NAME

    # ------------------------------------------------------------------ #
    # Download
    # ------------------------------------------------------------------ #

    async def download(self) -> Path:
        """Download RxNorm ZIP and return path to extracted directory."""
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)

        api_key = os.getenv("UMLS_API_KEY", "").strip()
        zip_path: Path | None = None

        if api_key:
            url = _UMLS_DOWNLOAD_URL.format(api_key=api_key)
            try:
                logger.info(
                    "RxNorm: downloading full release with UMLS API key",
                    extra={"ingest_source": _SOURCE_NAME},
                )
                zip_path = await download_to_file(
                    url,
                    _CACHE_DIR,
                    max_bytes=_MAX_DOWNLOAD_BYTES,
                    timeout_seconds=600.0,
                )
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                logger.warning(
                    "RxNorm: UMLS full-release download failed, falling back to prescribable subset",
                    extra={"ingest_source": _SOURCE_NAME, "ingest_error": str(exc)},
                )
                zip_path = None

        if zip_path is None:
            logger.info(
                "RxNorm: downloading prescribable subset (no auth required)",
                extra={"ingest_source": _SOURCE_NAME, "ingest_url": _PRESCRIBABLE_URL},
            )
            try:
                zip_path = await download_to_file(
                    _PRESCRIBABLE_URL,
                    _CACHE_DIR,
                    max_bytes=_MAX_DOWNLOAD_BYTES,
                    timeout_seconds=600.0,
                )
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                raise RuntimeError(
                    "RxNorm: both full-release and prescribable-subset downloads failed. "
                    f"Set UMLS_API_KEY env var for full access. Last error: {exc}"
                ) from exc

        return _extract_zip(zip_path, _CACHE_DIR / "extracted")

    # ------------------------------------------------------------------ #
    # Parse — stream RRF files, yield one dict per line
    # ------------------------------------------------------------------ #

    def parse(self, file_path: Path) -> Iterator[dict[str, Any]]:
        """Parse all four RRF files in the extracted directory.

        file_path is the directory that ``download()`` returned. Yields
        one dict per RRF line, tagged with ``_file`` so load() can route
        the record to its target table.
        """
        if not file_path.is_dir():
            raise ValueError(f"RxNorm parse() expected a directory, got: {file_path}")

        for rrf_name, fields in _FILE_FIELD_MAP.items():
            rrf_path = _find_rrf_file(file_path, rrf_name)
            if rrf_path is None:
                logger.warning(
                    "RxNorm: RRF file not found in extract dir",
                    extra={
                        "ingest_source": _SOURCE_NAME,
                        "ingest_rrf_file": rrf_name,
                        "ingest_dir": str(file_path),
                    },
                )
                continue

            file_key = rrf_name.replace(".RRF", "")
            yield from _stream_rrf_file(rrf_path, fields, file_key)

    # ------------------------------------------------------------------ #
    # Load — batch-upsert all four tables then build crosswalks
    # ------------------------------------------------------------------ #

    async def load(self, records: Iterator[dict[str, Any]]) -> IngestionResult:
        """Route each record to its target table and flush via shared primitives.

        Main tables (concepts, relationships, attributes, semantic_types)
        use ``flush_upsert_batch`` with the table's natural unique key.
        Cross-batch duplicates are handled by ON CONFLICT DO UPDATE.

        After all four tables are flushed the two derived crosswalk
        tables are built via SQL INSERT...SELECT. Each crosswalk build
        runs inside a SAVEPOINT so a failure there can't roll back the
        ~15M main-table rows above it.
        """
        _REPO_ROOT = Path(__file__).resolve().parents[3]
        _DRUG_DB_ROOT = _REPO_ROOT / "modules" / "drug-database"
        for _p in (str(_REPO_ROOT), str(_DRUG_DB_ROOT)):
            if _p not in sys.path:
                sys.path.insert(0, _p)

        from src.models.rxnorm_tables import (  # type: ignore[import]
            RxNormAttribute,
            RxNormConcept,
            RxNormRelationship,
            RxNormSemanticType,
        )

        from shared.data_ingestion.batching import ErrorAggregator, flush_upsert_batch

        # str → str_ rename on the RxNormConcept column: the ORM column
        # name is "str" in Postgres but "str_" in the ORM attribute. The
        # __table__ object uses the DB column name, so pg_insert works
        # with the dict key "str" — we convert str_ back to str on flush.
        # (The parser emits "str_" to avoid Python's built-in clash.)
        CONCEPT_KEY_REMAP = {"str_": "str"}

        TABLE_CFG: dict[str, dict[str, Any]] = {
            "RXNCONSO": {
                "table": RxNormConcept.__table__,
                "unique_key": ["rxcui", "rxaui"],
                "remap": CONCEPT_KEY_REMAP,
            },
            "RXNREL": {
                "table": RxNormRelationship.__table__,
                "unique_key": ["rui"],
                "remap": {},
            },
            "RXNSAT": {
                "table": RxNormAttribute.__table__,
                "unique_key": ["atui"],
                "remap": {},
            },
            "RXNSTY": {
                "table": RxNormSemanticType.__table__,
                "unique_key": ["atui"],
                "remap": {},
            },
        }

        errors = ErrorAggregator()
        buffers: dict[str, list[dict[str, Any]]] = defaultdict(list)
        processed = 0
        inserted = 0
        skipped = 0

        def _remap_keys(row: dict[str, Any], remap: dict[str, str]) -> dict[str, Any]:
            if not remap:
                return row
            return {remap.get(k, k): v for k, v in row.items()}

        def _flush(file_key: str) -> None:
            nonlocal inserted, skipped
            rows = buffers[file_key]
            if not rows:
                return
            cfg = TABLE_CFG[file_key]
            remapped = [_remap_keys(r, cfg["remap"]) for r in rows]
            ins, dd = flush_upsert_batch(
                self._db,
                source_name=self.source_name,
                table=cfg["table"],
                unique_key=cfg["unique_key"],
                rows=remapped,
                errors=errors,
            )
            inserted += ins
            skipped += dd
            buffers[file_key] = []

        for record in records:
            file_key = record.pop("_file", None)
            if file_key not in TABLE_CFG:
                errors.record("unknown_file", f"unknown _file key: {file_key!r}")
                continue
            processed += 1
            buffers[file_key].append(record)
            if len(buffers[file_key]) >= _BATCH_SIZE:
                _flush(file_key)

        for file_key in list(buffers.keys()):
            _flush(file_key)

        # Build derived crosswalks from what's now committed in the main tables.
        ndc_ins, ndc_err = self._build_ndc_crosswalk()
        atc_ins, atc_err = self._build_atc_crosswalk()
        inserted += ndc_ins + atc_ins
        errors.total_errors += ndc_err + atc_err

        errors.log_summary(source_name=self.source_name)

        logger.info(
            "RxNorm load complete",
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

    # ------------------------------------------------------------------ #
    # Crosswalk builders — Postgres-only SQL, each in its own SAVEPOINT
    # ------------------------------------------------------------------ #

    def _build_ndc_crosswalk(self) -> tuple[int, int]:
        """Build rxnorm_ndc_crosswalk from rxnorm_attributes + rxnorm_concepts.

        Postgres-only — uses ``DISTINCT ON``, ``SUBSTRING … FROM … FOR``, and
        ``ON CONFLICT … DO UPDATE``. On any other dialect the crosswalk build
        is a no-op: in tests we run against SQLite where rewriting this as
        portable SQL would obscure the production query, and crosswalk
        coverage is asserted against dev/mock/prod in the data-load waves.
        """
        if not _is_postgres(self._db):
            logger.info(
                "RxNorm: skipping NDC crosswalk build on non-postgres dialect",
                extra={
                    "ingest_source": _SOURCE_NAME,
                    "ingest_dialect": _dialect_name(self._db),
                },
            )
            return 0, 0
        try:
            with self._db.begin_nested():
                sql = text("""
                    INSERT INTO drug_database.rxnorm_ndc_crosswalk
                        (ndc_11, rxcui, drug_name, tty, created_at, updated_at)
                    SELECT DISTINCT ON (SUBSTRING(ra.atv FROM 1 FOR 11))
                        SUBSTRING(ra.atv FROM 1 FOR 11) AS ndc_11,
                        ra.rxcui,
                        rc.str AS drug_name,
                        rc.tty,
                        NOW(),
                        NOW()
                    FROM drug_database.rxnorm_attributes ra
                    LEFT JOIN drug_database.rxnorm_concepts rc
                        ON rc.rxcui = ra.rxcui
                        AND rc.ispref = 'Y'
                        AND rc.lat = 'ENG'
                    WHERE ra.atn = 'NDC'
                      AND ra.atv IS NOT NULL
                      AND LENGTH(ra.atv) >= 11
                    ORDER BY SUBSTRING(ra.atv FROM 1 FOR 11), ra.rxcui
                    ON CONFLICT (ndc_11) DO UPDATE
                        SET rxcui = EXCLUDED.rxcui,
                            drug_name = EXCLUDED.drug_name,
                            tty = EXCLUDED.tty,
                            updated_at = NOW()
                """)
                result = self._db.execute(sql)
                return result.rowcount, 0
        except Exception as exc:
            logger.exception(
                "RxNorm NDC crosswalk build failed",
                extra={"ingest_source": _SOURCE_NAME, "ingest_error": str(exc)[:500]},
            )
            return 0, 1

    def _build_atc_crosswalk(self) -> tuple[int, int]:
        """Build rxnorm_atc_crosswalk from RXNSAT ATN='ATC' UNION RXNCONSO SAB='ATC'.

        Postgres-only for the same reasons as ``_build_ndc_crosswalk``.
        """
        if not _is_postgres(self._db):
            logger.info(
                "RxNorm: skipping ATC crosswalk build on non-postgres dialect",
                extra={
                    "ingest_source": _SOURCE_NAME,
                    "ingest_dialect": _dialect_name(self._db),
                },
            )
            return 0, 0
        try:
            with self._db.begin_nested():
                sql = text("""
                    INSERT INTO drug_database.rxnorm_atc_crosswalk
                        (rxcui, atc_code, atc_level, atc_name, created_at, updated_at)
                    SELECT DISTINCT ON (rxcui, atc_code)
                        rxcui,
                        atc_code,
                        CASE
                            WHEN LENGTH(atc_code) = 1 THEN '1'
                            WHEN LENGTH(atc_code) = 3 THEN '2'
                            WHEN LENGTH(atc_code) = 4 THEN '3'
                            WHEN LENGTH(atc_code) = 5 THEN '4'
                            ELSE '5'
                        END AS atc_level,
                        atc_name,
                        NOW(),
                        NOW()
                    FROM (
                        SELECT ra.rxcui, ra.atv AS atc_code, rc.str AS atc_name
                        FROM drug_database.rxnorm_attributes ra
                        LEFT JOIN drug_database.rxnorm_concepts rc
                            ON rc.rxcui = ra.rxcui AND rc.sab = 'ATC' AND rc.ispref = 'Y'
                        WHERE ra.atn = 'ATC' AND ra.atv IS NOT NULL

                        UNION

                        SELECT rc.rxcui, rc.code AS atc_code, rc.str AS atc_name
                        FROM drug_database.rxnorm_concepts rc
                        WHERE rc.sab = 'ATC' AND rc.code IS NOT NULL
                    ) combined
                    ORDER BY rxcui, atc_code
                    ON CONFLICT ON CONSTRAINT uq_rxnorm_atc_crosswalk DO UPDATE
                        SET atc_level = EXCLUDED.atc_level,
                            atc_name = EXCLUDED.atc_name,
                            updated_at = NOW()
                """)
                result = self._db.execute(sql)
                return result.rowcount, 0
        except Exception as exc:
            logger.exception(
                "RxNorm ATC crosswalk build failed",
                extra={"ingest_source": _SOURCE_NAME, "ingest_error": str(exc)[:500]},
            )
            return 0, 1


__all__ = [
    "_FILE_FIELD_MAP",
    "_RXNCONSO_FIELDS",
    "_RXNREL_FIELDS",
    "_RXNSAT_FIELDS",
    "_RXNSTY_FIELDS",
    "RxNormIngester",
    "_find_rrf_file",
    "_parse_rrf_line",
    "_stream_rrf_file",
]
