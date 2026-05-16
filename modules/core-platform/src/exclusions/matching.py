"""Exclusion matching engine: exact NPI + fuzzy name/state."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ExclusionListEntry


@dataclass(frozen=True)
class MatchCandidate:
    entity_type: str  # 'pharmacy' | 'prescriber' | 'member'
    entity_id: str
    npi: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    state: Optional[str] = None
    organization_name: Optional[str] = None


@dataclass
class MatchResult:
    exclusion_list_id: int
    confidence: str  # 'exact' | 'probable' | 'possible'
    score: float
    source: str


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


class ExactMatcher:
    """Matches by NPI only.

    BLOCK-3 fix (P0a v2): filter WHERE reinstate_date IS NULL so reinstated
    entities no longer produce false-positive blocks on legitimate prescribers
    and pharmacies.
    """

    def match(self, session: Session, entity: MatchCandidate) -> List[MatchResult]:
        if not entity.npi:
            return []
        rows = (
            session.execute(
                select(ExclusionListEntry)
                .where(ExclusionListEntry.npi == entity.npi)
                .where(ExclusionListEntry.reinstate_date.is_(None))
            )
            .scalars()
            .all()
        )
        return [
            MatchResult(exclusion_list_id=r.id, confidence="exact", score=100.0, source=r.source)
            for r in rows
        ]


class FuzzyMatcher:
    """Fuzzy last+first+state matcher with configurable thresholds.

    - name + state fuzzy above `probable_threshold` → 'probable'
    - last-name-only above `possible_threshold` → 'possible'
    """

    def __init__(self, *, probable_threshold: int = 90, possible_threshold: int = 85) -> None:
        self.probable_threshold = probable_threshold
        self.possible_threshold = possible_threshold

    def match(self, session: Session, entity: MatchCandidate) -> List[MatchResult]:
        if not entity.last_name and not entity.organization_name:
            return []
        # BLOCK-3 fix (P0a v2): exclude reinstated rows so reinstated
        # entities no longer produce false-positive matches.
        rows = (
            session.execute(
                select(ExclusionListEntry).where(ExclusionListEntry.reinstate_date.is_(None))
            )
            .scalars()
            .all()
        )
        out: List[MatchResult] = []
        e_last = _norm(entity.last_name)
        e_first = _norm(entity.first_name)
        e_state = _norm(entity.state)
        e_org = _norm(entity.organization_name)
        for r in rows:
            r_last = _norm(r.last_name)
            r_first = _norm(r.first_name)
            r_state = _norm(r.state)
            r_org = _norm(r.organization_name)

            if e_org and r_org:
                score = fuzz.token_sort_ratio(e_org, r_org)
                if score >= self.probable_threshold:
                    out.append(MatchResult(r.id, "probable", float(score), r.source))
                    continue
                if score >= self.possible_threshold:
                    out.append(MatchResult(r.id, "possible", float(score), r.source))
                    continue

            if e_last and r_last:
                full_e = f"{e_last} {e_first}".strip()
                full_r = f"{r_last} {r_first}".strip()
                score = fuzz.token_sort_ratio(full_e, full_r)
                state_ok = (not e_state) or (not r_state) or (e_state == r_state)
                if score >= self.probable_threshold and state_ok:
                    out.append(MatchResult(r.id, "probable", float(score), r.source))
                    continue
                last_score = fuzz.ratio(e_last, r_last)
                if last_score >= self.possible_threshold:
                    out.append(MatchResult(r.id, "possible", float(last_score), r.source))
        return out


class ExclusionMatcher:
    """Combines exact + fuzzy matchers. De-dupes by exclusion_list_id — the
    highest-confidence hit wins.
    """

    _RANK = {"exact": 3, "probable": 2, "possible": 1}

    def __init__(
        self,
        exact: ExactMatcher | None = None,
        fuzzy: FuzzyMatcher | None = None,
    ) -> None:
        self.exact = exact or ExactMatcher()
        self.fuzzy = fuzzy or FuzzyMatcher()

    def screen(
        self,
        session: Session,
        entity: MatchCandidate,
        *,
        sources: Sequence[str] = ("OIG", "SAM"),
    ) -> List[MatchResult]:
        results: List[MatchResult] = []
        results.extend(self.exact.match(session, entity))
        results.extend(self.fuzzy.match(session, entity))
        # filter by allowed sources
        allowed = set(sources)
        results = [r for r in results if r.source in allowed]
        # de-dupe — keep highest confidence per exclusion_list_id
        best: dict[int, MatchResult] = {}
        for r in results:
            cur = best.get(r.exclusion_list_id)
            if cur is None or self._RANK[r.confidence] > self._RANK[cur.confidence]:
                best[r.exclusion_list_id] = r
        return list(best.values())
