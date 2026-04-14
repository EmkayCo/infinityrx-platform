"""Final coverage gap tests — reaches 99% threshold."""
from __future__ import annotations

import sys
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import pytest

from src.services.fda_ndc_parser import parse_fda_ndc_csv
from src.services.mac_list import MACListError, parse_mac_list_csv
from src.services.nadac_parser import parse_nadac_csv
from src.utils.ndc import InvalidNDCError, normalize_ndc


class TestNDCDashSegmentTotalNot10Or11:
    def test_dash_format_with_wrong_total_digits_raises(self) -> None:
        # 3-3-2 = 8 digits total — neither 10 nor 11
        with pytest.raises(InvalidNDCError, match="must total 10 or 11"):
            normalize_ndc("000-333-22")


class TestFDAParserCSVInvalidNDC:
    def test_csv_with_invalid_ndc_row_skipped(self) -> None:
        # The CSV parse path delegates to parse_fda_ndc_json; test the CSV wrapper covers lines 77-79
        csv_content = "package_ndc,brand_name\nBADNDC,TestDrug\n00093-3149-05,ValidDrug\n"
        result = parse_fda_ndc_csv(csv_content)
        # BADNDC should be skipped; only the valid NDC returned
        assert len(result) == 1
        assert result[0]["ndc_11"] == "00093314905"


class TestMACListParserEdgeCases:
    def test_invalid_price_string_raises_error(self) -> None:
        tenant_id = uuid.uuid4()
        csv_content = "ndc,price_per_unit,effective_date\n00093314905,not_a_number,2026-01-01\n"
        with pytest.raises(MACListError) as exc_info:
            parse_mac_list_csv(csv_content, tenant_id)
        assert any(
            "Invalid price_per_unit" in e_str
            for err in exc_info.value.errors
            for e_str in err["errors"]
        )

    def test_parse_date_invalid_format_returns_none_for_termination(self) -> None:
        # termination_date with invalid format → _parse_date returns None (lines 111-112)
        tenant_id = uuid.uuid4()
        csv_content = (
            "ndc,price_per_unit,effective_date,termination_date\n"
            "00093314905,0.030000,2026-01-01,not-a-date\n"
        )
        result = parse_mac_list_csv(csv_content, tenant_id)
        # Invalid termination_date silently becomes None
        assert result[0]["termination_date"] is None


class TestNADACParserDateParseError:
    def test_invalid_effective_date_row_skipped(self) -> None:
        # Lines 79-80: date.fromisoformat raises ValueError → row skipped
        csv_content = (
            "ndc,nadac_per_unit,effective_date\n"
            "00093314905,0.045000,not-a-date\n"
            "00093314906,0.050000,2026-01-01\n"
        )
        result = parse_nadac_csv(csv_content)
        # Row with bad date is skipped
        assert len(result) == 1
        assert result[0]["ndc_11"] == "00093314906"


class TestRouterSchemaValidatorNDC:
    """Trigger schema validator ValueError for invalid NDC (schemas/drugs.py lines 130-133)."""

    def test_ndc_lookup_params_schema_invalid_ndc(self) -> None:
        from src.api.schemas.drugs import NDCLookupParams
        with pytest.raises(Exception):
            NDCLookupParams(ndc_11="INVALID")


