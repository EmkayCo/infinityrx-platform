"""RED tests for PHI encryption on Member model — 100% coverage required."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from src.services.member_service import MemberService
from src.api.schemas.member import MemberCreate, PhiAccessLevel


class TestPhiFieldsMasking:
    def test_full_access_returns_unmasked_phi(self):
        """PHI access level 'full' returns real values."""
        svc = MemberService.__new__(MemberService)
        raw = {
            "first_name": "Alice",
            "last_name": "Johnson",
            "date_of_birth": "1990-05-10",
            "ssn": "123456789",
            "phone": "+15555550100",
            "email": "alice@example.com",
        }
        masked = svc.mask_phi(raw, access_level=PhiAccessLevel.FULL)
        assert masked["first_name"] == "Alice"
        assert masked["last_name"] == "Johnson"
        assert masked["ssn"] == "123456789"

    def test_partial_access_masks_ssn_and_dob(self):
        svc = MemberService.__new__(MemberService)
        raw = {
            "first_name": "Alice",
            "last_name": "Johnson",
            "date_of_birth": "1990-05-10",
            "ssn": "123456789",
            "phone": "+15555550100",
            "email": "alice@example.com",
        }
        masked = svc.mask_phi(raw, access_level=PhiAccessLevel.PARTIAL)
        assert masked["ssn"] == "***-**-6789"
        assert masked["date_of_birth"] == "****-**-10"
        assert masked["first_name"] == "Alice"  # name visible at partial

    def test_redacted_access_masks_all_phi(self):
        svc = MemberService.__new__(MemberService)
        raw = {
            "first_name": "Alice",
            "last_name": "Johnson",
            "date_of_birth": "1990-05-10",
            "ssn": "123456789",
            "phone": "+15555550100",
            "email": "alice@example.com",
        }
        masked = svc.mask_phi(raw, access_level=PhiAccessLevel.REDACTED)
        assert masked["first_name"] == "**REDACTED**"
        assert masked["last_name"] == "**REDACTED**"
        assert masked["ssn"] == "**REDACTED**"
        assert masked["date_of_birth"] == "**REDACTED**"
        assert masked["phone"] == "**REDACTED**"
        assert masked["email"] == "**REDACTED**"


class TestMemberCreateValidation:
    def test_valid_member_create_passes(self):
        data = MemberCreate(
            member_id="MEM001",
            first_name="John",
            last_name="Doe",
            date_of_birth="1985-03-15",
            gender="M",
            rx_bin="123456",
            effective_date="2026-01-01",
        )
        assert data.member_id == "MEM001"

    def test_invalid_gender_rejected(self):
        with pytest.raises(Exception):
            MemberCreate(
                member_id="MEM001",
                first_name="John",
                last_name="Doe",
                date_of_birth="1985-03-15",
                gender="X",  # invalid — must be M, F, or U
                rx_bin="123456",
                effective_date="2026-01-01",
            )

    def test_invalid_rx_bin_rejected(self):
        """BIN must be exactly 6 digits (LESSON-004: use fullmatch)."""
        with pytest.raises(Exception):
            MemberCreate(
                member_id="MEM001",
                first_name="John",
                last_name="Doe",
                date_of_birth="1985-03-15",
                gender="M",
                rx_bin="12345",  # 5 digits — invalid
                effective_date="2026-01-01",
            )

    def test_rx_bin_with_trailing_newline_rejected(self):
        """LESSON-004: trailing newline must be rejected."""
        with pytest.raises(Exception):
            MemberCreate(
                member_id="MEM001",
                first_name="John",
                last_name="Doe",
                date_of_birth="1985-03-15",
                gender="M",
                rx_bin="123456\n",  # trailing newline — must fail
                effective_date="2026-01-01",
            )

    def test_ssn_format_validation(self):
        """SSN must be 9 digits (no dashes), validated with fullmatch."""
        data = MemberCreate(
            member_id="MEM001",
            first_name="John",
            last_name="Doe",
            date_of_birth="1985-03-15",
            gender="M",
            rx_bin="123456",
            effective_date="2026-01-01",
            ssn="123456789",
        )
        assert data.ssn == "123456789"

    def test_ssn_with_dashes_rejected(self):
        with pytest.raises(Exception):
            MemberCreate(
                member_id="MEM001",
                first_name="John",
                last_name="Doe",
                date_of_birth="1985-03-15",
                gender="M",
                rx_bin="123456",
                effective_date="2026-01-01",
                ssn="123-45-6789",
            )
