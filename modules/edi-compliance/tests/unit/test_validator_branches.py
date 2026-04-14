"""Branch coverage for validator edge cases."""

from __future__ import annotations

from decimal import Decimal
from datetime import datetime, timezone

import pytest

from src.x12.delimiters import Delimiters
from src.x12.generators.gen_835 import generate_835
from src.x12.generators.schemas import Generate835Request, N1Party, TrnTrace
from src.x12.validators.validator import (
    ValidationLevel,
    _validate_syntax,
    validate_x12,
    validate_835_basic,
)

_DELIMS = Delimiters(element="*", sub_element=":", segment="~")
_NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

TENANT_ID = "11111111-1111-1111-1111-111111111111"
PARTNER_ID = "22222222-2222-2222-2222-222222222222"


def _make_835() -> str:
    req = Generate835Request(
        tenant_id=TENANT_ID,
        trading_partner_id=PARTNER_ID,
        isa_control_number=1,
        gs_control_number=1,
        st_control_number=1,
        payment_date="20260101",
        payment_amount=Decimal("100.00"),
        credit_debit_flag="C",
        payment_method="ACH",
        check_eft_number="EFT001",
        payer=N1Party(entity_qualifier="PR", name="PAYER"),
        payee=N1Party(entity_qualifier="PE", name="PAYEE"),
        trace=TrnTrace(check_eft_number="EFT001", payer_id="P001"),
        claims=[],
        sender_qualifier="ZZ",
        sender_id="INFINITYRX     ",
        receiver_qualifier="ZZ",
        test_mode=True,
        implementation_guide="005010X221A1",
    )
    return generate_835(req, _DELIMS, _NOW)


def test_validate_no_isa_first():
    """ISA not the first segment triggers L1-001 and early return."""
    raw = "GS*HP*A*B*20260101*1200*1*X*005010X221A1~ISA*00*          *00*          *ZZ*A*ZZ*B*260101*1200*^*00501*000000001*0*T*:~IEA*1*000000001~"
    result = _validate_syntax(raw, _DELIMS)
    codes = [e.code for e in result]
    assert "L1-001" in codes


def test_validate_iea_not_last():
    """IEA not the last segment triggers L1-002."""
    raw = _make_835()
    # Add a segment after IEA
    corrupted = raw + "GS*HP*extra~"
    result = validate_x12(corrupted)
    assert not result.is_valid
    codes = [e.code for e in result.errors]
    assert "L1-002" in codes


def test_validate_control_number_mismatch():
    """ISA13 != IEA02 triggers L1-007."""
    raw = _make_835()
    # Corrupt IEA02 to a different control number
    corrupted = raw.replace("IEA*1*000000001~", "IEA*1*000000099~")
    result = validate_x12(corrupted)
    assert not result.is_valid
    codes = [e.code for e in result.errors]
    assert "L1-007" in codes


def test_validate_se01_non_numeric():
    """SE01 non-numeric value triggers L1-010."""
    raw = _make_835()
    # Find and corrupt SE01
    corrupted = raw.replace("SE*", "SE*X*")
    # Remove the original proper SE
    import re
    corrupted = re.sub(r"SE\*\d+\*", "SE*X*", raw, count=1)
    result = validate_x12(corrupted)
    assert not result.is_valid
    codes = [e.code for e in result.errors]
    assert "L1-010" in codes


def test_validate_se01_count_mismatch():
    """SE01 count that doesn't match actual segment count triggers L1-009."""
    raw = _make_835()
    # Replace SE segment count with wrong value
    import re
    corrupted = re.sub(r"SE\*(\d+)\*", "SE*99*", raw, count=1)
    result = validate_x12(corrupted)
    assert not result.is_valid
    codes = [e.code for e in result.errors]
    assert "L1-009" in codes


def test_validate_x12_invalid_delimiters():
    """Completely invalid EDI content triggers L1-000 (detect_delimiters failure)."""
    result = validate_x12("THIS IS NOT X12 EDI AT ALL")
    assert not result.is_valid
    assert result.errors[0].code == "L1-000"


