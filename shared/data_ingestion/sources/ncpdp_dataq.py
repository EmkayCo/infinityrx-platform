"""NCPDP DataQ v3.1 Monthly Master ingestion source.

Parses the 13 fixed-width files from the monthly NCPDP DataQ ZIP archive and
bulk-loads them into the pharmacy_dir schema via NCPDPIngestionService.

NCPDP DataQ is a subscription service — files are manually staged (not HTTP
downloaded).  Override download() to just return the pre-staged ZIP path.

File layout (all fixed-width, CRLF-terminated, latin-1 encoded):
  mas.txt      — 1000 chars/rec — master pharmacy record
  mas_tx.txt   — 150 chars/rec  — taxonomy codes (one-to-many)
  mas_stl.txt  — 150 chars/rec  — state licenses (one-to-many)
  mas_svc.txt  — 150 chars/rec  — service flags (one per pharmacy)
  mas_rr.txt   — 150 chars/rec  — remittance records (one-to-many)
  mas_erx.txt  — 150 chars/rec  — eRx capabilities (one-to-many)
  mas_md.txt   — 150 chars/rec  — Medicaid enrollment (one-to-many)
  mas_fwa.txt  — 502 chars/rec  — FWA actions (one-to-many, largest file)
  mas_coo.txt  — 150 chars/rec  — geocoding dates (one per pharmacy)
  mas_af.txt   — 1000 chars/rec — chain additional info (5-char chain ID key)
  mas_pc.txt   — 500 chars/rec  — chain patient care (6-char chain ID key)
  mas_pr.txt   — 500 chars/rec  — chain programs (6-char chain ID key)
  mas_rec.txt  — 500 chars/rec  — chain recertification (6-char chain ID key)

Copyright header: first record in each file starts with '9999999' — skip it.
All date fields: MMDDYYYY format, '00000000' means no date.

Field positions: shared/data_ingestion/sources/ncpdp_field_positions.py
Field registry: registered at module import time.

LESSON-004: \\A...\\Z regex anchors (not ^...$) for all validation.
LESSON-005: Log extra keys prefixed with 'ingest_'.
LESSON-011: No TenantScopedMixin — global reference data.
"""

from __future__ import annotations

import logging
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from shared.data_ingestion.base import DataSourceIngester, IngestionResult
from shared.data_ingestion.date_parsers import parse_mmddyyyy
from shared.data_ingestion.field_registry import register_field
from shared.data_ingestion.sources.ncpdp_field_positions import SVC_CODES

logger = logging.getLogger(__name__)

_SOURCE_NAME = "ncpdp"

# ---------------------------------------------------------------------------
# Field registry — run at module import time
# ---------------------------------------------------------------------------

for _col, _desc, _pos, _dtype in [
    ("ncpdp_provider_id", "NCPDP Provider ID (7 digits)", "0:7", "str"),
    ("legal_name", "Legal business name", "7:67", "str"),
    ("dba_name", "DBA name", "67:127", "str"),
    ("store_number", "Store number", "187:197", "str"),
    ("address_line_1", "Physical address line 1", "197:257", "str"),
    ("address_line_2", "Physical address line 2", "257:307", "str"),
    ("city", "City", "307:337", "str"),
    ("state", "State abbreviation", "337:339", "str"),
    ("zip5", "ZIP code", "339:344", "str"),
    ("zip_plus4", "ZIP+4 extension", "344:348", "str"),
    ("phone", "Phone number (10 digits)", "348:358", "str"),
    ("phone_extension", "Phone extension", "358:363", "str"),
    ("fax", "Fax number", "363:373", "str"),
    ("email", "Email address", "373:423", "str"),
    ("cross_street", "Cross-street / intersection", "423:473", "str"),
    ("nabp_number", "NABP / chain identifier", "473:483", "str"),
    ("pharmacy_type_code", "Pharmacy type code", "487:489", "str"),
    ("store_open_date", "Store open date MMDDYYYY", "536:544", "date"),
    ("store_close_date", "Store close date MMDDYYYY", "544:552", "date"),
    ("mailing_address_line_1", "Mailing address line 1", "552:612", "str"),
    ("mailing_city", "Mailing city", "662:692", "str"),
    ("mailing_state", "Mailing state", "692:694", "str"),
    ("mailing_zip5", "Mailing ZIP5", "694:699", "str"),
    ("npi", "National Provider Identifier", "857:867", "str"),
    ("dea_number", "DEA registration number", "867:876", "str"),
    ("dea_expiration_date", "DEA expiration date", "879:887", "date"),
    ("federal_tax_id", "Federal Tax ID / EIN", "887:896", "str"),
    ("deactivation_date", "Deactivation date MMDDYYYY", "921:929", "date"),
]:
    register_field(
        source=_SOURCE_NAME,
        table="pharmacy_dir.ncpdp_pharmacies",
        column=_col,
        description=_desc,
        source_file="mas.txt",
        source_position=_pos,
        data_type=_dtype,
    )

