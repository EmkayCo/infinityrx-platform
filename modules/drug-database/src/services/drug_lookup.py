"""Drug lookup service — NDC-based drug detail retrieval with Redis caching.

Cache strategy: 24-hour TTL on full drug detail.
Redis key format: tenant:{tenant_id}:drug:ndc:{ndc_11}
"""
from __future__ import annotations

import json
import logging
from datetime import date
from decimal import Decimal
from typing import Any

from src.utils.ndc import normalize_ndc

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 86_400  # 24 hours


def _serialize(obj: Any) -> Any:
    """JSON serializer for Decimal and date types."""
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, date):
        return obj.isoformat()
    raise TypeError(f"Not serializable: {type(obj)}")


class DrugLookupService:
    """NDC lookup with Redis caching.

    Callers inject db (SQLAlchemy Session) and redis (Redis client).
    Keeps service testable without live infrastructure.
    """

    def __init__(self, db: Any, redis: Any, tenant_id: str) -> None:
        self._db = db
        self._redis = redis
        self._tenant_id = tenant_id

    def _cache_key(self, ndc_11: str) -> str:
        return f"tenant:{self._tenant_id}:drug:ndc:{ndc_11}"

    def get_drug(self, raw_ndc: str) -> dict[str, Any] | None:
        """Return full drug detail for NDC. Checks cache first.

        Returns None if drug not found.
        """
        ndc_11 = normalize_ndc(raw_ndc)
        cache_key = self._cache_key(ndc_11)

        cached = self._redis.get(cache_key)
        if cached is not None:
            logger.debug("cache hit", extra={"svc_name": "drug_lookup", "drug_ndc": ndc_11})
            return json.loads(cached)

        from src.models.tables import DrugProduct

        drug = self._db.query(DrugProduct).filter(DrugProduct.ndc_11 == ndc_11).first()
        if drug is None:
            return None

        result = self._drug_to_dict(drug)
        self._redis.setex(cache_key, _CACHE_TTL_SECONDS, json.dumps(result, default=_serialize))
        logger.debug("cache miss — loaded from db", extra={"svc_name": "drug_lookup", "drug_ndc": ndc_11})
        return result

    def invalidate_cache(self, ndc_11: str) -> None:
        """Invalidate cached entry for an NDC (call after data refresh)."""
        self._redis.delete(self._cache_key(ndc_11))

    @staticmethod
    def _drug_to_dict(drug: Any) -> dict[str, Any]:
        return {
            "id": str(drug.id),
            "ndc_11": drug.ndc_11,
            "ndc_formatted": drug.ndc_formatted,
            "proprietary_name": drug.proprietary_name,
            "nonproprietary_name": drug.nonproprietary_name,
            "drug_name_display": drug.drug_name_display,
            "drug_type": drug.drug_type,
            "dea_schedule": drug.dea_schedule,
            "otc_rx": drug.otc_rx,
            "dosage_form": drug.dosage_form,
            "route_of_administration": drug.route_of_administration,
            "strength": drug.strength,
            "labeler_name": drug.labeler_name,
            "marketing_status": drug.marketing_status,
            "is_specialty": drug.is_specialty,
            "is_biosimilar": drug.is_biosimilar,
            "is_glp1": drug.is_glp1,
            "gpi_code": drug.gpi_code,
            "atc_code": drug.atc_code,
            "therapeutic_class_1": drug.therapeutic_class_1,
            "therapeutic_class_2": drug.therapeutic_class_2,
            "is_active": drug.is_active,
            "data_source": drug.data_source,
        }


class MultiSourceIndicator:
    """Computes multi-source generic eligibility (3+ manufacturers = MAC eligible)."""

    MULTI_SOURCE_THRESHOLD = 3

    @staticmethod
    def compute(labeler_counts: dict[str, int]) -> dict[str, bool]:
        """Given {nonproprietary_name: distinct_labeler_count}, return multi-source flags."""
        return {
            name: count >= MultiSourceIndicator.MULTI_SOURCE_THRESHOLD
            for name, count in labeler_counts.items()
        }
