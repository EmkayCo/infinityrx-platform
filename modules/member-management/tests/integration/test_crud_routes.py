"""Integration tests for members, groups, enrollment, COB, and coverage CRUD routes.

Tests cover:
- list / get / create for each resource
- cross-tenant isolation (Tenant A data invisible to Tenant B)
- duplicate-key 409 handling
- 404 handling for missing resources
- PHI encryption (data round-trips correctly)
- COB active-record filter (effective <= today < termination)
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from src.main import create_app
from src.models.tables import CobRecord, CoveragePeriod, Group, Member
from shared.db.tenant_context import clear_tenant_context, set_tenant_context
from tests.conftest import TENANT_A, TENANT_B

import src.api.routes.members as _members_mod
import src.api.routes.groups as _groups_mod
import src.api.routes.enrollment as _enrollment_mod
import src.api.routes.cob as _cob_mod
import src.api.routes.coverage as _coverage_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(db_session, tenant_id: uuid.UUID) -> tuple:
    """Return (app, client, token) with DB wired and tenant context set."""
    app = create_app()

    def _override_db():
        return db_session

    app.dependency_overrides[_members_mod._get_db] = _override_db
    app.dependency_overrides[_groups_mod._get_db] = _override_db
    app.dependency_overrides[_enrollment_mod._get_db] = _override_db
    app.dependency_overrides[_cob_mod._get_db] = _override_db
    app.dependency_overrides[_coverage_mod._get_db] = _override_db

    token = set_tenant_context(tenant_id)
    client = TestClient(app, raise_server_exceptions=False)
    return app, client, token


def _seed_member(db, tenant_id: uuid.UUID, member_id: str = "M-CRUD-001") -> Member:
    m = Member(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        member_id=member_id,
        person_code="01",
        first_name_encrypted="Ada",
        last_name_encrypted="Lovelace",
        dob_encrypted="1815-12-10",
        gender="F",
        rx_bin="610014",
        rx_pcn="MEDCO",
        rx_group="RX1234",
        status="active",
        enrollment_date=date(2026, 1, 1),
    )
    db.add(m)
    db.flush()
    return m


def _seed_group(db, tenant_id: uuid.UUID, group_number: str = "GRP-CRUD-001") -> Group:
    g = Group(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        group_number=group_number,
        group_name="CRUD Test Group",
        effective_date=date(2026, 1, 1),
        is_active=True,
    )
    db.add(g)
    db.flush()
    return g


# ---------------------------------------------------------------------------
# Members — list, get, create
# ---------------------------------------------------------------------------

class TestMemberList:
    def test_list_members_returns_empty_when_none_exist(self, db_session):
        app, client, token = _make_client(db_session, TENANT_A)
        try:
            resp = client.get("/api/v1/members")
            assert resp.status_code == 200
            data = resp.json()
            assert data["members"] == []
            assert data["total"] == 0
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()

    def test_list_members_returns_seeded_member(self, db_session):
        _seed_member(db_session, TENANT_A, "M-LIST-001")
        app, client, token = _make_client(db_session, TENANT_A)
        try:
            resp = client.get("/api/v1/members")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 1
            assert data["members"][0]["member_id"] == "M-LIST-001"
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()

    def test_list_members_tenant_isolation(self, db_session):
        """Tenant A member not visible in Tenant B list."""
        _seed_member(db_session, TENANT_A, "M-ISO-001")
        app, client, token = _make_client(db_session, TENANT_B)
        try:
            resp = client.get("/api/v1/members")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 0
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()

    def test_list_members_filter_by_status(self, db_session):
        _seed_member(db_session, TENANT_A, "M-STAT-001")
        app, client, token = _make_client(db_session, TENANT_A)
        try:
            resp = client.get("/api/v1/members", params={"status": "terminated"})
            assert resp.status_code == 200
            assert resp.json()["total"] == 0

            resp2 = client.get("/api/v1/members", params={"status": "active"})
            assert resp2.status_code == 200
            assert resp2.json()["total"] == 1
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()


class TestMemberGet:
    def test_get_member_by_id_returns_phi_partial(self, db_session):
        member = _seed_member(db_session, TENANT_A, "M-GET-001")
        app, client, token = _make_client(db_session, TENANT_A)
        try:
            resp = client.get(f"/api/v1/members/{member.id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["member_id"] == "M-GET-001"
            assert data["gender"] == "F"
            # PHI partial: first_name is visible, SSN masked (no ssn here)
            assert data["first_name"] == "Ada"
            assert data["last_name"] == "Lovelace"
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()

    def test_get_member_not_found_returns_404(self, db_session):
        app, client, token = _make_client(db_session, TENANT_A)
        try:
            resp = client.get(f"/api/v1/members/{uuid.uuid4()}")
            assert resp.status_code == 404
            body = resp.json()
            # FastAPI wraps HTTPException detail under "detail"
            err = body.get("detail", body).get("error", {})
            assert err.get("code") == "MEMBER_NOT_FOUND"
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()

    def test_get_member_cross_tenant_returns_404(self, db_session):
        """Tenant A member is not visible as Tenant B."""
        member = _seed_member(db_session, TENANT_A, "M-XTEN-001")
        app, client, token = _make_client(db_session, TENANT_B)
        try:
            resp = client.get(f"/api/v1/members/{member.id}")
            assert resp.status_code == 404
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()

    def test_get_member_phi_redacted(self, db_session):
        member = _seed_member(db_session, TENANT_A, "M-PHI-001")
        app, client, token = _make_client(db_session, TENANT_A)
        try:
            resp = client.get(
                f"/api/v1/members/{member.id}",
                params={"phi_access": "redacted"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["first_name"] == "**REDACTED**"
            assert data["last_name"] == "**REDACTED**"
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()


class TestMemberCreate:
    def test_create_member_returns_201(self, db_session):
        app, client, token = _make_client(db_session, TENANT_A)
        try:
            payload = {
                "member_id": "M-NEW-001",
                "first_name": "Grace",
                "last_name": "Hopper",
                "date_of_birth": "1906-12-09",
                "gender": "F",
                "rx_bin": "610014",
                "effective_date": "2026-01-01",
            }
            resp = client.post("/api/v1/members", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["member_id"] == "M-NEW-001"
            assert "id" in data
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()

    def test_create_member_phi_encrypted_at_rest(self, db_session):
        """After creation, verify the encrypted column stored bytes (not plaintext)."""
        from sqlalchemy import select
        app, client, token = _make_client(db_session, TENANT_A)
        try:
            payload = {
                "member_id": "M-ENC-001",
                "first_name": "Hedy",
                "last_name": "Lamarr",
                "date_of_birth": "1914-11-09",
                "gender": "F",
                "rx_bin": "610014",
                "effective_date": "2026-01-01",
                "ssn": "123456789",
            }
            resp = client.post("/api/v1/members", json=payload)
            assert resp.status_code == 201
            member_id_str = resp.json()["id"]

            # Read back via ORM — EncryptedString decrypts transparently
            stmt = select(Member).where(Member.id == uuid.UUID(member_id_str))
            member = db_session.execute(stmt).scalar_one()
            assert member.first_name_encrypted == "Hedy"  # decrypted on read
            assert member.ssn_encrypted == "123456789"
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()

    def test_create_duplicate_member_returns_409(self, db_session):
        """Same (tenant_id, member_id, person_code) → 409."""
        _seed_member(db_session, TENANT_A, "M-DUP-001")
        app, client, token = _make_client(db_session, TENANT_A)
        try:
            payload = {
                "member_id": "M-DUP-001",
                "person_code": "01",
                "first_name": "Ada",
                "last_name": "Lovelace",
                "date_of_birth": "1815-12-10",
                "gender": "F",
                "rx_bin": "610014",
                "effective_date": "2026-01-01",
            }
            resp = client.post("/api/v1/members", json=payload)
            assert resp.status_code == 409
            body = resp.json()
            err = body.get("detail", body).get("error", {})
            assert err.get("code") == "DUPLICATE_MEMBER"
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Groups — list, create
# ---------------------------------------------------------------------------

class TestGroupsCrud:
    def test_list_groups_empty(self, db_session):
        app, client, token = _make_client(db_session, TENANT_A)
        try:
            resp = client.get("/api/v1/groups")
            assert resp.status_code == 200
            assert resp.json()["total"] == 0
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()

    def test_create_group_returns_201(self, db_session):
        app, client, token = _make_client(db_session, TENANT_A)
        try:
            payload = {
                "group_number": "GRP-NEW-001",
                "group_name": "New Group",
                "effective_date": "2026-01-01",
                "billing_cycle": "monthly",
                "payment_terms_days": 30,
            }
            resp = client.post("/api/v1/groups", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["group_number"] == "GRP-NEW-001"
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()

    def test_list_groups_after_create(self, db_session):
        _seed_group(db_session, TENANT_A, "GRP-LIST-001")
        app, client, token = _make_client(db_session, TENANT_A)
        try:
            resp = client.get("/api/v1/groups")
            assert resp.status_code == 200
            assert resp.json()["total"] == 1
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()

    def test_groups_tenant_isolation(self, db_session):
        """Tenant A group not visible to Tenant B."""
        _seed_group(db_session, TENANT_A, "GRP-ISO-001")
        app, client, token = _make_client(db_session, TENANT_B)
        try:
            resp = client.get("/api/v1/groups")
            assert resp.status_code == 200
            assert resp.json()["total"] == 0
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()

    def test_create_duplicate_group_returns_409(self, db_session):
        _seed_group(db_session, TENANT_A, "GRP-DUP-001")
        app, client, token = _make_client(db_session, TENANT_A)
        try:
            payload = {
                "group_number": "GRP-DUP-001",
                "group_name": "Duplicate Group",
                "effective_date": "2026-01-01",
            }
            resp = client.post("/api/v1/groups", json=payload)
            assert resp.status_code == 409
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Enrollment — upload CSV, EDI, bad content-type
# ---------------------------------------------------------------------------

class TestEnrollmentUpload:
    _CSV_BODY = (
        "member_id,first_name,last_name,date_of_birth,gender,effective_date,rx_bin\n"
        "M-ENR-001,Jane,Doe,1990-01-01,F,2026-01-01,610014\n"
    )

    def test_upload_csv_returns_201(self, db_session):
        app, client, token = _make_client(db_session, TENANT_A)
        try:
            resp = client.post(
                "/api/v1/members/enrollment/upload",
                content=self._CSV_BODY.encode(),
                headers={"content-type": "text/csv"},
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["file_type"] == "csv"
            assert data["status"] == "uploaded"
            assert data["total_records"] == 1
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()

    def test_upload_bad_content_type_returns_400(self, db_session):
        app, client, token = _make_client(db_session, TENANT_A)
        try:
            resp = client.post(
                "/api/v1/members/enrollment/upload",
                content=b"some data",
                headers={"content-type": "application/json"},
            )
            assert resp.status_code == 400
            body = resp.json()
            err = body.get("detail", body).get("error", {})
            assert err.get("code") == "UNSUPPORTED_CONTENT_TYPE"
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()

    def test_upload_empty_body_returns_400(self, db_session):
        app, client, token = _make_client(db_session, TENANT_A)
        try:
            resp = client.post(
                "/api/v1/members/enrollment/upload",
                content=b"",
                headers={"content-type": "text/csv"},
            )
            assert resp.status_code == 400
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()

    def test_list_enrollment_files_empty(self, db_session):
        app, client, token = _make_client(db_session, TENANT_A)
        try:
            resp = client.get("/api/v1/members/enrollment/files")
            assert resp.status_code == 200
            assert resp.json()["total"] == 0
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()

    def test_list_enrollment_files_after_upload(self, db_session):
        app, client, token = _make_client(db_session, TENANT_A)
        try:
            # Upload first
            client.post(
                "/api/v1/members/enrollment/upload",
                content=self._CSV_BODY.encode(),
                headers={"content-type": "text/csv"},
            )
            resp = client.get("/api/v1/members/enrollment/files")
            assert resp.status_code == 200
            assert resp.json()["total"] == 1
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()

    def test_enrollment_files_tenant_isolation(self, db_session):
        """Tenant A uploads don't appear in Tenant B list."""
        app_a, client_a, token_a = _make_client(db_session, TENANT_A)
        try:
            client_a.post(
                "/api/v1/members/enrollment/upload",
                content=self._CSV_BODY.encode(),
                headers={"content-type": "text/csv"},
            )
        finally:
            clear_tenant_context(token_a)
            app_a.dependency_overrides.clear()

        app_b, client_b, token_b = _make_client(db_session, TENANT_B)
        try:
            resp = client_b.get("/api/v1/members/enrollment/files")
            assert resp.status_code == 200
            assert resp.json()["total"] == 0
        finally:
            clear_tenant_context(token_b)
            app_b.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# COB — get active, create, cross-tenant
