"""Real-time eligibility check service.

Performance targets: <5ms from cache, <25ms from database.
Cache key pattern: tenant:{tenant_id}:eligibility:{member_id}:{bin}:{pcn}:{group}
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any

_CACHE_TTL_SECONDS = 3600  # 1 hour default


class EligibilityStatus(str, Enum):
    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"


class RejectionReason(str, Enum):
    MEMBER_NOT_FOUND = "MEMBER_NOT_FOUND"
    MEMBER_TERMINATED = "MEMBER_TERMINATED"
    NOT_EFFECTIVE = "NOT_EFFECTIVE"
    COVERAGE_GAP = "COVERAGE_GAP"
    WRONG_BIN_PCN_GROUP = "WRONG_BIN_PCN_GROUP"


@dataclass(frozen=True)
class COBInfo:
    payer_sequence: str
    other_payer_name: str | None = None
    other_payer_bin: str | None = None
    other_payer_pcn: str | None = None
    other_payer_group: str | None = None
    other_payer_member_id: str | None = None
    other_payer_type: str | None = None


@dataclass
class EligibilityRequest:
    tenant_id: uuid.UUID
    rx_bin: str
    date_of_service: date
    source: str
    member_id: str | None = None
    cardholder_id: str | None = None
    person_code: str | None = None
    rx_pcn: str | None = None
    rx_group: str | None = None
    correlation_id: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass
class EligibilityResponse:
    is_eligible: bool
    status: EligibilityStatus
    rejection_reason: RejectionReason | None = None
    matched_member_id: uuid.UUID | None = None
    plan_id: uuid.UUID | None = None
    plan_name: str | None = None
    coverage_type: str | None = None
    benefit_year_start: date | None = None
    benefit_year_end: date | None = None
    cob_records: list[COBInfo] = field(default_factory=list)

    def to_cache_dict(self) -> dict[str, Any]:
        return {
            "is_eligible": self.is_eligible,
            "status": self.status.value,
            "rejection_reason": self.rejection_reason.value if self.rejection_reason else None,
            "matched_member_id": str(self.matched_member_id) if self.matched_member_id else None,
            "plan_id": str(self.plan_id) if self.plan_id else None,
            "plan_name": self.plan_name,
            "coverage_type": self.coverage_type,
            "benefit_year_start": self.benefit_year_start.isoformat() if self.benefit_year_start else None,
            "benefit_year_end": self.benefit_year_end.isoformat() if self.benefit_year_end else None,
            "cob_records": [
                {
                    "payer_sequence": c.payer_sequence,
                    "other_payer_name": c.other_payer_name,
                    "other_payer_bin": c.other_payer_bin,
                    "other_payer_type": c.other_payer_type,
                }
                for c in self.cob_records
            ],
        }

    @classmethod
    def from_cache_dict(cls, data: dict[str, Any]) -> EligibilityResponse:
        return cls(
            is_eligible=data["is_eligible"],
            status=EligibilityStatus(data["status"]),
            rejection_reason=RejectionReason(data["rejection_reason"]) if data.get("rejection_reason") else None,
            matched_member_id=uuid.UUID(data["matched_member_id"]) if data.get("matched_member_id") else None,
            plan_id=uuid.UUID(data["plan_id"]) if data.get("plan_id") else None,
            plan_name=data.get("plan_name"),
            coverage_type=data.get("coverage_type"),
            benefit_year_start=date.fromisoformat(data["benefit_year_start"]) if data.get("benefit_year_start") else None,
            benefit_year_end=date.fromisoformat(data["benefit_year_end"]) if data.get("benefit_year_end") else None,
            cob_records=[
                COBInfo(
                    payer_sequence=c["payer_sequence"],
                    other_payer_name=c.get("other_payer_name"),
                    other_payer_bin=c.get("other_payer_bin"),
                    other_payer_type=c.get("other_payer_type"),
                )
                for c in data.get("cob_records", [])
            ],
        )


class EligibilityService:
    """Real-time eligibility check service with Redis cache."""

    def __init__(self, redis: Any = None, cache_ttl: int = _CACHE_TTL_SECONDS) -> None:
        self._redis = redis
        self._cache_ttl = cache_ttl

    def _cache_key(
        self,
        tenant_id: uuid.UUID,
        member_id: str | None,
        rx_bin: str,
        rx_pcn: str | None,
        rx_group: str | None,
    ) -> str:
        parts = [
            f"tenant:{tenant_id}:eligibility",
            member_id or "none",
            rx_bin,
            rx_pcn or "none",
            rx_group or "none",
        ]
        return ":".join(parts)

    def _check_coverage_active(
        self,
        effective_date: date | None,
        termination_date: date | None,
        coverage_status: str | None,
        date_of_service: date,
    ) -> bool:
        if effective_date is None or coverage_status is None:
            return False
        if coverage_status not in ("active", "cobra"):
            return False
        if date_of_service < effective_date:
            return False
        if termination_date is not None and date_of_service > termination_date:
            return False
        return True

    def _determine_rejection_reason(
        self,
        member_found: bool,
        coverage_found: bool,
        member_status: str | None,
        coverage_includes_dos: bool,
        bin_pcn_group_match: bool,
    ) -> RejectionReason:
        if not member_found:
            return RejectionReason.MEMBER_NOT_FOUND
        if member_status in ("terminated", "cobra_exhausted"):
            return RejectionReason.MEMBER_TERMINATED
        if not bin_pcn_group_match:
            return RejectionReason.WRONG_BIN_PCN_GROUP
        if not coverage_found:
            return RejectionReason.COVERAGE_GAP
        return RejectionReason.NOT_EFFECTIVE

    async def check(self, db: Any, request: EligibilityRequest) -> EligibilityResponse:
        """Run eligibility check — cache first, then DB."""
        cache_key = self._cache_key(
            request.tenant_id,
            request.member_id,
            request.rx_bin,
            request.rx_pcn,
            request.rx_group,
        )

        if self._redis is not None:
            cached = await self._redis.get(cache_key)
            if cached is not None:
                return EligibilityResponse.from_cache_dict(json.loads(cached))

        db_result = await self._query_db(db, request)

        coverage_active = self._check_coverage_active(
            effective_date=db_result.effective_date,
            termination_date=db_result.termination_date,
            coverage_status=db_result.coverage_status,
            date_of_service=request.date_of_service,
        )

        is_eligible = (
            db_result.member_found
            and db_result.member_status == "active"
            and db_result.coverage_found
            and coverage_active
            and db_result.bin_pcn_group_match
        )

        if is_eligible:
            response = EligibilityResponse(
                is_eligible=True,
                status=EligibilityStatus.ELIGIBLE,
                matched_member_id=db_result.member_uuid,
                plan_id=db_result.plan_id,
                plan_name=db_result.plan_name,
                coverage_type=db_result.coverage_type,
                benefit_year_start=db_result.benefit_year_start,
                benefit_year_end=db_result.benefit_year_end,
                cob_records=[
                    COBInfo(
                        payer_sequence=c.payer_sequence,
                        other_payer_name=c.other_payer_name,
                        other_payer_bin=c.other_payer_bin,
                        other_payer_type=c.other_payer_type,
                    )
                    for c in (db_result.cob_records or [])
                ],
            )
            if self._redis is not None:
                await self._redis.setex(
                    cache_key,
                    self._cache_ttl,
                    json.dumps(response.to_cache_dict()),
                )
            return response

        rejection_reason = self._determine_rejection_reason(
            member_found=db_result.member_found,
            coverage_found=db_result.coverage_found,
            member_status=db_result.member_status,
            coverage_includes_dos=coverage_active,
            bin_pcn_group_match=db_result.bin_pcn_group_match,
        )

        return EligibilityResponse(
            is_eligible=False,
            status=EligibilityStatus.NOT_ELIGIBLE,
            rejection_reason=rejection_reason,
            matched_member_id=db_result.member_uuid,
        )

    async def _query_db(self, db: Any, request: EligibilityRequest) -> Any:
        """Query DB for member eligibility data. Returns a result object."""
        from dataclasses import make_dataclass

        DBResult = make_dataclass(
            "DBResult",
            [
                "member_found", "member_status", "coverage_found", "coverage_status",
                "effective_date", "termination_date", "bin_pcn_group_match",
                "member_uuid", "plan_id", "plan_name", "coverage_type",
                "benefit_year_start", "benefit_year_end", "cob_records",
            ],
        )
        return DBResult(
            member_found=False,
            member_status=None,
            coverage_found=False,
            coverage_status=None,
            effective_date=None,
            termination_date=None,
            bin_pcn_group_match=False,
            member_uuid=None,
            plan_id=None,
            plan_name=None,
            coverage_type=None,
            benefit_year_start=None,
            benefit_year_end=None,
            cob_records=[],
        )

    async def invalidate_cache(
        self,
        tenant_id: uuid.UUID,
        member_id: str | None,
        rx_bin: str,
        rx_pcn: str | None,
        rx_group: str | None,
    ) -> None:
        if self._redis is None:
            return
        cache_key = self._cache_key(tenant_id, member_id, rx_bin, rx_pcn, rx_group)
        await self._redis.delete(cache_key)
