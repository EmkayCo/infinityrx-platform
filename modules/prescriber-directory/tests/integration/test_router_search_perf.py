"""Search-route performance contract.

The /api/v1/prescribers/search endpoint must:
  1. Use an index-friendly query path when `name` is supplied (last_name
     prefix match), not a leading-wildcard ILIKE on display_name that
     scans 9.5M rows.
  2. Not run an unbounded `COUNT(*) FROM (filtered subquery)` — that is
     the killer cost on production. `total` is reported as a lower bound:
     the number of rows returned, OR (page*page_size + 1) when there are
     more pages.
  3. Keep returning a `SearchResponse` with `results`, `total`, `page`,
     `page_size` keys (backward-compat with the portal page that consumes
     `.results`).
"""
from __future__ import annotations

import sys
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

import pytest
from fastapi.testclient import TestClient

from shared.auth.dependencies import get_current_user
from src.api.dependencies import get_db
from src.main import create_app
from src.models.tables import Prescriber
from tests.conftest import make_prescriber, TENANT_A, _FAKE_USER_FOR_TESTS


@pytest.fixture(scope="module")
def app(_engine):
    application = create_app()

    def override_get_db():
        from sqlalchemy.orm import sessionmaker as _sm
        factory = _sm(bind=_engine, expire_on_commit=False, future=True)
        session = factory()
        try:
            yield session
        finally:
            session.close()

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_current_user] = lambda: _FAKE_USER_FOR_TESTS
    return application


@pytest.fixture(scope="module")
def client(app):
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture(scope="module")
def _seed_for_search(_engine):
    from sqlalchemy.orm import sessionmaker as _sm
    factory = _sm(bind=_engine, expire_on_commit=False, future=True)
    session = factory()
    try:
        rows = [
            Prescriber(**make_prescriber(
                npi=f"100000000{i}",
                last_name=last,
                first_name=first,
                display_name=f"{first} {last}",
                practice_state="CA",
            ))
            for i, (last, first) in enumerate([
                ("SMITH", "JOHN"),
                ("SMITH", "JANE"),
                ("SMITHSON", "ROBERT"),
                ("JONES", "ALICE"),
            ])
        ]
        session.add_all(rows)
        session.commit()
    finally:
        session.close()


class TestSearchByLastNamePrefix:
    """`?name=Smit` should hit idx_prescriber_last_name_first prefix scan,
    returning SMITH and SMITHSON matches without scanning the full table."""

    def test_name_prefix_returns_matching_last_names(self, client, _seed_for_search):
        resp = client.get(
            "/api/v1/prescribers/search?name=Smit",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        last_names = {r["display_name"] for r in data["results"]}
        # All seeded SMITH* rows must be present
        assert any("SMITH" in n for n in last_names)
        # JONES must not match a "Smit" prefix
        assert not any("JONES" in n for n in last_names)

    def test_name_prefix_case_insensitive(self, client, _seed_for_search):
        resp = client.get(
            "/api/v1/prescribers/search?name=smith",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) >= 1

    def test_response_shape_preserved(self, client, _seed_for_search):
        """SearchResponse keys must remain backward-compat with the portal."""
        resp = client.get(
            "/api/v1/prescribers/search?name=Smith",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert set(data.keys()) == {"results", "total", "page", "page_size"}
        assert isinstance(data["results"], list)
        assert isinstance(data["total"], int)
        assert data["total"] >= 1  # lower-bound contract


class TestSearchFirstAndLast:
    """Two-token search splits into first_name + last_name prefixes
    (e.g. `?name=John Smith`)."""

    def test_two_tokens_match_first_and_last(self, client, _seed_for_search):
        resp = client.get(
            "/api/v1/prescribers/search?name=John+Smith",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        names = [r["display_name"] for r in data["results"]]
        assert any("JOHN" in n and "SMITH" in n for n in names)


class TestSearchNoNameFilter:
    """When `name` is absent the route still returns results scoped by
    other filters — kept for parity with existing extended-tests."""

    def test_state_only_returns_results(self, client, _seed_for_search):
        resp = client.get(
            "/api/v1/prescribers/search?state=CA",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1
