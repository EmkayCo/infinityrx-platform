"""Unit tests for DrugLookupService and MultiSourceIndicator."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.services.drug_lookup import DrugLookupService, MultiSourceIndicator


class MockRedis:
    """Simple in-memory Redis mock."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


class MockDB:
    """Minimal DB mock that returns a pre-configured drug."""

    def __init__(self, drug=None) -> None:
        self._drug = drug

    def query(self, model):
        return self

    def filter(self, *args):
        return self

    def first(self):
        return self._drug


class TestDrugLookupServiceCacheHit:
    def test_returns_cached_value_without_db_call(self) -> None:
        redis = MockRedis()
        db = MockDB(drug=None)  # DB would return nothing
        tenant_id = "11111111-1111-1111-1111-111111111111"

        cached_drug = {"ndc_11": "00093314905", "drug_name_display": "Metformin"}
        redis.setex(
            f"tenant:{tenant_id}:drug:ndc:00093314905",
            86400,
            json.dumps(cached_drug),
        )

        svc = DrugLookupService(db=db, redis=redis, tenant_id=tenant_id)
        result = svc.get_drug("00093314905")

        assert result is not None
        assert result["ndc_11"] == "00093314905"
        assert result["drug_name_display"] == "Metformin"

    def test_cache_key_includes_tenant_id(self) -> None:
        redis = MockRedis()
        tenant_id = "11111111-1111-1111-1111-111111111111"

        drug_mock = MagicMock()
        drug_mock.id = "some-uuid"
        drug_mock.ndc_11 = "00093314905"
        drug_mock.ndc_formatted = "00093-3149-05"
        drug_mock.proprietary_name = None
        drug_mock.nonproprietary_name = "metformin"
        drug_mock.drug_name_display = "Metformin"
        drug_mock.drug_type = "generic"
        drug_mock.dea_schedule = None
        drug_mock.otc_rx = "Rx"
        drug_mock.dosage_form = "TABLET"
        drug_mock.route_of_administration = "ORAL"
        drug_mock.strength = "500mg"
        drug_mock.labeler_name = "Teva"
        drug_mock.marketing_status = "active"
        drug_mock.is_specialty = False
        drug_mock.is_biosimilar = False
        drug_mock.is_glp1 = False
        drug_mock.gpi_code = None
        drug_mock.atc_code = None
        drug_mock.therapeutic_class_1 = None
        drug_mock.therapeutic_class_2 = None
        drug_mock.is_active = True
        drug_mock.data_source = "fda_ndc"

        db = MockDB(drug=drug_mock)
        svc = DrugLookupService(db=db, redis=redis, tenant_id=tenant_id)
        svc.get_drug("00093314905")

        # Cache should be set with tenant-scoped key
        key = f"tenant:{tenant_id}:drug:ndc:00093314905"
        assert redis.get(key) is not None


class TestDrugLookupServiceCacheMiss:
    def test_queries_db_on_cache_miss(self) -> None:
        redis = MockRedis()
        tenant_id = "11111111-1111-1111-1111-111111111111"

        drug_mock = MagicMock()
        drug_mock.id = "test-id"
        drug_mock.ndc_11 = "00093314905"
        drug_mock.ndc_formatted = "00093-3149-05"
        drug_mock.proprietary_name = None
        drug_mock.nonproprietary_name = "metformin"
        drug_mock.drug_name_display = "Metformin"
        drug_mock.drug_type = "generic"
        drug_mock.dea_schedule = None
        drug_mock.otc_rx = "Rx"
        drug_mock.dosage_form = "TABLET"
        drug_mock.route_of_administration = "ORAL"
        drug_mock.strength = "500mg"
        drug_mock.labeler_name = "Teva"
        drug_mock.marketing_status = "active"
        drug_mock.is_specialty = False
        drug_mock.is_biosimilar = False
        drug_mock.is_glp1 = False
        drug_mock.gpi_code = None
        drug_mock.atc_code = None
        drug_mock.therapeutic_class_1 = None
        drug_mock.therapeutic_class_2 = None
        drug_mock.is_active = True
        drug_mock.data_source = "fda_ndc"

        db = MockDB(drug=drug_mock)
        svc = DrugLookupService(db=db, redis=redis, tenant_id=tenant_id)
        result = svc.get_drug("00093314905")

        assert result is not None
        assert result["ndc_11"] == "00093314905"

    def test_returns_none_for_unknown_ndc(self) -> None:
        redis = MockRedis()
        db = MockDB(drug=None)
        tenant_id = "11111111-1111-1111-1111-111111111111"
        svc = DrugLookupService(db=db, redis=redis, tenant_id=tenant_id)
        result = svc.get_drug("99999999999")
        assert result is None

    def test_normalizes_ndc_before_cache_lookup(self) -> None:
        redis = MockRedis()
        tenant_id = "11111111-1111-1111-1111-111111111111"
        cached = {"ndc_11": "00093314905", "drug_name_display": "Metformin"}
        # Store with NDC-11 key
        redis.setex(f"tenant:{tenant_id}:drug:ndc:00093314905", 86400, json.dumps(cached))

        db = MockDB(drug=None)
        svc = DrugLookupService(db=db, redis=redis, tenant_id=tenant_id)
        # Query with dashed format — should normalize and hit cache
        result = svc.get_drug("00093-3149-05")
        assert result is not None
        assert result["ndc_11"] == "00093314905"


class TestDrugLookupServiceInvalidateCache:
    def test_invalidate_removes_cached_entry(self) -> None:
        redis = MockRedis()
        tenant_id = "11111111-1111-1111-1111-111111111111"
        key = f"tenant:{tenant_id}:drug:ndc:00093314905"
        redis.setex(key, 86400, json.dumps({"ndc_11": "00093314905"}))

        db = MockDB(drug=None)
        svc = DrugLookupService(db=db, redis=redis, tenant_id=tenant_id)
        svc.invalidate_cache("00093314905")

        assert redis.get(key) is None


class TestMultiSourceIndicator:
    def test_three_or_more_labelers_is_multi_source(self) -> None:
        counts = {"metformin": 3}
        result = MultiSourceIndicator.compute(counts)
        assert result["metformin"] is True

    def test_two_labelers_is_not_multi_source(self) -> None:
        counts = {"insulin lispro": 2}
        result = MultiSourceIndicator.compute(counts)
        assert result["insulin lispro"] is False

    def test_one_labeler_is_single_source(self) -> None:
        counts = {"rare drug": 1}
        result = MultiSourceIndicator.compute(counts)
        assert result["rare drug"] is False

    def test_empty_input_returns_empty(self) -> None:
        result = MultiSourceIndicator.compute({})
        assert result == {}

    def test_threshold_is_exactly_three(self) -> None:
        assert MultiSourceIndicator.MULTI_SOURCE_THRESHOLD == 3
