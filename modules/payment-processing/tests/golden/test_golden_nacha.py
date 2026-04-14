"""Golden master tests for NACHA file output.

First run generates the golden file. Subsequent runs compare byte-for-byte.
If output changes, verify intentionally and delete the .golden file to regenerate.

H-16: time is frozen to 2026-04-13 because nacha_generator._batch_header reads
date.today() for the company descriptive date — without freezing, the golden
fixture drifts every day.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from freezegun import freeze_time

from src.services.nacha_generator import (
    NachaBatchConfig,
    NachaEntryDetail,
    NachaFileConfig,
    TC_CREDIT_CHECKING,
    generate_nacha_file,
)

GOLDEN_DIR = Path(__file__).parent
GOLDEN_NACHA = GOLDEN_DIR / "nacha_sample.golden"
GOLDEN_ECHO = GOLDEN_DIR / "echo_400_sample.golden"

FILE_CFG = NachaFileConfig(
    immediate_destination="021000021",
    immediate_origin="1234567890",
    immediate_destination_name="BANK OF TEST       ",
    immediate_origin_name="INFINITYRX LLC         ",
)

BATCH_CFG = NachaBatchConfig(
    company_name="INFINITYRX      ",
    company_id="1234567890",
    entry_class_code="CCD",
    company_entry_description="PAYMT     ",
    originating_dfi_id="02100002",
    effective_date=date(2026, 4, 15),
)

GOLDEN_ENTRIES = [
    NachaEntryDetail(
        routing_number="021000021",
        account_number="12345678901234567",
        amount=Decimal("1234.56"),
        individual_id="BP-00001       ",
        individual_name="TEST PHARMACY LLC     ",
        trace_number="021000020000001",
        transaction_code=TC_CREDIT_CHECKING,
    ),
    NachaEntryDetail(
        routing_number="021000089",
        account_number="98765432109876543",
        amount=Decimal("567.89"),
        individual_id="BP-00002       ",
        individual_name="ANOTHER PHARMA CO     ",
        trace_number="021000020000002",
        transaction_code=TC_CREDIT_CHECKING,
    ),
]


@freeze_time("2026-04-13")
def _generate_golden_nacha() -> str:
    result = generate_nacha_file(
        FILE_CFG, BATCH_CFG, GOLDEN_ENTRIES,
        creation_date=date(2026, 4, 13),
        creation_time="0800",
    )
    return result.file_content


@freeze_time("2026-04-13")
class TestNachaGoldenMaster:
    def test_nacha_output_matches_golden(self):
        content = _generate_golden_nacha()

        if not GOLDEN_NACHA.exists():
            GOLDEN_NACHA.write_text(content, encoding="ascii")
            pytest.skip("Golden file created — run tests again to verify")

        golden = GOLDEN_NACHA.read_text(encoding="ascii")
        assert content == golden, (
            "NACHA file output changed! Verify the change is intentional "
            "then delete tests/golden/nacha_sample.golden to update."
        )

    def test_nacha_golden_total_is_correct(self):
        content = _generate_golden_nacha()
        result = generate_nacha_file(FILE_CFG, BATCH_CFG, GOLDEN_ENTRIES, creation_date=date(2026, 4, 13), creation_time="0800")
        assert result.total_amount == Decimal("1802.45")

    def test_nacha_golden_entry_count(self):
        result = generate_nacha_file(FILE_CFG, BATCH_CFG, GOLDEN_ENTRIES, creation_date=date(2026, 4, 13), creation_time="0800")
        assert result.entry_count == 2

    def test_nacha_golden_all_lines_94_chars(self):
        content = _generate_golden_nacha()
        lines = [l for l in content.split("\n") if l]
        for line in lines:
            assert len(line) == 94


class TestEchoGoldenMaster:
    def test_echo_output_matches_golden(self):
        from src.services.vendor_adapter import EchoAdapter, PaymentInstruction

        adapter = EchoAdapter(client_id="ECHO001   ", client_name="InfinityRx")
        instructions = [
            PaymentInstruction(
                billing_payment_id="BP-00001",
                pay_to_entity_id="ENT-001",
                pay_to_name="Test Pharmacy LLC",
                pay_to_npi="1234567890",
                amount=Decimal("1234.56"),
            ),
            PaymentInstruction(
                billing_payment_id="BP-00002",
                pay_to_entity_id="ENT-002",
                pay_to_name="Another Pharma Co",
                pay_to_npi="0987654321",
                amount=Decimal("567.89"),
            ),
        ]
        result = adapter.format_batch(instructions, "BATCH-GOLDEN", effective_date=date(2026, 4, 15))
        content = result.file_content

        if not GOLDEN_ECHO.exists():
            GOLDEN_ECHO.write_text(content, encoding="ascii")
            pytest.skip("Golden Echo file created — run tests again to verify")

        golden = GOLDEN_ECHO.read_text(encoding="ascii")
        assert content == golden, (
            "Echo Spec 400 output changed! Verify and delete tests/golden/echo_400_sample.golden to update."
        )
