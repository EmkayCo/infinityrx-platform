"""Additional coverage tests for Session 2 code paths."""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient

from src.main import create_app
from src.services.cob_service import CobSequence, PayerRecord
from src.services.x12_270_271 import (
    X12EligibilityInquiry,
    X12ParseError,
    X12Parser,
    X12ResponseBuilder,
    X12ServiceTypeCode,
    _parse_x12_date,
    _split_x12,
)
from shared.db.tenant_context import set_tenant_context, clear_tenant_context
from tests.conftest import TENANT_A

import src.api.routes.members as _members_mod
import src.api.routes.groups as _groups_mod
import src.api.routes.enrollment as _enrollment_mod
import src.api.routes.cob as _cob_mod
import src.api.routes.coverage as _coverage_mod

TENANT_ID = str(uuid.UUID("11111111-1111-1111-1111-111111111111"))
MEMBER_UUID = str(uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))


def _make_wired_client(db_session) -> TestClient:
    """Build a TestClient with the DB dependency wired to db_session and Tenant A context."""
    app = create_app()

    def _override_db():
        return db_session

    app.dependency_overrides[_members_mod._get_db] = _override_db
    app.dependency_overrides[_groups_mod._get_db] = _override_db
    app.dependency_overrides[_enrollment_mod._get_db] = _override_db
    app.dependency_overrides[_cob_mod._get_db] = _override_db
    app.dependency_overrides[_coverage_mod._get_db] = _override_db
    return app, TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# _parse_x12_date error paths (line 60)
# ---------------------------------------------------------------------------

class TestParseX12Date:
    def test_invalid_length_raises(self):
        with pytest.raises(X12ParseError, match="invalid X12 date"):
            _parse_x12_date("20260")

    def test_non_digit_raises(self):
        with pytest.raises(X12ParseError, match="invalid X12 date"):
            _parse_x12_date("2026AB01")


# ---------------------------------------------------------------------------
# _split_x12 error paths (line 72)
# ---------------------------------------------------------------------------

class TestSplitX12:
    def test_isa_too_short_raises(self):
        with pytest.raises(X12ParseError, match="ISA segment too short"):
            _split_x12("ISA*short~")

    def test_not_starting_with_isa_raises(self):
        with pytest.raises(X12ParseError, match="missing ISA"):
            _split_x12("GS*something~")


# ---------------------------------------------------------------------------
# X12Parser — missing segment paths (lines 102, 156, 158)
# ---------------------------------------------------------------------------

# Minimal ISA header (106 chars exactly) for crafting truncated/broken 270s
_ISA_PREFIX = (
    "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
    "*260413*1200*^*00501*000000001*0*T*:"
)  # 105 chars, + "~" = 106

_VALID_ISA = _ISA_PREFIX + "~"


