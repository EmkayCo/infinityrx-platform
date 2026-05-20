"""Additional router coverage tests — batch lookup, overrides delete, FDB stub."""
from __future__ import annotations

import sys
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.dependencies import get_db
from src.main import create_app
from src.models.ndc_tables import Drug, NDCBase
from src.models.pricing_tables import PricingBase
from src.models.tables import (
    DrugBase,
    DrugPricingHistory,
    TenantPricingOverride,
)
from src.services.fdb_adapter import FDBAdapterStub

TENANT_A = "11111111-1111-1111-1111-111111111111"
TENANT_B = "22222222-2222-2222-2222-222222222222"
_NOW = datetime.now(timezone.utc)

_METFORMIN_ID = "00093-3149-cov"
_HUMALOG_ID = "00002-1436-cov"


@pytest.fixture(scope="module")
def _engine():
    engine = create_engine(
        "sqlite:///file:drug_test_router?mode=memory&cache=shared&uri=true",
        connect_args={"check_same_thread": False},
    )
    for table in DrugBase.metadata.tables.values():
        table.schema = None
    for table in NDCBase.metadata.tables.values():
        table.schema = None
    for table in PricingBase.metadata.tables.values():
        table.schema = None

    DrugBase.metadata.create_all(engine)
    NDCBase.metadata.create_all(engine)
    PricingBase.metadata.create_all(engine)
    yield engine
    PricingBase.metadata.drop_all(engine)
    NDCBase.metadata.drop_all(engine)
    DrugBase.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="module")
def client(_engine) -> TestClient:
    app = create_app()
    _Factory = sessionmaker(bind=_engine, autocommit=False, autoflush=False)

    def _override_db():
        s = _Factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override_db
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def seed_db(_engine):
    Factory = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    session = Factory()

    d1 = Drug(
        product_id=_METFORMIN_ID,
        product_ndc="00093-3149",
        ndc_11="00093314905",
        non_proprietary_name="metformin hydrochloride",
        labeler_name="Teva Pharmaceuticals",
        marketing_category_name="ANDA",
        ndc_exclude_flag=None,
        created_at=_NOW,
        updated_at=_NOW,
    )
    d2 = Drug(
        product_id=_HUMALOG_ID,
        product_ndc="00002-1436",
        ndc_11="00002143601",
        proprietary_name="Humalog",
        non_proprietary_name="insulin lispro",
        labeler_name="Eli Lilly",
        marketing_category_name="NDA",
        ndc_exclude_flag=None,
        created_at=_NOW,
        updated_at=_NOW,
    )
    session.add_all([d1, d2])

    # Pricing history
    ph = DrugPricingHistory(
        ndc_11="00093314905",
        price_type="NADAC",
        old_price=Decimal("0.040000"),
        new_price=Decimal("0.045000"),
        change_percentage=Decimal("12.5000"),
        effective_date=date(2026, 1, 1),
        data_source="cms_nadac",
        created_at=_NOW,
    )
    session.add(ph)

    # Override for delete test
    override = TenantPricingOverride(
        id=uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
        tenant_id=uuid.UUID(TENANT_A),
        ndc_11="00093314905",
        price_type="MAC",
        price_per_unit=Decimal("0.030000"),
        effective_date=date(2026, 1, 1),
        data_source="tenant_mac",
        created_at=_NOW,
        updated_at=_NOW,
    )
    session.add(override)

    session.commit()
    session.close()


class TestBatchLookup:
    def test_batch_lookup_multiple_ndcs(self, client, seed_db) -> None:
        resp = client.get(
            "/api/v1/drugs/lookup/batch?ndcs=00093314905&ndcs=00002143601",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_batch_lookup_too_many_ndcs_returns_400(self, client, seed_db) -> None:
        ndcs = "&".join(f"ndcs={str(i).zfill(11)}" for i in range(101))
        resp = client.get(
            f"/api/v1/drugs/lookup/batch?{ndcs}",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 400

    def test_batch_lookup_skips_invalid_ndcs(self, client, seed_db) -> None:
        resp = client.get(
            "/api/v1/drugs/lookup/batch?ndcs=00093314905&ndcs=INVALID",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


class TestPricingHistory:
    def test_pricing_history_returned(self, client, seed_db) -> None:
        resp = client.get(
            "/api/v1/drugs/pricing/00093314905/history",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["price_type"] == "NADAC"

    def test_pricing_invalid_ndc_history_returns_400(self, client, seed_db) -> None:
        resp = client.get(
            "/api/v1/drugs/pricing/BADINPUT/history",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 400


class TestDeleteOverride:
    def test_delete_nonexistent_override_returns_404(self, client, seed_db) -> None:
        fake_id = uuid.uuid4()
        resp = client.delete(
            f"/api/v1/drugs/overrides/{fake_id}",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 404

    def test_delete_other_tenant_override_returns_404(self, client, seed_db) -> None:
        resp = client.delete(
            "/api/v1/drugs/overrides/ffffffff-ffff-ffff-ffff-ffffffffffff",
            headers={"X-Tenant-Id": TENANT_B},
        )
        assert resp.status_code == 404


class TestEquivalentsInvalidNDC:
    def test_invalid_ndc_returns_400(self, client, seed_db) -> None:
        resp = client.get(
            "/api/v1/drugs/equivalents/BADINPUT",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 400


class TestREMSInvalidNDC:
    def test_invalid_ndc_returns_400(self, client, seed_db) -> None:
        resp = client.get(
            "/api/v1/drugs/rems/BADINPUT",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 400


class TestRefreshStatus:
    def test_refresh_status_returns_list(self, client, seed_db) -> None:
        resp = client.get(
            "/api/v1/drugs/refresh/status",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestFDBAdapterStub:
    """FDB adapter stub raises NotImplementedError on all concrete methods."""

    def test_fetch_feed_raises(self) -> None:
        stub = FDBAdapterStub()
        with pytest.raises(NotImplementedError, match="FDB spec TBD"):
            stub.fetch_feed()

    def test_parse_feed_raises(self) -> None:
        stub = FDBAdapterStub()
        with pytest.raises(NotImplementedError, match="FDB spec TBD"):
            stub.parse_feed(b"")

    def test_parse_pricing_raises(self) -> None:
        stub = FDBAdapterStub()
        with pytest.raises(NotImplementedError, match="FDB spec TBD"):
            stub.parse_pricing(b"")

    def test_parse_interactions_raises(self) -> None:
        stub = FDBAdapterStub()
        with pytest.raises(NotImplementedError, match="FDB spec TBD"):
            stub.parse_interactions(b"")

    def test_parse_dosing_raises(self) -> None:
        stub = FDBAdapterStub()
        with pytest.raises(NotImplementedError, match="FDB spec TBD"):
            stub.parse_dosing(b"")
