"""Unit tests for FDA NDC parser, NADAC parser, and MAC list uploader."""
from __future__ import annotations

import sys
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from src.services.fda_ndc_parser import parse_fda_ndc_json
from src.services.mac_list import MACListError, parse_mac_list_csv
from src.services.nadac_parser import parse_nadac_csv


class TestFDANDCParser:
    def test_parses_valid_record(self) -> None:
        records = [
            {
                "package_ndc": "00093-3149-05",
                "brand_name": "Metformin",
                "generic_name": "metformin hydrochloride",
                "labeler_name": "Teva Pharmaceuticals",
                "dosage_form": "TABLET",
                "route": ["ORAL"],
                "marketing_status": "Prescription",
            }
        ]
        result = parse_fda_ndc_json(records)
        assert len(result) == 1
        assert result[0]["ndc_11"] == "00093314905"
        assert result[0]["drug_name_display"] == "Metformin"
        assert result[0]["data_source"] == "fda_ndc"

    def test_invalid_ndc_skipped(self) -> None:
        records = [
            {"package_ndc": "BAD", "brand_name": "Bad Drug"},
            {"package_ndc": "00093-3149-05", "brand_name": "Good Drug"},
        ]
        result = parse_fda_ndc_json(records)
        assert len(result) == 1
        assert result[0]["drug_name_display"] == "Good Drug"

    def test_marketing_status_discontinued(self) -> None:
        records = [
            {"package_ndc": "00093-3149-05", "marketing_status": "Discontinued"},
        ]
        result = parse_fda_ndc_json(records)
        assert result[0]["marketing_status"] == "discontinued"

    def test_drug_name_falls_back_to_generic(self) -> None:
        records = [
            {"package_ndc": "00093-3149-05", "generic_name": "metformin", "brand_name": None},
        ]
        result = parse_fda_ndc_json(records)
        assert result[0]["drug_name_display"] == "metformin"

    def test_otc_mapping(self) -> None:
        records = [
            {"package_ndc": "00093-3149-05", "product_type": "OTC_DRUG", "brand_name": "Ibuprofen"},
        ]
        result = parse_fda_ndc_json(records)
        assert result[0]["otc_rx"] == "OTC"

    def test_empty_list_returns_empty(self) -> None:
        assert parse_fda_ndc_json([]) == []


class TestNADACParser:
    def test_parses_valid_csv(self) -> None:
        csv_content = "ndc,nadac_per_unit,effective_date,unit_type\n00093314905,0.045000,2026-01-01,EA\n"
        result = parse_nadac_csv(csv_content)
        assert len(result) == 1
        assert result[0]["ndc_11"] == "00093314905"
        assert result[0]["price_per_unit"] == Decimal("0.045000")
        assert result[0]["price_type"] == "NADAC"
        assert result[0]["effective_date"] == date(2026, 1, 1)

    def test_invalid_ndc_skipped(self) -> None:
        csv_content = "ndc,nadac_per_unit,effective_date\nBAD,0.045000,2026-01-01\n00093314905,0.045000,2026-01-01\n"
        result = parse_nadac_csv(csv_content)
        assert len(result) == 1

    def test_invalid_price_skipped(self) -> None:
        csv_content = "ndc,nadac_per_unit,effective_date\n00093314905,NOT_A_PRICE,2026-01-01\n"
        result = parse_nadac_csv(csv_content)
        assert result == []

    def test_missing_effective_date_skipped(self) -> None:
        csv_content = "ndc,nadac_per_unit,effective_date\n00093314905,0.045000,\n"
        result = parse_nadac_csv(csv_content)
        assert result == []

    def test_price_is_decimal_not_float(self) -> None:
        csv_content = "ndc,nadac_per_unit,effective_date\n00093314905,0.045123,2026-01-01\n"
        result = parse_nadac_csv(csv_content)
        assert isinstance(result[0]["price_per_unit"], Decimal)
        assert not isinstance(result[0]["price_per_unit"], float)

    def test_price_6_decimal_places(self) -> None:
        csv_content = "ndc,nadac_per_unit,effective_date\n00093314905,0.04512345,2026-01-01\n"
        result = parse_nadac_csv(csv_content)
        # Quantized to 6 decimal places
        assert result[0]["price_per_unit"] == Decimal("0.045123")


class TestMACListParser:
    def test_parses_valid_csv(self) -> None:
        tenant_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
        csv_content = "ndc,price_per_unit,effective_date,unit_type\n00093314905,0.030000,2026-01-01,EA\n"
        result = parse_mac_list_csv(csv_content, tenant_id)
        assert len(result) == 1
        assert result[0]["ndc_11"] == "00093314905"
        assert result[0]["price_per_unit"] == Decimal("0.030000")
        assert result[0]["tenant_id"] == tenant_id

    def test_invalid_ndc_raises_mac_error(self) -> None:
        tenant_id = uuid.uuid4()
        csv_content = "ndc,price_per_unit,effective_date\nBAD,0.030000,2026-01-01\n"
        with pytest.raises(MACListError) as exc_info:
            parse_mac_list_csv(csv_content, tenant_id)
        assert len(exc_info.value.errors) == 1
        assert exc_info.value.errors[0]["row"] == 2

    def test_duplicate_ndc_raises_error_with_row_info(self) -> None:
        tenant_id = uuid.uuid4()
        csv_content = (
            "ndc,price_per_unit,effective_date\n"
            "00093314905,0.030000,2026-01-01\n"
            "00093314905,0.035000,2026-01-01\n"
        )
        with pytest.raises(MACListError) as exc_info:
            parse_mac_list_csv(csv_content, tenant_id)
        # Row 3 is the duplicate
        rows_with_errors = [e["row"] for e in exc_info.value.errors]
        assert 3 in rows_with_errors

    def test_zero_price_raises_error(self) -> None:
        tenant_id = uuid.uuid4()
        csv_content = "ndc,price_per_unit,effective_date\n00093314905,0.000000,2026-01-01\n"
        with pytest.raises(MACListError):
            parse_mac_list_csv(csv_content, tenant_id)

    def test_missing_effective_date_raises_error(self) -> None:
        tenant_id = uuid.uuid4()
        csv_content = "ndc,price_per_unit,effective_date\n00093314905,0.030000,\n"
        with pytest.raises(MACListError):
            parse_mac_list_csv(csv_content, tenant_id)

    def test_all_errors_reported_not_just_first(self) -> None:
        tenant_id = uuid.uuid4()
        csv_content = (
            "ndc,price_per_unit,effective_date\n"
            "BAD1,0.030000,2026-01-01\n"
            "BAD2,0.030000,2026-01-01\n"
        )
        with pytest.raises(MACListError) as exc_info:
            parse_mac_list_csv(csv_content, tenant_id)
        assert len(exc_info.value.errors) == 2

    def test_price_is_decimal(self) -> None:
        tenant_id = uuid.uuid4()
        csv_content = "ndc,price_per_unit,effective_date\n00093314905,0.030000,2026-01-01\n"
        result = parse_mac_list_csv(csv_content, tenant_id)
        assert isinstance(result[0]["price_per_unit"], Decimal)
        assert not isinstance(result[0]["price_per_unit"], float)