def test_validate_gs_ge_count_mismatch():
    """GS without matching GE triggers L1-004."""
    raw = _make_835()
    # Add extra GS
    corrupted = raw.replace("GS*HP*", "GS*HP*EXTRA~GS*HP*", 1)
    result = validate_x12(corrupted)
    assert not result.is_valid
    codes = [e.code for e in result.errors]
    assert "L1-004" in codes


def test_validate_835_guide_bpr_too_short():
    """BPR with fewer than 3 elements triggers L2-835-002."""
    from src.x12.validators.validator import validate_835_basic
    # Build a minimal 835 with BPR having only 1 element
    raw = (
        "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
        "*260101*1200*^*00501*000000055*0*T*:~"
        "GS*HP*SENDER*RECEIVER*20260101*1200*1*X*005010X221A1~"
        "ST*835*0001*005010X221A1~"
        "BPR*~"  # BPR with only 1 element
        "TRN*1*EFT055*PAYER001~"
        "DTM*405*20260101~"
        "N1*PR*PAYER~"
        "N1*PE*PAYEE~"
        "SE*8*0001~"
        "GE*1*1~"
        "IEA*1*000000055~"
    )
    errors = validate_835_basic(raw, _DELIMS)
    assert any("L2-835-002" in e for e in errors)


def test_validate_se_too_short():
    """SE segment with no elements skips the count check (line 115->113 branch)."""
    raw = _make_835()
    # Replace SE with a bare SE segment (no elements)
    import re
    # Replace SE*N*NNNN with just SE (no elements)
    corrupted = re.sub(r"SE\*\d+\*\d+~", "SE~", raw, count=1)
    result = _validate_syntax(corrupted, _DELIMS)
    # Should not crash; SE with no elements is skipped without an error
    codes = [e.code for e in result]
    assert "L1-010" not in codes  # No SE01 numeric error since SE01 doesn't exist


def test_validate_business_nm1_empty_npi():
    """NM1 with XX qualifier but empty NPI field skips NPI check (line 141 branch)."""
    raw = (
        "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
        "*260101*1200*^*00501*000000050*0*T*:~"
        "GS*HP*SENDER*RECEIVER*20260101*1200*1*X*005010X221A1~"
        "ST*835*0001*005010X221A1~"
        "BPR*I*100.00*C*ACH~~~~~~~~~~~~~~~~20260101~"
        "TRN*1*EFT050*PAYER001~"
        "DTM*405*20260101~"
        "N1*PR*PAYER~"
        "N1*PE*PAYEE~"
        "NM1*85*2*PROVIDER*****XX*~"  # NM109 is empty — skips Luhn check
        "SE*10*0001~"
        "GE*1*1~"
        "IEA*1*000000050~"
    )
    result = validate_x12(raw)
    # NM1 with empty NPI should not add L3-001 error
    codes = [e.code for e in result.errors]
    assert "L3-001" not in codes


def test_gen_835_validation_failure_raises():
    """Generator raises ValueError when generated 835 fails validation."""
    from unittest.mock import patch
    from src.x12.generators.gen_835 import generate_835
    from src.x12.generators.schemas import Generate835Request, N1Party, TrnTrace
    from decimal import Decimal
    from datetime import datetime, timezone

    req = Generate835Request(
        tenant_id=TENANT_ID,
        trading_partner_id=PARTNER_ID,
        isa_control_number=1,
        gs_control_number=1,
        st_control_number=1,
        payment_date="20260101",
        payment_amount=Decimal("100.00"),
        credit_debit_flag="C",
        payment_method="ACH",
        check_eft_number="EFT001",
        payer=N1Party(entity_qualifier="PR", name="PAYER"),
        payee=N1Party(entity_qualifier="PE", name="PAYEE"),
        trace=TrnTrace(check_eft_number="EFT001", payer_id="P001"),
        claims=[],
        sender_qualifier="ZZ",
        sender_id="INFINITYRX     ",
        receiver_qualifier="ZZ",
        test_mode=True,
        implementation_guide="005010X221A1",
    )
    with patch("src.x12.validators.validator.validate_835_basic", return_value=["L1-001: some error"]):
        with patch("src.x12.generators.gen_835.validate_835_basic", return_value=["L1-001: some error"], create=True):
            with pytest.raises(ValueError, match="Generated 835 failed validation"):
                generate_835(req, _DELIMS, _NOW)
