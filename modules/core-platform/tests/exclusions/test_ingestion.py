from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from src.exclusions.ingestion import (
    IngestionReport,
    OIGIngestionClient,
    SAMIngestionClient,
    _parse_date,
    _pick,
)

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "exclusions" / "sample_oig.csv"


def test_parse_date_formats():
    assert _parse_date("20200115") is not None
    assert _parse_date("2020-01-15") is not None
    assert _parse_date("01/15/2020") is not None
    assert _parse_date("") is None
    assert _parse_date(None) is None
    assert _parse_date("   ") is None
    assert _parse_date("not a date") is None


def test_parse_date_sam_v4_mm_dd_yyyy():
    """SAM v4 activationDate is MM-DD-YYYY (e.g. '01-15-2024'). Must not be dropped."""
    from datetime import datetime
    result = _parse_date("01-15-2024")
    assert result is not None, "_parse_date must accept SAM v4 MM-DD-YYYY format"
    assert result == datetime(2024, 1, 15)


def test_parse_date_malformed_returns_none_not_crash():
    """Malformed date must return None (not raise), so rows are inserted with NULL date."""
    assert _parse_date("99-99-9999") is None
    assert _parse_date("hello-world") is None


def test_pick_case_insensitive():
    assert _pick({"Foo": "bar"}, "FOO") == "bar"
    assert _pick({"Foo": None}, "FOO") is None
    assert _pick({"Foo": "  "}, "FOO") is None
    assert _pick({}, "FOO") is None


@respx.mock
async def test_oig_ingest_fixture_idempotent(db_session):
    csv_text = FIX.read_text()
    respx.get("https://example.test/oig.csv").mock(
        return_value=httpx.Response(200, text=csv_text)
    )
    async with httpx.AsyncClient() as http:
        client = OIGIngestionClient(http, url="https://example.test/oig.csv")
        report = await client.ingest(db_session)

    assert report.source == "OIG"
    assert report.total_seen == 6
    assert report.inserted == 5  # 5 non-empty rows; blank row skipped
    assert report.skipped_malformed == 1  # blank row

    # re-run — idempotent (all updates, no new inserts)
    respx.get("https://example.test/oig.csv").mock(return_value=httpx.Response(200, text=csv_text))
    async with httpx.AsyncClient() as http:
        client = OIGIngestionClient(http, url="https://example.test/oig.csv")
        report2 = await client.ingest(db_session)
    assert report2.inserted == 0
    assert report2.updated == 5


@respx.mock
async def test_oig_http_error(db_session):
    respx.get("https://example.test/oig.csv").mock(return_value=httpx.Response(500))
    async with httpx.AsyncClient() as http:
        client = OIGIngestionClient(http, url="https://example.test/oig.csv")
        with pytest.raises(httpx.HTTPStatusError):
            await client.ingest(db_session)


@respx.mock
async def test_oig_normalize_catches_errors(db_session, monkeypatch):
    csv_text = "LASTNAME,FIRSTNAME\nA,B\n"
    respx.get("https://example.test/oig.csv").mock(return_value=httpx.Response(200, text=csv_text))

    from src.exclusions import ingestion as ing

    def boom(self, raw):  # noqa: ARG001
        raise RuntimeError("bad")

    monkeypatch.setattr(ing.OIGIngestionClient, "normalize", boom)
    async with httpx.AsyncClient() as http:
        client = OIGIngestionClient(http, url="https://example.test/oig.csv")
        rep = await client.ingest(db_session)
    assert rep.skipped_malformed == 1
    assert rep.errors