for _col, _desc, _pos, _dtype in [
    ("taxonomy_code", "NUCC taxonomy code (10 chars)", "7:17", "str"),
    ("primary_indicator", "Primary taxonomy flag", "17:18", "str"),
    ("deactivation_date", "Deactivation date MMDDYYYY", "19:27", "date"),
]:
    register_field(
        source=_SOURCE_NAME,
        table="pharmacy_dir.ncpdp_pharmacy_taxonomies",
        column=_col,
        description=_desc,
        source_file="mas_tx.txt",
        source_position=_pos,
        data_type=_dtype,
    )


# ---------------------------------------------------------------------------
# Internal parse helpers
# ---------------------------------------------------------------------------


def _strip(value: str) -> str | None:
    """Strip and return None for empty strings."""
    s = value.strip()
    return s if s else None


def _parse_mas_record(rec: str) -> dict[str, Any]:
    """Parse a single mas.txt record (1000 chars) into a row dict."""
    return {
        "ncpdp_provider_id": rec[0:7].strip(),
        "legal_name": _strip(rec[7:67]),
        "dba_name": _strip(rec[67:127]),
        "raw_field_127": _strip(rec[127:187]),
        "store_number": _strip(rec[187:197]),
        "address_line_1": _strip(rec[197:257]),
        "address_line_2": _strip(rec[257:307]),
        "city": _strip(rec[307:337]),
        "state": _strip(rec[337:339]),
        "zip5": _strip(rec[339:344]),
        "zip_plus4": _strip(rec[344:348]),
        "phone": _strip(rec[348:358]),
        "phone_extension": _strip(rec[358:363]),
        "fax": _strip(rec[363:373]),
        "email": _strip(rec[373:423]),
        "cross_street": _strip(rec[423:473]),
        "nabp_number": _strip(rec[473:483]),
        "raw_field_483": _strip(rec[483:487]),
        "pharmacy_type_code": _strip(rec[487:489]),
        "raw_field_489": _strip(rec[489:536]),
        "store_open_date": parse_mmddyyyy(rec[536:544]),
        "store_close_date": parse_mmddyyyy(rec[544:552]),
        "mailing_address_line_1": _strip(rec[552:612]),
        "mailing_address_line_2": _strip(rec[612:662]),
        "mailing_city": _strip(rec[662:692]),
        "mailing_state": _strip(rec[692:694]),
        "mailing_zip5": _strip(rec[694:699]),
        "mailing_zip_plus4": _strip(rec[699:703]),
        "auth_official_last_name": _strip(rec[703:723]),
        "auth_official_first_name": _strip(rec[723:743]),
        "auth_official_title": _strip(rec[743:773]),
        "auth_official_phone": _strip(rec[773:784]),
        "auth_official_email": _strip(rec[784:834]),
        "raw_field_834": _strip(rec[834:839]),
        "raw_field_839": _strip(rec[839:843]),
        "raw_field_843": _strip(rec[843:857]),
        "npi": _strip(rec[857:867]),
        "dea_number": _strip(rec[867:876]),
        "raw_field_876": _strip(rec[876:879]),
        "dea_expiration_date": parse_mmddyyyy(rec[879:887]),
        "federal_tax_id": _strip(rec[887:896]),
        "raw_field_896": _strip(rec[896:908]),
        "raw_field_908": _strip(rec[908:921]),
        "deactivation_date": parse_mmddyyyy(rec[921:929]),
        "raw_field_929": _strip(rec[929:1000]),
    }


