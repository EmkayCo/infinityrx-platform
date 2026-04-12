"""ExclusionScreeningService — orchestrates matcher + persistence + events."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .._shim import events as event_bus
from .._shim.notifications import NotificationService
from ..models import ExclusionListEntry, ExclusionMatch
from .matching import ExclusionMatcher, MatchCandidate

logger = logging.getLogger("core.exclusions.service")

EVENT_MATCH_FOUND = "exclusion.match_found"
EVENT_ENTITY_BLOCKED = "exclusion.entity_blocked"


@dataclass
class TenantScreeningConfig:
    screening_frequency: str = "monthly"
    entity_types: Sequence[str] = ("pharmacy", "prescriber", "member")
    auto_block_threshold: str = "exact"  # 'exact' | 'probable' | 'possible'


class ExclusionScreeningService:
    def __init__(self, session: Session, matcher: Optional[ExclusionMatcher] = None) -> None:
        self._session = session
        self._matcher = matcher or ExclusionMatcher()

    def screen_entity(
        self,
        *,
        tenant_id: str,
        entity: MatchCandidate,
        config: Optional[TenantScreeningConfig] = None,
    ) -> List[ExclusionMatch]:
        cfg = config or TenantScreeningConfig()
        if entity.entity_type not in cfg.entity_types:
            return []
        results = self._matcher.screen(self._session, entity)
        created: List[ExclusionMatch] = []
        for r in results:
            row = ExclusionMatch(
                tenant_id=tenant_id,
                exclusion_list_id=r.exclusion_list_id,
                matched_entity_type=entity.entity_type,
                matched_entity_id=entity.entity_id,
                match_confidence=r.confidence,
                status="pending",
                match_metadata={"score": r.score, "source": r.source},
            )
            self._session.add(row)
            self._session.flush()
            created.append(row)
            event_bus.publish(
                EVENT_MATCH_FOUND,
                {
                    "tenant_id": tenant_id,
                    "match_id": row.id,
                    "exclusion_list_id": r.exclusion_list_id,
                    "entity_type": entity.entity_type,
                    "entity_id": entity.entity_id,
                    "confidence": r.confidence,
                    "source": r.source,
                },
            )
            NotificationService.create(
                tenant_id=tenant_id,  # type: ignore[arg-type]
                notification_type="exclusion.match_found",
                title=f"Potential exclusion match ({r.confidence})",
                message=(
                    f"{entity.entity_type} {entity.entity_id} matched "
                    f"{r.source} exclusion list entry {r.exclusion_list_id}"
                ),
                severity="warning" if r.confidence != "exact" else "critical",
                link=f"/exclusions/matches/{row.id}",
            )
            if self._confidence_rank(r.confidence) >= self._confidence_rank(cfg.auto_block_threshold):
                event_bus.publish(
                    EVENT_ENTITY_BLOCKED,
                    {
                        "tenant_id": tenant_id,
                        "entity_type": entity.entity_type,
                        "entity_id": entity.entity_id,
                        "match_id": row.id,
                        "confidence": r.confidence,
                    },
                )
        self._session.commit()
        return created

    @staticmethod
    def _confidence_rank(c: str) -> int:
        return {"possible": 1, "probable": 2, "exact": 3}.get(c, 0)

    def confirm(self, *, match_id: str, user_id: str) -> ExclusionMatch:
        row = self._load(match_id)
        row.status = "confirmed"
        row.reviewed_by = user_id
        row.reviewed_at = datetime.now(timezone.utc)
        self._session.commit()
        event_bus.publish(
            EVENT_ENTITY_BLOCKED,
            {
                "tenant_id": row.tenant_id,
                "entity_type": row.matched_entity_type,
                "entity_id": row.matched_entity_id,
                "match_id": row.id,
                "confidence": row.match_confidence,
                "reason": "confirmed_by_reviewer",
            },
        )
        return row

    def dismiss(self, *, match_id: str, user_id: str, reason: str) -> ExclusionMatch:
        if not reason or not reason.strip():
            raise ValueError("dismiss reason required")
        row = self._load(match_id)
        row.status = "dismissed"
        row.reviewed_by = user_id
        row.reviewed_at = datetime.now(timezone.utc)
        row.review_reason = reason
        self._session.commit()
        return row

    def _load(self, match_id: str) -> ExclusionMatch:
        row = self._session.get(ExclusionMatch, match_id)
        if row is None:
            raise LookupError(f"exclusion_match {match_id} not found")
        return row

    def status(self, *, tenant_id: str) -> dict:
        last_oig = self._session.execute(
            select(func.max(ExclusionListEntry.last_updated)).where(ExclusionListEntry.source == "OIG")
        ).scalar()
        last_sam = self._session.execute(
            select(func.max(ExclusionListEntry.last_updated)).where(ExclusionListEntry.source == "SAM")
        ).scalar()
        counts_rows = self._session.execute(
            select(ExclusionMatch.status, func.count(ExclusionMatch.id))
            .where(ExclusionMatch.tenant_id == tenant_id)
            .group_by(ExclusionMatch.status)
        ).all()
        counts = {s: c for s, c in counts_rows}
        return {
            "last_oig_refresh": last_oig,
            "last_sam_refresh": last_sam,
            "match_counts": {
                "pending": counts.get("pending", 0),
                "confirmed": counts.get("confirmed", 0),
                "dismissed": counts.get("dismissed", 0),
            },
        }
