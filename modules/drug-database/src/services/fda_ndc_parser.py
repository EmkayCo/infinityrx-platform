"""FDA NDC Directory parser.

Parses the FDA NDC JSON/CSV export into DrugProduct dicts ready for upsert.
No DB calls — pure data transformation.
"""
from __future__ import annotations

import csv
import io
import logging
from typing import Any

from src.utils.ndc import InvalidNDCError, normalize_ndc, format_ndc

logger = logging.getLogger(__name__)


def parse_fda_ndc_json(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse FDA NDC JSON records into normalized DrugProduct dicts.

    Unknown/malformed NDCs are skipped with a warning logged.
    """
    results = []
    for raw in records:
        try:
            product_ndc = raw.get("product_ndc", "") or ""
            # FDA JSON uses 5-4 dashes for product NDC; packaging adds package code
            # Build full NDC-11 from labeler + product + package
            package_ndc = raw.get("package_ndc", "") or product_ndc
            ndc_11 = normalize_ndc(package_ndc)
        except InvalidNDCError:
            logger.warning(
                "skipping invalid NDC in FDA feed",
                extra={"svc_name": "fda_ndc_parser", "raw_ndc": str(raw.get("package_ndc", ""))[:20]},
            )
            continue

        labeler_code = ndc_11[:5]
        product_code = ndc_11[5:9]
        package_code = ndc_11[9:]

        results.append({
            "ndc_11": ndc_11,
            "ndc_formatted": format_ndc(ndc_11),
            "labeler_code": labeler_code,
            "product_code": product_code,
            "package_code": package_code,
            "proprietary_name": raw.get("brand_name") or raw.get("proprietary_name"),
            "nonproprietary_name": raw.get("generic_name") or raw.get("nonproprietary_name"),
            "drug_name_display": (
                raw.get("brand_name")
                or raw.get("proprietary_name")
                or raw.get("generic_name")
                or raw.get("nonproprietary_name")
                or ndc_11
            ),
            "dosage_form": raw.get("dosage_form"),
            "route_of_administration": (raw.get("route") or [None])[0]
            if isinstance(raw.get("route"), list)
            else raw.get("route"),
            "labeler_name": raw.get("labeler_name"),
            "marketing_status": _map_marketing_status(raw.get("marketing_status", "")),
            "marketing_start_date": _parse_date(raw.get("marketing_start_date")),
            "marketing_end_date": _parse_date(raw.get("marketing_end_date")),
            "dea_schedule": raw.get("dea_schedule"),
            "otc_rx": _map_otc_rx(raw.get("product_type", "")),
            "fda_application_number": raw.get("application_number"),
            "is_active": True,
            "data_source": "fda_ndc",
        })

    return results


def parse_fda_ndc_csv(csv_content: str) -> list[dict[str, Any]]:
    """Parse FDA NDC CSV export into normalized DrugProduct dicts."""
    reader = csv.DictReader(io.StringIO(csv_content))
    raw_records = list(reader)
    return parse_fda_ndc_json(raw_records)


def _map_marketing_status(status: str) -> str:
    status_lower = (status or "").lower()
    if "discontinued" in status_lower:
        return "discontinued"
    if "pending" in status_lower:
        return "pending"
    return "active"


def _map_otc_rx(product_type: str) -> str | None:
    pt = (product_type or "").upper()
    if "OTC" in pt:
        return "OTC"
    if "PRESCRIPTION" in pt or "RX" in pt:
        return "Rx"
    return None


def _parse_date(val: str | None) -> Any:
    if not val:
        return None
    from datetime import date as date_type
    try:
        return date_type.fromisoformat(str(val)[:10])
    except (ValueError, TypeError):
        return None