def _parse_mas_tx_record(rec: str) -> dict[str, Any]:
    """Parse a single mas_tx.txt record (150 chars)."""
    return {
        "ncpdp_provider_id": rec[0:7].strip(),
        "taxonomy_code": _strip(rec[7:17]),
        "primary_indicator": _strip(rec[17:18]),
        "raw_field_18": _strip(rec[18:19]),
        "deactivation_date": parse_mmddyyyy(rec[19:27]),
    }


def _parse_mas_stl_record(rec: str) -> dict[str, Any]:
    """Parse a single mas_stl.txt record (150 chars)."""
    return {
        "ncpdp_provider_id": rec[0:7].strip(),
        "state": _strip(rec[7:9]),
        "license_number": _strip(rec[9:29]),
        "expiration_date": parse_mmddyyyy(rec[29:37]),
        "deactivation_date": parse_mmddyyyy(rec[37:45]),
    }


def _parse_mas_svc_record(rec: str) -> dict[str, Any]:
    """Parse a single mas_svc.txt record (150 chars) into boolean service flags."""
    ncpdp_id = rec[0:7].strip()
    services_raw = rec[7:].rstrip()

    # Parse [Y/N][2-digit-code] pairs
    svc_map: dict[str, bool] = {}
    i = 0
    while i + 2 < len(services_raw):
        flag = services_raw[i]
        code = services_raw[i + 1 : i + 3]
        if flag in ("Y", "N") and code.isdigit():
            svc_map[code] = flag == "Y"
            i += 3
        else:
            i += 1

    # Map codes to named columns
    code_to_col: dict[str, str] = {
        "02": "svc_retail",
        "03": "svc_mail_order",
        "04": "svc_specialty",
        "05": "svc_long_term_care",
        "06": "svc_home_infusion",
        "07": "svc_compounding",
        "10": "svc_clinic",
        "11": "svc_nuclear",
        "12": "svc_dme",
        "13": "svc_home_health",
        "14": "svc_hospice",
        "16": "svc_hospital_outpatient",
        "18": "svc_indian_health",
        "19": "svc_correctional",
        "23": "svc_military",
        "26": "svc_340b",
        "28": "svc_ambulatory_surgery",
        "29": "svc_central_fill",
        "30": "svc_dialysis",
        "32": "svc_immunization",
        "33": "svc_mtm",
        "35": "svc_mtm",    # same column as 33
        "36": "svc_pharmacogenomics",
        "37": "svc_specialty_infusion",
        "40": "svc_other",
    }

    row: dict[str, Any] = {
        "ncpdp_provider_id": ncpdp_id,
        "services_raw": services_raw if services_raw.strip() else None,
        # Default all flags to None
        **{col: None for col in set(code_to_col.values())},
    }
    for code, val in svc_map.items():
        col = code_to_col.get(code)
        if col:
            row[col] = val

    return row


def _parse_mas_rr_record(rec: str) -> dict[str, Any]:
    """Parse a single mas_rr.txt record (150 chars)."""
    return {
        "ncpdp_provider_id": rec[0:7].strip(),
        "aba_routing_number": _strip(rec[7:16]),
        "bank_account_number": _strip(rec[16:24]),
        "electronic_payment_flag": _strip(rec[24:25]),
        "effective_date": parse_mmddyyyy(rec[25:33]),
        "deactivation_date": parse_mmddyyyy(rec[33:41]),
    }


def _parse_mas_erx_record(rec: str) -> dict[str, Any]:
    """Parse a single mas_erx.txt record (150 chars)."""
    return {
        "ncpdp_provider_id": rec[0:7].strip(),
        "software_vendor_code": _strip(rec[7:9]),
        "erx_capable_flag": _strip(rec[9:10]),
        "transaction_types": _strip(rec[10:103]),
        "effective_date": parse_mmddyyyy(rec[103:111]),
        "deactivation_date": parse_mmddyyyy(rec[111:119]),
    }


