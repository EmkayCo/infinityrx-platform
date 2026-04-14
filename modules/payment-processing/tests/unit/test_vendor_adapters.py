"""Unit tests for vendor adapter implementations."""
from __future__ import annotations

from datetime import date
from decimal import Decimal


from src.services.nacha_generator import NachaBatchConfig, NachaFileConfig
from src.services.vendor_adapter import (
    CheckAdapter,
    DirectAchAdapter,
    EchoAdapter,
    PaymentInstruction,
    ZelisAdapter,
    get_adapter_class,
)

INSTRUCTIONS = [
    PaymentInstruction(
        billing_payment_id="BP-001",
        pay_to_entity_id="ENT-001",
        pay_to_name="Test Pharmacy",
        pay_to_npi="1234567890",
        amount=Decimal("100.00"),
        routing_number="021000021",
        account_number="123456789012345",
    ),
    PaymentInstruction(
        billing_payment_id="BP-002",
        pay_to_entity_id="ENT-002",
        pay_to_name="Another Pharmacy",
        pay_to_npi="0987654321",
        amount=Decimal("250.50"),
        routing_number="021000021",
        account_number="987654321098765",
    ),
]


class TestDirectAchAdapter:
    def _make_adapter(self) -> DirectAchAdapter:
        return DirectAchAdapter(
            file_cfg=NachaFileConfig(
                immediate_destination="021000021",
                immediate_origin="1234567890",
                immediate_destination_name="BANK OF TEST",
                immediate_origin_name="INFINITYRX LLC",
            ),
            batch_cfg=NachaBatchConfig(
                company_name="INFINITYRX",
                company_id="1234567890",
                entry_class_code="CCD",
                company_entry_description="PAYMT",
                originating_dfi_id="02100002",
                effective_date=date(2026, 4, 15),
            ),
        )

    def test_format_batch_returns_nacha_file(self):
        adapter = self._make_adapter()
        result = adapter.format_batch(INSTRUCTIONS, "BATCH-001")
        assert result.success is True
        assert result.file_content is not None
        assert "1" == result.file_content[0]  # file header

    def test_format_empty_instructions_fails(self):
        adapter = self._make_adapter()
        result = adapter.format_batch([], "BATCH-001")
        assert result.success is False

    def test_submit_returns_vendor_reference(self):
        adapter = self._make_adapter()
        formatted = adapter.format_batch(INSTRUCTIONS, "BATCH-001")
        submitted = adapter.submit(formatted, "SUB-001")
        assert submitted.success is True
        assert submitted.vendor_reference is not None
        assert "NACHA" in submitted.vendor_reference

    def test_submit_failed_formatted_returns_failure(self):
        from src.services.vendor_adapter import SubmitResult
        adapter = self._make_adapter()
        failed = SubmitResult(success=False, error_message="bad format")
        result = adapter.submit(failed, "SUB-001")
        assert result.success is False

    def test_total_amount_matches_instructions(self):
        adapter = self._make_adapter()
        result = adapter.format_batch(INSTRUCTIONS, "BATCH-001")
        assert result.raw_response is not None
        total_str = result.raw_response["total_amount"]
        assert Decimal(total_str) == Decimal("350.50")

    def test_health_check_returns_healthy(self):
        adapter = self._make_adapter()
        result = adapter.health_check()
        assert result.status == "healthy"

    def test_poll_settlement_returns_pending(self):
        adapter = self._make_adapter()
        results = adapter.poll_settlement("ref", ["BP-001", "BP-002"])
        assert all(r.status == "pending" for r in results)

    def test_parse_return_handles_return_data(self):
        adapter = self._make_adapter()
        raw = {"returns": [{"billing_payment_id": "BP-001", "return_code": "R01", "return_reason": "NSF", "trace_number": "123"}]}
        results = adapter.parse_return(raw)
        assert len(results) == 1
        assert results[0].return_code == "R01"

    def test_instructions_missing_bank_details_skipped(self):
        adapter = self._make_adapter()
        instr_no_bank = PaymentInstruction(
            billing_payment_id="BP-003",
            pay_to_entity_id="ENT-003",
            pay_to_name="No Bank Pharmacy",
            pay_to_npi=None,
            amount=Decimal("50.00"),
        )
        result = adapter.format_batch([instr_no_bank], "BATCH-001")
        assert result.success is False


