from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
import pytest
import respx
from sqlalchemy import text

from src.exclusions import job_handler as jh
from src.exclusions.matching import MatchCandidate
from src.jobs.registry import default_registry
from src._shim import db as db_shim


def test_exclusion_refresh_registered():
    assert "exclusion_refresh" in default_registry.known_types()


@pytest.fixture()
def _source_shim_tables():
    """Create oig_leie_exclusions and sam_exclusions tables in the test SQLite DB.

    Required by any test that calls run_exclusion_refresh(), because the
    aggregator stage reads from these source shim tables. The _fresh_db autouse
    fixture already configures the engine; we just create the tables here.
    """
    engine = db_shim.get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS oig_leie_exclusions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lastname TEXT, firstname TEXT, midname TEXT,
                busname TEXT, general TEXT, specialty TEXT,
                upin TEXT, npi TEXT, dob TEXT,
                address TEXT, city TEXT, state TEXT, zip TEXT,
                excltype TEXT, excldate TEXT, reindate TEXT,
                waiverdate TEXT, waiverstate TEXT,
                raw_payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS sam_exclusions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                classification_type TEXT, name TEXT,
                address_line_1 TEXT, address_line_2 TEXT,
                city TEXT, state_province TEXT, zip_postal_code TEXT,
                country_code TEXT, duns_number TEXT, uei_sam TEXT,
                cage_code TEXT, npi TEXT, exclusion_type TEXT,
                exclusion_program TEXT, agency TEXT,
                active_date TEXT, termination_date TEXT,
                ct_code TEXT, additional_comments TEXT,
                affiliations TEXT, raw_payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))


# Table-name overrides used by all job-handler tests so the aggregator stage
# reads from bare SQLite-compatible table names instead of schema-qualified ones.
_JH_TABLE_OVERRIDES = dict(
    _excl_table="core_exclusion_list",
    _oig_table="oig_leie_exclusions",
    _sam_table="sam_exclusions",
)


@respx.mock
async def test_run_exclusion_refresh_pipeline(db_session, _source_shim_tables, monkeypatch):
    # Mock both HTTP endpoints via the URLs the clients use
    from src._shim import config as cfg

    monkeypatch.setattr(cfg.settings, "OIG_EXCLUSION_URL", "https://example.test/oig.csv")
    respx.get("https://example.test/oig.csv").mock(
        return_value=httpx.Response(
            200,
            text="LASTNAME,FIRSTNAME,NPI,STATE\nSMITH,JOHN,1234567890,NY\n",
        )
    )
    respx.get("https://api.sam.gov/entity-information/v4/exclusions").mock(
        return_value=httpx.Response(200, json={"exclusionDetails": []})
    )

    # Provide a fake entity provider with one hit
    class FakeProvider:
        def list_active(self, tenant_id):  # noqa: ARG002
            return [
                MatchCandidate(
                    entity_type="prescriber", entity_id="p1", npi="1234567890"
                )
            ]

    jh.set_entity_provider(FakeProvider())
    try:
        result = await jh.run_exclusion_refresh({"tenant_id": "t1"}, **_JH_TABLE_OVERRIDES)
    finally:
        jh.set_entity_provider(jh._NoopEntityProvider())

    assert result["inserted"] >= 1
    assert result["rescreened"] == 1


async def test_run_exclusion_refresh_default_noop_provider(db_session, _source_shim_tables, monkeypatch):
    from src._shim import config as cfg

    monkeypatch.setattr(cfg.settings, "OIG_EXCLUSION_URL", "https://example.test/oig.csv")

    # Build a factory matching HttpClientFactory signature
    def factory():
        client = httpx.AsyncClient(transport=httpx.MockTransport(_mock))
        return client

    def _mock(request: httpx.Request) -> httpx.Response:
        if "oig" in str(request.url):
            return httpx.Response(200, text="LASTNAME\nA\n")
        return httpx.Response(200, json={"exclusionDetails": []})

    result = await jh.run_exclusion_refresh({}, http_client_factory=factory, **_JH_TABLE_OVERRIDES)
    assert result["rescreened"] == 0


def test_get_entity_provider_returns_default():
    jh.set_entity_provider(jh._NoopEntityProvider())
    assert jh.get_entity_provider() is not None
    assert list(jh.get_entity_provider().list_active(None)) == []


async def test_default_client_factory_returns_client():
    c = jh._default_client_factory()
    assert isinstance(c, httpx.AsyncClient)
    await c.aclose()


@respx.mock
async def test_exclusion_refresh_aggregates_to_production_table(_source_shim_tables, monkeypatch):
    """NEW BLOCK: exclusion_refresh must populate the production exclusion table.

    Seeds OIG + SAM source shim tables, calls run_exclusion_refresh, then
    asserts rows appear in core_exclusion_list (the bare-table test alias for
    core.exclusion_list). Previously the job ran ingestion but never called
    run_aggregation(), so adjudication continued to screen against stale data.
    """
    from src.models import ExclusionListEntry

    engine = db_shim.get_engine()
    with engine.begin() as conn:
        # Seed one OIG row
        conn.execute(text("""
            INSERT INTO oig_leie_exclusions
                (npi, lastname, firstname, state, excltype, excldate)
            VALUES ('1111111111', 'AGGTEST-SMITH', 'AGGTEST-JOHN', 'NY', '1128a1', '2020-01-01')
        """))
        # Seed one SAM row
        conn.execute(text("""
            INSERT INTO sam_exclusions
                (npi, name, classification_type, exclusion_type, active_date, state_province)
            VALUES ('2222222222', 'AGGTEST-BAD-PHARMA', 'Firm', 'SAM', '2021-03-15', 'CA')
        """))

    # Mock HTTP endpoints so OIGIngestionClient + SAMIngestionClient don't call real APIs
    from src._shim import config as cfg
    monkeypatch.setattr(cfg.settings, "OIG_EXCLUSION_URL", "https://example.test/oig.csv")
    respx.get("https://example.test/oig.csv").mock(
        return_value=httpx.Response(200, text="LASTNAME,FIRSTNAME\n")
    )
    respx.get("https://api.sam.gov/entity-information/v4/exclusions").mock(
        return_value=httpx.Response(200, json={"exclusionDetails": []})
    )

    result = await jh.run_exclusion_refresh({}, **_JH_TABLE_OVERRIDES)

    # The aggregator must have written both seeded rows into core_exclusion_list
    assert result["aggregated_inserted"] >= 2, (
        f"Expected >= 2 aggregated rows in production table, got {result['aggregated_inserted']}"
    )

    # Verify rows are actually in the shim table
    SessionLocal = db_shim.get_sessionmaker()
    s = SessionLocal()
    try:
        rows = s.query(ExclusionListEntry).all()
        npis = {r.npi for r in rows if r.npi}
        assert "1111111111" in npis or "2222222222" in npis, (
            f"Expected seeded NPIs in core_exclusion_list, found: {npis}"
        )
    finally:
        s.close()