class TestX12ParserMissingSegments:
    def test_missing_st_segment_raises(self):
        raw = (
            _VALID_ISA
            + "GS*HS*SENDER*RECEIVER*20260413*1200*1*X*005010X279A1~"
            + "SE*1*0001~GE*1*1~IEA*1*000000001~"
        )
        parser = X12Parser()
        with pytest.raises(X12ParseError, match="missing ST"):
            parser.parse_270(raw)

    def test_missing_member_nm1_raises(self):
        raw = (
            _VALID_ISA
            + "GS*HS*S*R*20260413*1200*1*X*005010X279A1~"
            + "ST*270*0001*005010X279A1~"
            + "BHT*0022*13*10001234*20260413*1200~"
            + "HL*1**20*1~"
            + "NM1*PR*2*INFINITYRX*****PI*610014~"
            + "HL*2*1*21*1~"
            + "NM1*1P*1*DOE*JOHN****XX*1234567893~"
            + "HL*3*2*22*0~"
            + "DTP*291*D8*20260413~"
            + "EQ*96~"
            + "SE*9*0001~GE*1*1~IEA*1*000000001~"
        )
        parser = X12Parser()
        with pytest.raises(X12ParseError, match="missing member"):
            parser.parse_270(raw)

    def test_missing_dos_raises(self):
        raw = (
            _VALID_ISA
            + "GS*HS*S*R*20260413*1200*1*X*005010X279A1~"
            + "ST*270*0001*005010X279A1~"
            + "BHT*0022*13*10001234*20260413*1200~"
            + "HL*1**20*1~"
            + "NM1*PR*2*INFINITYRX*****PI*610014~"
            + "HL*2*1*21*1~"
            + "NM1*1P*1*DOE*JOHN****XX*1234567893~"
            + "HL*3*2*22*0~"
            + "NM1*IL*1*SMITH*JANE****MI*M123456~"
            + "EQ*96~"
            + "SE*8*0001~GE*1*1~IEA*1*000000001~"
        )
        parser = X12Parser()
        with pytest.raises(X12ParseError, match="missing DTP"):
            parser.parse_270(raw)

    def test_missing_payer_nm1_raises(self):
        raw = (
            _VALID_ISA
            + "GS*HS*S*R*20260413*1200*1*X*005010X279A1~"
            + "ST*270*0001*005010X279A1~"
            + "BHT*0022*13*10001234*20260413*1200~"
            + "HL*1**20*1~"
            + "HL*2*1*21*1~"
            + "NM1*1P*1*DOE*JOHN****XX*1234567893~"
            + "HL*3*2*22*0~"
            + "NM1*IL*1*SMITH*JANE****MI*M123456~"
            + "DTP*291*D8*20260413~"
            + "EQ*96~"
            + "SE*8*0001~GE*1*1~IEA*1*000000001~"
        )
        parser = X12Parser()
        with pytest.raises(X12ParseError, match="missing payer"):
            parser.parse_270(raw)


# ---------------------------------------------------------------------------
# 271 builder — no DOB path (line 239 branch)
# ---------------------------------------------------------------------------

class TestX12ResponseBuilderNoDob:
    def _make_inquiry_no_dob(self) -> X12EligibilityInquiry:
        return X12EligibilityInquiry(
            member_id="M123456",
            date_of_service=date(2026, 4, 13),
            date_of_birth=None,  # ← no DOB
            first_name="JANE",
            last_name="SMITH",
            gender=None,
            payer_id="610014",
            trace_number="ABC123",
            service_type_codes=[X12ServiceTypeCode.PRESCRIPTION_DRUG],
        )

    def test_271_without_dob_skips_dmg_segment(self):
        builder = X12ResponseBuilder()
        inquiry = self._make_inquiry_no_dob()
        result = builder.build_eligible_271(
            inquiry=inquiry,
            plan_name="Plan",
            coverage_type="pharmacy",
            benefit_year_start=date(2026, 1, 1),
            benefit_year_end=date(2026, 12, 31),
            cob_records=[],
            control_number=2,
        )
        assert "DMG*" not in result

    def test_271_cob_with_no_name_or_bin_skipped(self):
        """COB record with neither name nor bin → no OI/MOA emitted (line 253 branch)."""
        builder = X12ResponseBuilder()
        inquiry = self._make_inquiry_no_dob()
        empty_cob = PayerRecord(
            sequence=CobSequence.SECONDARY,
            other_payer_name=None,
            other_payer_bin=None,
            effective_date=date(2026, 1, 1),
        )
        result = builder.build_eligible_271(
            inquiry=inquiry,
            plan_name="Plan",
            coverage_type="pharmacy",
            benefit_year_start=date(2026, 1, 1),
            benefit_year_end=date(2026, 12, 31),
            cob_records=[empty_cob],
            control_number=3,
        )
        assert "OI*" not in result


# ---------------------------------------------------------------------------
# Eligibility route — eligible path through 270 endpoint (line 106)
# ---------------------------------------------------------------------------

