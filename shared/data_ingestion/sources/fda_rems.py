"""FDA REMS (Risk Evaluation and Mitigation Strategies) ingestion source.

Downloads REMS-mentioning drug labels from the openFDA drug label API
(falling back to the pre-staged local JSON file) and upserts into
drug_database.drug_rems + drug_database.drug_rems_ndc via the shared
batching primitives.

Wave 9d refactor notes:

  - load() was a delegation to RemsIngestionService doing per-row ORM
    upserts. Now uses flush_upsert_batch for the parent table and a
    one-shot bulk DELETE + INSERT for drug_rems_ndc. RemsIngestionService
    was deleted from modules/drug-database/src/services/fda_supplementary_ingestion.py
    in the same commit.

  - KNOWN SILENT-OVERWRITE BUG (deliberately punted — see
    TODO-WAVE-REMS-EXTRACT below):

      The openFDA label payloads do NOT populate a top-level ``rems[]``
      key in the current openFDA build — verified against the
      live 766-record snapshot at data/reference/fda-rems/fda_rems.json:
      0/766 records have it. ``_parse_record`` therefore always takes
      the fallback path:

          rems_program_name = application_number
          rems_type         = None
          etasu_requirements= None

      Consequence: every REMS row written currently has its program
      name set to the NDA/BLA application number rather than the actual
      program name (e.g. "TIRF REMS Access Program"), and ``rems_type``
      and ``etasu_requirements`` are always NULL. Downstream consumers
      get "this app has a REMS" signal but no program structure.

      The 766 source labels collapse to ~325 unique application_numbers
      after upsert (many labels share an application — brand + generic
      SPL + revisions). Wave 9 target: ≥325 drug_rems rows.

      Fix scope for a future wave (tracked in tasks/TODO-WAVE-REMS-EXTRACT.md):
        1. Extract REMS program name from SPL sections (warnings_and_cautions,
           boxed_warning) using anchored patterns around "REMS" / "Risk
           Evaluation and Mitigation Strategy".
        2. Classify rems_type (Medication Guide / Communication Plan /
           ETASU / Shared System) from the same text.
        3. Pull enrollment requirements and program URLs from the label
           body. Populate etasu_requirements jsonb with a structured
           representation rather than the current regex-indicator dict.

LESSON-011: Global reference data — no TenantScopedMixin.
LESSON-004: \\A...\\Z anchors for all regex.
LESSON-005: All log extra keys prefixed with ingest_.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx

from shared.data_ingestion.base import DataSourceIngester, IngestionResult
from shared.data_ingestion.field_registry import register_field

logger = logging.getLogger(__name__)

_SOURCE_NAME = "fda_rems"
_DEST_DIR = Path("data/reference/fda-rems")
_FILENAME = "fda_rems.json"
_BATCH_SIZE = 1_000
_API_LIMIT = 100
_API_MAX_SKIP = 26_000
_OPENFDA_URL = "https://api.fda.gov/drug/label.json"

# LESSON-004: \A...\Z anchors for all validation regex
_DATE_RE = re.compile(r"\A(\d{4})(\d{2})(\d{2})\Z")

for _col, _desc, _pos, _dtype in [
    ("application_number",            "NDA/BLA application number",             "openfda.application_number", "str"),
    ("rems_program_name",             "REMS program name (see silent-bug note)", "rems",                       "str"),
    ("drug_name_brand",               "Brand name",                             "openfda.brand_name",         "str"),
    ("drug_name_generic",             "Generic/INN name",                       "openfda.generic_name",       "str"),
    ("ndc_codes",                     "NDC codes covered (JSONB)",              "openfda.package_ndc",        "json"),
    ("rems_type",                     "REMS type (see silent-bug note)",        "rems",                       "str"),
    ("etasu_requirements",            "ETASU requirements (JSONB)",             "rems",                       "json"),
    ("initial_approval_date",         "Initial approval date",                  "effective_time",             "date"),
    ("most_recent_modification_date", "Most recent modification date",           "effective_time",             "date"),
    ("status",                        "Status (Active/Modified/Released)",       "rems",                       "str"),
    ("shared_system_name",            "Shared REMS system name",                 "rems",                       "str"),
    ("raw_payload",                   "Full raw openFDA label payload (JSONB)", "full_label",                 "json"),
]:
    register_field(
        source=_SOURCE_NAME,
        table="drug_database.drug_rems",
        column=_col,
        description=_desc,
        source_file="openFDA_drug_label_api",
        source_position=_pos,
        data_type=_dtype,
    )


def _strip_or_none(value: str | None) -> str | None:
    if not value:
        return None
    stripped = value.strip()
    return stripped or None


def _parse_date_yyyymmdd(value: str | None) -> date | None:
    if not value:
        return None
    stripped = value.strip()
    m = _DATE_RE.match(stripped)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _extract_rems_type(rems_list: list[str] | None) -> str | None:
    """Infer REMS type from keyword presence in REMS text array."""
    if not rems_list:
        return None
    combined = " ".join(rems_list).upper()
    if "ETASU" in combined:
        return "ETASU"
    if "COMMUNICATION PLAN" in combined:
        return "Communication Plan"
    if "MEDICATION GUIDE" in combined:
        return "Medication Guide"
    return _strip_or_none(rems_list[0]) if rems_list else None


def _build_etasu_requirements(rems_list: list[str] | None) -> dict | None:
    """Build ETASU requirements dict from REMS text array."""
    if not rems_list:
        return None
    combined = " ".join(rems_list)
    return {
        "prescriber_certification": bool(re.search(r"prescrib", combined, re.IGNORECASE)),
        "pharmacy_certification": bool(re.search(r"pharmac", combined, re.IGNORECASE)),
        "patient_enrollment": bool(
            re.search(r"patient.*enroll|enroll.*patient", combined, re.IGNORECASE)
        ),
        "medication_guide": bool(re.search(r"medication guide", combined, re.IGNORECASE)),
        "communication_plan": bool(
            re.search(r"communication plan", combined, re.IGNORECASE)
        ),
    }


def _parse_record(label: dict[str, Any]) -> dict[str, Any] | None:
    """Parse one openFDA label into the drug_rems row shape.

    Returns None when the record has no usable application_number —
    without that we can't key the row.
    """
    openfda = label.get("openfda") or {}

    app_numbers = openfda.get("application_number") or []
    application_number = app_numbers[0] if app_numbers else None
    if not application_number:
        return None
    application_number = application_number.strip()

    rems_list: list[str] = label.get("rems") or []
    # TODO-WAVE-REMS-EXTRACT: openFDA labels do not populate a top-level
    # rems[] key in the current build (0/766 observed). The fallback
    # here silently sets rems_program_name to the application_number
    # and leaves rems_type / etasu_requirements None. A future wave
    # should parse the program name + type + enrollment requirements
    # from SPL free-text sections (warnings_and_cautions, boxed_warning).
    # See tasks/TODO-WAVE-REMS-EXTRACT.md for scope.
    rems_program_name = _strip_or_none(rems_list[0]) if rems_list else application_number

    brand_names = openfda.get("brand_name") or []
    generic_names = openfda.get("generic_name") or []
    ndc_codes: list[str] = openfda.get("package_ndc") or []

    effective_time_raw = _strip_or_none(label.get("effective_time"))
    parsed_date = _parse_date_yyyymmdd(effective_time_raw)

    raw_payload: dict[str, Any] = dict(label)

    return {
        "application_number": application_number,
        "rems_program_name": rems_program_name or application_number,
        "drug_name_brand": _strip_or_none(brand_names[0]) if brand_names else None,
        "drug_name_generic": _strip_or_none(generic_names[0]) if generic_names else None,
        "ndc_codes": ndc_codes if ndc_codes else None,
        "rems_type": _extract_rems_type(rems_list),
        "etasu_requirements": _build_etasu_requirements(rems_list),
        "initial_approval_date": parsed_date,
        "most_recent_modification_date": parsed_date,
        "status": "Active",
        "shared_system_name": None,
        "raw_payload": raw_payload,
    }


class FdaRemsIngester(DataSourceIngester):
    """FDA REMS ingester.

    Downloads REMS-mentioning drug labels via openFDA's label endpoint,
    caches to a local JSON file, streams-parses, and upserts into
    drug_database.drug_rems + drug_rems_ndc.

    See module docstring for the silent-overwrite bug on
    rems_program_name / rems_type / etasu_requirements — deliberately
    punted to a follow-up wave.

    LESSON-011: Global reference data — no TenantScopedMixin.
    """

    source_name = _SOURCE_NAME

    async def download(self) -> Path:
        """Fetch all REMS records from openFDA, write to local JSON.

        Falls back to the pre-staged data/reference/fda-rems/fda_rems.json
        when the API call fails (e.g. rate-limit / transient 5xx).
        """
        _DEST_DIR.mkdir(parents=True, exist_ok=True)
        dest = _DEST_DIR / _FILENAME
        all_records: list[dict[str, Any]] = []

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                skip = 0
                while skip <= _API_MAX_SKIP:
                    params = {
                        "search": (
                            '(warnings_and_cautions:"REMS" OR boxed_warning:"REMS") '
                            "AND _exists_:openfda.brand_name"
                        ),
                        "limit": _API_LIMIT,
                        "skip": skip,
                    }
                    try:
                        resp = await client.get(_OPENFDA_URL, params=params)
                        resp.raise_for_status()
                        data = resp.json()
                    except httpx.HTTPStatusError as exc:
                        if exc.response.status_code == 404:
                            logger.info(
                                "openFDA REMS pagination exhausted",
                                extra={"ingest_source": _SOURCE_NAME, "ingest_skip": skip},
                            )
                            break
                        raise

                    results = data.get("results") or []
                    if not results:
                        break
                    all_records.extend(results)
                    if len(results) < _API_LIMIT:
                        break
                    skip += _API_LIMIT

            dest.write_text(json.dumps(all_records), encoding="utf-8")
            logger.info(
                "REMS download complete",
                extra={"ingest_source": _SOURCE_NAME,
                       "ingest_record_count": len(all_records)},
            )
        except (httpx.HTTPError, httpx.TransportError) as exc:
            if dest.is_file():
                logger.warning(
                    "REMS download failed (%s) — using cached file at %s",
                    exc, dest,
                    extra={"ingest_source": _SOURCE_NAME},
                )
                return dest
            raise

        return dest

    def parse(self, file_path: Path) -> Iterator[dict[str, Any]]:
        """Parse the cached JSON and yield normalised REMS dicts."""
        raw_text = file_path.read_text(encoding="utf-8")
        records: list[dict[str, Any]] = json.loads(raw_text)
        for label in records:
            parsed = _parse_record(label)
            if parsed is not None:
                yield parsed

    async def load(self, records: Iterator[dict[str, Any]]) -> IngestionResult:
        """Upsert drug_rems via flush_upsert_batch; bulk-replace drug_rems_ndc.

        Two-phase so drug_rems_ndc's FK on rems_id has committed parents
        before INSERT. Phase 1 buffers and upserts all parent rows; phase
        2 collects surviving (application_number, ndc_codes) pairs, deletes
        every matching drug_rems_ndc row, then bulk-inserts the new set.

        This replaces the Wave 7-era RemsIngestionService which did per-row
        ORM upsert + per-row ORM delete+insert on NDC children — O(N*M)
        queries. The new path is O(N_batches) parent upserts and a single
        bulk replace for NDCs.
        """
        import sys
        from pathlib import Path as _Path

        from sqlalchemy import text

        from shared.data_ingestion.batching import (
            ErrorAggregator,
            flush_upsert_batch,
        )

        _repo_root = _Path(__file__).resolve().parents[3]
        _drug_db_root = _repo_root / "modules" / "drug-database"
        for _p in (str(_repo_root), str(_drug_db_root)):
            if _p not in sys.path:
                sys.path.insert(0, _p)

        from src.models.fda_supplementary_tables import DrugRems, DrugRemsNdc  # type: ignore[import]

        errors = ErrorAggregator()
        buffer: list[dict[str, Any]] = []
        # application_number -> list of NDC codes from the latest record seen.
        # Populated during phase 1 so phase 2 can bulk-replace without
        # re-parsing.
        ndcs_by_app: dict[str, list[str]] = {}
        processed = 0
        inserted = 0
        skipped = 0

        def _flush() -> None:
            nonlocal inserted, skipped
            if not buffer:
                return
            # flush_upsert_batch doesn't write columns that aren't in the
            # target table, so we strip ndc_codes from each row (it's a
            # JSONB column on drug_rems that we DO want to preserve) —
            # actually drug_rems.ndc_codes IS a column, so keep it.
            # Build the row with the exact DB column set:
            rows_for_upsert = [
                {
                    "application_number": r["application_number"],
                    "rems_program_name": r["rems_program_name"],
                    "drug_name_brand": r["drug_name_brand"],
                    "drug_name_generic": r["drug_name_generic"],
                    "ndc_codes": r["ndc_codes"],
                    "rems_type": r["rems_type"],
                    "etasu_requirements": r["etasu_requirements"],
                    "initial_approval_date": r["initial_approval_date"],
                    "most_recent_modification_date": r["most_recent_modification_date"],
                    "status": r["status"],
                    "shared_system_name": r["shared_system_name"],
                    "raw_payload": r["raw_payload"],
                }
                for r in buffer
            ]
            ins, dd = flush_upsert_batch(
                self._db,
                source_name=self.source_name,
                table=DrugRems.__table__,
                unique_key=["application_number", "rems_program_name"],
                rows=rows_for_upsert,
                errors=errors,
            )
            inserted += ins
            skipped += dd
            buffer.clear()

        for record in records:
            processed += 1
            app = record.get("application_number")
            if not app:
                errors.record("missing_app_number", "record has no application_number")
                continue
            buffer.append(record)
            ndc_codes = record.get("ndc_codes") or []
            if isinstance(ndc_codes, list) and ndc_codes:
                ndcs_by_app[app] = [n for n in ndc_codes if n]
            if len(buffer) >= _BATCH_SIZE:
                _flush()

        _flush()

        # Phase 2: bulk-replace drug_rems_ndc for every app we just upserted.
        if ndcs_by_app:
            try:
                # Look up rems_id for each application_number in one query.
                apps = list(ndcs_by_app.keys())
                rows = self._db.execute(
                    text(
                        "SELECT id, application_number "
                        "FROM drug_database.drug_rems "
                        "WHERE application_number = ANY(:apps)"
                    ),
                    {"apps": apps},
                ).fetchall()
                app_to_rems_id = {r[1]: r[0] for r in rows}

                rems_ids = list(app_to_rems_id.values())
                if rems_ids:
                    self._db.execute(
                        text(
                            "DELETE FROM drug_database.drug_rems_ndc "
                            "WHERE rems_id = ANY(:ids)"
                        ),
                        {"ids": rems_ids},
                    )

                ndc_rows = []
                now = datetime.now(UTC)
                for app, codes in ndcs_by_app.items():
                    rems_id = app_to_rems_id.get(app)
                    if rems_id is None:
                        continue
                    seen_ndc: set[str] = set()
                    for raw_ndc in codes:
                        ndc_11 = (raw_ndc or "").strip()[:11]
                        if not ndc_11 or ndc_11 in seen_ndc:
                            continue
                        seen_ndc.add(ndc_11)
                        ndc_rows.append({
                            "rems_id": rems_id,
                            "ndc_11": ndc_11,
                            "application_number": app,
                        })

                if ndc_rows:
                    self._db.execute(DrugRemsNdc.__table__.insert(), ndc_rows)
                self._db.commit()
                inserted += len(ndc_rows)
            except Exception as exc:
                self._db.rollback()
                errors.record("ndc_replace", str(exc), raw_row={"apps": len(ndcs_by_app)})

        errors.log_summary(source_name=self.source_name)

        logger.info(
            "FDA REMS load complete",
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
    "FdaRemsIngester",
    "_build_etasu_requirements",
    "_extract_rems_type",
    "_parse_date_yyyymmdd",
    "_parse_record",
]
