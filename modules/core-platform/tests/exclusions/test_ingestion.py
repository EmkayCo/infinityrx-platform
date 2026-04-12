from __future__ import annotations

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
from src.models import ExclusionListEntry

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "exclusions" / "sample_oig.csv"


def test_parse_date_formats():
    assert _parse_date("20200115") is not None
    assert _parse_date("2020-01-15") is not None
    assert _parse_date("01/15/2020") is not None
    assert _parse_date("") is None
    assert _parse_date(None) is None
    assert _parse_date("   ") is None
    assert _parse_date("not a date") is None


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
    body = {
        "exclusionDetails": [
            {
                "classification": "Individual",
                "firstName": "Alice",
                "lastName": "Jones",
                "state": "NY",
                "npi": "1112223334",
                "exclusionType": "SAM",
                "activationDate": "2021-01-01",
                "terminationDate": None,
            },
            {
                "classification": "Firm",
                "entityName": "Bad Pharma Inc",
                "state": "CA",
                "exclusionType": "SAM",
                "activationDate": "2020-05-05",
            },
            {"name": None},  # malformed
        ]
    }
    respx.get("https://api.sam.gov/entity-information/v3/exclusions").mock(
        return_value=httpx.Response(200, json=body)
    )
    async with httpx.AsyncClient() as http:
        client = SAMIngestionClient(http, api_key="key")
        report = await client.ingest(db_session)
    assert report.inserted == 2
    assert report.skipped_malformed == 1

    # Idempotent
    respx.get("https://api.sam.gov/entity-information/v3/exclusions").mock(
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
    respx.get("https://api.sam.gov/entity-information/v3/exclusions").mock(
        return_value=httpx.Response(200, json="something")
    )
    async with httpx.AsyncClient() as http:
        c = SAMIngestionClient(http, api_key="k")
        rep = await c.ingest(db_session)
    assert rep.total_seen == 0


@respx.mock
async def test_sam_normalize_error_counted(db_session, monkeypatch):
    respx.get("https://api.sam.gov/entity-information/v3/exclusions").mock(
        return_value=httpx.Response(200, json={"exclusionDetails": [{"name": "x"}]})
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