class TestEchoAdapter:
    def _make_adapter(self) -> EchoAdapter:
        return EchoAdapter(client_id="ECHO_CLIENT_001", client_name="InfinityRx")

    def test_format_batch_generates_400_char_records(self):
        adapter = self._make_adapter()
        result = adapter.format_batch(INSTRUCTIONS, "BATCH-001", effective_date=date(2026, 4, 15))
        assert result.success is True
        lines = [l for l in result.file_content.strip().split("\n") if l]
        for line in lines:
            assert len(line) == 400, f"Echo line not 400 chars: {len(line)}"

    def test_total_amount_correct(self):
        adapter = self._make_adapter()
        result = adapter.format_batch(INSTRUCTIONS, "BATCH-001")
        assert result.raw_response is not None
        assert Decimal(result.raw_response["total_amount"]) == Decimal("350.50")

    def test_submit_returns_echo_reference(self):
        adapter = self._make_adapter()
        formatted = adapter.format_batch(INSTRUCTIONS, "BATCH-001")
        submitted = adapter.submit(formatted, "SUB-ECHO-001")
        assert "ECHO" in submitted.vendor_reference

    def test_health_check_healthy(self):
        adapter = self._make_adapter()
        assert adapter.health_check().status == "healthy"

    def test_parse_return_parses_returns(self):
        adapter = self._make_adapter()
        raw = {"returns": [{"billing_payment_id": "BP-001", "return_code": "R02", "return_reason": "CLOSED"}]}
        results = adapter.parse_return(raw)
        assert results[0].return_code == "R02"


class TestZelisAdapter:
    def _make_adapter(self) -> ZelisAdapter:
        return ZelisAdapter(api_endpoint="https://api.zelis.test/v1", api_key="test_key")

    def test_format_batch_generates_json(self):
        import json
        adapter = self._make_adapter()
        result = adapter.format_batch(INSTRUCTIONS, "BATCH-001")
        assert result.success is True
        payload = json.loads(result.file_content)
        assert "payments" in payload
        assert len(payload["payments"]) == 2

    def test_total_amount_in_payload(self):
        import json
        adapter = self._make_adapter()
        result = adapter.format_batch(INSTRUCTIONS, "BATCH-001")
        payload = json.loads(result.file_content)
        assert Decimal(payload["total_amount"]) == Decimal("350.50")

    def test_amounts_are_strings_not_floats(self):
        import json
        adapter = self._make_adapter()
        result = adapter.format_batch(INSTRUCTIONS, "BATCH-001")
        payload = json.loads(result.file_content)
        for payment in payload["payments"]:
            assert isinstance(payment["amount"], str), "amount must be string not float"

    def test_submit_returns_zelis_reference(self):
        adapter = self._make_adapter()
        formatted = adapter.format_batch(INSTRUCTIONS, "BATCH-001")
        submitted = adapter.submit(formatted, "SUB-ZELIS-001")
        assert "ZELIS" in submitted.vendor_reference

    def test_health_check_healthy(self):
        assert self._make_adapter().health_check().status == "healthy"


class TestCheckAdapter:
    def _make_adapter(self) -> CheckAdapter:
        return CheckAdapter(bank_account="ACCT-123456", bank_routing="021000021")

    def test_format_batch_generates_csv(self):
        adapter = self._make_adapter()
        result = adapter.format_batch(INSTRUCTIONS, "BATCH-001")
        assert result.success is True
        assert "check_number" in result.file_content

    def test_csv_has_correct_count(self):
        adapter = self._make_adapter()
        result = adapter.format_batch(INSTRUCTIONS, "BATCH-001")
        lines = result.file_content.strip().split("\n")
        assert len(lines) == len(INSTRUCTIONS) + 1  # header + data rows

    def test_total_amount_correct(self):
        adapter = self._make_adapter()
        result = adapter.format_batch(INSTRUCTIONS, "BATCH-001")
        assert Decimal(result.raw_response["total_amount"]) == Decimal("350.50")

    def test_submit_returns_check_reference(self):
        adapter = self._make_adapter()
        formatted = adapter.format_batch(INSTRUCTIONS, "BATCH-001")
        submitted = adapter.submit(formatted, "SUB-CHK-001")
        assert "CHK" in submitted.vendor_reference

    def test_health_check_healthy(self):
        assert self._make_adapter().health_check().status == "healthy"