class TestRouterPricingNoEffectivePrice:
    """Test router path where select_effective_price returns None (branch 151->138)."""

    def test_pricing_returns_empty_when_no_effective_price(self) -> None:
        from fastapi.testclient import TestClient
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from src.api.dependencies import get_db
        from src.main import create_app
        from src.models.tables import DrugBase, DrugPricing, DrugProduct

        engine = create_engine(
            "sqlite:///file:drug_no_eff_price?mode=memory&cache=shared&uri=true",
            connect_args={"check_same_thread": False},
        )
        for table in DrugBase.metadata.tables.values():
            table.schema = None
        DrugBase.metadata.create_all(engine)

        Factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        _NOW = datetime.now(timezone.utc)

        session = Factory()
        drug = DrugProduct(
            ndc_11="11111111111",
            ndc_formatted="11111-1111-11",
            labeler_code="11111",
            product_code="1111",
            package_code="11",
            drug_name_display="TestDrug",
            nonproprietary_name="testdrug",
            drug_type="generic",
            marketing_status="active",
            is_active=True,
            is_specialty=False,
            is_biosimilar=False,
            is_glp1=False,
            unit_dose=False,
            is_limited_distribution=False,
            data_source="fda_ndc",
            last_updated_at=_NOW,
            created_at=_NOW,
            updated_at=_NOW,
        )
        session.add(drug)
        # Add a pricing entry whose effective_date is in the FUTURE so it won't be selected as of today
        # Actually the select_effective_price returns None when termination_date < requested_date
        # Add a terminated pricing record
        pricing = DrugPricing(
            ndc_11="11111111111",
            price_type="AWP",
            price_per_unit=Decimal("1.000000"),
            effective_date=date(2020, 1, 1),
            termination_date=date(2020, 6, 1),  # terminated before today
            data_source="fda_ndc",
            created_at=_NOW,
        )
        session.add(pricing)
        session.commit()
        session.close()

        app = create_app()

        def _override_db():
            s = Factory()
            try:
                yield s
            finally:
                s.close()

        app.dependency_overrides[get_db] = _override_db
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(
            "/api/v1/drugs/pricing/11111111111",
            headers={"X-Tenant-Id": "11111111-1111-1111-1111-111111111111"},
        )
        assert resp.status_code == 200
        # The terminated entry is excluded, so result is empty
        assert resp.json() == []

        DrugBase.metadata.drop_all(engine)
        engine.dispose()


