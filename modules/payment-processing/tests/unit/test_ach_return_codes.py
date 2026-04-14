"""Unit tests for ACH return code table — 100% coverage (financial path)."""
from __future__ import annotations


from src.services.ach_return_codes import (
    ACH_RETURN_CODES,
    ACH_RETURN_CODE_MAP,
    get_return_code,
    is_suspicious_return,
)


class TestAchReturnCodeTable:
    def test_has_r01(self):
        rc = get_return_code("R01")
        assert rc is not None
        assert rc.description == "Insufficient Funds"
        assert rc.is_retryable is True
        assert rc.default_action == "auto_retry"
        assert rc.retry_delay_days == 3

    def test_r01_not_suspicious(self):
        assert is_suspicious_return("R01") is False

    def test_has_r02_account_closed(self):
        rc = get_return_code("R02")
        assert rc is not None
        assert rc.is_retryable is False
        assert rc.default_action == "carryover"

    def test_has_r10_suspicious(self):
        rc = get_return_code("R10")
        assert rc is not None
        assert rc.triggers_fwa_alert is True
        assert is_suspicious_return("R10") is True

    def test_has_r07_suspicious(self):
        assert is_suspicious_return("R07") is True

    def test_has_r29_suspicious(self):
        assert is_suspicious_return("R29") is True

    def test_has_r05_suspicious(self):
        assert is_suspicious_return("R05") is True

    def test_unknown_code_returns_none(self):
        assert get_return_code("R99") is None

    def test_unknown_code_not_suspicious(self):
        assert is_suspicious_return("R99") is False

    def test_all_codes_have_required_fields(self):
        for rc in ACH_RETURN_CODES:
            assert rc.code.startswith("R"), f"{rc.code} must start with R"
            assert rc.description, f"{rc.code} must have description"
            assert rc.category in (
                "insufficient_funds", "account_closed", "unauthorized", "administrative", "other"
            ), f"{rc.code} has invalid category {rc.category}"
            assert rc.default_action in (
                "auto_retry", "carryover", "manual_review", "write_off"
            ), f"{rc.code} has invalid action {rc.default_action}"
            if rc.is_retryable:
                assert rc.retry_delay_days is not None, f"{rc.code} retryable but no delay"

    def test_map_matches_list(self):
        assert len(ACH_RETURN_CODE_MAP) == len(ACH_RETURN_CODES)

    def test_r85_exists(self):
        assert get_return_code("R85") is not None

    def test_r09_retryable_five_day_delay(self):
        rc = get_return_code("R09")
        assert rc is not None
        assert rc.is_retryable is True
        assert rc.retry_delay_days == 5

    def test_r16_account_frozen(self):
        rc = get_return_code("R16")
        assert rc is not None
        assert rc.default_action == "carryover"
        assert rc.is_retryable is False

    def test_r04_invalid_account(self):
        rc = get_return_code("R04")
        assert rc is not None
        assert rc.is_retryable is False
        assert rc.default_action == "carryover"