class TestAdapterRegistry:
    def test_direct_ach_registered(self):
        assert get_adapter_class("direct_ach") is DirectAchAdapter

    def test_echo_registered(self):
        assert get_adapter_class("echo") is EchoAdapter

    def test_zelis_registered(self):
        assert get_adapter_class("zelis") is ZelisAdapter

    def test_check_registered(self):
        assert get_adapter_class("check_issuing") is CheckAdapter

    def test_unknown_vendor_returns_none(self):
        assert get_adapter_class("unknown_vendor") is None


class TestDirectAchAdapterCoverage:
    def _make_adapter(self) -> DirectAchAdapter:
        return DirectAchAdapter(
            file_cfg=NachaFileConfig(
                immediate_destination="021000021",
                immediate_origin="1234567890",
                immediate_destination_name="BANK OF TEST",
                immediate_origin_name="INFINITYRX LLC",
            ),
            batch_cfg=NachaBatchConfig(
                company_name="INFINITYRX",
                company_id="1234567890",
                entry_class_code="CCD",
                company_entry_description="PAYMT",
                originating_dfi_id="02100002",
            ),
        )

    def test_format_with_effective_date(self):
        adapter = self._make_adapter()
        result = adapter.format_batch(INSTRUCTIONS, "BATCH-001", effective_date=date(2026, 4, 20))
        assert result.success is True


class TestEchoAdapterCoverage:
    def _make_adapter(self, with_endpoint: bool = False) -> EchoAdapter:
        return EchoAdapter(
            client_id="ECHO_CLIENT_001",
            client_name="InfinityRx",
            api_endpoint="https://echo.test/api" if with_endpoint else None,
        )

    def test_submit_failed_returns_failure(self):
        from src.services.vendor_adapter import SubmitResult
        adapter = self._make_adapter()
        failed = SubmitResult(success=False, error_message="format error")
        result = adapter.submit(failed, "SUB-001")
        assert result.success is False

    def test_poll_settlement_returns_pending(self):
        adapter = self._make_adapter()
        results = adapter.poll_settlement("ECHO-REF", ["BP-001", "BP-002"])
        assert len(results) == 2
        assert all(r.status == "pending" for r in results)

    def test_health_check_with_api_endpoint(self):
        adapter = self._make_adapter(with_endpoint=True)
        result = adapter.health_check()
        assert result.status == "healthy"
        assert result.check_type == "api_ping"


class TestZelisAdapterCoverage:
    def _make_adapter(self) -> ZelisAdapter:
        return ZelisAdapter(api_endpoint="https://api.zelis.test/v1", api_key="test_key")

    def test_submit_failed_returns_failure(self):
        from src.services.vendor_adapter import SubmitResult
        adapter = self._make_adapter()
        failed = SubmitResult(success=False, error_message="bad")
        result = adapter.submit(failed, "SUB-001")
        assert result.success is False

    def test_poll_settlement_returns_pending(self):
        adapter = self._make_adapter()
        results = adapter.poll_settlement("ZELIS-REF", ["BP-001"])
        assert results[0].status == "pending"

    def test_parse_return_zelis(self):
        adapter = self._make_adapter()
        raw = {"returns": [{"billing_payment_id": "BP-001", "return_code": "R02"}]}
        results = adapter.parse_return(raw)
        assert results[0].return_code == "R02"
        assert results[0].payment_method_used == "eft"


class TestCheckAdapterCoverage:
    def _make_adapter(self) -> CheckAdapter:
        return CheckAdapter(bank_account="ACCT-123456", bank_routing="021000021")

    def test_submit_failed_returns_failure(self):
        from src.services.vendor_adapter import SubmitResult
        adapter = self._make_adapter()
        failed = SubmitResult(success=False, error_message="bad")
        result = adapter.submit(failed, "SUB-001")
        assert result.success is False

    def test_poll_settlement_returns_pending(self):
        adapter = self._make_adapter()
        results = adapter.poll_settlement("CHK-REF", ["BP-001"])
        assert results[0].status == "pending"

    def test_parse_return_empty(self):
        adapter = self._make_adapter()
        results = adapter.parse_return({"returns": []})
        assert results == []