@respx.mock
async def test_sam_ingest_upsert(db_session):
    # v4 nested shape — official GSA fixture format.
    # fetch_records() reads "excludedEntity" and calls _flatten_v4_record on each.
    # After flattening the keys are: classificationType, name, npi, stateOrProvince,
    # exclusionType, activationDate, terminationDate, etc.
    body = {
        "totalRecords": 3,
        "excludedEntity": [
            {
                "exclusionDetails": {
                    "classificationType": "Individual",
                    "exclusionType": "SAM",
                },
                "exclusionIdentification": {
                    "entityName": "",
                    "firstName": "Alice",
                    "lastName": "Jones",
                    "npi": "1112223334",
                },
                "exclusionActions": {
                    "listOfActions": [
                        {"activateDate": "01-01-2021", "terminationDate": None},
                    ]
                },
                "exclusionPrimaryAddress": {"stateOrProvinceCode": "NY"},
                "exclusionOtherInformation": {},
            },
            {
                "exclusionDetails": {
                    "classificationType": "Firm",
                    "exclusionType": "SAM",
                },
                "exclusionIdentification": {
                    "entityName": "Bad Pharma Inc",
                    "npi": None,
                },
                "exclusionActions": {
                    "listOfActions": [
                        {"activateDate": "05-05-2020"},
                    ]
                },
                "exclusionPrimaryAddress": {"stateOrProvinceCode": "CA"},
                "exclusionOtherInformation": {},
            },
            # Malformed — missing exclusionDetails entirely
            {"exclusionIdentification": {"entityName": ""}},
        ],
        "links": {},
    }
    respx.get("https://api.sam.gov/entity-information/v4/exclusions").mock(
        return_value=httpx.Response(200, json=body)
    )
    async with httpx.AsyncClient() as http:
        client = SAMIngestionClient(http, api_key="key")
        report = await client.ingest(db_session)
    assert report.inserted == 2
    assert report.skipped_malformed == 1

    # Idempotent — re-running same body produces 0 inserts, 2 updates.
    respx.get("https://api.sam.gov/entity-information/v4/exclusions").mock(
        return_value=httpx.Response(200, json=body)
    )
    async with httpx.AsyncClient() as http:
        client = SAMIngestionClient(http, api_key="key")
        report2 = await client.ingest(db_session)
    assert report2.inserted == 0
    assert report2.updated == 2


@respx.mock
async def test_sam_ingest_list_body(db_session):
    records = [{"name": "ACME", "classification": "firm"}]
    respx.get("https://custom.example/sam").mock(return_value=httpx.Response(200, json=records))
    async with httpx.AsyncClient() as http:
        c = SAMIngestionClient(http, api_key="k", url="https://custom.example/sam")
        rep = await c.ingest(db_session)
    assert rep.inserted == 1


@respx.mock
async def test_sam_ingest_unknown_body_shape(db_session):
    respx.get("https://api.sam.gov/entity-information/v4/exclusions").mock(
        return_value=httpx.Response(200, json="something")
    )
    async with httpx.AsyncClient() as http:
        c = SAMIngestionClient(http, api_key="k")
        rep = await c.ingest(db_session)
    assert rep.total_seen == 0


@respx.mock
async def test_sam_normalize_error_counted(db_session, monkeypatch):
    # v4 nested shape with one valid entity — the monkeypatched normalize raises
    # on every record so all records land in skipped_malformed.
    body = {
        "totalRecords": 1,
        "excludedEntity": [
            {
                "exclusionDetails": {"classificationType": "Firm", "exclusionType": "SAM"},
                "exclusionIdentification": {"entityName": "x", "npi": None},
                "exclusionActions": {"listOfActions": []},
                "exclusionPrimaryAddress": {},
                "exclusionOtherInformation": {},
            }
        ],
        "links": {},
    }
    respx.get("https://api.sam.gov/entity-information/v4/exclusions").mock(
        return_value=httpx.Response(200, json=body)
    )
    from src.exclusions import ingestion as ing

    def boom(self, raw):  # noqa: ARG001
        raise RuntimeError("bad")

    monkeypatch.setattr(ing.SAMIngestionClient, "normalize", boom)
    async with httpx.AsyncClient() as http:
        c = SAMIngestionClient(http, api_key="k")
        rep = await c.ingest(db_session)
    assert rep.skipped_malformed == 1
    assert rep.errors


def test_ingestion_report_defaults():
    r = IngestionReport(source="X")
    assert r.inserted == 0 and r.errors == []


def test_oig_normalize_invalid_state(db_session):
    client = OIGIngestionClient(None, url="u")  # type: ignore[arg-type]
    data = client.normalize({"LASTNAME": "X", "STATE": "LONG"})
    assert data is not None and data["state"] is None


