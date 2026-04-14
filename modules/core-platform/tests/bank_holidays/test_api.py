"""Tests for the bank holidays REST API.

Strategy
--------
Uses FastAPI's dependency_overrides to inject a real Postgres session (the
same bh_db_session fixture from conftest.py) so the API handler exercises the
real ORM queries against core.bank_holidays.  Each test is isolated by the
transaction-rollback strategy in bh_db_session.

Auth is exercised via the shim auth module (set_current_user).
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src._shim import auth as auth_shim
from src._shim.db import get_session as shim_get_session
from src.bank_holidays.api import router as bh_router
from shared.db.models.bank_holidays import BankHoliday


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app(pg_session) -> FastAPI:
    """Build a test FastAPI app that injects the Postgres session."""
    app = FastAPI()
    app.include_router(bh_router, prefix="/api/v1")

    def _override_session():
        yield pg_session

    app.dependency_overrides[shim_get_session] = _override_session
    return app


def _seed(session, d: date, name: str, country: str = "US", is_bank: bool = True) -> BankHoliday:
    h = BankHoliday(
        id=uuid.uuid4(),
        holiday_date=d,
        name=name,
        country=country,
        is_federal=True,
        is_bank_holiday=is_bank,
    )
    session.add(h)
    session.flush()
    return h


# ---------------------------------------------------------------------------
# GET /bank-holidays — list
# ---------------------------------------------------------------------------


def test_list_holidays_empty(bh_db_session, tenant_admin_a) -> None:
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=True)
    resp = client.get("/api/v1/bank-holidays?year=2099")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_holidays_returns_seeded(bh_db_session, tenant_admin_a) -> None:
    _seed(bh_db_session, date(2026, 7, 3), "Independence Day (Observed)")
    _seed(bh_db_session, date(2026, 9, 7), "Labor Day")
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=True)
    resp = client.get("/api/v1/bank-holidays?year=2026")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    names = {r["name"] for r in data}
    assert "Independence Day (Observed)" in names
    assert "Labor Day" in names


def test_list_holidays_country_filter(bh_db_session, tenant_admin_a) -> None:
    _seed(bh_db_session, date(2026, 7, 1), "Canada Day", country="CA")
    _seed(bh_db_session, date(2026, 7, 3), "US Holiday", country="US")
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=True)
    resp = client.get("/api/v1/bank-holidays?year=2026&country=CA")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["country"] == "CA"


def test_list_holidays_requires_auth(bh_db_session) -> None:
    auth_shim.set_current_user(None)
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=False)
    resp = client.get("/api/v1/bank-holidays?year=2026")
    assert resp.status_code in (401, 422, 500)


def test_list_holidays_invalid_year(bh_db_session, tenant_admin_a) -> None:
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=True)
    resp = client.get("/api/v1/bank-holidays?year=abc")
    assert resp.status_code == 422


def test_list_holidays_year_too_low(bh_db_session, tenant_admin_a) -> None:
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=True)
    resp = client.get("/api/v1/bank-holidays?year=1800")
    assert resp.status_code == 422


def test_list_holidays_year_too_high(bh_db_session, tenant_admin_a) -> None:
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=True)
    resp = client.get("/api/v1/bank-holidays?year=2201")
    assert resp.status_code == 422


def test_list_holidays_response_shape(bh_db_session, tenant_admin_a) -> None:
    _seed(bh_db_session, date(2026, 7, 3), "Independence Day (Observed)")
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=True)
    resp = client.get("/api/v1/bank-holidays?year=2026")
    row = resp.json()[0]
    assert "id" in row
    assert "holiday_date" in row
    assert "name" in row
    assert "country" in row
    assert "is_federal" in row
    assert "is_bank_holiday" in row
    assert "created_at" in row


# ---------------------------------------------------------------------------
# POST /bank-holidays — create custom
# ---------------------------------------------------------------------------


def test_create_holiday_happy_path(bh_db_session, tenant_admin_a) -> None:
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=True)
    resp = client.post(
        "/api/v1/bank-holidays",
        json={"holiday_date": "2026-08-15", "name": "Custom Closure"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["holiday_date"] == "2026-08-15"
    assert data["name"] == "Custom Closure"
    assert data["country"] == "US"
    assert data["is_federal"] is False


def test_create_holiday_custom_country(bh_db_session, tenant_admin_a) -> None:
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=True)
    resp = client.post(
        "/api/v1/bank-holidays",
        json={"holiday_date": "2026-08-04", "name": "Civic Holiday", "country": "ca"},
    )
    assert resp.status_code == 201
    assert resp.json()["country"] == "CA"


def test_create_holiday_non_bank(bh_db_session, tenant_admin_a) -> None:
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=True)
    resp = client.post(
        "/api/v1/bank-holidays",
        json={"holiday_date": "2026-10-12", "name": "Columbus Day", "is_bank_holiday": False},
    )
    assert resp.status_code == 201
    assert resp.json()["is_bank_holiday"] is False


def test_create_holiday_invalid_date(bh_db_session, tenant_admin_a) -> None:
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=True)
    resp = client.post(
        "/api/v1/bank-holidays",
        json={"holiday_date": "not-a-date", "name": "Bad"},
    )
    assert resp.status_code == 422


def test_create_holiday_missing_name(bh_db_session, tenant_admin_a) -> None:
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=True)
    resp = client.post(
        "/api/v1/bank-holidays",
        json={"holiday_date": "2026-08-15"},
    )
    assert resp.status_code == 422


def test_create_holiday_requires_admin(bh_db_session, tenant_operator_a) -> None:
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=True)
    resp = client.post(
        "/api/v1/bank-holidays",
        json={"holiday_date": "2026-08-15", "name": "Custom"},
    )
    assert resp.status_code == 403


def test_create_holiday_duplicate_returns_409(bh_db_session, tenant_admin_a) -> None:
    """Duplicate (date, country) must return HTTP 409.

    Note: The POST handler catches IntegrityError and rolls back internally,
    so the outer bh_db_session transaction remains valid after this test.
    We use a fresh connection to avoid transaction state issues.
    """
    from shared.config import get_settings
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL_SYNC, future=True)
    conn = engine.connect()
    trans = conn.begin()
    SessionLocal = sessionmaker(bind=conn, expire_on_commit=False)
    pg_session = SessionLocal()

    try:
        # Pre-seed the duplicate row
        h = BankHoliday(
            id=uuid.uuid4(),
            holiday_date=date(2026, 8, 15),
            name="Existing Holiday",
            country="US",
            is_federal=True,
            is_bank_holiday=True,
        )
        pg_session.add(h)
        pg_session.flush()

        app = FastAPI()
        app.include_router(bh_router, prefix="/api/v1")

        def _override():
            yield pg_session

        app.dependency_overrides[shim_get_session] = _override
        client = TestClient(app, raise_server_exceptions=True)

        resp = client.post(
            "/api/v1/bank-holidays",
            json={"holiday_date": "2026-08-15", "name": "Duplicate"},
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["error"] == "holiday_already_exists"
    finally:
        pg_session.close()
        # The handler's session.rollback() already deassociates the transaction;
        # suppress the resulting SAWarning on cleanup.
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                trans.rollback()
            except Exception:
                pass
        conn.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# GET /bank-holidays/is-business-day/{iso_date}
# ---------------------------------------------------------------------------


def test_is_business_day_weekday_no_holiday(bh_db_session, tenant_admin_a) -> None:
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=True)
    resp = client.get("/api/v1/bank-holidays/is-business-day/2026-07-07")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_business_day"] is True
    assert data["reason"] is None


def test_is_business_day_saturday(bh_db_session, tenant_admin_a) -> None:
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=True)
    resp = client.get("/api/v1/bank-holidays/is-business-day/2026-07-04")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_business_day"] is False
    assert data["reason"] == "Saturday"


def test_is_business_day_sunday(bh_db_session, tenant_admin_a) -> None:
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=True)
    resp = client.get("/api/v1/bank-holidays/is-business-day/2026-07-05")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_business_day"] is False
    assert data["reason"] == "Sunday"


def test_is_business_day_holiday(bh_db_session, tenant_admin_a) -> None:
    _seed(bh_db_session, date(2026, 7, 3), "Independence Day (Observed)")
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=True)
    resp = client.get("/api/v1/bank-holidays/is-business-day/2026-07-03")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_business_day"] is False
    assert data["reason"] == "Independence Day (Observed)"


def test_is_business_day_date_field(bh_db_session, tenant_admin_a) -> None:
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=True)
    resp = client.get("/api/v1/bank-holidays/is-business-day/2026-07-07")
    assert resp.json()["date"] == "2026-07-07"


def test_is_business_day_invalid_date(bh_db_session, tenant_admin_a) -> None:
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=True)
    # Must use strict ISO 8601 (YYYY-MM-DD); dashes required
    resp = client.get("/api/v1/bank-holidays/is-business-day/not-a-date")
    assert resp.status_code == 422


def test_is_business_day_invalid_month_overflow(bh_db_session, tenant_admin_a) -> None:
    """2026-13-01 passes the YYYY-MM-DD regex but fromisoformat raises ValueError."""
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=True)
    resp = client.get("/api/v1/bank-holidays/is-business-day/2026-13-01")
    assert resp.status_code == 422


def test_is_business_day_requires_auth(bh_db_session) -> None:
    auth_shim.set_current_user(None)
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=False)
    resp = client.get("/api/v1/bank-holidays/is-business-day/2026-07-07")
    assert resp.status_code in (401, 422, 500)


def test_is_business_day_non_bank_holiday_counts_as_business(bh_db_session, tenant_admin_a) -> None:
    """is_bank_holiday=False should not block the day."""
    _seed(bh_db_session, date(2026, 10, 12), "Columbus Day", is_bank=False)
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=True)
    # Oct 12 2026 = Monday
    resp = client.get("/api/v1/bank-holidays/is-business-day/2026-10-12")
    assert resp.status_code == 200
    assert resp.json()["is_business_day"] is True


# ---------------------------------------------------------------------------
# GET /bank-holidays/next-business-day/{iso_date}
# ---------------------------------------------------------------------------


def test_next_business_day_happy_path(bh_db_session, tenant_admin_a) -> None:
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=True)
    resp = client.get("/api/v1/bank-holidays/next-business-day/2026-07-10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["from"] == "2026-07-10"
    assert data["next_business_day"] == "2026-07-13"


def test_next_business_day_from_saturday(bh_db_session, tenant_admin_a) -> None:
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=True)
    resp = client.get("/api/v1/bank-holidays/next-business-day/2026-07-04")
    assert resp.status_code == 200
    assert resp.json()["next_business_day"] == "2026-07-06"


def test_next_business_day_skips_holiday(bh_db_session, tenant_admin_a) -> None:
    _seed(bh_db_session, date(2026, 9, 7), "Labor Day")
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=True)
    resp = client.get("/api/v1/bank-holidays/next-business-day/2026-09-04")
    assert resp.status_code == 200
    assert resp.json()["next_business_day"] == "2026-09-08"


def test_next_business_day_invalid_date(bh_db_session, tenant_admin_a) -> None:
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=True)
    resp = client.get("/api/v1/bank-holidays/next-business-day/bad-date")
    assert resp.status_code == 422


def test_next_business_day_invalid_month_overflow(bh_db_session, tenant_admin_a) -> None:
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=True)
    resp = client.get("/api/v1/bank-holidays/next-business-day/2026-14-01")
    assert resp.status_code == 422


def test_next_business_day_requires_auth(bh_db_session) -> None:
    auth_shim.set_current_user(None)
    client = TestClient(_make_app(bh_db_session), raise_server_exceptions=False)
    resp = client.get("/api/v1/bank-holidays/next-business-day/2026-07-10")
    assert resp.status_code in (401, 422, 500)
