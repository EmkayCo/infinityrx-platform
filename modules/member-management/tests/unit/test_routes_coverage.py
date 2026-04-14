"""Coverage tests for API routes, schemas, CSV parser edge cases, and member service."""
from __future__ import annotations

import io
import sys
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from src.main import create_app
from src.api.schemas.member import (
    MemberCreate,
    MemberUpdate,
    MemberTerminate,
    GroupCreate,
    PhiAccessLevel,
)
from src.services.csv_parser import (
    CsvEnrollmentParser,
    FieldMapping,
    ParseError,
)
from src.services.edi_834_parser import (
    Edi834Parser,
    _parse_date,
)
from src.services.member_service import MemberService


@pytest.fixture()
def client():
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Route coverage
# ---------------------------------------------------------------------------

class TestMemberRoutes:
    def test_list_members_returns_empty(self, client):
        resp = client.get("/api/v1/members")
        assert resp.status_code == 200

    def test_create_member_returns_201(self, client):
        resp = client.post("/api/v1/members", json={
            "member_id": "MEM999",
            "first_name": "Test",
            "last_name": "User",
            "date_of_birth": "1990-01-01",
            "gender": "M",
            "rx_bin": "123456",
            "effective_date": "2026-01-01",
        })
        assert resp.status_code == 201

    def test_get_member_not_found(self, client):
        resp = client.get(f"/api/v1/members/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_update_member_not_found(self, client):
        resp = client.put(f"/api/v1/members/{uuid.uuid4()}", json={})
        assert resp.status_code == 404

    def test_terminate_member_not_found(self, client):
        resp = client.post(f"/api/v1/members/{uuid.uuid4()}/terminate", json={
            "termination_date": "2026-12-31",
            "termination_reason": "voluntary_withdrawal",
        })
        assert resp.status_code == 404

    def test_get_id_card_not_found(self, client):
        resp = client.get(f"/api/v1/members/{uuid.uuid4()}/id-card")
        assert resp.status_code == 404


class TestGroupRoutes:
    def test_list_groups_returns_empty(self, client):
        resp = client.get("/api/v1/groups")
        assert resp.status_code == 200

    def test_create_group_returns_201(self, client):
        resp = client.post("/api/v1/groups", json={
            "group_number": "GRP100",
            "group_name": "Test Group",
            "effective_date": "2026-01-01",
        })
        assert resp.status_code == 201

    def test_update_group_not_found(self, client):
        resp = client.put(f"/api/v1/groups/{uuid.uuid4()}", json={
            "group_number": "GRP100",
            "group_name": "Test Group",
            "effective_date": "2026-01-01",
        })
        assert resp.status_code == 404

    def test_get_group_members_returns_empty(self, client):
        resp = client.get(f"/api/v1/groups/{uuid.uuid4()}/members")
        assert resp.status_code == 200


class TestEnrollmentRoutes:
    def test_list_enrollment_files_returns_empty(self, client):
        resp = client.get("/api/v1/members/enrollment/files")
        assert resp.status_code == 200

    def test_get_file_not_found(self, client):
        resp = client.get(f"/api/v1/members/enrollment/files/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_preview_file_not_found(self, client):
        resp = client.get(f"/api/v1/members/enrollment/upload/{uuid.uuid4()}/preview")
        assert resp.status_code == 404

    def test_process_file_not_found(self, client):
        resp = client.post(f"/api/v1/members/enrollment/upload/{uuid.uuid4()}/process")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Schema validation coverage
# ---------------------------------------------------------------------------

class TestSchemaValidation:
    def test_member_create_invalid_gender(self):
        with pytest.raises(Exception):
            MemberCreate(
                member_id="M1", first_name="A", last_name="B",
                date_of_birth="1990-01-01", gender="X",
                rx_bin="123456", effective_date="2026-01-01"
            )

    def test_member_create_invalid_bin_too_short(self):
        with pytest.raises(Exception):
            MemberCreate(
                member_id="M1", first_name="A", last_name="B",
                date_of_birth="1990-01-01", gender="M",
                rx_bin="12345", effective_date="2026-01-01"
            )

    def test_member_create_bin_with_newline_rejected(self):
        with pytest.raises(Exception):
            MemberCreate(
                member_id="M1", first_name="A", last_name="B",
                date_of_birth="1990-01-01", gender="M",
                rx_bin="123456\n", effective_date="2026-01-01"
            )

    def test_member_create_invalid_ssn_with_dashes(self):
        with pytest.raises(Exception):
            MemberCreate(
                member_id="M1", first_name="A", last_name="B",
                date_of_birth="1990-01-01", gender="M",
                rx_bin="123456", effective_date="2026-01-01",
                ssn="123-45-6789"
            )

    def test_member_create_invalid_person_code(self):
        with pytest.raises(Exception):
            MemberCreate(
                member_id="M1", first_name="A", last_name="B",
                date_of_birth="1990-01-01", gender="M",
                rx_bin="123456", effective_date="2026-01-01",
                person_code="abc"
            )

    def test_member_create_invalid_state(self):
        with pytest.raises(Exception):
            MemberCreate(
                member_id="M1", first_name="A", last_name="B",
                date_of_birth="1990-01-01", gender="M",
                rx_bin="123456", effective_date="2026-01-01",
                state="123"
            )

    def test_member_update_invalid_gender(self):
        with pytest.raises(Exception):
            MemberUpdate(gender="Z")

    def test_member_update_invalid_ssn(self):
        with pytest.raises(Exception):
            MemberUpdate(ssn="123-45-6789")

    def test_member_update_none_fields_valid(self):
        upd = MemberUpdate()
        assert upd.gender is None
        assert upd.ssn is None

    def test_group_create_valid(self):
        g = GroupCreate(
            group_number="G1",
            group_name="My Group",
            effective_date="2026-01-01",
        )
        assert g.group_number == "G1"

    def test_member_create_no_ssn_passes(self):
        """ssn=None path in validator."""
        data = MemberCreate(
            member_id="M1", first_name="A", last_name="B",
            date_of_birth="1990-01-01", gender="M",
            rx_bin="123456", effective_date="2026-01-01",
            ssn=None,
        )
        assert data.ssn is None

    def test_member_create_valid_person_code(self):
        """person_code valid return path."""
        data = MemberCreate(
            member_id="M1", first_name="A", last_name="B",
            date_of_birth="1990-01-01", gender="M",
            rx_bin="123456", effective_date="2026-01-01",
            person_code="02",
        )
        assert data.person_code == "02"

    def test_member_create_valid_state(self):
        """state valid return path — also tests uppercase normalization."""
        data = MemberCreate(
            member_id="M1", first_name="A", last_name="B",
            date_of_birth="1990-01-01", gender="M",
            rx_bin="123456", effective_date="2026-01-01",
            state="ny",
        )
        assert data.state == "NY"

    def test_member_create_no_state_passes(self):
        """state=None path in validator."""
        data = MemberCreate(
            member_id="M1", first_name="A", last_name="B",
            date_of_birth="1990-01-01", gender="M",
            rx_bin="123456", effective_date="2026-01-01",
            state=None,
        )
        assert data.state is None

    def test_member_update_valid_gender(self):
        """MemberUpdate valid gender return path."""
        upd = MemberUpdate(gender="F")
        assert upd.gender == "F"

    def test_member_update_none_gender_passes(self):
        """MemberUpdate gender=None passes validator."""
        upd = MemberUpdate(gender=None)
        assert upd.gender is None

    def test_member_update_valid_ssn(self):
        """MemberUpdate ssn valid return path."""
        upd = MemberUpdate(ssn="987654321")
        assert upd.ssn == "987654321"

    def test_member_update_none_ssn_passes(self):
        """MemberUpdate ssn=None passes validator."""
        upd = MemberUpdate(ssn=None)
        assert upd.ssn is None


# ---------------------------------------------------------------------------
# CSV parser edge cases
# ---------------------------------------------------------------------------

class TestCsvParserEdgeCases:
    def _mapping(self) -> FieldMapping:
        return FieldMapping(
            member_id="member_id",
            first_name="first_name",
            last_name="last_name",
            date_of_birth="dob",
            gender="gender",
            effective_date="effective_date",
            rx_bin="bin",
            rx_pcn="pcn",
            rx_group="group",
            action="action",
        )

    def test_empty_member_id_returns_error(self):
        csv = "member_id,first_name,last_name,dob,gender,effective_date,bin,pcn,group,action\n,Alice,Johnson,1990-05-10,F,2026-01-01,999999,ABC,GRP1,ADD\n"
        parser = CsvEnrollmentParser(mapping=self._mapping())
        result = parser.parse_with_errors(io.StringIO(csv))
        assert any(e.field == "member_id" for e in result.errors)

    def test_invalid_gender_returns_error(self):
        csv = "member_id,first_name,last_name,dob,gender,effective_date,bin,pcn,group,action\nMEM1,Alice,Johnson,1990-05-10,Z,2026-01-01,999999,ABC,GRP1,ADD\n"
        parser = CsvEnrollmentParser(mapping=self._mapping())
        result = parser.parse_with_errors(io.StringIO(csv))
        assert any(e.field == "gender" for e in result.errors)

    def test_missing_first_name_returns_error(self):
        csv = "member_id,first_name,last_name,dob,gender,effective_date,bin,pcn,group,action\nMEM1,,Johnson,1990-05-10,F,2026-01-01,999999,ABC,GRP1,ADD\n"
        parser = CsvEnrollmentParser(mapping=self._mapping())
        result = parser.parse_with_errors(io.StringIO(csv))
        assert any(e.field == "first_name" for e in result.errors)

    def test_missing_last_name_returns_error(self):
        csv = "member_id,first_name,last_name,dob,gender,effective_date,bin,pcn,group,action\nMEM1,Alice,,1990-05-10,F,2026-01-01,999999,ABC,GRP1,ADD\n"
        parser = CsvEnrollmentParser(mapping=self._mapping())
        result = parser.parse_with_errors(io.StringIO(csv))
        assert any(e.field == "last_name" for e in result.errors)

    def test_parse_raises_on_any_error(self):
        csv = "member_id,first_name,last_name,dob,gender,effective_date,bin,pcn,group,action\nMEM1,Alice,Johnson,bad-date,F,2026-01-01,999999,ABC,GRP1,ADD\n"
        parser = CsvEnrollmentParser(mapping=self._mapping())
        with pytest.raises(ValueError):
            parser.parse(io.StringIO(csv))

    def test_termination_date_parsed_when_present(self):
        csv = "member_id,first_name,last_name,dob,gender,effective_date,bin,pcn,group,action,term_date\nMEM1,Alice,Johnson,1990-05-10,F,2026-01-01,999999,ABC,GRP1,TRM,2026-12-31\n"
        mapping = FieldMapping(
            member_id="member_id",
            first_name="first_name",
            last_name="last_name",
            date_of_birth="dob",
            gender="gender",
            effective_date="effective_date",
            rx_bin="bin",
            rx_pcn="pcn",
            rx_group="group",
            action="action",
            termination_date="term_date",
        )
        parser = CsvEnrollmentParser(mapping=mapping)
        records = parser.parse(io.StringIO(csv))
        assert records[0].termination_date is not None

    def test_bad_termination_date_returns_error(self):
        csv = "member_id,first_name,last_name,dob,gender,effective_date,bin,pcn,group,action,term_date\nMEM1,Alice,Johnson,1990-05-10,F,2026-01-01,999999,ABC,GRP1,TRM,not-a-date\n"
        mapping = FieldMapping(
            member_id="member_id",
            first_name="first_name",
            last_name="last_name",
            date_of_birth="dob",
            gender="gender",
            effective_date="effective_date",
            rx_bin="bin",
            rx_pcn="pcn",
            rx_group="group",
            action="action",
            termination_date="term_date",
        )
        parser = CsvEnrollmentParser(mapping=mapping)
        result = parser.parse_with_errors(io.StringIO(csv))
        assert any(e.field == "termination_date" for e in result.errors)

    def test_date_parsing_m_d_y_format(self):
        csv = "member_id,first_name,last_name,dob,gender,effective_date,bin,pcn,group,action\nMEM1,Alice,Johnson,05/10/1990,F,01/01/2026,999999,ABC,GRP1,ADD\n"
        parser = CsvEnrollmentParser(mapping=self._mapping())
        records = parser.parse(io.StringIO(csv))
        from datetime import date
        assert records[0].date_of_birth == date(1990, 5, 10)

    def test_missing_dob_column_returns_error(self):
        """date_of_birth column not present in CSV → parse error."""
        csv = "member_id,first_name,last_name,gender,effective_date,bin,pcn,group,action\nMEM1,Alice,Johnson,F,2026-01-01,999999,ABC,GRP1,ADD\n"
        mapping = FieldMapping(
            member_id="member_id", first_name="first_name", last_name="last_name",
            date_of_birth="dob",  # "dob" column not present
            gender="gender", effective_date="effective_date", rx_bin="bin",
            rx_pcn="pcn", rx_group="group", action="action",
        )
        parser = CsvEnrollmentParser(mapping=mapping)
        result = parser.parse_with_errors(io.StringIO(csv))
        assert any(e.field == "date_of_birth" for e in result.errors)

    def test_missing_effective_date_column_returns_error(self):
        """effective_date column not present → parse error."""
        csv = "member_id,first_name,last_name,dob,gender,bin,pcn,group,action\nMEM1,Alice,Johnson,1990-05-10,F,999999,ABC,GRP1,ADD\n"
        mapping = FieldMapping(
            member_id="member_id", first_name="first_name", last_name="last_name",
            date_of_birth="dob", gender="gender",
            effective_date="eff",  # not present
            rx_bin="bin", rx_pcn="pcn", rx_group="group", action="action",
        )
        parser = CsvEnrollmentParser(mapping=mapping)
        result = parser.parse_with_errors(io.StringIO(csv))
        assert any(e.field == "effective_date" for e in result.errors)

    def test_invalid_effective_date_format_returns_error(self):
        """Bad effective_date string → parse error."""
        csv = "member_id,first_name,last_name,dob,gender,effective_date,bin,pcn,group,action\nMEM1,Alice,Johnson,1990-05-10,F,not-a-date,999999,ABC,GRP1,ADD\n"
        parser = CsvEnrollmentParser(mapping=self._mapping())
        result = parser.parse_with_errors(io.StringIO(csv))
        assert any(e.field == "effective_date" for e in result.errors)

    def test_empty_dob_value_produces_none_record(self):
        """Empty dob cell → date_of_birth=None (not an error)."""
        csv = "member_id,first_name,last_name,dob,gender,effective_date,bin,pcn,group,action\nMEM1,Alice,Johnson,,F,2026-01-01,999999,ABC,GRP1,ADD\n"
        parser = CsvEnrollmentParser(mapping=self._mapping())
        records = parser.parse(io.StringIO(csv))
        assert records[0].date_of_birth is None

    def test_no_termination_date_mapping_skips_parsing(self):
        """When termination_date mapping is empty, that branch is skipped."""
        csv = "member_id,first_name,last_name,dob,gender,effective_date,bin,pcn,group,action\nMEM1,Alice,Johnson,1990-05-10,F,2026-01-01,999999,ABC,GRP1,TRM\n"
        mapping = FieldMapping(
            member_id="member_id", first_name="first_name", last_name="last_name",
            date_of_birth="dob", gender="gender", effective_date="effective_date",
            rx_bin="bin", rx_pcn="pcn", rx_group="group", action="action",
            termination_date="",  # empty → no termination_date parsing
        )
        parser = CsvEnrollmentParser(mapping=mapping)
        records = parser.parse(io.StringIO(csv))
        assert records[0].termination_date is None


# ---------------------------------------------------------------------------
# 834 parser edge cases
# ---------------------------------------------------------------------------

class TestEdi834EdgeCases:
    def test_parse_date_empty_returns_none(self):
        assert _parse_date("") is None

    def test_parse_date_iso_format(self):
        from datetime import date
        result = _parse_date("1990-03-15")
        assert result == date(1990, 3, 15)

    def test_parse_date_invalid_returns_none(self):
        result = _parse_date("not-a-date")
        assert result is None

    def test_segment_with_email_parsed(self):
        from tests.unit.test_edi_834_parser import MINIMAL_834
        parser = Edi834Parser()
        records = parser.parse(MINIMAL_834)
        assert records[0].email == "john.doe@example.com"

    def test_segment_with_phone_parsed(self):
        from tests.unit.test_edi_834_parser import MINIMAL_834
        parser = Edi834Parser()
        records = parser.parse(MINIMAL_834)
        assert records[0].phone == "5555551234"


# ---------------------------------------------------------------------------
# MemberService coverage
# ---------------------------------------------------------------------------

class TestMemberServiceCoverage:
    def test_redacted_fields_that_are_present(self):
        svc = MemberService.__new__(MemberService)
        raw = {
            "first_name": "Alice",
            "last_name": "Johnson",
            "middle_name": "M",
            "date_of_birth": "1990-05-10",
            "ssn": "123456789",
            "address_line_1": "123 Main",
            "address_line_2": "Apt 1",
            "city": "Anytown",
            "state": "NY",
            "zip_code": "10001",
            "phone": "+15555551234",
            "email": "alice@example.com",
        }
        masked = svc.mask_phi(raw, access_level=PhiAccessLevel.REDACTED)
        for field_name in raw:
            assert masked[field_name] == "**REDACTED**"

    def test_partial_ssn_short_redacted(self):
        svc = MemberService.__new__(MemberService)
        raw = {"ssn": "123"}
        masked = svc.mask_phi(raw, access_level=PhiAccessLevel.PARTIAL)
        assert masked["ssn"] == "**REDACTED**"

    def test_partial_dob_non_iso_format(self):
        svc = MemberService.__new__(MemberService)
        raw = {"date_of_birth": "19900510"}  # no dashes
        masked = svc.mask_phi(raw, access_level=PhiAccessLevel.PARTIAL)
        assert masked["date_of_birth"] == "**REDACTED**"
