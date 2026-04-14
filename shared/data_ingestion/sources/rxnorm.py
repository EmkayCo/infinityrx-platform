"""RxNorm DataSourceIngester — NLM normalized drug nomenclature.

Downloads the RxNorm full release ZIP from NLM's UMLS download service
(requires UMLS_API_KEY env var), extracts, and ingests four RRF files:
  RXNCONSO.RRF  — 18 fields, drug concepts
  RXNREL.RRF    — 16 fields, relationships
  RXNSAT.RRF    — 13 fields, attributes (includes NDC/ATC crosswalk data)
  RXNSTY.RRF    — 6 fields, semantic types

After core tables load, two derived crosswalk tables are built via SQL:
  rxnorm_ndc_crosswalk   — NDC → RxCUI (from RXNSAT ATN='NDC')
  rxnorm_atc_crosswalk   — RxCUI → ATC (from RXNSAT ATN='ATC' or SAB='ATC')

LESSON-011: Global reference data — no TenantScopedMixin.
LESSON-004: \\A...\\Z anchors for all regex.
LESSON-005: log extra keys prefixed with ingest_.
No floats anywhere in this module.
"""

from __future__ import annotations

import logging
import os
import re
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx

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
_MAX_DOWNLOAD_BYTES = 800 * 1024 * 1024  # 800 MB — full release is ~400 MB

# RRF files and their pipe-delimited field specs (field name, position index)
# RXNCONSO: 18 fields, pipe-delimited, trailing pipe
_RXNCONSO_FIELDS = [
    "rxcui", "lat", "ts", "lui", "stt", "sui", "ispref",
    "rxaui", "saui", "scui", "sdui", "sab", "tty", "code",
    "str", "srl", "suppress", "cvf",
]

# RXNREL: 16 fields
_RXNREL_FIELDS = [
    "rxcui1", "rxaui1", "stype1", "rel", "rxcui2", "rxaui2",
    "stype2", "rela", "rui", "srui", "sab", "sl", "rg",
    "dir", "suppress", "cvf",
]

# RXNSAT: 13 fields
_RXNSAT_FIELDS = [
    "rxcui", "lui", "sui", "rxaui", "stype", "code",
    "atui", "satui", "atn", "sab", "atv", "suppress", "cvf",
]

# RXNSTY: 6 fields
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

# LESSON-004: use \A...\Z anchors
_NDC_RE = re.compile(r"\A\d{11}\Z")


def _parse_rrf_line(line: str, fields: list[str], file_key: str) -> dict[str, Any]:
    """Parse a single pipe-delimited RRF line into a dict.

    RRF files have a trailing pipe on each line; split gives an extra empty
    string at the end. We take only as many values as there are fields.
    """
    parts = line.rstrip("\n").split("|")
    record: dict[str, Any] = {"_file": file_key}
    for i, field_name in enumerate(fields):
        val = parts[i] if i < len(parts) else ""
        # Normalize 'str' field key to avoid Python builtin collision
        key = "str_" if field_name == "str" else field_name
        record[key] = val if val else None
    return record


# ---------------------------------------------------------------------------
# Ingester class
# ---------------------------------------------------------------------------


class RxNormIngester(DataSourceIngester):
    """RxNorm full-release or prescribable-subset ingester.

    Download: tries full release (requires UMLS_API_KEY) then falls back to
    the no-auth prescribable subset ZIP.
    Parse: streams RRF files line by line; never loads full file into memory.
    Load: delegates to RxNormIngestionService with batch-1000 upserts.
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
                    f"RxNorm: both full-release and prescribable-subset downloads failed. "
                    f"Set UMLS_API_KEY env var for full access. Last error: {exc}"
                ) from exc

        extract_dir = _extract_zip(zip_path, _CACHE_DIR / "extracted")
        return extract_dir

    # ------------------------------------------------------------------ #
    # Parse — stream RRF files, yield one dict per line
    # ------------------------------------------------------------------ #

    def parse(self, file_path: Path) -> Iterator[dict[str, Any]]:
        """Parse all RRF files in the extracted directory.

        file_path is expected to be a directory containing .RRF files.
        Streams line by line; never reads the full file into memory.
        Tags each record with ``_file`` key for load() routing.
        """
        if file_path.is_dir():
            extract_dir = file_path
        else:
            raise ValueError(f"RxNorm parse() expected a directory, got: {file_path}")

        for rrf_name, fields in _FILE_FIELD_MAP.items():
            rrf_path = _find_rrf_file(extract_dir, rrf_name)
            if rrf_path is None:
                logger.warning(
                    "RxNorm: RRF file not found in extract dir",
                    extra={
                        "ingest_source": _SOURCE_NAME,
                        "ingest_rrf_file": rrf_name,
                        "ingest_dir": str(extract_dir),
                    },
                )
                continue

            file_key = rrf_name.replace(".RRF", "")
            yield from _stream_rrf_file(rrf_path, fields, file_key)

    # ------------------------------------------------------------------ #
    # Load — delegate to service
    # ------------------------------------------------------------------ #

    async def load(self, records: Iterator[dict[str, Any]]) -> IngestionResult:
        """Bulk-upsert all RxNorm records via RxNormIngestionService."""
        import sys

        _REPO_ROOT = Path(__file__).resolve().parents[3]
        _DRUG_DB_ROOT = _REPO_ROOT / "modules" / "drug-database"
        for _p in (str(_REPO_ROOT), str(_DRUG_DB_ROOT)):
            if _p not in sys.path:
                sys.path.insert(0, _p)

        from src.services.rxnorm_ingestion import RxNormIngestionService  # type: ignore[import]

        service = RxNormIngestionService(db_session=self._db)
        return await service.load_records(records, source_name=self.source_name)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


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
    """Recursively find a .RRF file by name inside directory."""
    for candidate in directory.rglob(filename):
        return candidate
    # Case-insensitive fallback
    lower = filename.lower()
    for candidate in directory.rglob("*"):
        if candidate.name.lower() == lower:
            return candidate
    return None


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


__all__ = [
    "RxNormIngester",
    "_parse_rrf_line",
    "_stream_rrf_file",
    "_RXNCONSO_FIELDS",
    "_RXNREL_FIELDS",
    "_RXNSAT_FIELDS",
    "_RXNSTY_FIELDS",
    "_FILE_FIELD_MAP",
]