def _parse_mas_md_record(rec: str) -> dict[str, Any]:
    """Parse a single mas_md.txt record (150 chars)."""
    return {
        "ncpdp_provider_id": rec[0:7].strip(),
        "state": _strip(rec[7:9]),
        "medicaid_provider_id": _strip(rec[9:29]),
        "effective_date": parse_mmddyyyy(rec[29:37]),
        "deactivation_date": parse_mmddyyyy(rec[37:45]),
    }


def _parse_mas_fwa_record(rec: str) -> dict[str, Any]:
    """Parse a single mas_fwa.txt record (502 chars)."""
    review_year_raw = rec[14:18].strip()
    review_year: int | None = None
    if review_year_raw.isdigit() and len(review_year_raw) == 4:
        review_year = int(review_year_raw)

    remainder = _strip(rec[28:502])

    return {
        "ncpdp_provider_id": rec[0:7].strip(),
        "fwa_flag_1": _strip(rec[7:8]),
        "fwa_flag_2": _strip(rec[8:9]),
        "schema_version": _strip(rec[9:12]),
        "review_year": review_year,
        "review_flag_1": _strip(rec[18:19]),
        "review_flag_2": _strip(rec[19:20]),
        "effective_date": parse_mmddyyyy(rec[20:28]),
        "raw_remainder": remainder,
    }


def _parse_mas_coo_record(rec: str) -> dict[str, Any]:
    """Parse a single mas_coo.txt record (150 chars)."""
    return {
        "ncpdp_provider_id": rec[0:7].strip(),
        "location_id": _strip(rec[7:14]),
        "geocode_start_date": parse_mmddyyyy(rec[14:22]),
        "geocode_end_date": parse_mmddyyyy(rec[22:30]),
        "latitude": None,
        "longitude": None,
        "geocode_match_type": None,
    }


def _parse_mas_af_record(rec: str) -> dict[str, Any]:
    """Parse a single mas_af.txt record (1000 chars) — chain entity."""
    return {
        "chain_entity_id": rec[0:5].strip(),
        "raw_content": _strip(rec[5:1000]),
    }


def _parse_mas_pc_record(rec: str) -> dict[str, Any]:
    """Parse a single mas_pc.txt record (500 chars) — chain entity."""
    return {
        "chain_entity_id": rec[0:6].strip(),
        "raw_content": _strip(rec[6:500]),
    }


def _parse_mas_pr_record(rec: str) -> dict[str, Any]:
    """Parse a single mas_pr.txt record (500 chars) — chain entity."""
    return {
        "chain_entity_id": rec[0:6].strip(),
        "raw_content": _strip(rec[6:500]),
    }


def _parse_mas_rec_record(rec: str) -> dict[str, Any]:
    """Parse a single mas_rec.txt record (500 chars) — chain entity."""
    return {
        "chain_entity_id": rec[0:6].strip(),
        "raw_content": _strip(rec[6:500]),
    }


# Map filename → (table_name, parser_function)
_FILE_PARSERS: list[tuple[str, str, Any]] = [
    ("mas.txt", "ncpdp_pharmacies", _parse_mas_record),
    ("mas_tx.txt", "ncpdp_pharmacy_taxonomies", _parse_mas_tx_record),
    ("mas_stl.txt", "ncpdp_pharmacy_state_licenses", _parse_mas_stl_record),
    ("mas_svc.txt", "ncpdp_pharmacy_services", _parse_mas_svc_record),
    ("mas_rr.txt", "ncpdp_pharmacy_remittance", _parse_mas_rr_record),
    ("mas_erx.txt", "ncpdp_pharmacy_erx_capabilities", _parse_mas_erx_record),
    ("mas_md.txt", "ncpdp_pharmacy_medicaid", _parse_mas_md_record),
    ("mas_fwa.txt", "ncpdp_pharmacy_fwa_actions", _parse_mas_fwa_record),
    ("mas_coo.txt", "ncpdp_pharmacy_coordinates", _parse_mas_coo_record),
    ("mas_af.txt", "ncpdp_pharmacy_additional_info", _parse_mas_af_record),
    ("mas_pc.txt", "ncpdp_pharmacy_patient_care", _parse_mas_pc_record),
    ("mas_pr.txt", "ncpdp_pharmacy_programs", _parse_mas_pr_record),
    ("mas_rec.txt", "ncpdp_pharmacy_recertification", _parse_mas_rec_record),
]


