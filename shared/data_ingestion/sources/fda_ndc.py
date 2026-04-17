"""FDA NDC Directory ingestion source.

Downloads https://www.accessdata.fda.gov/cder/ndctext.zip, streams-parses
product.txt and package.txt, and loads normalized records into
drug_database.drugs, drug_packages, drug_active_ingredients, and
drug_pharm_classes via the shared batching primitives.

Pipeline:
  parse()
    Reads product.txt and dedups drugs globally by (product_id, ndc_11) —
    the drugs table has TWO unique constraints and ON CONFLICT can only
    resolve one; later product_ids that claim the same ndc_11 evict the
    earlier claimant so child rows are never emitted for a drug that
    won't be in the table.  After dedup, yields in topological order:
    drugs → ingredients → pharm_classes → packages.  Packages are filtered
    to the surviving drug set so their FK into drugs is guaranteed.
  load()
    drugs — buffered, flush_upsert_batch by product_id.
    drug_packages — flush_upsert_batch by ndc_package_code_11.
    drug_active_ingredients / drug_pharm_classes — scoped-replace by
    drug_id with cross-batch scope tracking so a drug whose children span
    two flushes doesn't get its first flush's rows deleted by the second.

NDC-11 normalization rules (LESSON-004 — \\A...\\Z anchors):
  4-4-2 → pad labeler segment: 0{labeler}-{product}-{package}
  5-3-2 → pad product segment:  {labeler}-0{product}-{package}
  5-4-1 → pad package segment:  {labeler}-{product}-0{package}

LESSON-011: Global reference data — no TenantScopedMixin; shared cross-tenant.
LESSON-004: All regex uses \\A...\\Z anchors (not ^...$).
LESSON-005: All log extra keys prefixed with ingest_.
Financial precision: numerator_strength uses Decimal(18,6) ROUND_HALF_UP.
No floats anywhere.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

from shared.data_ingestion.base import DataSourceIngester, IngestionResult
from shared.data_ingestion.downloader import download_to_file, unzip_if_zipped
from shared.data_ingestion.field_registry import register_field
from shared.data_ingestion.parsers import parse_decimal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SOURCE_NAME = "fda_ndc"
_DOWNLOAD_URL = "https://www.accessdata.fda.gov/cder/ndctext.zip"
_DEST_DIR = Path("data/reference/fda-ndc")
_FILENAME = "ndctext.zip"

_BATCH_SIZE = 1_000

# Source-data sanitisation bounds. The FDA source occasionally emits values
# that exceed our schema's column limits; we truncate/clamp at the parser so
# a single bad row cannot poison a full INSERT batch (previous behaviour
# silently lost ~24K drug rows per run to StringDataRightTruncation cascades).
_DRUG_NPN_MAX_LEN = 500          # drugs.non_proprietary_name String(500)
_DRUG_PN_MAX_LEN = 500           # drugs.proprietary_name String(500)
_DRUG_LABELER_MAX_LEN = 500      # drugs.labeler_name String(500)
_INGREDIENT_SUBSTANCE_MAX_LEN = 500  # drug_active_ingredients.substance_name String(500)
# Numeric(18,6) → max 12 integer digits before decimal point. Values above
# this (e.g., gene-therapy viral-vector particle counts of 2e13 vg) cannot
# fit and are stored as NULL (matches the "q.s." handling for non-numeric
# strengths — preserve the substance, drop the numeric).
_INGREDIENT_STRENGTH_MAX = 10**12

# LESSON-004: Use \A...\Z anchors for all security/validation regex.
_NDC_DIGITS_RE = re.compile(r"\A\d{8,11}\Z")

# ---------------------------------------------------------------------------
# Field registry — run at module import time
# ---------------------------------------------------------------------------

for _col, _desc, _pos, _dtype in [
    ("product_id",   "FDA PRODUCTID (labeler-product)",       "PRODUCTID",    "str"),
    ("product_ndc",  "FDA PRODUCTNDC (5-4 format)",           "PRODUCTNDC",   "str"),
    ("ndc_11",       "11-digit NDC in 5-4-2 format",          "PRODUCTNDC",   "str"),
    ("product_type_name", "OTC/PRESCRIPTION/etc.",            "PRODUCTTYPENAME", "str"),
    ("proprietary_name",  "Brand name",                       "PROPRIETARYNAME", "str"),
    ("proprietary_name_suffix", "Brand name suffix",          "PROPRIETARYNAMESUFFIX", "str"),
    ("non_proprietary_name",    "Generic/INN name",           "NONPROPRIETARYNAME", "str"),
    ("dosage_form_name",        "Dosage form",                "DOSAGEFORMNAME", "str"),
    ("route_name",              "Route of administration",    "ROUTENAME", "str"),
    ("start_marketing_date",    "Marketing start (YYYYMMDD)", "STARTMARKETINGDATE", "date"),
    ("end_marketing_date",      "Marketing end (YYYYMMDD)",   "ENDMARKETINGDATE", "date"),
    ("marketing_category_name", "Marketing category",        "MARKETINGCATEGORYNAME", "str"),
    ("application_number",      "Orange Book NDA/ANDA number","APPLICATIONNUMBER", "str"),
    ("labeler_name",            "Labeler/manufacturer name",  "LABELERNAME", "str"),
    ("substance_name",          "Active substance(s), semicolon-separated", "SUBSTANCENAME", "str"),
    ("active_numerator_strength","Strength(s), semicolon-separated",        "ACTIVE_NUMERATOR_STRENGTH", "str"),
    ("active_ingred_unit",      "Unit(s), semicolon-separated",             "ACTIVE_INGRED_UNIT", "str"),
    ("pharm_classes",           "Pharmacological classes, comma-separated", "PHARM_CLASSES", "str"),
    ("dea_schedule",            "DEA schedule (CI-CV) or null",             "DEASCHEDULE", "str"),
    ("ndc_exclude_flag",        "Y=excluded from NDC directory",            "NDCEXCLUDEFLAG", "str"),
    ("listing_record_certified_through", "Annual certification date",       "LISTING_RECORD_CERTIFIED_THROUGH", "date"),
]:
    register_field(
        source=_SOURCE_NAME,
        table="drug_database.drugs",
        column=_col,
        description=_desc,
        source_file="product.txt",
        source_position=_pos,
        data_type=_dtype,
    )

for _col, _desc, _pos, _dtype in [
    ("product_ndc",         "Denormalized PRODUCTNDC",             "PRODUCTNDC", "str"),
    ("ndc_package_code",    "Full NDC including package segment",  "NDCPACKAGECODE", "str"),
    ("ndc_package_code_11", "Normalized 11-digit package NDC",     "NDCPACKAGECODE", "str"),
    ("package_description", "Package size/form description",       "PACKAGEDESCRIPTION", "str"),
    ("start_marketing_date","Marketing start",                     "STARTMARKETINGDATE", "date"),
    ("end_marketing_date",  "Marketing end",                       "ENDMARKETINGDATE", "date"),
    ("ndc_exclude_flag",    "Y=excluded",                          "NDCEXCLUDEFLAG", "str"),
    ("sample_package",      "Y=sample package",                    "SAMPLEPACKAGE", "str"),
]:
    register_field(
        source=_SOURCE_NAME,
        table="drug_database.drug_packages",
        column=_col,
        description=_desc,
        source_file="package.txt",
        source_position=_pos,
        data_type=_dtype,
    )


# ---------------------------------------------------------------------------
# NDC-11 normalization
# ---------------------------------------------------------------------------


def normalize_ndc_11(raw: str) -> str:
    """Normalize an NDC string to 11-digit 5-4-2 format.

    Accepts NDCs in any of the three common raw formats:
      - 4-4-2  (10 digits, dashes optional): pad labeler to 5
      - 5-3-2  (10 digits, dashes optional): pad product to 4
      - 5-4-1  (10 digits, dashes optional): pad package to 2
      - 11-digit strings (already normalized, 5-4-2): returned as-is

    Parameters
    ----------
    raw:
        Raw NDC string from the FDA file.  May include dashes.

    Returns
    -------
    str
        Zero-padded 11-digit string (no dashes), e.g. "00069420016".

    Raises
    ------
    ValueError
        If the raw NDC is invalid (not 8-11 digits after stripping dashes).
    """
    stripped = raw.replace("-", "").strip()
    # LESSON-004: \A...\Z anchors only — never ^...$
    if not _NDC_DIGITS_RE.match(stripped):
        raise ValueError(f"Invalid NDC (must be 8-11 digits after stripping dashes): {raw!r}")

    length = len(stripped)

    if length == 11:
        return stripped

    if length == 10:
        parts = raw.strip().split("-")
        if len(parts) == 3:
            seg_lengths = tuple(len(p) for p in parts)
            if seg_lengths == (4, 4, 2):
                return f"0{parts[0]}{parts[1]}{parts[2]}"
            if seg_lengths == (5, 3, 2):
                return f"{parts[0]}0{parts[1]}{parts[2]}"
            if seg_lengths == (5, 4, 1):
                return f"{parts[0]}{parts[1]}0{parts[2]}"
        # No dashes — default heuristic: treat as 5-4-1 (pad package).
        return stripped[:5] + stripped[5:9] + "0" + stripped[9]

    if length == 9:
        return f"0{stripped[:4]}{stripped[4:8]}0{stripped[8]}"

    if length == 8:
        return f"0{stripped[:4]}0{stripped[4:7]}0{stripped[7]}"

    raise ValueError(f"Cannot normalize NDC with {length} digits: {raw!r}")


def _truncate(value: str | None, max_len: int) -> str | None:
    """Return value truncated to max_len chars; None stays None."""
    if value is None:
        return None
    if len(value) > max_len:
        return value[:max_len]
    return value


def _parse_date(value: str | None) -> date | None:
    """Parse YYYYMMDD string to datetime.date; return None for empty/invalid."""
    if not value or not value.strip():
        return None
    val = value.strip()
    try:
        return date(int(val[:4]), int(val[4:6]), int(val[6:8]))
    except (ValueError, IndexError):
        return None


def _extract_class_type(pharm_class_raw: str) -> tuple[str, str | None]:
    """Extract class_type from a trailing [TYPE] marker.

    Returns (class_text, class_type_or_None).

    Examples:
        "Beta Blocker [EPC]" → ("Beta Blocker", "EPC")
        "Angiotensin 2 Receptor Blocker" → ("Angiotensin 2 Receptor Blocker", None)
    """
    pharm_class_raw = pharm_class_raw.strip()
    # LESSON-004: use \A...\Z pattern via re.fullmatch
    match = re.fullmatch(r"(.+?)\s*\[([A-Za-z]{2,4})\]", pharm_class_raw)
    if match:
        return match.group(1).strip(), match.group(2)
    return pharm_class_raw, None


def _stream_tsv(path: Path, encoding: str = "latin-1") -> Iterator[dict[str, str]]:
    """Stream a tab-separated file, yielding one dict per data row."""
    with path.open(encoding=encoding, errors="replace", newline="") as fh:
        header: list[str] | None = None
        for line_no, line in enumerate(fh):
            if line_no == 0:
                line = line.lstrip("\ufeff")
            line = line.rstrip("\r\n")
            if not line.strip():
                continue
            fields = line.split("\t")
            if header is None:
                header = fields
                continue
            row = dict(zip(header, fields, strict=False))
            yield row


def _parse_products(product_txt: Path) -> Iterator[dict[str, Any]]:
    """Stream-parse product.txt and yield normalized drug dicts.

    Yields ``{"table": "drugs", "row": {...}}``.
    """
    for row in _stream_tsv(product_txt):
        product_id = (row.get("PRODUCTID") or "").strip()
        if not product_id:
            continue

        product_ndc_raw = (row.get("PRODUCTNDC") or "").strip()
        try:
            digits = product_ndc_raw.replace("-", "")
            if re.fullmatch(r"\d{9}", digits):
                # 5-4 format; append "00" to get 11 digits (5-4-2)
                ndc_11 = digits + "00"
            else:
                ndc_11 = normalize_ndc_11(product_ndc_raw)
        except ValueError:
            logger.warning(
                "Skipping product with invalid PRODUCTNDC",
                extra={
                    "ingest_source": _SOURCE_NAME,
                    "ingest_product_id": product_id,
                    "ingest_raw_ndc": product_ndc_raw[:30],
                },
            )
            continue

        yield {
            "table": "drugs",
            "row": {
                "product_id": product_id,
                "product_ndc": product_ndc_raw,
                "ndc_11": ndc_11,
                "product_type_name": (row.get("PRODUCTTYPENAME") or "").strip() or None,
                "proprietary_name": _truncate(
                    (row.get("PROPRIETARYNAME") or "").strip() or None, _DRUG_PN_MAX_LEN
                ),
                "proprietary_name_suffix": (row.get("PROPRIETARYNAMESUFFIX") or "").strip() or None,
                "non_proprietary_name": _truncate(
                    (row.get("NONPROPRIETARYNAME") or "").strip() or None, _DRUG_NPN_MAX_LEN
                ),
                "dosage_form_name": (row.get("DOSAGEFORMNAME") or "").strip() or None,
                "route_name": (row.get("ROUTENAME") or "").strip() or None,
                "start_marketing_date": _parse_date(row.get("STARTMARKETINGDATE")),
                "end_marketing_date": _parse_date(row.get("ENDMARKETINGDATE")),
                "marketing_category_name": (row.get("MARKETINGCATEGORYNAME") or "").strip() or None,
                "application_number": (row.get("APPLICATIONNUMBER") or "").strip() or None,
                "labeler_name": _truncate(
                    (row.get("LABELERNAME") or "").strip() or None, _DRUG_LABELER_MAX_LEN
                ),
                "substance_name": (row.get("SUBSTANCENAME") or "").strip() or None,
                "active_numerator_strength": (row.get("ACTIVE_NUMERATOR_STRENGTH") or "").strip() or None,
                "active_ingred_unit": (row.get("ACTIVE_INGRED_UNIT") or "").strip() or None,
                "pharm_classes": (row.get("PHARM_CLASSES") or "").strip() or None,
                "dea_schedule": (row.get("DEASCHEDULE") or "").strip() or None,
                "ndc_exclude_flag": (row.get("NDCEXCLUDEFLAG") or "").strip() or None,
                "listing_record_certified_through": _parse_date(
                    row.get("LISTING_RECORD_CERTIFIED_THROUGH")
                ),
            },
        }


def _parse_packages(package_txt: Path) -> Iterator[dict[str, Any]]:
    """Stream-parse package.txt and yield normalized package dicts."""
    for row in _stream_tsv(package_txt):
        product_id = (row.get("PRODUCTID") or "").strip()
        if not product_id:
            continue

        ndc_package_code_raw = (row.get("NDCPACKAGECODE") or "").strip()
        try:
            ndc_11 = normalize_ndc_11(ndc_package_code_raw)
        except ValueError:
            logger.warning(
                "Skipping package with invalid NDCPACKAGECODE",
                extra={
                    "ingest_source": _SOURCE_NAME,
                    "ingest_product_id": product_id,
                    "ingest_raw_ndc": ndc_package_code_raw[:30],
                },
            )
            continue

        yield {
            "table": "drug_packages",
            "row": {
                "product_id": product_id,
                "product_ndc": (row.get("PRODUCTNDC") or "").strip() or None,
                "ndc_package_code": ndc_package_code_raw,
                "ndc_package_code_11": ndc_11,
                "package_description": (row.get("PACKAGEDESCRIPTION") or "").strip() or None,
                "start_marketing_date": _parse_date(row.get("STARTMARKETINGDATE")),
                "end_marketing_date": _parse_date(row.get("ENDMARKETINGDATE")),
                "ndc_exclude_flag": (row.get("NDCEXCLUDEFLAG") or "").strip() or None,
                "sample_package": (row.get("SAMPLEPACKAGE") or "").strip() or None,
            },
        }


def _explode_ingredients(drug_row: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Explode SUBSTANCENAME/STRENGTH/UNIT triples into one dict per ingredient.

    If the three semicolon-separated lists have mismatched lengths the drug is
    skipped (no ingredient rows yielded). This matches prior behaviour — the
    mismatch is a source-data defect, not an ingestion error.

    Non-numeric strengths like "q.s." are stored as NULL — never 0.
    """
    substance_raw = drug_row.get("substance_name")
    if not substance_raw:
        return
    substances = [s.strip() for s in substance_raw.split(";")]
    strengths = [s.strip() for s in (drug_row.get("active_numerator_strength") or "").split(";")]
    units = [s.strip() for s in (drug_row.get("active_ingred_unit") or "").split(";")]

    if len(strengths) != len(substances) or len(units) != len(substances):
        logger.warning(
            "Ingredient length mismatch — skipping drug's ingredients",
            extra={
                "ingest_source": _SOURCE_NAME,
                "ingest_product_id": drug_row.get("product_id"),
                "ingest_substances": len(substances),
                "ingest_strengths": len(strengths),
                "ingest_units": len(units),
            },
        )
        return

    product_id = drug_row.get("product_id")
    for seq, (subst, strength_str, unit_str) in enumerate(
        zip(substances, strengths, units, strict=True)
    ):
        if not subst:
            continue
        strength = parse_decimal(strength_str, quantize="0.000001")
        if strength is not None and strength >= _INGREDIENT_STRENGTH_MAX:
            strength = None  # Out of Numeric(18,6) range; keep substance, drop the number.
        yield {
            "drug_id": product_id,
            "sequence": seq,
            "substance_name": _truncate(subst, _INGREDIENT_SUBSTANCE_MAX_LEN),
            "numerator_strength": strength,
            "unit": unit_str or None,
        }


