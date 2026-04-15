"""Government exclusion lookup service.

Determines whether a pharmacy claim's payer is a government program
for Anti-Kickback Statute (AKS) compliance. Copay assistance cards
MUST be blocked when the payer is Medicare, Medicaid, TRICARE, VA,
FEP, IHS, or CHAMPVA.

Lookup priority:
  1. BIN + PCN + Group exact match  → HIGH confidence result
  2. BIN + PCN match                → use row confidence
  3. BIN-only match                 → use row confidence (may be MEDIUM)
  4. OCC code fallback              → MEDIUM
  5. No match                       → ELIGIBLE (not a government plan)

LESSON-011: GovernmentProgramBin is global reference data — no tenant_id.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from shared.models.gov_exclusion_tables import GovernmentProgramBin

logger = logging.getLogger(__name__)

# OCC codes that universally indicate a government plan regardless of BIN
_GOVERNMENT_OCC_CODES = frozenset({
    "11",  # Medicare Part B
    "12",  # Medicare Part A
    "13",  # Medicare Part D
    "14",  # Medicaid
    "15",  # Medicaid managed care
    "16",  # VA
    "20",  # TRICARE
    "22",  # CHAMPVA
})


@dataclass
class GovernmentPlanInfo:
    """Details about a matched government plan entry."""

    id: str
    bin: str
    pcn: Optional[str]
    group_number: Optional[str]
    plan_type: str
    plan_subtype: Optional[str]
    pbm_name: Optional[str]
    plan_name: Optional[str]
    mco_name: Optional[str]
    state: Optional[str]
    confidence: str
    notes: Optional[str]


@dataclass
class GovernmentCheckResult:
    """Result of a government plan check."""

    is_government: bool
    confidence: str  # HIGH | MEDIUM | LOW
    match_type: Optional[str]  # bin_pcn_group | bin_pcn | bin_only | occ | none
    plans: list[GovernmentPlanInfo] = field(default_factory=list)


@dataclass
class CopayCardEligibility:
    """Copay card eligibility determination."""

    eligible: bool  # True = card can be applied; False = BLOCKED
    status: str  # ELIGIBLE | BLOCKED | REVIEW
    reason: str
    government_check: GovernmentCheckResult


class GovernmentExclusionService:
    """Lookup service for government program BIN/PCN identification.

    Takes a synchronous SQLAlchemy Session (shared reference database).
    All lookups are read-only; no writes occur during a check.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def is_government_plan(
        self,
        bin: str,
        pcn: Optional[str] = None,
        group: Optional[str] = None,
        occ: Optional[str] = None,
    ) -> GovernmentCheckResult:
        """Check whether a BIN/PCN/Group combination is a government plan.

        Parameters
        ----------
        bin:    6-digit BIN (left-padded with zeros if shorter).
        pcn:    Processor Control Number (optional).
        group:  Group number (optional).
        occ:    OCC (Other Coverage Code) from claim (optional fallback).
        """
        normalized_bin = bin.zfill(6) if bin else bin

        # Priority 1: BIN + PCN + Group exact match
        if pcn and group:
            rows = self._query_bin_pcn_group(normalized_bin, pcn, group)
            if rows:
                return self._result_from_rows(rows, "bin_pcn_group")

        # Priority 2: BIN + PCN match
        if pcn:
            rows = self._query_bin_pcn(normalized_bin, pcn)
            if rows:
                return self._result_from_rows(rows, "bin_pcn")

        # Priority 3: BIN-only
        rows = self._query_bin_only(normalized_bin)
        if rows:
            return self._result_from_rows(rows, "bin_only")

        # Priority 4: OCC code fallback
        if occ and occ.strip() in _GOVERNMENT_OCC_CODES:
            return GovernmentCheckResult(
                is_government=True,
                confidence="MEDIUM",
                match_type="occ",
                plans=[],
            )

        return GovernmentCheckResult(
            is_government=False,
            confidence="HIGH",
            match_type="none",
            plans=[],
        )

    def check_copay_card_eligibility(
        self,
        bin: str,
        pcn: Optional[str] = None,
        group: Optional[str] = None,
        occ: Optional[str] = None,
    ) -> CopayCardEligibility:
        """Determine whether a copay assistance card may be applied.

        Returns BLOCKED if a government plan is detected at HIGH confidence,
        REVIEW if MEDIUM confidence (manual review required), ELIGIBLE otherwise.
        """
        check = self.is_government_plan(bin=bin, pcn=pcn, group=group, occ=occ)

        if not check.is_government:
            return CopayCardEligibility(
                eligible=True,
                status="ELIGIBLE",
                reason="No government program match found.",
                government_check=check,
            )

        if check.confidence == "HIGH":
            plan_types = list({p.plan_type for p in check.plans})
            reason = (
                f"Government program detected ({', '.join(plan_types)}). "
                "Copay assistance cards are prohibited under the Anti-Kickback Statute."
            )
            return CopayCardEligibility(
                eligible=False,
                status="BLOCKED",
                reason=reason,
                government_check=check,
            )

        # MEDIUM or LOW — flag for review
        return CopayCardEligibility(
            eligible=False,
            status="REVIEW",
            reason=(
                "Potential government program match (confidence: "
                f"{check.confidence}). Manual review required before "
                "applying copay assistance."
            ),
            government_check=check,
        )

    def get_plan_details(
        self,
        bin: str,
        pcn: Optional[str] = None,
        group: Optional[str] = None,
    ) -> list[GovernmentPlanInfo]:
        """Return all matching plan details for a BIN/PCN/Group combination."""
        normalized_bin = bin.zfill(6) if bin else bin
        q = self._db.query(GovernmentProgramBin).filter(
            GovernmentProgramBin.bin == normalized_bin
        )
        if pcn is not None:
            q = q.filter(GovernmentProgramBin.pcn == pcn)
        if group is not None:
            q = q.filter(GovernmentProgramBin.group_number == group)
        rows: list[GovernmentProgramBin] = q.all()
        return [self._to_plan_info(r) for r in rows]

    def get_state_coverage(self, state: str) -> list[GovernmentPlanInfo]:
        """Return all government program entries for a given two-letter state code."""
        rows: list[GovernmentProgramBin] = (
            self._db.query(GovernmentProgramBin)
            .filter(GovernmentProgramBin.state == state.upper())
            .all()
        )
        return [self._to_plan_info(r) for r in rows]

    # ------------------------------------------------------------------
    # Private query helpers
    # ------------------------------------------------------------------

    def _query_bin_pcn_group(
        self, bin: str, pcn: str, group: str
    ) -> list[GovernmentProgramBin]:
        return (
            self._db.query(GovernmentProgramBin)
            .filter(
                GovernmentProgramBin.bin == bin,
                GovernmentProgramBin.pcn == pcn,
                GovernmentProgramBin.group_number == group,
                GovernmentProgramBin.government_flag.is_(True),
            )
            .all()
        )

    def _query_bin_pcn(self, bin: str, pcn: str) -> list[GovernmentProgramBin]:
        return (
            self._db.query(GovernmentProgramBin)
            .filter(
                GovernmentProgramBin.bin == bin,
                GovernmentProgramBin.pcn == pcn,
                GovernmentProgramBin.group_number.is_(None),
                GovernmentProgramBin.government_flag.is_(True),
            )
            .all()
        )

    def _query_bin_only(self, bin: str) -> list[GovernmentProgramBin]:
        return (
            self._db.query(GovernmentProgramBin)
            .filter(
                GovernmentProgramBin.bin == bin,
                GovernmentProgramBin.pcn.is_(None),
                GovernmentProgramBin.group_number.is_(None),
                GovernmentProgramBin.government_flag.is_(True),
            )
            .all()
        )

    @staticmethod
    def _result_from_rows(
        rows: list[GovernmentProgramBin], match_type: str
    ) -> GovernmentCheckResult:
        """Build a GovernmentCheckResult from a list of matching rows.

        Confidence is the LOWEST of all matched rows (most conservative).
        """
        confidence_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        worst_confidence = max(
            rows, key=lambda r: confidence_rank.get(r.confidence, 99)
        ).confidence
        plans = [GovernmentExclusionService._to_plan_info(r) for r in rows]
        return GovernmentCheckResult(
            is_government=True,
            confidence=worst_confidence,
            match_type=match_type,
            plans=plans,
        )

    @staticmethod
    def _to_plan_info(row: GovernmentProgramBin) -> GovernmentPlanInfo:
        return GovernmentPlanInfo(
            id=str(row.id),
            bin=row.bin,
            pcn=row.pcn,
            group_number=row.group_number,
            plan_type=row.plan_type,
            plan_subtype=row.plan_subtype,
            pbm_name=row.pbm_name,
            plan_name=row.plan_name,
            mco_name=row.mco_name,
            state=row.state,
            confidence=row.confidence,
            notes=row.notes,
        )


__all__ = [
    "GovernmentExclusionService",
    "GovernmentCheckResult",
    "CopayCardEligibility",
    "GovernmentPlanInfo",
]