def _parse_file(
    zf: zipfile.ZipFile,
    filename: str,
    table_name: str,
    parser: Any,
) -> Iterator[dict[str, Any]]:
    """Stream-parse a single NCPDP fixed-width file inside the ZIP.

    Skips the copyright header (first record starting with '9999999').
    Yields ``{"table": table_name, "row": {...}}`` dicts.
    """
    with zf.open(filename) as f:
        first = True
        for raw_line in f:
            rec = raw_line.decode("latin-1").rstrip("\r\n")
            if first:
                first = False
                if rec.startswith("9999999"):
                    continue  # skip copyright header
            if not rec.strip():
                continue
            if rec.startswith("9999999"):
                continue  # skip any other header-like rows
            try:
                row = parser(rec)
                if row:
                    yield {"table": table_name, "row": row}
            except Exception as exc:
                logger.warning(
                    "NCPDP record parse error",
                    extra={
                        "ingest_source": _SOURCE_NAME,
                        "ingest_file": filename,
                        "ingest_error": str(exc)[:200],
                    },
                )


# ---------------------------------------------------------------------------
# DataSourceIngester subclass
# ---------------------------------------------------------------------------


class NCPDPDataQIngester(DataSourceIngester):
    """Ingestion pipeline for the NCPDP DataQ v3.1 Monthly Master ZIP.

    NCPDP DataQ is a subscription service — files are manually staged, not
    HTTP-downloaded. Pass the ZIP path to __init__; download() returns it.

    LESSON-011: Global reference data — NOT tenant-scoped.
    """

    source_name = _SOURCE_NAME

    def __init__(self, db_session: Session, zip_path: Path) -> None:
        super().__init__(db_session)
        self.zip_path = zip_path

    async def download(self) -> Path:
        """Return the pre-staged ZIP file path (no HTTP download needed)."""
        if not self.zip_path.is_file():
            raise FileNotFoundError(
                f"NCPDP DataQ ZIP not found at {self.zip_path}. "
                "Stage the file before running ingestion."
            )
        return self.zip_path

    def parse(self, file_path: Path) -> Iterator[dict[str, Any]]:
        """Stream-parse all 13 NCPDP files from the ZIP archive.

        Yields ``{"table": str, "row": dict}`` for every data record.
        Uses generators throughout — does NOT materialise lists.
        Total records across all files: ~1.28 million.
        """
        with zipfile.ZipFile(file_path, "r") as zf:
            available = set(zf.namelist())
            for filename, table_name, parser in _FILE_PARSERS:
                if filename not in available:
                    logger.warning(
                        "NCPDP file missing from ZIP",
                        extra={
                            "ingest_source": self.source_name,
                            "ingest_file": filename,
                        },
                    )
                    continue
                yield from _parse_file(zf, filename, table_name, parser)

    async def load(self, records: Iterator[dict[str, Any]]) -> IngestionResult:
        """Batch-load all 13 tables via NCPDPIngestionService.

        Imports the service lazily so the pharmacy-directory module root
        must be on sys.path (added by the load script or conftest).
        """
        import sys
        from pathlib import Path as _Path

        _REPO_ROOT = _Path(__file__).resolve().parents[4]
        _PHARM_ROOT = _REPO_ROOT / "modules" / "pharmacy-directory"
        for _p in (str(_REPO_ROOT), str(_PHARM_ROOT)):
            if _p not in sys.path:
                sys.path.insert(0, _p)

        from src.services.ncpdp_ingestion import NCPDPIngestionService

        service = NCPDPIngestionService(db_session=self._db)
        return await service.load_records(records, source_name=self.source_name)


__all__ = [
    "NCPDPDataQIngester",
    "_parse_mas_record",
    "_parse_mas_tx_record",
    "_parse_mas_stl_record",
    "_parse_mas_svc_record",
    "_parse_mas_rr_record",
    "_parse_mas_erx_record",
    "_parse_mas_md_record",
    "_parse_mas_fwa_record",
    "_parse_mas_coo_record",
    "_parse_mas_af_record",
    "_parse_mas_pc_record",
    "_parse_mas_pr_record",
    "_parse_mas_rec_record",
    "_parse_file",
]