def test_oig_normalize_no_identifier_returns_none(db_session):
    client = OIGIngestionClient(None, url="u")  # type: ignore[arg-type]
    assert client.normalize({"STATE": "NY"}) is None


@respx.mock
async def test_sam_v4_mm_dd_yyyy_date_persisted_not_null(db_session):
    """BLOCK-2: SAM v4 activationDate in MM-DD-YYYY must persist as a non-null date.

    Previously _parse_date did not accept MM-DD-YYYY so exclusion_date was silently
    dropped to NULL. This test asserts the date is persisted as date(2024, 1, 15).
    """
    from sqlalchemy import select
    from src.models import ExclusionListEntry

    body = {
        "totalRecords": 1,
        "excludedEntity": [
            {
                "exclusionDetails": {
                    "classificationType": "Individual",
                    "exclusionType": "SAM",
                },
                "exclusionIdentification": {
                    "entityName": "",
                    "firstName": "Jane",
                    "lastName": "Doe",
                    "npi": "1234567891",
                },
                "exclusionActions": {
                    "listOfActions": [
                        {"activateDate": "01-15-2024", "terminationDate": None},
                    ]
                },
                "exclusionPrimaryAddress": {"stateOrProvinceCode": "TX"},
                "exclusionOtherInformation": {},
            },
        ],
        "links": {},
    }
    respx.get("https://api.sam.gov/entity-information/v4/exclusions").mock(
        return_value=httpx.Response(200, json=body)
    )
    async with httpx.AsyncClient() as http:
        client = SAMIngestionClient(http, api_key="key")
        report = await client.ingest(db_session)

    assert report.inserted == 1, f"Expected 1 inserted, got {report.inserted}"
    assert report.skipped_malformed == 0

    row = db_session.execute(
        select(ExclusionListEntry).where(ExclusionListEntry.npi == "1234567891")
    ).scalars().first()
    assert row is not None, "Row must be persisted"
    assert row.exclusion_date is not None, (
        "exclusion_date must NOT be NULL — SAM v4 MM-DD-YYYY date was silently dropped"
    )
    # datetime(2024, 1, 15) stored — compare year/month/day to handle datetime vs date
    assert row.exclusion_date.year == 2024
    assert row.exclusion_date.month == 1
    assert row.exclusion_date.day == 15


@respx.mock
async def test_sam_v4_malformed_date_inserts_with_null_date(db_session):
    """BLOCK-2: malformed date in SAM v4 record must log warning and insert row with NULL date.

    Row must still be inserted (not skipped/crashed).
    """
    from sqlalchemy import select
    from src.models import ExclusionListEntry

    body = {
        "totalRecords": 1,
        "excludedEntity": [
            {
                "exclusionDetails": {
                    "classificationType": "Firm",
                    "exclusionType": "SAM",
                },
                "exclusionIdentification": {
                    "entityName": "Corrupt Pharma LLC",
                    "npi": None,
                },
                "exclusionActions": {
                    "listOfActions": [
                        {"activateDate": "not-a-date", "terminationDate": None},
                    ]
                },
                "exclusionPrimaryAddress": {"stateOrProvinceCode": "FL"},
                "exclusionOtherInformation": {},
            },
        ],
        "links": {},
    }
    respx.get("https://api.sam.gov/entity-information/v4/exclusions").mock(
        return_value=httpx.Response(200, json=body)
    )
    async with httpx.AsyncClient() as http:
        client = SAMIngestionClient(http, api_key="key")
        report = await client.ingest(db_session)

    # Row must be inserted (not skipped) — only the date is NULL
    assert report.inserted == 1, f"Row with malformed date must still be inserted, got inserted={report.inserted}"
    assert report.skipped_malformed == 0

    row = db_session.execute(
        select(ExclusionListEntry).where(ExclusionListEntry.organization_name == "Corrupt Pharma LLC")
    ).scalars().first()
    assert row is not None, "Row with malformed date must be inserted"
    assert row.exclusion_date is None, "exclusion_date must be NULL for malformed date input"
