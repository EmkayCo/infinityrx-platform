"""Abstract PaymentVendorAdapter interface + concrete adapter implementations.

New vendors: implement PaymentVendorAdapter and register in the factory.
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from .decimal_utils import money
from .nacha_generator import (
    TC_CREDIT_CHECKING,
    NachaBatchConfig,
    NachaEntryDetail,
    NachaFileConfig,
    NachaGenerationResult,
    generate_nacha_file,
)

logger = logging.getLogger("payment.adapters")


@dataclass
class PaymentInstruction:
    """Single payment instruction from Billing."""

    billing_payment_id: str
    pay_to_entity_id: str
    pay_to_name: str
    pay_to_npi: str | None
    amount: Decimal  # never float
    routing_number: str | None = None
    account_number: str | None = None
    payment_method: str = "ach"


@dataclass
class SubmitResult:
    success: bool
    vendor_reference: str | None = None
    error_message: str | None = None
    raw_response: dict[str, Any] | None = None
    file_content: str | None = None  # for file-based adapters


@dataclass
class SettlementStatus:
    billing_payment_id: str
    status: str  # settled, returned, pending, rejected
    settlement_date: date | None = None
    settlement_reference: str | None = None
    return_code: str | None = None
    return_reason: str | None = None
    vendor_payment_id: str | None = None
    payment_method_used: str | None = None
    trace_number: str | None = None


@dataclass
class HealthCheckResult:
    status: str  # healthy, degraded, down
    response_time_ms: int | None = None
    error_message: str | None = None
    check_type: str = "api_ping"


class PaymentVendorAdapter(ABC):
    """Abstract interface every vendor adapter must implement."""

    @abstractmethod
    def format_batch(
        self,
        instructions: list[PaymentInstruction],
        batch_id: str,
        effective_date: date | None = None,
    ) -> SubmitResult:
        """Format payment instructions into vendor-specific format."""

    @abstractmethod
    def submit(self, formatted: SubmitResult, submission_id: str) -> SubmitResult:
        """Submit formatted payload to vendor. Returns updated SubmitResult."""

    @abstractmethod
    def poll_settlement(
        self, vendor_reference: str, billing_payment_ids: list[str]
    ) -> list[SettlementStatus]:
        """Poll vendor for settlement status of previously submitted payments."""

    @abstractmethod
    def parse_return(self, raw_data: dict[str, Any]) -> list[SettlementStatus]:
        """Parse a return file/payload from the vendor into SettlementStatus records."""

    @abstractmethod
    def health_check(self) -> HealthCheckResult:
        """Perform a health check against the vendor endpoint."""


class DirectAchAdapter(PaymentVendorAdapter):
    """NACHA/direct ACH adapter — generates NACHA files for bank submission."""

    def __init__(
        self,
        file_cfg: NachaFileConfig,
        batch_cfg: NachaBatchConfig,
        originator_trace_prefix: str = "12345600",
    ) -> None:
        self._file_cfg = file_cfg
        self._batch_cfg = batch_cfg
        self._trace_prefix = originator_trace_prefix[:8].ljust(8, "0")

    def format_batch(
        self,
        instructions: list[PaymentInstruction],
        batch_id: str,
        effective_date: date | None = None,
    ) -> SubmitResult:
        if not instructions:
            return SubmitResult(success=False, error_message="No payment instructions provided")

        cfg = self._batch_cfg
        if effective_date:
            from dataclasses import replace
            cfg = replace(cfg, effective_date=effective_date)

        entries = []
        for idx, instr in enumerate(instructions):
            if not instr.routing_number or not instr.account_number:
                logger.warning("Missing bank details for entity %s", instr.pay_to_entity_id)
                continue
            trace = f"{self._trace_prefix}{str(idx + 1).zfill(7)}"
            entries.append(
                NachaEntryDetail(
                    routing_number=instr.routing_number,
                    account_number=instr.account_number,
                    amount=instr.amount,
                    individual_id=instr.billing_payment_id[:15],
                    individual_name=instr.pay_to_name[:22],
                    trace_number=trace,
                    transaction_code=TC_CREDIT_CHECKING,
                )
            )

        if not entries:
            return SubmitResult(success=False, error_message="No valid bank details in instructions")

        result: NachaGenerationResult = generate_nacha_file(
            self._file_cfg, cfg, entries
        )
        return SubmitResult(
            success=True,
            file_content=result.file_content,
            raw_response={
                "total_amount": str(result.total_amount),
                "entry_count": result.entry_count,
                "file_hash": result.file_hash,
            },
        )

    def submit(self, formatted: SubmitResult, submission_id: str) -> SubmitResult:
        if not formatted.success:
            return formatted
        logger.info("NACHA file ready for SFTP delivery: submission %s", submission_id)
        return SubmitResult(
            success=True,
            vendor_reference=f"NACHA-{submission_id[:8]}",
            file_content=formatted.file_content,
            raw_response=formatted.raw_response,
        )

    def poll_settlement(
        self, vendor_reference: str, billing_payment_ids: list[str]
    ) -> list[SettlementStatus]:
        return [
            SettlementStatus(billing_payment_id=bid, status="pending")
            for bid in billing_payment_ids
        ]

    def parse_return(self, raw_data: dict[str, Any]) -> list[SettlementStatus]:
        results = []
        for entry in raw_data.get("returns", []):
            results.append(
                SettlementStatus(
                    billing_payment_id=entry.get("billing_payment_id", ""),
                    status="returned",
                    return_code=entry.get("return_code"),
                    return_reason=entry.get("return_reason"),
                    trace_number=entry.get("trace_number"),
                )
            )
        return results

    def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(status="healthy", check_type="sftp_connect")


class EchoAdapter(PaymentVendorAdapter):
    """Echo Health Spec 400 file adapter."""

    def __init__(
        self,
        client_id: str,
        client_name: str,
        api_endpoint: str | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_name = client_name
        self._api_endpoint = api_endpoint

    def format_batch(
        self,
        instructions: list[PaymentInstruction],
        batch_id: str,
        effective_date: date | None = None,
    ) -> SubmitResult:
        """Generate Echo Spec 400 fixed-width file."""
        lines: list[str] = []
        eff = (effective_date or date.today()).strftime("%Y%m%d")

        for instr in instructions:
            amount_cents = int(
                (instr.amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )
            npi_field = instr.pay_to_npi[:10].ljust(10) if instr.pay_to_npi else " " * 10
            line = (
                self._client_id[:10].ljust(10)
                + eff
                + npi_field
                + instr.pay_to_name[:35].ljust(35)
                + str(amount_cents).zfill(12)
                + instr.billing_payment_id[:20].ljust(20)
                + " " * 302
                + "ACH"
            )[:400]
            lines.append(line)

        file_content = "\n".join(lines) + "\n"
        total = money(sum(i.amount for i in instructions))
        return SubmitResult(
            success=True,
            file_content=file_content,
            raw_response={
                "total_amount": str(total),
                "record_count": len(instructions),
                "batch_id": batch_id,
                "format": "echo_400",
            },
        )

    def submit(self, formatted: SubmitResult, submission_id: str) -> SubmitResult:
        if not formatted.success:
            return formatted
        logger.info("Echo Spec 400 file ready: submission %s", submission_id)
        return SubmitResult(
            success=True,
            vendor_reference=f"ECHO-{submission_id[:8]}",
            file_content=formatted.file_content,
            raw_response=formatted.raw_response,
        )

    def poll_settlement(
        self, vendor_reference: str, billing_payment_ids: list[str]
    ) -> list[SettlementStatus]:
        return [
            SettlementStatus(billing_payment_id=bid, status="pending")
            for bid in billing_payment_ids
        ]

    def parse_return(self, raw_data: dict[str, Any]) -> list[SettlementStatus]:
        results = []
        for entry in raw_data.get("returns", []):
            results.append(
                SettlementStatus(
                    billing_payment_id=entry.get("billing_payment_id", ""),
                    status="returned",
                    return_code=entry.get("return_code"),
                    return_reason=entry.get("return_reason"),
                    payment_method_used="eft",
                )
            )
        return results

    def health_check(self) -> HealthCheckResult:
        if self._api_endpoint:
            return HealthCheckResult(status="healthy", response_time_ms=120, check_type="api_ping")
        return HealthCheckResult(status="healthy", check_type="sftp_connect")


class ZelisAdapter(PaymentVendorAdapter):
    """Zelis API JSON adapter."""

    def __init__(self, api_endpoint: str, api_key: str) -> None:
        self._api_endpoint = api_endpoint
        self._api_key = api_key

    def format_batch(
        self,
        instructions: list[PaymentInstruction],
        batch_id: str,
        effective_date: date | None = None,
    ) -> SubmitResult:
        """Build Zelis JSON payload."""
        payments = [
            {
                "payment_id": instr.billing_payment_id,
                "payee_npi": instr.pay_to_npi or "",
                "payee_name": instr.pay_to_name,
                "amount": str(instr.amount),
                "effective_date": (effective_date or date.today()).isoformat(),
            }
            for instr in instructions
        ]
        payload = {
            "batch_id": batch_id,
            "total_amount": str(money(sum(i.amount for i in instructions))),
            "payment_count": len(instructions),
            "payments": payments,
        }
        return SubmitResult(
            success=True,
            file_content=json.dumps(payload, indent=2),
            raw_response={"format": "zelis_json", "batch_id": batch_id},
        )

    def submit(self, formatted: SubmitResult, submission_id: str) -> SubmitResult:
        if not formatted.success:
            return formatted
        logger.info("Zelis JSON payload ready: submission %s", submission_id)
        return SubmitResult(
            success=True,
            vendor_reference=f"ZELIS-{submission_id[:8]}",
            file_content=formatted.file_content,
            raw_response=formatted.raw_response,
        )

    def poll_settlement(
        self, vendor_reference: str, billing_payment_ids: list[str]
    ) -> list[SettlementStatus]:
        return [
            SettlementStatus(billing_payment_id=bid, status="pending")
            for bid in billing_payment_ids
        ]

    def parse_return(self, raw_data: dict[str, Any]) -> list[SettlementStatus]:
        results = []
        for entry in raw_data.get("returns", []):
            results.append(
                SettlementStatus(
                    billing_payment_id=entry.get("billing_payment_id", ""),
                    status="returned",
                    return_code=entry.get("return_code"),
                    payment_method_used="eft",
                )
            )
        return results

    def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(status="healthy", response_time_ms=95, check_type="api_ping")


class CheckAdapter(PaymentVendorAdapter):
    """Check issuance adapter — generates check CSV file."""

    def __init__(self, bank_account: str, bank_routing: str) -> None:
        self._bank_account = bank_account
        self._bank_routing = bank_routing

    def format_batch(
        self,
        instructions: list[PaymentInstruction],
        batch_id: str,
        effective_date: date | None = None,
    ) -> SubmitResult:
        issue_date = (effective_date or date.today()).strftime("%Y-%m-%d")
        lines = ["check_number,payee_name,payee_address,amount,issue_date,account,reference"]
        for idx, instr in enumerate(instructions):
            check_num = f"CHK{str(idx + 1).zfill(8)}"
            lines.append(
                f"{check_num},{instr.pay_to_name},,{instr.amount},{issue_date},"
                f"{self._bank_account},{instr.billing_payment_id}"
            )
        file_content = "\n".join(lines) + "\n"
        total = money(sum(i.amount for i in instructions))
        return SubmitResult(
            success=True,
            file_content=file_content,
            raw_response={
                "total_amount": str(total),
                "check_count": len(instructions),
                "format": "check_csv",
            },
        )

    def submit(self, formatted: SubmitResult, submission_id: str) -> SubmitResult:
        if not formatted.success:
            return formatted
        return SubmitResult(
            success=True,
            vendor_reference=f"CHK-{submission_id[:8]}",
            file_content=formatted.file_content,
            raw_response=formatted.raw_response,
        )

    def poll_settlement(
        self, vendor_reference: str, billing_payment_ids: list[str]
    ) -> list[SettlementStatus]:
        return [
            SettlementStatus(billing_payment_id=bid, status="pending")
            for bid in billing_payment_ids
        ]

    def parse_return(self, raw_data: dict[str, Any]) -> list[SettlementStatus]:
        return []

    def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(status="healthy", check_type="sftp_connect")


# Adapter factory
_ADAPTER_REGISTRY: dict[str, type] = {
    "direct_ach": DirectAchAdapter,
    "echo": EchoAdapter,
    "zelis": ZelisAdapter,
    "check_issuing": CheckAdapter,
}


def get_adapter_class(vendor_type: str) -> type | None:
    return _ADAPTER_REGISTRY.get(vendor_type)
