"""Tests targeting specific coverage gaps."""
from __future__ import annotations

import json
import sys
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from src.services.drug_lookup import DrugLookupService, _serialize
from src.services.fda_ndc_parser import _map_marketing_status, _map_otc_rx, _parse_date, parse_fda_ndc_json
from src.services.mac_list import parse_mac_list_csv
from src.services.nadac_parser import parse_nadac_csv
from src.utils.ndc import InvalidNDCError, normalize_ndc


class TestNDCNormalizerGaps:
    def test_invalid_digit_count_not_10_or_11_raises(self) -> None:
        # 9 digits — not 10 or 11
        with pytest.raises(InvalidNDCError, match="9 digits"):
            normalize_ndc("000933149")


class TestFDAParserGaps:
    def test_route_as_string_not_list(self) -> None:
        records = [
            {
                "package_ndc": "00093-3149-05",
                "brand_name": "Drug",
                "route": "ORAL",  # string, not list
            }
        ]
        result = parse_fda_ndc_json(records)
        assert result[0]["route_of_administration"] == "ORAL"

    def test_empty_route_field(self) -> None:
        records = [
            {
                "package_ndc": "00093-3149-05",
                "brand_name": "Drug",
                "route": None,
            }
        ]
        result = parse_fda_ndc_json(records)
        assert result[0]["route_of_administration"] is None

    def test_marketing_status_pending(self) -> None:
        assert _map_marketing_status("Pending") == "pending"

    def test_marketing_status_active(self) -> None:
        assert _map_marketing_status("Prescription") == "active"

    def test_otc_rx_prescription(self) -> None:
        assert _map_otc_rx("PRESCRIPTION") == "Rx"

    def test_otc_rx_unknown(self) -> None:
        assert _map_otc_rx("UNKNOWN") is None

    def test_parse_date_invalid_returns_none(self) -> None:
        assert _parse_date("not-a-date") is None

    def test_parse_date_none_returns_none(self) -> None:
        assert _parse_date(None) is None

    def test_ndc_11_with_no_dashes(self) -> None:
        records = [
            {
                "package_ndc": "00093314905",  # already 11-digit no dashes
                "brand_name": "Drug",
            }
        ]
        result = parse_fda_ndc_json(records)
        assert len(result) == 1
        assert result[0]["ndc_11"] == "00093314905"

    def test_name_falls_back_to_ndc_when_all_none(self) -> None:
        records = [{"package_ndc": "00093314905", "brand_name": None, "generic_name": None}]
        result = parse_fda_ndc_json(records)
        assert result[0]["drug_name_display"] == "00093314905"


class TestNADACParserGaps:
    def test_uses_price_per_unit_column_fallback(self) -> None:
        # Some NADAC files use "price_per_unit" instead of "nadac_per_unit"
        csv_content = "ndc,price_per_unit,effective_date\n00093314905,0.045000,2026-01-01\n"
        result = parse_nadac_csv(csv_content)
        assert len(result) == 1
        assert result[0]["price_per_unit"] == Decimal("0.045000")


class TestMACListParserGaps:
    def test_negative_price_raises_error(self) -> None:
        tenant_id = uuid.uuid4()
        csv_content = "ndc,price_per_unit,effective_date\n00093314905,-0.030000,2026-01-01\n"
        with pytest.raises(Exception):
            parse_mac_list_csv(csv_content, tenant_id)

    def test_termination_date_included_when_present(self) -> None:
        tenant_id = uuid.uuid4()
        csv_content = "ndc,price_per_unit,effective_date,termination_date\n00093314905,0.030000,2026-01-01,2026-12-31\n"
        result = parse_mac_list_csv(csv_content, tenant_id)
        assert result[0]["termination_date"] == date(2026, 12, 31)

    def test_termination_date_none_when_absent(self) -> None:
        tenant_id = uuid.uuid4()
        csv_content = "ndc,price_per_unit,effective_date\n00093314905,0.030000,2026-01-01\n"
        result = parse_mac_list_csv(csv_content, tenant_id)
        assert result[0]["termination_date"] is None


class TestDrugLookupSerialize:
    def test_serialize_decimal(self) -> None:
        result = _serialize(Decimal("1.23"))
        assert result == "1.23"

    def test_serialize_date(self) -> None:
        result = _serialize(date(2026, 1, 1))
        assert result == "2026-01-01"

    def test_serialize_unknown_type_raises(self) -> None:
        with pytest.raises(TypeError):
            _serialize(object())

    def test_drug_to_dict_str_id(self) -> None:
        drug = MagicMock()
        drug.id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        drug.ndc_11 = "00093314905"
        drug.ndc_formatted = "00093-3149-05"
        drug.proprietary_name = None
        drug.nonproprietary_name = "metformin"
        drug.drug_name_display = "Metformin"
        drug.drug_type = "generic"
        drug.dea_schedule = None
        drug.otc_rx = "Rx"
        drug.dosage_form = "TABLET"
        drug.route_of_administration = "ORAL"
        drug.strength = "500mg"
        drug.labeler_name = "Teva"
        drug.marketing_status = "active"
        drug.is_specialty = False
        drug.is_biosimilar = False
        drug.is_glp1 = False
        drug.gpi_code = None
        drug.atc_code = None
        drug.therapeutic_class_1 = None
        drug.therapeutic_class_2 = None
        drug.is_active = True
        drug.data_source = "fda_ndc"

        result = DrugLookupService._drug_to_dict(drug)
        assert isinstance(result["id"], str)
        assert result["ndc_11"] == "00093314905"