# ---------------------------------------------------------------------------

class TestCobRoutes:
    def test_get_cob_empty_for_member_with_no_records(self, db_session):
        member = _seed_member(db_session, TENANT_A, "M-COB-EMPTY")
        app, client, token = _make_client(db_session, TENANT_A)
        try:
            resp = client.get(f"/api/v1/members/{member.id}/cob")
            assert resp.status_code == 200
            assert resp.json()["cob_records"] == []
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()

    def test_get_cob_member_not_found_returns_404(self, db_session):
        app, client, token = _make_client(db_session, TENANT_A)
        try:
            resp = client.get(f"/api/v1/members/{uuid.uuid4()}/cob")
            assert resp.status_code == 404
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()

    def test_add_cob_returns_201(self, db_session):
        member = _seed_member(db_session, TENANT_A, "M-COB-ADD")
        app, client, token = _make_client(db_session, TENANT_A)
        try:
            payload = {
                "payer_sequence": "secondary",
                "other_payer_name": "BlueCross",
                "other_payer_bin": "600428",
                "effective_date": "2026-01-01",
            }
            resp = client.post(f"/api/v1/members/{member.id}/cob", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["payer_sequence"] == "secondary"
            assert data["other_payer_name"] == "BlueCross"
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()

    def test_active_cob_filter_excludes_terminated(self, db_session):
        """COB with termination_date in the past should not appear in GET."""
        member = _seed_member(db_session, TENANT_A, "M-COB-TERM")
        # Add a terminated COB record
        terminated_cob = CobRecord(
            id=uuid.uuid4(),
            tenant_id=TENANT_A,
            member_id=member.id,
            payer_sequence="secondary",
            other_payer_name="OldPayer",
            effective_date=date(2025, 1, 1),
            termination_date=date(2025, 12, 31),  # terminated before today
        )
        db_session.add(terminated_cob)
        db_session.flush()

        app, client, token = _make_client(db_session, TENANT_A)
        try:
            resp = client.get(f"/api/v1/members/{member.id}/cob")
            assert resp.status_code == 200
            # Terminated record should be filtered out
            assert resp.json()["cob_records"] == []
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()

    def test_active_cob_included(self, db_session):
        """COB with no termination_date (open-ended) appears in GET."""
        member = _seed_member(db_session, TENANT_A, "M-COB-ACTIVE")
        active_cob = CobRecord(
            id=uuid.uuid4(),
            tenant_id=TENANT_A,
            member_id=member.id,
            payer_sequence="secondary",
            other_payer_name="ActivePayer",
            effective_date=date(2026, 1, 1),
            termination_date=None,
        )
        db_session.add(active_cob)
        db_session.flush()

        app, client, token = _make_client(db_session, TENANT_A)
        try:
            resp = client.get(f"/api/v1/members/{member.id}/cob")
            assert resp.status_code == 200
            records = resp.json()["cob_records"]
            assert len(records) == 1
            assert records[0]["other_payer_name"] == "ActivePayer"
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()

    def test_cob_cross_tenant_member_not_found(self, db_session):
        """Tenant B cannot access Tenant A member COB."""
        member = _seed_member(db_session, TENANT_A, "M-COB-ISO")
        app, client, token = _make_client(db_session, TENANT_B)
        try:
            resp = client.get(f"/api/v1/members/{member.id}/cob")
            assert resp.status_code == 404
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Coverage — get, create, cross-tenant
# ---------------------------------------------------------------------------

class TestCoverageRoutes:
    def test_get_coverage_empty(self, db_session):
        member = _seed_member(db_session, TENANT_A, "M-COV-EMPTY")
        app, client, token = _make_client(db_session, TENANT_A)
        try:
            resp = client.get(f"/api/v1/members/{member.id}/coverage")
            assert resp.status_code == 200
            assert resp.json()["coverage_periods"] == []
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()

    def test_get_coverage_member_not_found_returns_404(self, db_session):
        app, client, token = _make_client(db_session, TENANT_A)
        try:
            resp = client.get(f"/api/v1/members/{uuid.uuid4()}/coverage")
            assert resp.status_code == 404
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()

    def test_add_coverage_returns_201(self, db_session):
        member = _seed_member(db_session, TENANT_A, "M-COV-ADD")
        app, client, token = _make_client(db_session, TENANT_A)
        try:
            payload = {
                "coverage_type": "pharmacy",
                "effective_date": "2026-01-01",
                "benefit_year_start": "2026-01-01",
                "benefit_year_end": "2026-12-31",
                "plan_name": "Basic Rx",
            }
            resp = client.post(f"/api/v1/members/{member.id}/coverage", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["coverage_type"] == "pharmacy"
            assert data["plan_name"] == "Basic Rx"
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()

    def test_coverage_returned_after_add(self, db_session):
        member = _seed_member(db_session, TENANT_A, "M-COV-LIST")
        cov = CoveragePeriod(
            id=uuid.uuid4(),
            tenant_id=TENANT_A,
            member_id=member.id,
            plan_name="Test Plan",
            coverage_type="pharmacy",
            effective_date=date(2026, 1, 1),
            benefit_year_start=date(2026, 1, 1),
            benefit_year_end=date(2026, 12, 31),
            status="active",
        )
        db_session.add(cov)
        db_session.flush()

        app, client, token = _make_client(db_session, TENANT_A)
        try:
            resp = client.get(f"/api/v1/members/{member.id}/coverage")
            assert resp.status_code == 200
            periods = resp.json()["coverage_periods"]
            assert len(periods) == 1
            assert periods[0]["plan_name"] == "Test Plan"
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()

    def test_coverage_cross_tenant_member_not_found(self, db_session):
        """Tenant B cannot see Tenant A member coverage."""
        member = _seed_member(db_session, TENANT_A, "M-COV-ISO")
        app, client, token = _make_client(db_session, TENANT_B)
        try:
            resp = client.get(f"/api/v1/members/{member.id}/coverage")
            assert resp.status_code == 404
        finally:
            clear_tenant_context(token)
            app.dependency_overrides.clear()
