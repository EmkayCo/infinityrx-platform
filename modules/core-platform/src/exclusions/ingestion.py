"""OIG LEIE and SAM.gov ingestion clients.

- OIG CSV columns vary by year. We handle common variants case-insensitively.
- Each client is idempotent: a natural key (source + npi | source + name+dob)
  is used for upsert, so re-running does not duplicate rows.
- Malformed rows are counted and skipped — never crash the ingestion.
"""
from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ExclusionListEntry

logger = logging.getLogger("core.exclusions.ingestion")


@dataclass
class IngestionReport:
    source: str
    inserted: int = 0
    updated: int = 0
    skipped_malformed: int = 0
    total_seen: int = 0
    errors: List[str] = field(default_factory=list)


def _parse_date(raw: str | None) -> Optional[datetime]:
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _pick(mapping: Mapping[str, Any], *keys: str) -> Optional[str]:
    for k in keys:
        for mk in mapping:
            if mk and mk.strip().upper() == k.strip().upper():
                val = mapping[mk]
                if val is None:
                    return None
                return str(val).strip() or None
    return None


def _upsert_entry(
    session: Session, *, source: str, data: Dict[str, Any], report: IngestionReport
) -> None:
    """Upsert by (source, npi) when NPI present, else by (source, last, first, state)."""
    stmt = select(ExclusionListEntry).where(ExclusionListEntry.source == source)
    if data.get("npi"):
        stmt = stmt.where(ExclusionListEntry.npi == data["npi"])
    else:
        stmt = (
            stmt.where(ExclusionListEntry.last_name == data.get("last_name"))
            .where(ExclusionListEntry.first_name == data.get("first_name"))
            .where(ExclusionListEntry.state == data.get("state"))
            .where(ExclusionListEntry.organization_name == data.get("organization_name"))
        )
    existing = session.execute(stmt).scalars().first()
    now = datetime.now(timezone.utc)
    if existing is None:
        row = ExclusionListEntry(source=source, last_updated=now, **data)
        session.add(row)
        report.inserted += 1
    else:
        for k, v in data.items():
            setattr(existing, k, v)
        existing.last_updated = now
        report.updated += 1


class OIGIngestionClient:
    """Downloads the OIG LEIE CSV and upserts rows into core_exclusion_list."""

    def __init__(self, http_client: httpx.AsyncClient, *, url: str) -> None:
        self._http = http_client
        self._url = url

    async def fetch_csv(self) -> str:
        resp = await self._http.get(self._url)
        resp.raise_for_status()
        return resp.text

    def parse_rows(self, csv_text: str) -> Iterable[Dict[str, Any]]:
        reader = csv.DictReader(io.StringIO(csv_text))
        for raw in reader:
            yield raw

    def normalize(self, raw: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
        last = _pick(raw, "LASTNAME", "LAST_NAME", "LAST NAME")
        first = _pick(raw, "FIRSTNAME", "FIRST_NAME", "FIRST NAME")
        org = _pick(raw, "BUSNAME", "BUSINESS_NAME", "ORGANIZATION", "ORGNAME")
        npi = _pick(raw, "NPI")
        state = _pick(raw, "STATE")
        excl_type = _pick(raw, "EXCLTYPE", "EXCLUSION_TYPE", "EXCL_TYPE")
        excl_date = _parse_date(_pick(raw, "EXCLDATE", "EXCLUSION_DATE"))
        reinstate = _parse_date(_pick(raw, "REINDATE", "REINSTATE_DATE"))

        if not (last or org or npi):
            return None  # malformed — no identifying field
        if state and len(state) != 2:
            state = None
        if npi and (len(npi) != 10 or not npi.isdigit()):
            npi = None
        entity_type = "individual" if last else "organization"
        return {
            "entity_type": entity_type,
            "npi": npi,
            "first_name": first,
            "last_name": last,
            "organization_name": org,
            "state": state,
            "exclusion_type": excl_type,
            "exclusion_date": excl_date,
            "reinstate_date": reinstate,
        }

    async def ingest(self, session: Session) -> IngestionReport:
        report = IngestionReport(source="OIG")
        csv_text = await self.fetch_csv()
        for raw in self.parse_rows(csv_text):
            report.total_seen += 1
            try:
                data = self.normalize(raw)
            except Exception as exc:  # noqa: BLE001
                report.skipped_malformed += 1
                report.errors.append(f"normalize error: {exc}")
                continue
            if data is None:
                report.skipped_malformed += 1
                continue
            _upsert_entry(session, source="OIG", data=data, report=report)
        session.commit()
        logger.info(
            "oig_ingestion_complete",
            extra={"inserted": report.inserted, "updated": report.updated, "skipped": report.skipped_malformed},
        )
        return report


class SAMIngestionClient:
    """Queries the SAM.gov entity exclusions endpoint."""

    DEFAULT_URL = "https://api.sam.gov/entity-information/v4/exclusions"

    def __init__(self, http_client: httpx.AsyncClient, *, api_key: str, url: str | None = None) -> None:
        self._http = http_client
        self._api_key = api_key
        self._url = url or self.DEFAULT_URL

    async def fetch_records(self) -> List[Dict[str, Any]]:
        resp = await self._http.get(self._url, params={"api_key": self._api_key})
        resp.raise_for_status()
        body = resp.json()
        if isinstance(body, dict):
            return list(body.get("exclusionDetails", []))
        if isinstance(body, list):
            return body
        return []

    def normalize(self, raw: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
        name = raw.get("name") or raw.get("entityName")
        classification = (raw.get("classification") or "").lower()
        npi = raw.get("npi")
        state = raw.get("state")
        if not name and not npi:
            return None
        is_individual = "individual" in classification or raw.get("firstName") is not None
        if is_individual:
            return {
                "entity_type": "individual",
                "npi": str(npi) if npi else None,
                "first_name": raw.get("firstName"),
                "last_name": raw.get("lastName") or name,
                "organization_name": None,
                "state": state,
                "exclusion_type": raw.get("exclusionType"),
                "exclusion_date": _parse_date(raw.get("activationDate")),
                "reinstate_date": _parse_date(raw.get("terminationDate")),
            }
        return {
            "entity_type": "organization",
            "npi": str(npi) if npi else None,
            "first_name": None,
            "last_name": None,
            "organization_name": name,
            "state": state,
            "exclusion_type": raw.get("exclusionType"),
            "exclusion_date": _parse_date(raw.get("activationDate")),
            "reinstate_date": _parse_date(raw.get("terminationDate")),
        }

    async def ingest(self, session: Session) -> IngestionReport:
        report = IngestionReport(source="SAM")
        records = await self.fetch_records()
        for raw in records:
            report.total_seen += 1
            try:
                data = self.normalize(raw)
            except Exception as exc:  # noqa: BLE001
                report.skipped_malformed += 1
                report.errors.append(f"normalize error: {exc}")
                continue
            if data is None:
                report.skipped_malformed += 1
                continue
            _upsert_entry(session, source="SAM", data=data, report=report)
        session.commit()
        logger.info(
            "sam_ingestion_complete",
            extra={"inserted": report.inserted, "updated": report.updated, "skipped": report.skipped_malformed},
        )
        return report