class TestEligibilityRoute270EligiblePath:
    @pytest.fixture
    def client(self):
        return TestClient(create_app(), raise_server_exceptions=False)

    @pytest.fixture
    def headers(self):
        return {"x-tenant-id": TENANT_ID, "Content-Type": "text/plain"}

    def test_270_eligible_path_via_mock(self, client, headers):
        """Patch EligibilityService to return eligible, ensuring line 106 is hit."""
        from src.services.eligibility_service import (
            EligibilityResponse,
            EligibilityStatus,
        )
        import src.api.routes.eligibility as elig_module

        original_svc = elig_module._eligibility_svc

        class _FakeService:
            async def check(self, db, req):
                return EligibilityResponse(
                    is_eligible=True,
                    status=EligibilityStatus.ELIGIBLE,
                    matched_member_id=uuid.UUID(MEMBER_UUID),
                    plan_name="Basic Rx",
                    coverage_type="pharmacy",
                    benefit_year_start=date(2026, 1, 1),
                    benefit_year_end=date(2026, 12, 31),
                )

        elig_module._eligibility_svc = _FakeService()

        minimal_270 = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*260413*1200*^*00501*000000001*0*T*:~"
            "GS*HS*SENDER*RECEIVER*20260413*1200*1*X*005010X279A1~"
            "ST*270*0001*005010X279A1~"
            "BHT*0022*13*10001234*20260413*1200~"
            "HL*1**20*1~"
            "NM1*PR*2*INFINITYRX*****PI*610014~"
            "HL*2*1*21*1~"
            "NM1*1P*1*DOE*JOHN****XX*1234567893~"
            "HL*3*2*22*0~"
            "TRN*1*ABC123*9INFINITYRX~"
            "NM1*IL*1*SMITH*JANE****MI*M123456~"
            "DMG*D8*19800101*F~"
            "DTP*291*D8*20260413~"
            "EQ*96~"
            "SE*13*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        try:
            resp = client.post(
                "/api/v1/eligibility/270",
                content=minimal_270,
                headers=headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["is_eligible"] is True
            assert "transaction_271" in data
        finally:
            elig_module._eligibility_svc = original_svc


# ---------------------------------------------------------------------------
# COB route — update path (404 when member not found)
# ---------------------------------------------------------------------------

class TestCobRouteUpdate:
    @pytest.fixture
    def wired(self, db_session):
        token = set_tenant_context(TENANT_A)
        app, client = _make_wired_client(db_session)
        yield client
        clear_tenant_context(token)
        app.dependency_overrides.clear()

    def test_update_cob_returns_404(self, wired):
        """PUT /members/{nonexistent}/cob/{id} → 404 (member not found)."""
        cob_id = str(uuid.uuid4())
        resp = wired.put(
            f"/api/v1/members/{MEMBER_UUID}/cob/{cob_id}",
            json={"termination_date": "2026-12-31"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Enrollment route — upload path
# ---------------------------------------------------------------------------

class TestEnrollmentUploadRoute:
    @pytest.fixture
    def wired(self, db_session):
        token = set_tenant_context(TENANT_A)
        app, client = _make_wired_client(db_session)
        yield client
        clear_tenant_context(token)
        app.dependency_overrides.clear()

    def test_upload_enrollment_file_returns_201(self, wired):
        # Columns match _DEFAULT_FIELD_MAPPING column names
        csv_body = (
            "member_id,first_name,last_name,date_of_birth,gender,effective_date,rx_bin\n"
            "M001,Jane,Doe,1990-01-01,F,2026-01-01,610014\n"
        )
        resp = wired.post(
            "/api/v1/members/enrollment/upload",
            content=csv_body.encode(),
            headers={"content-type": "text/csv"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["status"] == "uploaded"


# ---------------------------------------------------------------------------
# X12 NM1 segment with fewer elements (branches 132->116, 138->116, etc.)
# ---------------------------------------------------------------------------

class TestX12ParserShortNm1:
    def test_nm1_pr_with_fewer_than_10_elements_skips_payer_id(self):
        """NM1*PR with < 10 elements — payer_id stays None until another NM1 sets it."""
        raw = (
            _VALID_ISA
            + "GS*HS*S*R*20260413*1200*1*X*005010X279A1~"
            + "ST*270*0001*005010X279A1~"
            + "BHT*0022*13*10001234*20260413*1200~"
            + "HL*1**20*1~"
            + "NM1*PR*2~"  # ← only 3 elements, no payer ID at index 9
            + "NM1*PR*2*INFINITYRX*****PI*610014~"  # second NM1 with full payer ID
            + "HL*2*1*21*1~"
            + "NM1*1P*1*DOE*JOHN****XX*1234567893~"
            + "HL*3*2*22*0~"
            + "TRN*1*ABC123*9INFINITYRX~"
            + "NM1*IL*1*SMITH*JANE****MI*M123456~"
            + "DTP*291*D8*20260413~"
            + "EQ*96~"
            + "SE*11*0001~GE*1*1~IEA*1*000000001~"
        )
        parser = X12Parser()
        inquiry = parser.parse_270(raw)
        assert inquiry.payer_id == "610014"

    def test_nm1_il_with_fewer_elements_uses_defaults(self):
        """NM1*IL with fewer than 10 elements — member_id stays None from that segment."""
        raw = (
            _VALID_ISA
            + "GS*HS*S*R*20260413*1200*1*X*005010X279A1~"
            + "ST*270*0001*005010X279A1~"
            + "BHT*0022*13*10001234*20260413*1200~"
            + "HL*1**20*1~"
            + "NM1*PR*2*INFINITYRX*****PI*610014~"
            + "HL*2*1*21*1~"
            + "NM1*1P*1*DOE*JOHN****XX*1234567893~"
            + "HL*3*2*22*0~"
            + "TRN*1*ABC123*9INFINITYRX~"
            + "NM1*IL*1~"  # ← short NM1 — no name, no member ID
            + "NM1*IL*1*SMITH*JANE****MI*M123456~"  # second one has the ID
            + "DTP*291*D8*20260413~"
            + "EQ*96~"
            + "SE*11*0001~GE*1*1~IEA*1*000000001~"
        )
        parser = X12Parser()
        inquiry = parser.parse_270(raw)
        assert inquiry.member_id == "M123456"

    def test_dmg_segment_without_gender(self):
        """DMG*D8*19800101 (no gender element) — gender stays None."""
        raw = (
            _VALID_ISA
            + "GS*HS*S*R*20260413*1200*1*X*005010X279A1~"
            + "ST*270*0001*005010X279A1~"
            + "BHT*0022*13*10001234*20260413*1200~"
            + "HL*1**20*1~"
            + "NM1*PR*2*INFINITYRX*****PI*610014~"
            + "HL*2*1*21*1~"
            + "NM1*1P*1*DOE*JOHN****XX*1234567893~"
            + "HL*3*2*22*0~"
            + "TRN*1*ABC123*9INFINITYRX~"
            + "NM1*IL*1*SMITH*JANE****MI*M123456~"
            + "DMG*D8*19800101~"  # no gender
            + "DTP*291*D8*20260413~"
            + "EQ*96~"
            + "SE*11*0001~GE*1*1~IEA*1*000000001~"
        )
        parser = X12Parser()
        inquiry = parser.parse_270(raw)
        assert inquiry.date_of_birth is not None
        assert inquiry.gender is None


# ---------------------------------------------------------------------------
# Coverage route — update path (404 when member not found)
# ---------------------------------------------------------------------------

class TestCoverageRouteUpdate:
    @pytest.fixture
    def wired(self, db_session):
        token = set_tenant_context(TENANT_A)
        app, client = _make_wired_client(db_session)
        yield client
        clear_tenant_context(token)
        app.dependency_overrides.clear()

    def test_update_coverage_returns_404(self, wired):
        """PUT /members/{nonexistent}/coverage/{id} → 404 (member not found)."""
        period_id = str(uuid.uuid4())
        resp = wired.put(
            f"/api/v1/members/{MEMBER_UUID}/coverage/{period_id}",
            json={"termination_date": "2026-12-31"},
        )
        assert resp.status_code == 404