def _explode_pharm_classes(drug_row: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Split PHARM_CLASSES on commas and extract [TYPE] markers."""
    pharm_classes_raw = drug_row.get("pharm_classes")
    if not pharm_classes_raw:
        return
    product_id = drug_row.get("product_id")
    for seq, raw_class in enumerate(pharm_classes_raw.split(",")):
        stripped = raw_class.strip()
        if not stripped:
            continue
        text, ctype = _extract_class_type(stripped)
        yield {
            "drug_id": product_id,
            "sequence": seq,
            "pharm_class": text,
            "class_type": ctype,
        }


class FDANDCIngester(DataSourceIngester):
    """Ingestion pipeline for the FDA NDC Directory (ndctext.zip).

    Downloads the ZIP, streams product.txt and package.txt, and loads records
    into drug_database.drugs, drug_packages, drug_active_ingredients, and
    drug_pharm_classes via shared batching primitives.

    This is a global reference-data ingester — NOT tenant-scoped (LESSON-011).
    """

    source_name = _SOURCE_NAME

    async def download(self) -> Path:
        """Download ndctext.zip from FDA and return its local path."""
        return await download_to_file(
            _DOWNLOAD_URL,
            dest_dir=_DEST_DIR,
            filename=_FILENAME,
        )

    def parse(self, file_path: Path) -> Iterator[dict[str, Any]]:
        """Extract ZIP and stream drugs → children → packages.

        Drugs are globally deduped BEFORE any child rows are yielded — the
        drugs table has two unique constraints (product_id and ndc_11) and a
        cross-row ndc_11 collision forces eviction of one product_id's entire
        record. Children referencing an evicted product_id would violate the
        FK on insert, so the parser drops them here instead of having load()
        discover the mismatch at INSERT time.

        Records are yielded in topological order (drugs → ingredients →
        pharm_classes → packages) so load() can flush each table before the
        next one starts, satisfying the FK dependency chain.
        """
        extracted = unzip_if_zipped(file_path, file_path.parent)

        if extracted.is_dir():
            product_txt = extracted / "product.txt"
            package_txt = extracted / "package.txt"
        else:
            product_txt = extracted.parent / "product.txt"
            package_txt = extracted.parent / "package.txt"

        surviving: dict[str, dict[str, Any]] = {}
        if product_txt.exists():
            surviving = self._dedup_drugs(product_txt)

            for drug_row in surviving.values():
                yield {"table": "drugs", "row": drug_row}

            for drug_row in surviving.values():
                for ing in _explode_ingredients(drug_row):
                    yield {"table": "drug_active_ingredients", "row": ing}

            for drug_row in surviving.values():
                for pc in _explode_pharm_classes(drug_row):
                    yield {"table": "drug_pharm_classes", "row": pc}
        else:
            logger.warning(
                "product.txt not found in extracted ZIP",
                extra={"ingest_source": self.source_name, "ingest_path": str(extracted)},
            )

        if package_txt.exists():
            for record in _parse_packages(package_txt):
                # Filter packages whose parent drug was evicted by ndc_11
                # collision in _dedup_drugs — otherwise the FK insert fails.
                if record["row"].get("product_id") in surviving:
                    yield record
        else:
            logger.warning(
                "package.txt not found in extracted ZIP",
                extra={"ingest_source": self.source_name, "ingest_path": str(extracted)},
            )

    @staticmethod
    def _dedup_drugs(product_txt: Path) -> dict[str, dict[str, Any]]:
        """Materialise product.txt rows and dedup globally by (product_id, ndc_11).

        Returns a dict keyed by product_id. Last-seen wins for duplicate
        product_ids; when two product_ids claim the same ndc_11 the later one
        wins and the earlier claimant is evicted entirely so child rows are
        never emitted for an evicted product_id.
        """
        by_pid: dict[str, dict[str, Any]] = {}
        by_ndc_11: dict[str, str] = {}
        for record in _parse_products(product_txt):
            row = record["row"]
            pid = row.get("product_id")
            if not pid:
                continue
            ndc_11 = row.get("ndc_11")
            if ndc_11:
                prior_pid = by_ndc_11.get(ndc_11)
                if prior_pid and prior_pid != pid:
                    by_pid.pop(prior_pid, None)
                by_ndc_11[ndc_11] = pid
            by_pid[pid] = row
        return by_pid

    async def load(self, records: Iterator[dict[str, Any]]) -> IngestionResult:
        """Route records to their target tables and flush via shared primitives.

        Drug global dedup already happened in ``parse()`` — records for
        ``drugs`` and its children are guaranteed consistent on arrival.

        Children (ingredients, pharm_classes) use scoped-replace with
        cross-batch scope tracking: once a drug_id has been pre-deleted in an
        earlier flush this run, we don't delete it again — otherwise a drug
        whose children span two flushes would lose the first flush's rows.

        Packages are a straightforward upsert by ndc_package_code_11.

        A one-time flush of the drugs buffer is forced on the first non-drug
        record so dependent INSERTs (which have FKs into drugs) see committed
        parent rows.
        """
        import sys
        from collections import defaultdict
        from datetime import UTC, datetime
        from pathlib import Path as _Path

        from shared.data_ingestion.batching import ErrorAggregator, flush_upsert_batch

        _REPO_ROOT = _Path(__file__).resolve().parents[3]
        _DRUG_DB_ROOT = _REPO_ROOT / "modules" / "drug-database"
        for _p in (str(_REPO_ROOT), str(_DRUG_DB_ROOT)):
            if _p not in sys.path:
                sys.path.insert(0, _p)

        from src.models.ndc_tables import (  # type: ignore[import]
            Drug,
            DrugActiveIngredient,
            DrugPackage,
            DrugPharmClass,
        )

        UPSERT_CFG: dict[str, dict[str, Any]] = {
            "drug_packages": {
                "table": DrugPackage.__table__,
                "unique_key": ["ndc_package_code_11"],
            },
        }
        SCOPED_CFG: dict[str, dict[str, Any]] = {
            "drug_active_ingredients": {
                "table": DrugActiveIngredient.__table__,
                "scope_key": ["drug_id"],
                "unique_key": ["drug_id", "sequence"],
            },
            "drug_pharm_classes": {
                "table": DrugPharmClass.__table__,
                "scope_key": ["drug_id"],
                "unique_key": ["drug_id", "sequence"],
            },
        }

        errors = ErrorAggregator()
        drugs_all: list[dict[str, Any]] = []
        buffers: dict[str, list[dict[str, Any]]] = defaultdict(list)
        deleted_scopes: dict[str, set[tuple[Any, ...]]] = defaultdict(set)
        processed = 0
        inserted = 0
        skipped = 0
        drugs_flushed = False

        def _flush_drugs() -> None:
            nonlocal drugs_flushed, inserted, skipped
            if drugs_flushed:
                return
            drugs_flushed = True

            for i in range(0, len(drugs_all), _BATCH_SIZE):
                chunk = drugs_all[i : i + _BATCH_SIZE]
                ins, dd = flush_upsert_batch(
                    self._db,
                    source_name=self.source_name,
                    table=Drug.__table__,
                    unique_key=["product_id"],
                    rows=chunk,
                    errors=errors,
                )
                inserted += ins
                skipped += dd

            drugs_all.clear()

        def _flush_upsert(tname: str) -> None:
            nonlocal inserted, skipped
            rows = buffers[tname]
            if not rows:
                return
            cfg = UPSERT_CFG[tname]
            ins, dd = flush_upsert_batch(
                self._db,
                source_name=self.source_name,
                table=cfg["table"],
                unique_key=cfg["unique_key"],
                rows=rows,
                errors=errors,
            )
            inserted += ins
            skipped += dd
            buffers[tname] = []

        def _flush_scoped(tname: str) -> None:
            nonlocal inserted, skipped
            rows = buffers[tname]
            if not rows:
                return
            cfg = SCOPED_CFG[tname]
            table = cfg["table"]
            scope_key = cfg["scope_key"]
            unique_key = cfg["unique_key"]

            buckets: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
            for row in rows:
                scope = tuple(row.get(c) for c in scope_key)
                buckets.setdefault(scope, []).append(row)

            try:
                new_scopes = [s for s in buckets if s not in deleted_scopes[tname]]
                if new_scopes:
                    col = table.c[scope_key[0]]
                    self._db.execute(
                        table.delete().where(col.in_([s[0] for s in new_scopes]))
                    )
                    deleted_scopes[tname].update(new_scopes)

                to_insert: list[dict[str, Any]] = []
                dedup_dropped = 0
                for scope_rows in buckets.values():
                    seen: dict[tuple[Any, ...], dict[str, Any]] = {}
                    for row in scope_rows:
                        key = tuple(row.get(c) for c in unique_key)
                        if key not in seen:
                            seen[key] = row
                    dedup_dropped += len(scope_rows) - len(seen)
                    to_insert.extend(seen.values())

                if to_insert:
                    now = datetime.now(UTC)
                    col_names = {c.name for c in table.columns}
                    enriched = [
                        {
                            **r,
                            **(
                                {"created_at": now}
                                if "created_at" in col_names and "created_at" not in r
                                else {}
                            ),
                        }
                        for r in to_insert
                    ]
                    self._db.execute(table.insert(), enriched)

                self._db.commit()
                inserted += len(to_insert)
                skipped += dedup_dropped

            except Exception as exc:
                self._db.rollback()
                msg = str(exc)
                errors.record(
                    f"scoped_replace:{tname}",
                    msg,
                    raw_row={"batch_size": len(rows), "scopes": len(buckets)},
                )
                errors.total_errors += max(len(rows) - 1, 0)
                logger.exception(
                    "FDA NDC scoped replace failed",
                    extra={
                        "ingest_source": self.source_name,
                        "ingest_table": tname,
                        "ingest_batch_size": len(rows),
                        "ingest_error": msg[:500],
                    },
                )

            buffers[tname] = []

        # --- Main loop ----------------------------------------------------

        for record in records:
            tbl = record.get("table")
            row = record.get("row")
            if not tbl or not row:
                errors.record("empty_record", "missing table or row")
                continue
            processed += 1

            if tbl == "drugs":
                if drugs_flushed:
                    errors.record(
                        "drugs_after_flush",
                        "drug row arrived after drugs buffer was flushed",
                        raw_row=row,
                    )
                    continue
                drugs_all.append(row)
                continue

            # First non-drug record triggers the one-time drugs flush so
            # dependent child/package INSERTs see committed parent rows.
            if not drugs_flushed:
                _flush_drugs()

            if tbl in UPSERT_CFG:
                buffers[tbl].append(row)
                if len(buffers[tbl]) >= _BATCH_SIZE:
                    _flush_upsert(tbl)
            elif tbl in SCOPED_CFG:
                buffers[tbl].append(row)
                if len(buffers[tbl]) >= _BATCH_SIZE:
                    _flush_scoped(tbl)
            else:
                errors.record("unknown_table", f"no config for table {tbl}", raw_row=row)

        # Final flushes.
        _flush_drugs()
        for tname in list(buffers.keys()):
            if not buffers[tname]:
                continue
            if tname in UPSERT_CFG:
                _flush_upsert(tname)
            elif tname in SCOPED_CFG:
                _flush_scoped(tname)

        errors.log_summary(source_name=self.source_name)

        logger.info(
            "FDA NDC load complete",
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
    "FDANDCIngester",
    "normalize_ndc_11",
]
