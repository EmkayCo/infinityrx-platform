"""Unit tests for PHI controls: watermarking, access logging, masking, export restrictions.

100% coverage required on all PHI paths.
"""

from __future__ import annotations

import uuid

import pytest
from src.services.phi_controls import (
    PhiControlsService,
    classify_report_phi_status,
    get_phi_masking_level,
    log_phi_access,
    requires_export_restriction,
    requires_watermark,
)

PHI_FIELDS_REGISTRY = {
    "member_name",
    "dob",
    "date_of_birth",
    "address",
    "phone",
    "ssn",
    "member_id",
    "rx_number",
    "ndc",
}


class TestClassifyReportPhiStatus:
    def test_report_with_phi_columns_is_phi(self) -> None:
        columns = [
            {"field": "claim_id", "label": "Claim ID"},
            {"field": "member_name", "label": "Member Name"},
        ]
        assert classify_report_phi_status(columns, PHI_FIELDS_REGISTRY) is True

    def test_report_without_phi_columns_is_not_phi(self) -> None:
        columns = [
            {"field": "claim_id", "label": "Claim ID"},
            {"field": "amount_paid", "label": "Amount Paid"},
            {"field": "pharmacy_npi", "label": "Pharmacy NPI"},
        ]
        assert classify_report_phi_status(columns, PHI_FIELDS_REGISTRY) is False

    def test_empty_columns_not_phi(self) -> None:
        assert classify_report_phi_status([], PHI_FIELDS_REGISTRY) is False

    def test_ndc_is_phi(self) -> None:
        columns = [{"field": "ndc", "label": "NDC"}]
        assert classify_report_phi_status(columns, PHI_FIELDS_REGISTRY) is True

    def test_rx_number_is_phi(self) -> None:
        columns = [{"field": "rx_number", "label": "Rx Number"}]
        assert classify_report_phi_status(columns, PHI_FIELDS_REGISTRY) is True


class TestGetPhiMaskingLevel:
    def test_admin_gets_full_detail(self) -> None:
        level = get_phi_masking_level("tenant_admin")
        assert level == "full_detail"

    def test_operator_with_phi_permission_gets_full_detail(self) -> None:
        level = get_phi_masking_level("operator", permissions=["phi_access"])
        assert level == "full_detail"

    def test_operator_without_phi_gets_partial(self) -> None:
        level = get_phi_masking_level("operator", permissions=[])
        assert level == "partial"

    def test_client_portal_user_gets_redacted(self) -> None:
        level = get_phi_masking_level("client_portal")
        assert level == "redacted"

    def test_unknown_role_gets_redacted(self) -> None:
        level = get_phi_masking_level("unknown_role")
        assert level == "redacted"

    def test_system_role_gets_full_detail(self) -> None:
        level = get_phi_masking_level("system")
        assert level == "full_detail"


class TestRequiresWatermark:
    def test_phi_report_pdf_requires_watermark(self) -> None:
        assert requires_watermark(contains_phi=True, output_format="pdf") is True

    def test_non_phi_report_pdf_no_watermark(self) -> None:
        assert requires_watermark(contains_phi=False, output_format="pdf") is False

    def test_phi_report_csv_no_watermark(self) -> None:
        # watermark only for PDF
        assert requires_watermark(contains_phi=True, output_format="csv") is False

    def test_phi_report_excel_no_watermark(self) -> None:
        assert requires_watermark(contains_phi=True, output_format="excel") is False


class TestRequiresExportRestriction:
    def test_phi_report_restricted_role_cannot_export(self) -> None:
        assert (
            requires_export_restriction(
                contains_phi=True, masking_level="redacted", role="client_portal"
            )
            is True
        )

    def test_phi_report_authorized_role_can_export(self) -> None:
        assert (
            requires_export_restriction(
                contains_phi=True, masking_level="full_detail", role="tenant_admin"
            )
            is False
        )

    def test_non_phi_report_never_restricted(self) -> None:
        assert (
            requires_export_restriction(
                contains_phi=False, masking_level="redacted", role="client_portal"
            )
            is False
        )


class TestLogPhiAccess:
    def test_log_returns_entry_with_required_fields(self) -> None:
        entry = log_phi_access(
            tenant_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            report_run_id=str(uuid.uuid4()),
            report_definition_id=str(uuid.uuid4()),
            access_type="download",
            masking_level="full_detail",
            ip_address="192.168.1.100",
        )
        assert "tenant_id" in entry
        assert "user_id" in entry
        assert "report_run_id" in entry
        assert "report_definition_id" in entry
        assert "access_type" in entry
        assert "masking_level" in entry
        assert "accessed_at" in entry
        assert entry["access_type"] == "download"
        assert entry["masking_level"] == "full_detail"

    def test_log_access_type_must_be_valid(self) -> None:
        with pytest.raises(ValueError, match="Invalid access_type"):
            log_phi_access(
                tenant_id="t1",
                user_id="u1",
                report_run_id="r1",
                report_definition_id="d1",
                access_type="invalid_type",
                masking_level="full_detail",
                ip_address=None,
            )

    def test_log_masking_level_must_be_valid(self) -> None:
        with pytest.raises(ValueError, match="Invalid masking_level"):
            log_phi_access(
                tenant_id="t1",
                user_id="u1",
                report_run_id="r1",
                report_definition_id="d1",
                access_type="view",
                masking_level="bogus_level",
                ip_address=None,
            )


class TestPhiControlsService:
    def test_service_instantiation(self) -> None:
        service = PhiControlsService()
        assert service is not None

    def test_get_phi_fields_returns_set(self) -> None:
        service = PhiControlsService()
        fields = service.get_phi_fields()
        assert isinstance(fields, (set, frozenset))
        assert "member_name" in fields

    def test_mask_row_full_detail_unchanged(self) -> None:
        service = PhiControlsService()
        row = {"member_name": "John", "claim_id": "C001"}
        result = service.mask_row(row, "full_detail")
        assert result["member_name"] == "John"

    def test_mask_row_redacted_hides_phi(self) -> None:
        service = PhiControlsService()
        row = {"member_name": "John", "dob": "1980-01-01", "claim_id": "C001"}
        result = service.mask_row(row, "redacted")
        assert result["member_name"] == "[REDACTED]"
        assert result["dob"] == "[REDACTED]"
        assert result["claim_id"] == "C001"

    def test_watermark_text_for_phi_pdf(self) -> None:
        service = PhiControlsService()
        text = service.get_watermark_text()
        assert "CONFIDENTIAL" in text
        assert "PROTECTED HEALTH INFORMATION" in text