class TestRouterUpdateExistingOverride:
    """Test router path that updates an existing override (lines 274-276)."""

    def test_upload_mac_list_updates_existing_override(self) -> None:
        from fastapi.testclient import TestClient
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from src.api.dependencies import get_db
        from src.main import create_app
        from src.models.tables import DrugBase, DrugProduct, TenantPricingOverride

        engine = create_engine(
            "sqlite:///file:drug_update_override?mode=memory&cache=shared&uri=true",
            connect_args={"check_same_thread": False},
        )
        for table in DrugBase.metadata.tables.values():
            table.schema = None
        DrugBase.metadata.create_all(engine)

        Factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        _NOW = datetime.now(timezone.utc)
        TENANT = "22222222-2222-2222-2222-222222222222"

        session = Factory()
        drug = DrugProduct(
            ndc_11="22222222222",
            ndc_formatted="22222-2222-22",
            labeler_code="22222",
            product_code="2222",
            package_code="22",
            drug_name_display="TestDrug2",
            nonproprietary_name="testdrug2",
            drug_type="generic",
            marketing_status="active",
            is_active=True,
            is_specialty=False,
            is_biosimilar=False,
            is_glp1=False,
            unit_dose=False,
            is_limited_distribution=False,
            data_source="fda_ndc",
            last_updated_at=_NOW,
            created_at=_NOW,
            updated_at=_NOW,
        )
        session.add(drug)
        # Pre-seed an existing override so upload triggers the UPDATE path
        existing = TenantPricingOverride(
            id=uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"),
            tenant_id=uuid.UUID(TENANT),
            ndc_11="22222222222",
            price_type="MAC",
            price_per_unit=Decimal("0.010000"),
            effective_date=date(2026, 1, 1),
            data_source="tenant_mac",
            created_at=_NOW,
            updated_at=_NOW,
        )
        session.add(existing)
        session.commit()
        session.close()

        app = create_app()

        def _override_db():
            s = Factory()
            try:
                yield s
            finally:
                s.close()

        app.dependency_overrides[get_db] = _override_db
        client = TestClient(app, raise_server_exceptions=False)

        csv_content = "ndc,price_per_unit,effective_date\n22222222222,0.020000,2026-01-01\n"
        resp = client.post(
            "/api/v1/drugs/overrides/upload",
            files={"file": ("mac.csv", csv_content.encode(), "text/csv")},
            headers={"X-Tenant-Id": TENANT},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["records_applied"] == 1

        DrugBase.metadata.drop_all(engine)
        engine.dispose()


class TestRouterShortagesWithStatusFilter:
    """Test shortages listing with status filter (branch 328->330)."""

    def test_list_shortages_with_status_filter(self) -> None:
        from fastapi.testclient import TestClient
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from src.api.dependencies import get_db
        from src.main import create_app
        from src.models.tables import DrugBase, DrugShortage

        engine = create_engine(
            "sqlite:///file:drug_shortage_filter?mode=memory&cache=shared&uri=true",
            connect_args={"check_same_thread": False},
        )
        for table in DrugBase.metadata.tables.values():
            table.schema = None
        DrugBase.metadata.create_all(engine)

        Factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        _NOW = datetime.now(timezone.utc)
        TENANT = "33333333-3333-3333-3333-333333333333"

        session = Factory()
        session.add(DrugShortage(
            ndc_11="33333333333",
            shortage_status="active",
            start_date=date(2026, 1, 1),
            created_at=_NOW,
        ))
        session.add(DrugShortage(
            ndc_11="33333333334",
            shortage_status="resolved",
            start_date=date(2025, 6, 1),
            created_at=_NOW,
        ))
        session.commit()
        session.close()

        app = create_app()

        def _override_db():
            s = Factory()
            try:
                yield s
            finally:
                s.close()

        app.dependency_overrides[get_db] = _override_db
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(
            "/api/v1/drugs/shortages?status=active",
            headers={"X-Tenant-Id": TENANT},
        )
        assert resp.status_code == 200
        results = resp.json()
        assert all(r["shortage_status"] == "active" for r in results)
        assert len(results) == 1

        DrugBase.metadata.drop_all(engine)
        engine.dispose()


class TestRouterShortageInvalidNDC:
    """Test GET /shortages/{ndc} with invalid NDC (lines 337-338)."""

    def test_get_shortage_invalid_ndc_returns_400(self) -> None:
        from fastapi.testclient import TestClient
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from src.api.dependencies import get_db
        from src.main import create_app
        from src.models.tables import DrugBase

        engine = create_engine(
            "sqlite:///file:drug_shortage_badndc?mode=memory&cache=shared&uri=true",
            connect_args={"check_same_thread": False},
        )
        for table in DrugBase.metadata.tables.values():
            table.schema = None
        DrugBase.metadata.create_all(engine)

        Factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        app = create_app()

        def _override_db():
            s = Factory()
            try:
                yield s
            finally:
                s.close()

        app.dependency_overrides[get_db] = _override_db
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(
            "/api/v1/drugs/shortages/BADNDC",
            headers={"X-Tenant-Id": "33333333-3333-3333-3333-333333333333"},
        )
        assert resp.status_code == 400

        DrugBase.metadata.drop_all(engine)
        engine.dispose()


class TestDependenciesGetDB:
    """Cover get_db generator (dependencies.py lines 14-15) via TestClient."""

    def test_get_db_dependency_health_endpoint(self) -> None:
        from fastapi.testclient import TestClient
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from src.api.dependencies import get_db
        from src.main import create_app
        from src.models.tables import DrugBase

        engine = create_engine(
            "sqlite:///file:drug_deps_health?mode=memory&cache=shared&uri=true",
            connect_args={"check_same_thread": False},
        )
        for table in DrugBase.metadata.tables.values():
            table.schema = None
        DrugBase.metadata.create_all(engine)

        Factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        app = create_app()

        # Use the REAL get_db (not overridden) which calls get_db_session — but
        # we patch get_db_session to yield our test session
        from contextlib import contextmanager
        from unittest.mock import patch as mpatch

        @contextmanager
        def _fake_session_ctx():
            s = Factory()
            try:
                yield s
            finally:
                s.close()

        with mpatch("src.api.dependencies.get_db_session", _fake_session_ctx):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get(
                "/api/v1/drugs/health",
                headers={"X-Tenant-Id": "44444444-4444-4444-4444-444444444444"},
            )
        assert resp.status_code == 200

        DrugBase.metadata.drop_all(engine)
        engine.dispose()
